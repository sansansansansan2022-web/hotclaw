import path from "path";
import { exec, execFile } from "child_process";
import { promisify } from "util";
import { readJsonFileSync } from "@/lib/json";
import { OPENCLAW_HOME } from "@/lib/openclaw-paths";

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

export const DEFAULT_MODEL_PROBE_TIMEOUT_MS = 15000;

type ProviderApiType = "anthropic-messages" | "openai-completions" | string;

interface ProviderConfig {
  baseUrl?: string;
  apiKey?: string;
  api?: ProviderApiType;
  authHeader?: boolean | string;
  headers?: Record<string, string>;
}

interface ProbeResult {
  provider?: string;
  model?: string;
  mode?: "api_key" | "oauth" | string;
  status?: "ok" | "error" | "unknown" | string;
  error?: string;
  latencyMs?: number;
}

interface DirectProbeResult {
  ok: boolean;
  elapsed: number;
  status: string;
  error?: string;
  mode: "api_key";
  source: "direct_model_probe";
  precision: "model";
  text?: string;
}

export interface ModelProbeOutcome {
  ok: boolean;
  elapsed: number;
  model: string;
  mode: "api_key" | "oauth" | "unknown" | string;
  status: string;
  error?: string;
  text?: string;
  source: "direct_model_probe" | "openclaw_provider_probe";
  precision: "model" | "provider";
}

interface ProbeModelParams {
  providerId: string;
  modelId: string;
  timeoutMs?: number;
}

const MODELS_PATH = path.join(OPENCLAW_HOME, "agents", "main", "agent", "models.json");

function quoteShellArg(arg: string): string {
  if (/^[A-Za-z0-9_./:=@-]+$/.test(arg)) return arg;
  return `"${arg.replace(/"/g, '""')}"`;
}

async function execOpenclaw(args: string[]): Promise<{ stdout: string; stderr: string }> {
  const env = { ...process.env, FORCE_COLOR: "0" };

  if (process.platform !== "win32") {
    return execFileAsync("openclaw", args, {
      maxBuffer: 10 * 1024 * 1024,
      env,
    });
  }

  const command = `openclaw ${args.map(quoteShellArg).join(" ")}`;
  return execAsync(command, {
    maxBuffer: 10 * 1024 * 1024,
    env,
    shell: "cmd.exe",
  });
}

function parseJsonFromMixedOutput(output: string): any {
  for (let i = 0; i < output.length; i++) {
    if (output[i] !== "{") continue;
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let j = i; j < output.length; j++) {
      const ch = output[j];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === "\"") inString = false;
        continue;
      }
      if (ch === "\"") {
        inString = true;
        continue;
      }
      if (ch === "{") depth++;
      else if (ch === "}") {
        depth--;
        if (depth === 0) {
          const candidate = output.slice(i, j + 1).trim();
          try {
            const parsed = JSON.parse(candidate);
            if (parsed && typeof parsed === "object") return parsed;
          } catch {}
          break;
        }
      }
    }
  }
  throw new Error("Failed to parse JSON output from openclaw models status --probe --json");
}

function loadProviderConfig(providerId: string): ProviderConfig | null {
  try {
    const parsed = readJsonFileSync<any>(MODELS_PATH);
    const providers = parsed?.providers;
    if (!providers || typeof providers !== "object") return null;
    const exact = providers[providerId];
    if (exact && typeof exact === "object") return exact as ProviderConfig;
    const normalizedTarget = providerId.toLowerCase();
    for (const [key, value] of Object.entries(providers)) {
      if (key.toLowerCase() === normalizedTarget && value && typeof value === "object") {
        return value as ProviderConfig;
      }
    }
    return null;
  } catch {
    return null;
  }
}

function pickAuthHeader(providerCfg: ProviderConfig, apiKey: string): Record<string, string> {
  const out: Record<string, string> = {};
  const authHeader = providerCfg.authHeader;
  const api = providerCfg.api;

  if (typeof authHeader === "string" && authHeader.trim()) {
    out[authHeader.trim()] = apiKey;
    return out;
  }

  if (authHeader === false) {
    out["x-api-key"] = apiKey;
    return out;
  }

  if (api === "anthropic-messages") {
    out["x-api-key"] = apiKey;
    out["Authorization"] = `Bearer ${apiKey}`;
    return out;
  }

  out["Authorization"] = `Bearer ${apiKey}`;
  return out;
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal, cache: "no-store" });
  } finally {
    clearTimeout(timer);
  }
}

function classifyErrorStatus(httpStatus: number, errorText: string): string {
  const normalized = errorText.toLowerCase();
  if (normalized.includes("timed out")) return "timeout";
  if (normalized.includes("model_not_supported")) return "model_not_supported";
  if (httpStatus === 401 || httpStatus === 403 || normalized.includes("unauthorized")) return "auth";
  if (httpStatus === 429 || normalized.includes("rate limit")) return "rate_limit";
  if (httpStatus === 402 || normalized.includes("billing")) return "billing";
  return "error";
}

function extractErrorMessage(payload: any, fallback: string): string {
  const direct = payload?.error?.message || payload?.message || payload?.error;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  return fallback;
}

