import { NextResponse } from "next/server";
import { DEFAULT_MODEL_PROBE_TIMEOUT_MS, probeModel } from "@/lib/model-probe";

const PROBE_TIMEOUT_MS = DEFAULT_MODEL_PROBE_TIMEOUT_MS;

export async function POST(req: Request) {
  try {
    const { provider: providerIdRaw, modelId: modelIdRaw } = await req.json();
    const providerId = String(providerIdRaw || "").trim();
    const modelId = String(modelIdRaw || "").trim();
    if (!providerId || !modelId) {
      return NextResponse.json({ error: "Missing provider or modelId" }, { status: 400 });
    }

    const result = await probeModel({ providerId, modelId, timeoutMs: PROBE_TIMEOUT_MS });
    return NextResponse.json({
      ok: result.ok,
      elapsed: result.elapsed,
      model: result.model,
      mode: result.mode,
      status: result.status,
      error: result.error,
      text: result.text,
      precision: result.precision,
      source: result.source,
    });
  } catch (err: any) {
    return NextResponse.json(
      { ok: false, error: err.message || "Probe failed", elapsed: 0 },
      { status: 500 }
    );
  }
}

