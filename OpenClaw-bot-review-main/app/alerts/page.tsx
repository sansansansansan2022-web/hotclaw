"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

interface AlertRule {
  id: string;
  name: string;
  enabled: boolean;
  threshold?: number;
  targetAgents?: string[];
}

interface AlertConfig {
  enabled: boolean;
  receiveAgent: string;
  rules: AlertRule[];
  checkInterval?: number;
}

interface Agent {
  id: string;
  name: string;
  emoji: string;
}

const RULE_DESCRIPTIONS: Record<string, Record<string, string>> = {
  "zh-TW": {
    model_unavailable: "模型不可用 - 當測試模型失敗時觸發",
    bot_no_response: "Bot 長時間無回應 - 當機器人超過設定時間未回應時觸發",
    message_failure_rate: "訊息失敗率升高 - 當訊息失敗率超過閾值時觸發",
    cron连续_failure: "Cron 連續失敗 - 當定時任務連續失敗超過設定次數時觸發",
  },
  zh: {
    model_unavailable: "模型不可用 - 当测试模型失败时触发",
    bot_no_response: "Bot 长时间无响应 - 当机器人超过设定时间未响应时触发",
    message_failure_rate: "消息失败率升高 - 当消息失败率超过阈值时触发",
    cron连续_failure: "Cron 连续失败 - 当定时任务连续失败超过设定次数时触发",
  },
  en: {
    model_unavailable: "Model Unavailable - Triggered when model test fails",
    bot_no_response: "Bot Long Time No Response - Triggered when bot is inactive for set period",
    message_failure_rate: "Message Failure Rate High - Triggered when failure rate exceeds threshold",
    cron连续_failure: "Cron Continuous Failure - Triggered when cron jobs fail multiple times in a row",
  },
};