async function probeModelDirect(params: ProbeModelParams): Promise<DirectProbeResult | null> {
  const providerCfg = loadProviderConfig(params.providerId);
  if (!providerCfg?.baseUrl || !providerCfg.api || !providerCfg.apiKey) return null;

  const timeoutMs = params.timeoutMs ?? DEFAULT_MODEL_PROBE_TIMEOUT_MS;
  // Kimi providers require temperature=1
  const isKimiProvider = params.providerId === "kimi-coding" || params.providerId === "moonshot";
  const temperature = isKimiProvider ? 1 : 0;

  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(providerCfg.headers || {}),
    ...pickAuthHeader(providerCfg, providerCfg.apiKey),
  };

  if (providerCfg.api === "anthropic-messages") {
    if (!headers["anthropic-version"]) headers["anthropic-version"] = "2023-06-01";
    const url = `${providerCfg.baseUrl.replace(/\/+$/, "")}/v1/messages`;
    const body = {
      model: params.modelId,
      max_tokens: 8,
      messages: [{ role: "user", content: "Reply with OK." }],
      temperature,
    };
    const start = Date.now();
    try {
      const resp = await fetchWithTimeout(url, { method: "POST", headers, body: JSON.stringify(body) }, timeoutMs);
      const elapsed = Date.now() - start;
      if (resp.ok) {
        return {
          ok: true,
          elapsed,
          status: "ok",
          mode: "api_key",
          source: "direct_model_probe",
          precision: "model",
          text: "OK (direct model probe)",
        };
      }
      let payload: any = null;
      try { payload = await resp.json(); } catch {}
      const error = extractErrorMessage(payload, `HTTP ${resp.status}`);
      return {
        ok: false,
        elapsed,
        status: classifyErrorStatus(resp.status, error),
        error,
        mode: "api_key",
        source: "direct_model_probe",
        precision: "model",
      };
    } catch (err: any) {
      const elapsed = Date.now() - start;
      const isTimeout = err?.name === "AbortError";
      return {
        ok: false,
        elapsed,
        status: isTimeout ? "timeout" : "network",
        error: isTimeout ? "LLM request timed out." : (err?.message || "Network error"),
        mode: "api_key",
        source: "direct_model_probe",
        precision: "model",
      };
    }
  }

  if (providerCfg.api === "openai-completions") {
    const url = `${providerCfg.baseUrl.replace(/\/+$/, "")}/chat/completions`;
    const body = {
      model: params.modelId,
      messages: [{ role: "user", content: "Reply with OK." }],
      max_tokens: 8,
      temperature,
    };
    const start = Date.now();
    try {
      const resp = await fetchWithTimeout(url, { method: "POST", headers, body: JSON.stringify(body) }, timeoutMs);
      const elapsed = Date.now() - start;
      if (resp.ok) {
        return {
          ok: true,
          elapsed,
          status: "ok",
          mode: "api_key",
          source: "direct_model_probe",
          precision: "model",
          text: "OK (direct model probe)",
        };
      }
      let payload: any = null;
      try { payload = await resp.json(); } catch {}
      const error = extractErrorMessage(payload, `HTTP ${resp.status}`);
      return {
        ok: false,
        elapsed,
        status: classifyErrorStatus(resp.status, error),
        error,
        mode: "api_key",
        source: "direct_model_probe",
        precision: "model",
      };
    } catch (err: any) {
      const elapsed = Date.now() - start;
      const isTimeout = err?.name === "AbortError";
      return {
        ok: false,
        elapsed,
        status: isTimeout ? "timeout" : "network",
        error: isTimeout ? "LLM request timed out." : (err?.message || "Network error"),
        mode: "api_key",
        source: "direct_model_probe",
        precision: "model",
      };
    }
  }

  return null;
}

async function probeProviderViaOpenclaw(params: ProbeModelParams): Promise<ModelProbeOutcome> {
  const timeoutMs = params.timeoutMs ?? DEFAULT_MODEL_PROBE_TIMEOUT_MS;
  const startedAt = Date.now();
  const { stdout, stderr } = await execOpenclaw([
      "models",
      "status",
      "--probe",
      "--json",
      "--probe-timeout",
      String(timeoutMs),
      "--probe-provider",
      String(params.providerId),
    ]);
  const parsed = parseJsonFromMixedOutput(`${stdout}\n${stderr || ""}`);
  const results: ProbeResult[] = parsed?.auth?.probes?.results || [];
  const fullModel = `${params.providerId}/${params.modelId}`;

  const exact =
    results.find((r) => r.provider === params.providerId && r.model === fullModel) ||
    results.find((r) => r.provider === params.providerId && typeof r.model === "string" && r.model.endsWith(`/${params.modelId}`));
  const matched = exact || results.find((r) => r.provider === params.providerId);

  if (!matched) {
    return {
      ok: false,
      elapsed: Date.now() - startedAt,
      model: fullModel,
      mode: "unknown",
      status: "unknown",
      error: `No probe result for provider ${params.providerId}`,
      precision: "provider",
      source: "openclaw_provider_probe",
    };
  }

  const ok = matched.status === "ok";
  return {
    ok,
    elapsed: matched.latencyMs ?? (Date.now() - startedAt),
    model: matched.model || fullModel,
    mode: matched.mode || "unknown",
    status: matched.status || "unknown",
    error: ok ? undefined : (matched.error || `Probe status: ${matched.status || "unknown"}`),
    precision: exact ? "model" : "provider",
    source: "openclaw_provider_probe",
    text: ok ? `OK (${exact ? "model-level" : "provider-level"} openclaw probe)` : undefined,
  };
}

export function parseModelRef(modelStr: string): { providerId: string; modelId: string } {
  const [providerId, ...rest] = modelStr.split("/");
  return { providerId: providerId || "", modelId: rest.join("/") || providerId || "" };
}

export async function probeModel(params: ProbeModelParams): Promise<ModelProbeOutcome> {
  const direct = await probeModelDirect(params);
  if (direct) {
    return {
      ...direct,
      model: `${params.providerId}/${params.modelId}`,
    };
  }
  return probeProviderViaOpenclaw(params);
}
