"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useI18n } from "@/lib/i18n";
import { GatewayStatus } from "./gateway-status";
import {
  AgentCard,
  ModelBadge,
  type AgentModelOptionGroup,
  type PlatformTestResult,
  type AgentModelTestResult,
  type AgentSessionTestResult,
} from "./components/agent-card";

interface Platform {
  name: string;
  accountId?: string;
  appId?: string;
  botOpenId?: string;
  botUserId?: string;
}

interface Agent {
  id: string;
  name: string;
  emoji: string;
  model: string;
  platforms: Platform[];
  session?: {
    lastActive: number | null;
    totalTokens: number;
    contextTokens: number;
    sessionCount: number;
    todayAvgResponseMs: number;
    messageCount: number;
    weeklyResponseMs: number[];
    weeklyTokens: number[];
  };
}

interface GroupChat {
  groupId: string;
  channel: string;
  agents: { id: string; emoji: string; name: string }[];
}

interface ConfigData {
  agents: Agent[];
  defaults: { model: string; fallbacks: string[] };
  providers?: Array<{
    id: string;
    accessMode?: "auth" | "api_key";
    models?: Array<{ id: string; name?: string }>;
  }>;
  gateway?: { port: number; token?: string; host?: string };
  groupChats?: GroupChat[];
}

interface DayStat {
  date: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  messageCount: number;
  avgResponseMs: number;
}

interface AllStats {
  daily: DayStat[];
  weekly: DayStat[];
  monthly: DayStat[];
}

type TimeRange = "daily" | "weekly" | "monthly";

interface SubagentActivityEvent {
  key: string;
  text: string;
  at: number;
}

interface SubagentInfo {
  toolId: string;
  label: string;
  activityEvents?: SubagentActivityEvent[];
}

interface AgentActivityData {
  agentId: string;
  name: string;
  emoji: string;
  state: "idle" | "working" | "waiting" | "offline";
  lastActive: number;
  subagents?: SubagentInfo[];
  cronJobs?: Array<{
    key: string;
    jobId: string;
    label: string;
    isRunning: boolean;
    lastRunAt: number;
    nextRunAt?: number;
    durationMs?: number;
    lastStatus: "success" | "running" | "failed";
    lastSummary?: string;
    consecutiveFailures: number;
  }>;
}

type TFunc = (key: string) => string;

let cachedHomeData: ConfigData | null = null;
let cachedHomeError: string | null = null;
let cachedHomeAllStats: AllStats | null = null;
let cachedHomeLastUpdated = "";
let cachedHomeRefreshInterval = 0;
let cachedHomeAgentStates: Record<string, string> = {};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

function formatMs(ms: number): string {
  if (!ms) return "-";
  if (ms < 1000) return ms + "ms";
  return (ms / 1000).toFixed(1) + "s";
}