export default function AlertsPage() {
  const { t, locale } = useI18n();
  const [config, setConfig] = useState<AlertConfig | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkResults, setCheckResults] = useState<string[]>([]);
  const [lastCheckTime, setLastCheckTime] = useState<string>("");
  const [checkInterval, setCheckInterval] = useState(10);

  // 从配置加载 checkInterval
  useEffect(() => {
    if (config?.checkInterval) {
      setCheckInterval(config.checkInterval);
    }
  }, [config?.checkInterval]);

  const ruleDescriptions = RULE_DESCRIPTIONS[locale as keyof typeof RULE_DESCRIPTIONS] || RULE_DESCRIPTIONS.zh;
  const isEnglish = locale === "en";
  const isTraditionalChinese = locale === "zh-TW";
  const timeLocale = isEnglish ? "en-US" : isTraditionalChinese ? "zh-TW" : "zh-CN";
  const ui = {
    minutes5: isEnglish ? "5 minutes" : isTraditionalChinese ? "5 分鐘" : "5 分钟",
    minutes10: isEnglish ? "10 minutes" : isTraditionalChinese ? "10 分鐘" : "10 分钟",
    minutes30: isEnglish ? "30 minutes" : isTraditionalChinese ? "30 分鐘" : "30 分钟",
    hour1: isEnglish ? "1 hour" : isTraditionalChinese ? "1 小時" : "1 小时",
    hours2: isEnglish ? "2 hours" : isTraditionalChinese ? "2 小時" : "2 小时",
    hours5: isEnglish ? "5 hours" : isTraditionalChinese ? "5 小時" : "5 小时",
    checking: isEnglish ? "⏳ Checking..." : isTraditionalChinese ? "⏳ 檢查中..." : "⏳ 检查中...",
    checkNow: isEnglish ? "🔄 Check Now" : isTraditionalChinese ? "🔄 立即檢查" : "🔄 立即检查",
    alertsTriggered: isEnglish ? "⚠️ Alerts Triggered" : isTraditionalChinese ? "⚠️ 警報觸發" : "⚠️ 告警触发",
    checkingAlerts: isEnglish ? "⏳ Checking alerts..." : isTraditionalChinese ? "⏳ 正在檢查警報..." : "⏳ 正在检查告警...",
    timeout: isEnglish ? "Timeout (s):" : isTraditionalChinese ? "超時 (秒):" : "超时 (秒):",
    failureRate: isEnglish ? "Failure rate (%):" : isTraditionalChinese ? "失敗率 (%):" : "失败率 (%):",
    maxFailures: isEnglish ? "Max failures:" : isTraditionalChinese ? "最大失敗數:" : "最大失败数:",
    threshold: isEnglish ? "Threshold:" : isTraditionalChinese ? "閾值:" : "阈值:",
    monitor: isEnglish ? "Monitor:" : isTraditionalChinese ? "檢測機器人:" : "检测机器人:",
    emptyMeansAll: isEnglish ? "(empty = all)" : isTraditionalChinese ? "(不選則檢測所有)" : "(不选则检测所有)",
    saved: isEnglish ? "Saved" : isTraditionalChinese ? "已保存" : "已保存",
  };

  // 加载配置
  useEffect(() => {
    Promise.all([
      fetch("/api/alerts").then((r) => r.json()),
      fetch("/api/config").then((r) => r.json()),
    ])
      .then(([alertData, configData]) => {
        setConfig(alertData);
        setAgents(configData.agents || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // 定时检查告警（不自动触发，由用户点击按钮触发）
  useEffect(() => {
    if (!config?.enabled) return;
    
    const checkAlerts = () => {
      setChecking(true);
      fetch("/api/alerts/check", { method: "POST" })
        .then((r) => r.json())
        .then((data) => {
          if (data.results && data.results.length > 0) {
            setCheckResults(data.results);
            setLastCheckTime(new Date().toLocaleTimeString(timeLocale));
          }
        })
        .catch(console.error)
        .finally(() => setChecking(false));
    };

    // 只设置定时器，不立即检查
    const timer = setInterval(checkAlerts, checkInterval * 60 * 1000);
    return () => clearInterval(timer);
  }, [config?.enabled, checkInterval, locale]);

  const handleManualCheck = () => {
    setChecking(true);
    fetch("/api/alerts/check", { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (data.results && data.results.length > 0) {
          setCheckResults(data.results);
          setLastCheckTime(new Date().toLocaleTimeString(timeLocale));
        }
      })
      .catch(console.error)
      .finally(() => setChecking(false));
  };

  const handleToggle = () => {
    if (!config) return;
    setSaving(true);
    fetch("/api/alerts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !config.enabled }),
    })
      .then((r) => r.json())
      .then((newConfig) => {
        setConfig(newConfig);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      })
      .finally(() => setSaving(false));
  };

  const handleAgentChange = (agentId: string) => {
    if (!config) return;
    setSaving(true);
    fetch("/api/alerts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ receiveAgent: agentId }),
    })
      .then((r) => r.json())
      .then((newConfig) => {
        setConfig(newConfig);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      })
      .finally(() => setSaving(false));
  };

  const handleIntervalChange = (value: number) => {
    if (!config) return;
    setCheckInterval(value);
    setSaving(true);
    fetch("/api/alerts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checkInterval: value }),
    })
      .then((r) => r.json())
      .then((newConfig) => {
        setConfig(newConfig);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      })
      .finally(() => setSaving(false));
  };

  const handleRuleToggle = (ruleId: string) => {
    if (!config) return;
    const rules = config.rules.map((r) =>
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    );
    setSaving(true);
    fetch("/api/alerts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules }),
    })
      .then((r) => r.json())
      .then((newConfig) => {
        setConfig(newConfig);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      })
      .finally(() => setSaving(false));
  };

  const handleThresholdChange = (ruleId: string, value: number) => {
    if (!config) return;
    const rules = config.rules.map((r) =>
      r.id === ruleId ? { ...r, threshold: value } : r
    );
    setSaving(true);
    fetch("/api/alerts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules }),
    })
      .then((r) => r.json())
      .then((newConfig) => {
        setConfig(newConfig);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      })
      .finally(() => setSaving(false));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--text-muted)]">{t("common.loading")}</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-400">{t("common.loadError")}</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen p-4 md:p-8 max-w-4xl mx-auto">
      <div className="flex flex-col gap-3 mb-6 md:mb-8 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            🔔 {t("alerts.title") || "Alert Center"}
          </h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">
            {t("alerts.subtitle") || "Configure system alerts and notifications"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* 检查间隔设置 */}
          {config.enabled && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-[var(--text-muted)]">{t("alerts.checkInterval") || "Check Interval"}:</span>
              <select
                value={checkInterval}
                onChange={(e) => handleIntervalChange(Number(e.target.value))}
                className="px-2 py-1 text-sm rounded border border-[var(--border)] bg-[var(--card)] text-[var(--text)]"
              >
                <option value={5}>{ui.minutes5}</option>
                <option value={10}>{ui.minutes10}</option>
                <option value={30}>{ui.minutes30}</option>
                <option value={60}>{ui.hour1}</option>
                <option value={120}>{ui.hours2}</option>
                <option value={300}>{ui.hours5}</option>
              </select>
            </div>
          )}
          {/* 手动检查按钮 */}
          {config.enabled && (
            <button
              onClick={handleManualCheck}
              disabled={checking}
              className="px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-sm hover:border-[var(--accent)] transition disabled:opacity-50"
            >
              {checking ? ui.checking : ui.checkNow}
            </button>
          )}
          <Link
            href="/"
            className="px-4 py-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-sm hover:border-[var(--accent)] transition"
          >
            {t("common.backHome") || "Back"}
          </Link>
        </div>
      </div>

      {/* 检查结果展示 */}
      {config.enabled && checkResults.length > 0 && (
        <div className="p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/10 mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-yellow-400">
              {ui.alertsTriggered} ({checkResults.length})
            </h3>
            {lastCheckTime && <span className="text-xs text-[var(--text-muted)]">{lastCheckTime}</span>}
          </div>
          <ul className="space-y-1">
            {checkResults.map((result, i) => (
              <li key={i} className="text-sm text-yellow-300">• {result}</li>
            ))}
          </ul>
        </div>
      )}

      {config.enabled && checking && (
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)] mb-6 text-center text-[var(--text-muted)]">
          {ui.checkingAlerts}
        </div>
      )}

      {/* 告警总开关 */}
      <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{t("alerts.enableAlerts") || "Enable Alerts"}</h2>
            <p className="text-[var(--text-muted)] text-sm mt-1">
              {t("alerts.enableDesc") || "Turn on/off all alert notifications"}
            </p>
          </div>
          <button
            onClick={handleToggle}
            disabled={saving}
            className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
              config.enabled ? "bg-green-500" : "bg-gray-600"
            }`}
          >
            <span
              className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                config.enabled ? "translate-x-7" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>

      {/* 接收告警的机器人 */}
      <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] mb-6">
        <h2 className="text-lg font-semibold mb-3">{t("alerts.receiveAgent") || "Receive Alert Agent"}</h2>
        <div className="flex flex-wrap gap-2">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => handleAgentChange(agent.id)}
              disabled={!config.enabled || saving}
              className={`px-4 py-2 rounded-lg border transition ${
                config.receiveAgent === agent.id
                  ? "bg-[var(--accent)] text-[var(--bg)] border-[var(--accent)]"
                  : "bg-[var(--bg)] border-[var(--border)] hover:border-[var(--accent)]"
              } ${!config.enabled ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {agent.emoji} {agent.name}
            </button>
          ))}
        </div>
      </div>

      {/* 告警规则列表 */}
      <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <h2 className="text-lg font-semibold mb-3">{t("alerts.rules") || "Alert Rules"}</h2>
        <p className="text-[var(--text-muted)] text-sm mb-4">
          {t("alerts.rulesDesc") || "Configure which conditions trigger alerts"}
        </p>
        <div className="space-y-4">
          {config.rules.map((rule) => (
            <div
              key={rule.id}
              className="p-4 rounded-lg border border-[var(--border)] bg-[var(--bg)]"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => handleRuleToggle(rule.id)}
                    disabled={!config.enabled || saving}
                    className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors ${
                      rule.enabled ? "bg-green-500" : "bg-gray-600"
                    } ${!config.enabled ? "opacity-50" : ""}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        rule.enabled ? "translate-x-5" : "translate-x-1"
                      }`}
                    />
                  </button>
                  <div>
                    <h3 className="font-medium">{rule.name}</h3>
                    <p className="text-[var(--text-muted)] text-xs">
                      {ruleDescriptions[rule.id] || rule.id}
                    </p>
                  </div>
                </div>
                {rule.threshold !== undefined && rule.id !== "bot_no_response" && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--text-muted)]">
                      {rule.id === "bot_no_response" ? ui.timeout :
                       rule.id === "message_failure_rate" ? ui.failureRate :
                       rule.id === "cron连续_failure" ? ui.maxFailures :
                       ui.threshold}
                    </span>
                    <input
                      type="number"
                      value={rule.threshold}
                      onChange={(e) => handleThresholdChange(rule.id, Number(e.target.value))}
                      disabled={!config.enabled || !rule.enabled || saving}
                      className="w-20 px-2 py-1 text-sm rounded border border-[var(--border)] bg-[var(--card)] text-[var(--text)] disabled:opacity-50"
                    />
                  </div>
                )}
                {rule.id === "bot_no_response" && rule.threshold !== undefined && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--text-muted)]">
                      {ui.timeout}
                    </span>
                    <input
                      type="number"
                      value={rule.threshold}
                      onChange={(e) => handleThresholdChange(rule.id, Number(e.target.value))}
                      disabled={!config.enabled || !rule.enabled || saving}
                      className="w-20 px-2 py-1 text-sm rounded border border-[var(--border)] bg-[var(--card)] text-[var(--text)] disabled:opacity-50"
                    />
                  </div>
                )}
              </div>
              {/* bot_no_response 规则：选择要检测的机器人 */}
              {rule.id === "bot_no_response" && rule.enabled && (
                <div className="mt-3 pt-3 border-t border-[var(--border)]">
                  <div className="flex flex-wrap gap-2 items-center">
                    <span className="text-xs text-[var(--text-muted)]">
                      {ui.monitor}
                    </span>
                    {agents.map((agent) => {
                      const selected = rule.targetAgents?.includes(agent.id) ?? true;
                      return (
                        <button
                          key={agent.id}
                          onClick={() => {
                            const currentAgents = rule.targetAgents || [];
                            const newAgents = selected
                              ? currentAgents.filter((id) => id !== agent.id)
                              : [...currentAgents, agent.id];
                            const finalAgents = newAgents.length === 0 && !rule.targetAgents 
                              ? agents.map(a => a.id)
                              : newAgents;
                            
                            const rules = config.rules.map((r) =>
                              r.id === rule.id ? { ...r, targetAgents: finalAgents } : r
                            );
                            setSaving(true);
                            fetch("/api/alerts", {
                              method: "PUT",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ rules }),
                            })
                              .then((r) => r.json())
                              .then((newConfig) => {
                                setConfig(newConfig);
                                setSaved(true);
                                setTimeout(() => setSaved(false), 2000);
                              })
                              .finally(() => setSaving(false));
                          }}
                          disabled={!config.enabled || saving}
                          className={`px-2 py-1 text-xs rounded border transition ${
                            selected
                              ? "bg-[var(--accent)] text-[var(--bg)] border-[var(--accent)]"
                              : "bg-[var(--bg)] border-[var(--border)] hover:border-[var(--accent)]"
                          } disabled:opacity-50`}
                        >
                          {agent.emoji} {agent.name}
                        </button>
                      );
                    })}
                    <span className="text-xs text-[var(--text-muted)] ml-2">
                      {ui.emptyMeansAll}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 保存提示 */}
      {saved && (
        <div className="fixed bottom-8 right-8 px-4 py-2 rounded-lg bg-green-500 text-white text-sm animate-fade-in">
          ✓ {ui.saved}
        </div>
      )}
    </main>
  );
}
