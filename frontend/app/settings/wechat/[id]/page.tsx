"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getWeChatConfig, createWeChatConfig, updateWeChatConfig, testWeChatConnection } from "@/lib/api";

interface Props {
  params: Promise<{ id: string }>;
}

export default function WeChatSettingsPage({ params }: Props) {
  const [accountId, setAccountId] = useState<string>("");
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [defaultAuthor, setDefaultAuthor] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);
  const [needOpenComment, setNeedOpenComment] = useState(true);
  const [onlyFansCanComment, setOnlyFansCanComment] = useState(false);

  useEffect(() => {
    params.then(p => {
      setAccountId(p.id);
      loadConfig(p.id);
    });
  }, []);

  async function loadConfig(id: string) {
    try {
      const data = await getWeChatConfig(id);
      setConfig(data as any);
      if (data) {
        setDefaultAuthor((data as any).default_author || "");
        setIsEnabled((data as any).is_enabled ?? true);
      }
    } catch (e) {
      // No config exists yet
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      if (config) {
        // Update
        await updateWeChatConfig(accountId, {
          app_id: appId || undefined,
          app_secret: appSecret || undefined,
          default_author: defaultAuthor || undefined,
          is_enabled: isEnabled,
          need_open_comment: needOpenComment,
          only_fans_can_comment: onlyFansCanComment,
        });
        setSuccess("配置已更新");
        setAppSecret("");
      } else {
        // Create
        if (!appId || !appSecret) {
          setError("请填写 AppID 和 AppSecret");
          setSaving(false);
          return;
        }
        await createWeChatConfig({
          account_id: accountId,
          app_id: appId,
          app_secret: appSecret,
          default_author: defaultAuthor || undefined,
          is_enabled: isEnabled,
          need_open_comment: needOpenComment,
          only_fans_can_comment: onlyFansCanComment,
        });
        setSuccess("配置已创建");
        await loadConfig(accountId);
      }
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!appId || !appSecret) {
      setError("请先填写 AppID 和 AppSecret");
      return;
    }

    setTesting(true);
    setError(null);

    try {
      const result = await testWeChatConnection({
        app_id: appId,
        app_secret: appSecret,
      });
      if ((result as any).success) {
        setSuccess("连接测试成功！");
      } else {
        setError((result as any).message || "连接测试失败");
      }
    } catch (e: any) {
      setError(e.message || "测试失败");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link
            href="/accounts"
            className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
          >
            <span>&larr;</span>
            <span>账号列表</span>
          </Link>
          <span className="text-slate-500">/</span>
          <Link
            href={`/accounts/${accountId}`}
            className="text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            账号详情
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium">微信配置</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto p-6">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">微信公众号配置</h1>
          <p className="text-slate-400 text-sm">
            配置公众号凭证以开通真实发布能力。配置后，草稿可以发布到微信公众号。
          </p>
        </div>

        {/* Status */}
        {config && (
          <div className="mb-6 p-4 bg-slate-800/60 rounded-xl border border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-400">AppID</div>
                <div className="text-white font-mono">{config.app_id_masked}</div>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-400">状态</div>
                <div className={`font-medium ${config.is_enabled ? "text-emerald-400" : "text-slate-500"}`}>
                  {config.is_enabled ? "已启用" : "已禁用"}
                </div>
              </div>
            </div>
            {config.test_status && (
              <div className="mt-3 pt-3 border-t border-slate-700">
                <span className={`text-xs px-2 py-1 rounded ${
                  config.test_status === "success" ? "bg-emerald-900/50 text-emerald-400" :
                  config.test_status === "failed" ? "bg-red-900/50 text-red-400" :
                  "bg-slate-700 text-slate-400"
                }`}>
                  {config.test_status === "success" ? "连接正常" :
                   config.test_status === "failed" ? "连接失败" : "未测试"}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Form */}
        <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              AppID <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={appId}
              onChange={e => setAppId(e.target.value)}
              placeholder="wx1234567890abcdef"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              AppSecret <span className="text-red-400">*</span>
            </label>
            <input
              type="password"
              value={appSecret}
              onChange={e => setAppSecret(e.target.value)}
              placeholder={config ? "已保存，如需修改请填写新值" : "请填写 AppSecret"}
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
            {config?.has_app_secret && !appSecret && (
              <p className="mt-1 text-xs text-slate-500">已有 AppSecret，如需修改请填写新值</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              默认作者
            </label>
            <input
              type="text"
              value={defaultAuthor}
              onChange={e => setDefaultAuthor(e.target.value)}
              placeholder="作者名称（可选）"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={e => setIsEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
              />
              <span className="text-sm text-slate-300">启用微信发布</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={needOpenComment}
                onChange={e => setNeedOpenComment(e.target.checked)}
                className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
              />
              <span className="text-sm text-slate-300">开启评论功能</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyFansCanComment}
                onChange={e => setOnlyFansCanComment(e.target.checked)}
                className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
              />
              <span className="text-sm text-slate-300">仅粉丝可评论</span>
            </label>
          </div>

          {/* Messages */}
          {error && (
            <div className="p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="p-3 bg-emerald-900/30 border border-emerald-700 rounded-lg text-emerald-400 text-sm">
              {success}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 text-white rounded-lg transition-colors"
            >
              {saving ? "保存中..." : "保存配置"}
            </button>
            <button
              onClick={handleTest}
              disabled={testing || !appId || !appSecret}
              className="px-6 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg transition-colors"
            >
              {testing ? "测试中..." : "测试连接"}
            </button>
          </div>
        </div>

        {/* Help */}
        <div className="mt-6 p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
          <h3 className="text-sm font-medium text-slate-300 mb-2">如何获取凭证？</h3>
          <ol className="text-xs text-slate-400 space-y-1 list-decimal list-inside">
            <li>登录微信公众平台 (https://mp.weixin.qq.com)</li>
            <li>进入「设置与开发」→「基本配置」</li>
            <li>获取 AppID 和 AppSecret</li>
            <li>确保已开通草稿箱和发布能力</li>
          </ol>
        </div>
      </main>
    </div>
  );
}
