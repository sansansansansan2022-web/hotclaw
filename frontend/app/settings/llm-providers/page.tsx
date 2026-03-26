"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  listLLMProviders,
  createLLMProvider,
  updateLLMProvider,
  deleteLLMProvider,
  testLLMProvider,
  setDefaultLLMProvider,
  LLMProviderInfo,
  LLM_PROVIDER_TEMPLATES,
} from "@/lib/api";

export default function LLMProvidersPage() {
  const [providers, setProviders] = useState<LLMProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [selected, setSelected] = useState<LLMProviderInfo | null>(null);
  const [editing, setEditing] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    provider_id: "",
    name: "",
    description: "",
    api_key: "",
    base_url: "",
    default_model: "",
    supported_models: [] as string[],
    is_enabled: false,
    is_default: false,
    timeout: 60,
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    latency?: number;
  } | null>(null);

  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadProviders();
  }, []);

  async function loadProviders() {
    setLoading(true);
    try {
      const data = await listLLMProviders();
      setProviders(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData({
      provider_id: "",
      name: "",
      description: "",
      api_key: "",
      base_url: "",
      default_model: "",
      supported_models: [],
      is_enabled: false,
      is_default: false,
      timeout: 60,
    });
    setTestResult(null);
  }

  function handleAdd() {
    resetForm();
    setSelected(null);
    setEditing(true);
    setShowAdd(true);
  }

  function handleSelect(provider: LLMProviderInfo) {
    setSelected(provider);
    setFormData({
      provider_id: provider.provider_id,
      name: provider.name,
      description: provider.description || "",
      api_key: provider.api_key || "",
      base_url: provider.base_url || "",
      default_model: provider.default_model || "",
      supported_models: provider.supported_models || [],
      is_enabled: provider.is_enabled,
      is_default: provider.is_default,
      timeout: provider.timeout,
    });
    setEditing(false);
    setShowAdd(false);
    setTestResult(null);
    setMessage("");
  }

  function handleTemplateSelect(providerId: string) {
    const template = LLM_PROVIDER_TEMPLATES.find((t) => t.provider_id === providerId);
    if (template) {
      setFormData((prev) => ({
        ...prev,
        provider_id: template.provider_id,
        name: template.name,
        description: template.description,
        base_url: template.base_url,
        default_model: template.default_model,
        supported_models: [...template.supported_models],
      }));
    }
  }

  async function handleTest() {
    if (!formData.api_key) {
      setTestResult({ success: false, message: "请先输入 API Key" });
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      const result = await testLLMProvider({
        provider_id: formData.provider_id,
        api_key: formData.api_key,
        base_url: formData.base_url,
        model: formData.default_model,
      });

      if (result.success) {
        setTestResult({
          success: true,
          message: result.response_preview || "测试成功",
          latency: result.latency_ms,
        });
      } else {
        setTestResult({
          success: false,
          message: result.error_message || "测试失败",
        });
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "测试请求失败",
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setMessage("");

    try {
      if (showAdd) {
        await createLLMProvider({
          provider_id: formData.provider_id,
          name: formData.name,
          description: formData.description || undefined,
          api_key: formData.api_key || undefined,
          base_url: formData.base_url || undefined,
          default_model: formData.default_model || undefined,
          supported_models: formData.supported_models.length > 0 ? formData.supported_models : undefined,
          is_enabled: formData.is_enabled,
          is_default: formData.is_default,
          timeout: formData.timeout,
        });
        setMessage("创建成功");
      } else if (selected) {
        await updateLLMProvider(selected.provider_id, {
          name: formData.name,
          description: formData.description || undefined,
          api_key: formData.api_key || undefined,
          base_url: formData.base_url || undefined,
          default_model: formData.default_model || undefined,
          supported_models: formData.supported_models.length > 0 ? formData.supported_models : undefined,
          is_enabled: formData.is_enabled,
          is_default: formData.is_default,
          timeout: formData.timeout,
        });
        setMessage("保存成功");
      }

      setEditing(false);
      await loadProviders();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    if (!confirm(`确定删除 ${selected.name}?`)) return;

    try {
      await deleteLLMProvider(selected.provider_id);
      setSelected(null);
      resetForm();
      await loadProviders();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function handleSetDefault(providerId: string) {
    try {
      await setDefaultLLMProvider(providerId);
      await loadProviders();
      setMessage("已设为默认 Provider");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "设置失败");
    }
  }

  return (
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 font-mono">
      <header className="bg-[#2a2a4a] border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <Link href="/" className="text-cyan-400 hover:text-cyan-300 text-[12px]">
          &larr; 返回编辑部
        </Link>
        <span className="text-[14px] text-gray-300 tracking-widest">LLM API 配置</span>
      </header>

      <main className="max-w-[1000px] mx-auto p-6 flex gap-6">
        {/* Provider list */}
        <div className="w-[280px] shrink-0">
          <div className="flex items-center justify-between mb-2 border-b border-gray-700/50 pb-1">
            <span className="text-[10px] text-cyan-400/80">已配置 Provider</span>
            <button
              onClick={handleAdd}
              className="text-[9px] text-cyan-400 hover:text-cyan-300 border border-cyan-600/50 px-2 py-0.5 rounded-sm"
            >
              + 添加
            </button>
          </div>

          {loading ? (
            <div className="text-[10px] text-gray-500 py-4">加载中...</div>
          ) : providers.length === 0 ? (
            <div className="text-[10px] text-gray-500 py-4">暂无配置，点击添加</div>
          ) : (
            <div className="space-y-1">
              {providers.map((p) => (
                <button
                  key={p.provider_id}
                  onClick={() => handleSelect(p)}
                  className={`w-full text-left px-3 py-2 rounded-sm text-[11px] transition-colors border ${
                    selected?.provider_id === p.provider_id
                      ? "bg-cyan-900/30 border-cyan-600/50 text-cyan-300"
                      : "bg-gray-900/30 border-gray-700/50 text-gray-300 hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold">{p.name}</span>
                    {p.is_default && (
                      <span className="text-[8px] text-yellow-400 border border-yellow-600/30 px-1 rounded-sm">
                        默认
                      </span>
                    )}
                  </div>
                  <div className="text-[9px] text-gray-500 mt-0.5">{p.provider_id}</div>
                  <div className="text-[9px] text-gray-500">
                    {p.default_model || "(未设置模型)"}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={`text-[8px] px-1.5 py-0.5 rounded-sm border ${
                        p.is_enabled
                          ? "text-green-400 border-green-600/30"
                          : "text-gray-500 border-gray-600/30"
                      }`}
                    >
                      {p.is_enabled ? "启用" : "禁用"}
                    </span>
                    {p.test_status && (
                      <span
                        className={`text-[8px] px-1.5 py-0.5 rounded-sm border ${
                          p.test_status === "success"
                            ? "text-green-400 border-green-600/30"
                            : "text-red-400 border-red-600/30"
                        }`}
                      >
                        {p.test_status === "success" ? "测试OK" : "测试失败"}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail / Form */}
        <div className="flex-1 min-w-0">
          {!selected && !showAdd ? (
            <div className="text-[11px] text-gray-500 py-12 text-center">
              选择左侧 Provider 查看详情，或点击&quot;+ 添加&quot;新建配置
            </div>
          ) : (
            <div className="space-y-4">
              {/* Provider selector for new */}
              {showAdd && (
                <div className="bg-gray-900/50 border border-gray-700 rounded-sm p-4">
                  <div className="text-[10px] text-cyan-400/80 mb-3">选择 Provider 类型</div>
                  <div className="grid grid-cols-2 gap-2">
                    {LLM_PROVIDER_TEMPLATES.map((t) => (
                      <button
                        key={t.provider_id}
                        onClick={() => handleTemplateSelect(t.provider_id)}
                        className={`text-left px-3 py-2 rounded-sm text-[10px] border transition-colors ${
                          formData.provider_id === t.provider_id
                            ? "bg-cyan-900/30 border-cyan-600/50 text-cyan-300"
                            : "bg-gray-800/50 border-gray-700/50 text-gray-300 hover:border-gray-600"
                        }`}
                      >
                        <div className="font-bold">{t.name}</div>
                        <div className="text-[9px] text-gray-500 mt-0.5 truncate">{t.description}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Form */}
              <div className="bg-gray-900/50 border border-gray-700 rounded-sm p-4 space-y-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-cyan-400/80">
                    {showAdd ? "新建 Provider" : "Provider 配置"}
                  </span>
                  {editing && (
                    <div className="flex gap-2">
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="text-[9px] text-cyan-400 hover:text-cyan-300 border border-cyan-600/50 px-2 py-0.5 rounded-sm disabled:opacity-50"
                      >
                        {saving ? "保存中..." : "保存"}
                      </button>
                      <button
                        onClick={() => {
                          setEditing(false);
                          if (selected) handleSelect(selected);
                          if (showAdd) resetForm();
                        }}
                        className="text-[9px] text-gray-400 hover:text-white border border-gray-600 px-2 py-0.5 rounded-sm"
                      >
                        取消
                      </button>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[9px] text-gray-400 block mb-1">Provider ID</label>
                    <input
                      type="text"
                      value={formData.provider_id}
                      onChange={(e) => setFormData({ ...formData, provider_id: e.target.value })}
                      disabled={!showAdd}
                      className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                      placeholder="如: openai"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] text-gray-400 block mb-1">显示名称</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      disabled={!editing}
                      className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                      placeholder="如: OpenAI GPT-4"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[9px] text-gray-400 block mb-1">API Key</label>
                  <input
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    disabled={!editing}
                    className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                    placeholder="sk-..."
                  />
                </div>

                <div>
                  <label className="text-[9px] text-gray-400 block mb-1">Base URL</label>
                  <input
                    type="text"
                    value={formData.base_url}
                    onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                    disabled={!editing}
                    className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[9px] text-gray-400 block mb-1">默认模型</label>
                    <input
                      type="text"
                      value={formData.default_model}
                      onChange={(e) => setFormData({ ...formData, default_model: e.target.value })}
                      disabled={!editing}
                      className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                      placeholder="gpt-4o-mini"
                    />
                  </div>
                  <div>
                    <label className="text-[9px] text-gray-400 block mb-1">超时时间 (秒)</label>
                    <input
                      type="number"
                      value={formData.timeout}
                      onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) || 60 })}
                      disabled={!editing}
                      min={5}
                      max={300}
                      className="w-full bg-gray-800 border border-gray-600 rounded-sm px-2 py-1.5 text-[10px] text-gray-200 disabled:opacity-50"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-[10px]">
                    <input
                      type="checkbox"
                      checked={formData.is_enabled}
                      onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                      disabled={!editing}
                      className="w-3 h-3"
                    />
                    <span className="text-gray-300">启用</span>
                  </label>
                  <label className="flex items-center gap-2 text-[10px]">
                    <input
                      type="checkbox"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      disabled={!editing}
                      className="w-3 h-3"
                    />
                    <span className="text-gray-300">设为默认</span>
                  </label>
                </div>

                {message && (
                  <div className="text-[9px] text-cyan-400 mt-2">{message}</div>
                )}
              </div>

              {/* Actions */}
              {selected && (
                <div className="flex gap-3">
                  {!editing ? (
                    <button
                      onClick={() => setEditing(true)}
                      className="text-[10px] text-cyan-400 hover:text-cyan-300 border border-cyan-600/50 px-3 py-1.5 rounded-sm"
                    >
                      编辑配置
                    </button>
                  ) : (
                    <button
                      onClick={handleTest}
                      disabled={testing}
                      className="text-[10px] text-green-400 hover:text-green-300 border border-green-600/50 px-3 py-1.5 rounded-sm disabled:opacity-50"
                    >
                      {testing ? "测试中..." : "测试连接"}
                    </button>
                  )}

                  {!editing && !selected.is_default && (
                    <button
                      onClick={() => handleSetDefault(selected.provider_id)}
                      className="text-[10px] text-yellow-400 hover:text-yellow-300 border border-yellow-600/50 px-3 py-1.5 rounded-sm"
                    >
                      设为默认
                    </button>
                  )}

                  <button
                    onClick={handleDelete}
                    className="text-[10px] text-red-400 hover:text-red-300 border border-red-600/50 px-3 py-1.5 rounded-sm"
                  >
                    删除
                  </button>
                </div>
              )}

              {/* Test result */}
              {testResult && (
                <div
                  className={`bg-gray-900/50 border rounded-sm p-3 ${
                    testResult.success ? "border-green-600/50" : "border-red-600/50"
                  }`}
                >
                  <div className={`text-[10px] ${testResult.success ? "text-green-400" : "text-red-400"}`}>
                    {testResult.success ? "[测试成功]" : "[测试失败]"}
                  </div>
                  <div className="text-[9px] text-gray-400 mt-1">{testResult.message}</div>
                  {testResult.latency && (
                    <div className="text-[9px] text-gray-500 mt-1">耗时: {testResult.latency}ms</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