// 趋势折线图
function TrendChart({ data, lines, height = 180, t }: { data: DayStat[]; lines: { key: keyof DayStat; color: string; label: string }[]; height?: number; t: TFunc }) {
  if (data.length === 0) return <div className="flex items-center justify-center h-32 text-[var(--text-muted)] text-sm">{t("common.noData")}</div>;

  const pad = { top: 16, right: 16, bottom: 50, left: 56 };
  const width = Math.max(500, data.length * 56 + pad.left + pad.right);
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;

  let maxVal = 0;
  for (const d of data) for (const l of lines) { const v = d[l.key] as number; if (v > maxVal) maxVal = v; }
  if (maxVal === 0) maxVal = 1;

  const ticks = Array.from({ length: 5 }, (_, i) => Math.round((maxVal / 4) * i));

  function toX(i: number) { return pad.left + (i / (data.length - 1 || 1)) * chartW; }
  function toY(v: number) { return pad.top + chartH - (v / maxVal) * chartH; }

  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} className="text-[var(--text-muted)]">
        {ticks.map((tick, i) => (
          <g key={i}>
            <line x1={pad.left} y1={toY(tick)} x2={width - pad.right} y2={toY(tick)} stroke="currentColor" opacity={0.12} />
            <text x={pad.left - 8} y={toY(tick) + 4} textAnchor="end" fontSize={10} fill="currentColor">{formatTokens(tick)}</text>
          </g>
        ))}
        {lines.map((l) => {
          const points = data.map((d, i) => `${toX(i)},${toY(d[l.key] as number)}`).join(" ");
          return <polyline key={l.key} points={points} fill="none" stroke={l.color} strokeWidth={2} opacity={0.85} />;
        })}
        {lines.map((l) => data.map((d, i) => (
          <circle key={`${l.key}-${i}`} cx={toX(i)} cy={toY(d[l.key] as number)} r={3} fill={l.color} opacity={0.9}>
            <title>{`${d.date} ${l.label}: ${formatTokens(d[l.key] as number)}`}</title>
          </circle>
        )))}
        {data.map((d, i) => (
          <text key={i} x={toX(i)} y={height - pad.bottom + 16} textAnchor="middle" fontSize={9} fill="currentColor"
            transform={`rotate(-30, ${toX(i)}, ${height - pad.bottom + 16})`}>{d.date.slice(5)}</text>
        ))}
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + chartH} stroke="currentColor" opacity={0.25} />
        <line x1={pad.left} y1={pad.top + chartH} x2={width - pad.right} y2={pad.top + chartH} stroke="currentColor" opacity={0.25} />
      </svg>
    </div>
  );
}

// 响应时间趋势图
function ResponseTrendChart({ data, height = 180, t }: { data: DayStat[]; height?: number; t: TFunc }) {
  const filtered = data.filter(d => d.avgResponseMs > 0);
  if (filtered.length === 0) return <div className="flex items-center justify-center h-32 text-[var(--text-muted)] text-sm">{t("home.noResponseData")}</div>;

  const pad = { top: 16, right: 16, bottom: 50, left: 56 };
  const width = Math.max(500, filtered.length * 56 + pad.left + pad.right);
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;
  const maxVal = Math.max(...filtered.map(d => d.avgResponseMs));

  const ticks = Array.from({ length: 5 }, (_, i) => Math.round((maxVal / 4) * i));
  function toX(i: number) { return pad.left + (i / (filtered.length - 1 || 1)) * chartW; }
  function toY(v: number) { return pad.top + chartH - (v / maxVal) * chartH; }

  const points = filtered.map((d, i) => `${toX(i)},${toY(d.avgResponseMs)}`).join(" ");

  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} className="text-[var(--text-muted)]">
        {ticks.map((tick, i) => (
          <g key={i}>
            <line x1={pad.left} y1={toY(tick)} x2={width - pad.right} y2={toY(tick)} stroke="currentColor" opacity={0.12} />
            <text x={pad.left - 8} y={toY(tick) + 4} textAnchor="end" fontSize={10} fill="currentColor">{formatMs(tick)}</text>
          </g>
        ))}
        <polyline points={points} fill="none" stroke="#f59e0b" strokeWidth={2} opacity={0.85} />
        {filtered.map((d, i) => (
          <circle key={i} cx={toX(i)} cy={toY(d.avgResponseMs)} r={3} fill="#f59e0b" opacity={0.9}>
            <title>{`${d.date}: ${formatMs(d.avgResponseMs)}`}</title>
          </circle>
        ))}
        {filtered.map((d, i) => (
          <text key={`l-${i}`} x={toX(i)} y={height - pad.bottom + 16} textAnchor="middle" fontSize={9} fill="currentColor"
            transform={`rotate(-30, ${toX(i)}, ${height - pad.bottom + 16})`}>{d.date.slice(5)}</text>
        ))}
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + chartH} stroke="currentColor" opacity={0.25} />
        <line x1={pad.left} y1={pad.top + chartH} x2={width - pad.right} y2={pad.top + chartH} stroke="currentColor" opacity={0.25} />
      </svg>
    </div>
  );
}

export default function Home() {
  const { t, locale } = useI18n();
  const [data, setData] = useState<ConfigData | null>(cachedHomeData);
  const [error, setError] = useState<string | null>(cachedHomeError);
  const [refreshInterval, setRefreshInterval] = useState(cachedHomeRefreshInterval);
  const [lastUpdated, setLastUpdated] = useState<string>(cachedHomeLastUpdated);
  const [loading, setLoading] = useState(false);
  const [allStats, setAllStats] = useState<AllStats | null>(cachedHomeAllStats);
  const [statsRange, setStatsRange] = useState<TimeRange>("daily");
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [testResults, setTestResults] = useState<Record<string, AgentModelTestResult | null> | null>(null);
  const [testing, setTesting] = useState(false);
  const [platformTestResults, setPlatformTestResults] = useState<Record<string, PlatformTestResult | null> | null>(null);
  const [testingPlatforms, setTestingPlatforms] = useState(false);
  const [sessionTestResults, setSessionTestResults] = useState<Record<string, AgentSessionTestResult | null> | null>(null);
  const [testingSessions, setTestingSessions] = useState(false);
  const [dmSessionResults, setDmSessionResults] = useState<Record<string, PlatformTestResult | null> | null>(null);
  const [testingDmSessions, setTestingDmSessions] = useState(false);
  const [agentStates, setAgentStates] = useState<Record<string, string>>(cachedHomeAgentStates);
  const [agentActivity, setAgentActivity] = useState<AgentActivityData[] | null>(null);

  const RANGE_LABELS: Record<TimeRange, string> = { daily: t("range.daily"), weekly: t("range.weekly"), monthly: t("range.monthly") };

  const REFRESH_OPTIONS = [
    { label: t("refresh.manual"), value: 0 },
    { label: t("refresh.10s"), value: 10 },
    { label: t("refresh.30s"), value: 30 },
    { label: t("refresh.1m"), value: 60 },
    { label: t("refresh.5m"), value: 300 },
    { label: t("refresh.10m"), value: 600 },
  ];

  const parseApiPayload = useCallback(async (resp: Response) => {
    const raw = await resp.text();
    let parsed: any = null;
    try {
      parsed = JSON.parse(raw);
    } catch {}
    const errorText = parsed?.error || raw || `HTTP ${resp.status}`;
    return { ok: resp.ok, status: resp.status, data: parsed, errorText };
  }, []);

  const callTestApi = useCallback(async (url: string) => {
    const requestWithMethod = async (method: "POST" | "GET") => {
      const resp = await fetch(url, { method, cache: "no-store" });
      return parseApiPayload(resp);
    };

    const first = await requestWithMethod("POST");
    if (first.ok) return first.data;

    const methodIssue = first.status === 405 || /method not allowed/i.test(first.errorText || "");
    if (!methodIssue) throw new Error(first.errorText);

    const fallback = await requestWithMethod("GET");
    if (fallback.ok) return fallback.data;
    throw new Error(fallback.errorText || first.errorText);
  }, [parseApiPayload]);

  const fetchData = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    Promise.all([
      fetch("/api/config").then((r) => r.json()),
      fetch("/api/stats-all").then((r) => r.json()),
    ])
      .then(([configData, statsData]) => {
        if (configData.error) {
          setError(configData.error);
          cachedHomeError = configData.error;
        } else {
          setData(configData);
          setError(null);
          cachedHomeData = configData;
          cachedHomeError = null;
        }
        if (!statsData.error) {
          setAllStats(statsData);
          cachedHomeAllStats = statsData;
        }
        const updated = new Date().toLocaleTimeString("zh-CN");
        setLastUpdated(updated);
        cachedHomeLastUpdated = updated;
      })
      .catch((e) => {
        setError(e.message);
        cachedHomeError = e.message;
      })
      .finally(() => {
        if (!silent) setLoading(false);
      });
  }, []);

  const changeAgentModel = useCallback(async (agentId: string, model: string) => {
    const resp = await fetch("/api/config/agent-model", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agentId, model }),
    });
    const payload = await parseApiPayload(resp);
    if (!payload.ok) {
      throw new Error(payload.errorText || t("agent.modelApplyFailed"));
    }
    fetchData(true);
  }, [fetchData, parseApiPayload, t]);

  // 首次加载 - 从 localStorage 恢复测试状态
  useEffect(() => {
    fetchData(!!cachedHomeData);
    const savedTestResults = localStorage.getItem('agentTestResults');
    if (savedTestResults) {
      try {
        setTestResults(JSON.parse(savedTestResults));
      } catch (e) {
        console.error('Failed to parse testResults from localStorage', e);
      }
    }
    const savedPlatformTestResults = localStorage.getItem('platformTestResults');
    if (savedPlatformTestResults) {
      try {
        setPlatformTestResults(JSON.parse(savedPlatformTestResults));
      } catch (e) {
        console.error('Failed to parse platformTestResults from localStorage', e);
      }
    }
    const savedSessionTestResults = localStorage.getItem('sessionTestResults');
    if (savedSessionTestResults) {
      try {
        setSessionTestResults(JSON.parse(savedSessionTestResults));
      } catch (e) {
        console.error('Failed to parse sessionTestResults from localStorage', e);
      }
    }
    const savedDmSessionResults = localStorage.getItem('dmSessionResults');
    if (savedDmSessionResults) {
      try {
        setDmSessionResults(JSON.parse(savedDmSessionResults));
      } catch (e) {
        console.error('Failed to parse dmSessionResults from localStorage', e);
      }
    }
  }, [fetchData]);

  useEffect(() => {
    cachedHomeRefreshInterval = refreshInterval;
  }, [refreshInterval]);

  // 保存测试结果到 localStorage
  useEffect(() => {
    if (testResults) {
      localStorage.setItem('agentTestResults', JSON.stringify(testResults));
    }
  }, [testResults]);

  useEffect(() => {
    if (platformTestResults) {
      localStorage.setItem('platformTestResults', JSON.stringify(platformTestResults));
    }
  }, [platformTestResults]);

  useEffect(() => {
    if (sessionTestResults) {
      localStorage.setItem('sessionTestResults', JSON.stringify(sessionTestResults));
    }
  }, [sessionTestResults]);

  useEffect(() => {
    if (dmSessionResults) {
      localStorage.setItem('dmSessionResults', JSON.stringify(dmSessionResults));
    }
  }, [dmSessionResults]);

  const testAllAgents = useCallback(() => {
    setTesting(true);
    // Set all agents to null (testing indicator) so UI shows ⏳
    const pending: Record<string, any> = {};
    if (data) for (const a of data.agents) pending[a.id] = null;
    setTestResults(pending);
    callTestApi("/api/test-bound-models")
      .then((resp) => {
        if (resp.results) {
          const map: Record<string, { ok: boolean; text?: string; error?: string; elapsed: number }> = {};
          for (const r of resp.results) map[r.agentId] = r;
          setTestResults(map);
        }
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Request failed";
        const failed: Record<string, { ok: boolean; error: string; elapsed: number }> = {};
        if (data) for (const a of data.agents) failed[a.id] = { ok: false, error: msg, elapsed: 0 };
        setTestResults(failed);
      })
      .finally(() => setTesting(false));
  }, [data, callTestApi]);

  const testAllPlatforms = useCallback(() => {
    setTestingPlatforms(true);
    // Set all agent:platform combos to null (⏳)
    const pending: Record<string, any> = {};
    if (data) {
      for (const a of data.agents) {
        for (const p of a.platforms) {
          pending[`${a.id}:${p.name}`] = null;
        }
      }
    }
    setPlatformTestResults(pending);
    callTestApi("/api/test-platforms")
      .then((resp) => {
        if (resp.results) {
          const map: Record<string, PlatformTestResult> = {};
          for (const r of resp.results) map[`${r.agentId}:${r.platform}`] = r;
          setPlatformTestResults(map);
        }
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Request failed";
        const failed: Record<string, PlatformTestResult> = {};
        if (data) {
          for (const a of data.agents) {
            for (const p of a.platforms) {
              failed[`${a.id}:${p.name}`] = {
                ok: false,
                error: msg,
                elapsed: 0,
              };
            }
          }
        }
        setPlatformTestResults(failed);
      })
      .finally(() => setTestingPlatforms(false));
  }, [data, callTestApi]);

  const testAllSessions = useCallback(() => {
    setTestingSessions(true);
    const pending: Record<string, any> = {};
    if (data) for (const a of data.agents) pending[a.id] = null;
    setSessionTestResults(pending);
    callTestApi("/api/test-sessions")
      .then((resp) => {
        if (resp.results) {
          const map: Record<string, { ok: boolean; reply?: string; error?: string; elapsed: number }> = {};
          for (const r of resp.results) map[r.agentId] = r;
          setSessionTestResults(map);
        }
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Request failed";
        const failed: Record<string, { ok: boolean; error: string; elapsed: number }> = {};
        if (data) for (const a of data.agents) failed[a.id] = { ok: false, error: msg, elapsed: 0 };
        setSessionTestResults(failed);
      })
      .finally(() => setTestingSessions(false));
  }, [data, callTestApi]);

  const testAllDmSessions = useCallback(() => {
    setTestingDmSessions(true);
    const pending: Record<string, any> = {};
    if (data) {
      for (const a of data.agents) {
        for (const p of a.platforms) {
          pending[`${a.id}:${p.name}`] = null;
        }
      }
    }
    setDmSessionResults(pending);
    callTestApi("/api/test-dm-sessions")
      .then((resp) => {
        if (resp.results) {
          const map: Record<string, PlatformTestResult> = {};
          for (const r of resp.results) map[`${r.agentId}:${r.platform}`] = r;
          setDmSessionResults(map);
        }
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Request failed";
        const failed: Record<string, PlatformTestResult> = {};
        if (data) {
          for (const a of data.agents) {
            for (const p of a.platforms) {
              failed[`${a.id}:${p.name}`] = {
                ok: false,
                error: msg,
                elapsed: 0,
              };
            }
          }
        }
        setDmSessionResults(failed);
      })
      .finally(() => setTestingDmSessions(false));
  }, [data, callTestApi]);

  // 定时刷新
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (refreshInterval > 0) {
      timerRef.current = setInterval(fetchData, refreshInterval * 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [refreshInterval, fetchData]);

  // Agent 状态轮询 (30秒)
  useEffect(() => {
    const fetchStatus = () => {
      fetch("/api/agent-status")
        .then(r => r.json())
        .then(d => {
          if (d.statuses) {
            const map: Record<string, string> = {};
            for (const s of d.statuses) map[s.agentId] = s.state;
            setAgentStates(map);
            cachedHomeAgentStates = map;
          }
        })
        .catch(() => {});
    };
    fetchStatus();
    const timer = setInterval(fetchStatus, 30000);
    return () => clearInterval(timer);
  }, []);

  // Agent 任務活動輪詢 (30秒)
  useEffect(() => {
    const fetchActivity = () => {
      fetch("/api/agent-activity", { cache: "no-store" })
        .then(r => r.json())
        .then(d => {
          if (d.agents) setAgentActivity(d.agents);
        })
        .catch(() => {});
    };
    fetchActivity();
    const timer = setInterval(fetchActivity, 30000);
    return () => clearInterval(timer);
  }, []);

  if (error && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-400">{t("common.loadError")}: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--text-muted)]">{t("common.loading")}</p>
      </div>
    );
  }

  const providerAccessModeMap: Record<string, "auth" | "api_key"> = {};
  for (const p of data.providers || []) {
    if (!p?.id || !p.accessMode) continue;
    providerAccessModeMap[p.id] = p.accessMode;
  }
  const modelOptions: AgentModelOptionGroup[] = (data.providers || [])
    .filter((provider) => provider?.id && Array.isArray(provider.models) && provider.models.length > 0)
    .map((provider) => ({
      providerId: provider.id,
      providerName: provider.id,
      accessMode: provider.accessMode,
      models: (provider.models || []).map((model) => ({
        id: model.id,
        name: model.name || model.id,
      })),
    }));
  return (
    <div className="p-3 md:p-4 max-w-6xl mx-auto">
      {/* 头部 */}
      <div className="flex flex-col gap-2 mb-3 md:flex-row md:items-center md:justify-between">
        <div className="hidden md:block">
          <h1 className="text-xl font-bold flex items-center gap-2">
            🤖 {t("home.pageTitle")}
          </h1>
          <p className="text-[var(--text-muted)] text-xs mt-0.5">
            {t("models.totalPrefix")} {data.agents.length} {t("home.agentCount")} · {t("home.defaultModel")}: {data.defaults.model}
          </p>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
          <button
            onClick={testAllAgents}
            disabled={testing}
            className="shrink-0 px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-[var(--text)] text-sm font-medium hover:border-[var(--accent)] transition disabled:opacity-50 cursor-pointer"
          >
            {testing ? t("home.testingAll") : t("home.testAll")}
          </button>
          <button
            onClick={testAllPlatforms}
            disabled={testingPlatforms}
            className="shrink-0 px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-[var(--text)] text-sm font-medium hover:border-[var(--accent)] transition disabled:opacity-50 cursor-pointer"
          >
            {testingPlatforms ? t("home.testingPlatforms") : t("home.testPlatforms")}
          </button>
          <button
            onClick={testAllSessions}
            disabled={testingSessions}
            className="shrink-0 px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-[var(--text)] text-sm font-medium hover:border-[var(--accent)] transition disabled:opacity-50 cursor-pointer"
          >
            {testingSessions ? t("home.testingSessions") : t("home.testSessions")}
          </button>
          <button
            onClick={testAllDmSessions}
            disabled={testingDmSessions}
            className="shrink-0 px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-[var(--text)] text-sm font-medium hover:border-[var(--accent)] transition disabled:opacity-50 cursor-pointer"
          >
            {testingDmSessions ? t("home.testingDmSessions") : t("home.testDmSessions")}
          </button>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="shrink-0">
          <GatewayStatus hideIconOnMobile />
        </div>
        <div className="flex items-center gap-2 min-w-0 max-w-full overflow-x-auto pb-1 md:overflow-visible md:pb-0">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="shrink-0 px-3 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-sm text-[var(--text)] cursor-pointer hover:border-[var(--accent)] transition"
          >
            {REFRESH_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.value === 0 ? `🔄 ${opt.label}` : `⏱️ ${opt.label}`}
              </option>
            ))}
          </select>
          {refreshInterval === 0 && (
            <button
              onClick={() => fetchData(false)}
              disabled={loading}
              className="shrink-0 px-3 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-sm hover:border-[var(--accent)] transition disabled:opacity-50"
            >
              {loading ? "⏳" : "🔄"}
            </button>
          )}
          {lastUpdated && (
            <span className="shrink-0 text-xs text-[var(--text-muted)] whitespace-nowrap">
              {t("home.updatedAt")} {lastUpdated}
            </span>
          )}
        </div>
      </div>

      {/* 卡片墙 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {data.agents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} gatewayPort={data.gateway?.port || 18789} gatewayToken={data.gateway?.token} gatewayHost={data.gateway?.host} t={t} testResult={testResults?.[agent.id]} platformTestResults={platformTestResults || undefined} sessionTestResult={sessionTestResults?.[agent.id]} agentState={agentStates[agent.id]} dmSessionResults={dmSessionResults || undefined} providerAccessModeMap={providerAccessModeMap} modelOptions={modelOptions} onModelChange={changeAgentModel} />
        ))}
      </div>

      {/* Agent 任務追蹤 */}
      {agentActivity && agentActivity.some(a => a.state !== "offline") && (
        <div className="mt-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <h2 className="text-sm font-semibold text-[var(--text-muted)] mb-3">📋 {t("home.agentTaskTracking")}</h2>
          <div className="space-y-2">
            {agentActivity
              .filter(a => a.state !== "offline")
              .map(agent => (
                <div key={agent.agentId} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                  <span className="text-lg leading-none mt-0.5">{agent.emoji || "🤖"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-[var(--text)]">{agent.name}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        agent.state === "working" ? "bg-emerald-500/20 text-emerald-400" :
                        agent.state === "waiting" ? "bg-amber-500/20 text-amber-400" :
                        "bg-[var(--border)] text-[var(--text-muted)]"
                      }`}>
                        {agent.state === "working"
                          ? t("home.agentTaskState.working")
                          : agent.state === "waiting"
                            ? t("home.agentTaskState.waiting")
                            : t("home.agentTaskState.idle")}
                      </span>
                    </div>
                    {agent.subagents && agent.subagents.length > 0 ? (
                      <div className="space-y-1">
                        <div className="text-[10px] uppercase tracking-wide opacity-60">{t("home.agentTaskSubtasks")}</div>
                        {agent.subagents.map((sub, i) => (
                          <div key={i} className="text-xs text-[var(--text-muted)]">
                            <span className="text-[var(--accent)] mr-1">↳</span>
                            <span className="font-medium text-[var(--text)]">{sub.label}</span>
                            {sub.activityEvents && sub.activityEvents.length > 0 && (
                              <span className="ml-2 opacity-70">— {sub.activityEvents[sub.activityEvents.length - 1].text}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-[var(--text-muted)] opacity-60">{t("home.agentTaskNoSubtasks")}</div>
                    )}
                    {agent.cronJobs && agent.cronJobs.length > 0 ? (
                      <div className="space-y-1 mt-2 pt-2 border-t border-[var(--border)]">
                        <div className="text-[10px] uppercase tracking-wide opacity-60">{t("home.agentTaskCron")}</div>
                        {agent.cronJobs.map((cron) => (
                          <div key={cron.key} className="text-xs text-[var(--text-muted)]">
                            <div className="flex items-center gap-2">
                              <span className="text-yellow-400">⏰</span>
                              <span className="font-medium text-[var(--text)]">{cron.label}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                cron.lastStatus === "running"
                                  ? "bg-sky-500/20 text-sky-400"
                                  : cron.lastStatus === "failed"
                                    ? "bg-red-500/20 text-red-400"
                                    : "bg-emerald-500/20 text-emerald-400"
                              }`}>
                                {cron.lastStatus === "running"
                                  ? t("home.agentTaskCronState.running")
                                  : cron.lastStatus === "failed"
                                    ? t("home.agentTaskCronState.failed")
                                    : t("home.agentTaskCronState.success")}
                              </span>
                              {cron.consecutiveFailures > 0 && (
                                <span className="text-[10px] text-red-400">
                                  {t("home.agentTaskCronFailures")} {cron.consecutiveFailures}
                                </span>
                              )}
                            </div>
                            <div className="ml-5 opacity-70">
                              {cron.lastSummary || t("home.agentTaskCronNoSummary")}
                            </div>
                            <div className="ml-5 mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-[10px] opacity-60">
                              {cron.durationMs !== undefined && (
                                <span>{t("home.agentTaskCronDuration")} {Math.max(1, Math.round(cron.durationMs / 1000))}s</span>
                              )}
                              {cron.nextRunAt ? (
                                <span>
                                  {t("home.agentTaskCronNextRun")} {new Date(cron.nextRunAt).toLocaleTimeString(locale === "zh" ? "zh-CN" : locale, { hour: "2-digit", minute: "2-digit" })}
                                </span>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-[var(--text-muted)] opacity-60 mt-2">{t("home.agentTaskNoCron")}</div>
                    )}
                  </div>
                  <div className="text-[10px] text-[var(--text-muted)] whitespace-nowrap">
                    {agent.lastActive ? new Date(agent.lastActive).toLocaleTimeString(locale === "zh" ? "zh-CN" : locale, { hour: "2-digit", minute: "2-digit" }) : ""}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* 汇总统计趋势 */}
      {allStats && (
        <div className="mt-8 p-5 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <div className="flex flex-col gap-2 mb-4 md:flex-row md:items-center md:justify-between">
            <h2 className="text-sm font-semibold text-[var(--text)]">{t("home.globalTrend")}</h2>
            <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
              {(Object.keys(RANGE_LABELS) as TimeRange[]).map((r) => (
                <button key={r} onClick={() => setStatsRange(r)}
                  className={`px-3 py-1 text-xs transition ${statsRange === r ? "bg-[var(--accent)] text-[var(--bg)] font-medium" : "bg-[var(--bg)] text-[var(--text-muted)] hover:text-[var(--text)]"}`}
                >{RANGE_LABELS[r]}</button>
              ))}
            </div>
          </div>
          {(() => {
            const currentData = allStats[statsRange];
            const totalInput = currentData.reduce((s, d) => s + d.inputTokens, 0);
            const totalOutput = currentData.reduce((s, d) => s + d.outputTokens, 0);
            const totalMsgs = currentData.reduce((s, d) => s + d.messageCount, 0);
            return (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                  <div className="p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                    <div className="text-[10px] text-[var(--text-muted)]">{t("home.totalInputToken")}</div>
                    <div className="text-lg font-bold text-blue-400">{formatTokens(totalInput)}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                    <div className="text-[10px] text-[var(--text-muted)]">{t("home.totalOutputToken")}</div>
                    <div className="text-lg font-bold text-emerald-400">{formatTokens(totalOutput)}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                    <div className="text-[10px] text-[var(--text-muted)]">{t("home.totalMessages")}</div>
                    <div className="text-lg font-bold text-purple-400">{totalMsgs}</div>
                  </div>
                </div>
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-[var(--text-muted)]">{t("home.tokenTrend")}</span>
                    <div className="flex items-center gap-3 text-[10px]">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Input</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Output</span>
                    </div>
                  </div>
                  <TrendChart data={currentData} lines={[
                    { key: "inputTokens", color: "#3b82f6", label: "Input" },
                    { key: "outputTokens", color: "#10b981", label: "Output" },
                  ]} t={t} />
                </div>
                {statsRange === "daily" && (
                  <div>
                    <span className="text-xs text-[var(--text-muted)]">{t("home.avgResponseTrend")}</span>
                    <ResponseTrendChart data={currentData} t={t} />
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* 群聊管理 */}
      {data.groupChats && data.groupChats.length > 0 && (
        <div className="mt-8 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <h2 className="text-sm font-semibold text-[var(--text-muted)] mb-3">
            {t("home.groupTopology")}
          </h2>
          <div className="space-y-3">
            {data.groupChats.map((group, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                <span className="text-lg">{group.channel === "feishu" ? "📱" : "🎮"}</span>
                <div className="flex-1">
                  <div className="text-xs text-[var(--text-muted)] mb-1">
                    {group.channel === "feishu" ? t("home.feishuGroup") : t("home.discordChannel")} · {group.groupId.split(":")[1]}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {group.agents.map((a) => (
                      <span key={a.id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-[var(--card)] border border-[var(--border)]">
                        {a.emoji} {a.name}
                      </span>
                    ))}
                  </div>
                </div>
                <span className="text-xs text-[var(--text-muted)]">{group.agents.length} {t("home.bots")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fallback 信息 */}
      {data.defaults.fallbacks.length > 0 && (
        <div className="mt-8 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <h2 className="text-sm font-semibold text-[var(--text-muted)] mb-2">
            {t("home.fallbackModels")}
          </h2>
          <div className="flex flex-wrap gap-2">
            {data.defaults.fallbacks.map((f, i) => (
              <ModelBadge key={i} model={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
