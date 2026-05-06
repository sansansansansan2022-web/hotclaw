"use client";

import { useState } from "react";
import type { NodeState } from "@/hooks/useTaskSSE";

// 文章数据接口
export interface ArticleContent {
  content_markdown: string;
  word_count: number;
  structure?: {
    sections: Array<{ heading: string; summary: string }>;
  };
  tags?: string[];
}

interface WeChatArticleProps {
  content: ArticleContent;
  title?: string;
}

// Markdown 解析器（简化版）
function parseMarkdown(markdown: string): string {
  let html = markdown;

  // 转义 HTML 特殊字符（先处理代码块）
  const codeBlocks: string[] = [];
  html = html.replace(/```[\s\S]*?```/g, (match) => {
    codeBlocks.push(match);
    return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
  });

  // 转义 HTML
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  // 恢复代码块
  codeBlocks.forEach((code, i) => {
    const escapedCode = code
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'");
    html = html.replace(`__CODE_BLOCK_${i}__`, escapedCode);
  });

  // 处理标题
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // 处理引用块
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote><p>$1</p></blockquote>');

  // 处理分割线
  html = html.replace(/^---+$/gm, "<hr/>");
  html = html.replace(/^\*\*\*+$/gm, "<hr/>");

  // 处理内联代码
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // 处理代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");

  // 处理加粗
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // 处理斜体
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // 处理无序列表
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

  // 处理有序列表
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  // 处理链接
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

  // 处理图片
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" />');

  // 处理段落
  html = html
    .split("\n\n")
    .map((para) => {
      const trimmed = para.trim();
      if (!trimmed) return "";
      if (
        trimmed.startsWith("<h") ||
        trimmed.startsWith("<ul") ||
        trimmed.startsWith("<ol") ||
        trimmed.startsWith("<blockquote") ||
        trimmed.startsWith("<pre") ||
        trimmed.startsWith("<hr")
      ) {
        return trimmed;
      }
      // 修复列表项被段落包裹的问题
      if (trimmed.startsWith("<li>")) {
        return trimmed;
      }
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("\n");

  return html;
}

export default function WeChatArticle({ content, title }: WeChatArticleProps) {
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);
  const [showToast, setShowToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToastMessage = (type: "success" | "error", message: string) => {
    setShowToast({ type, message });
    setTimeout(() => setShowToast(null), 3000);
  };

  const handleCopyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(content.content_markdown);
      setCopiedFormat("markdown");
      showToastMessage("success", "Markdown 已复制到剪贴板");
      setTimeout(() => setCopiedFormat(null), 2000);
    } catch {
      showToastMessage("error", "复制失败，请手动选择复制");
    }
  };

  const handleCopyHTML = async () => {
    try {
      const htmlContent = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title || "微信公众号文章"}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.8;
      color: #3e3e3e;
      max-width: 677px;
      margin: 0 auto;
      padding: 20px 30px;
    }
    h1 { font-size: 28px; text-align: center; margin-bottom: 24px; color: #1a1a1a; }
    h2 { font-size: 20px; font-weight: bold; margin: 32px 0 16px; color: #1a1a1a; border-left: 4px solid #07c160; padding-left: 12px; }
    h3 { font-size: 18px; font-weight: bold; margin: 24px 0 12px; color: #333; }
    p { margin: 12px 0; text-align: justify; text-indent: 2em; }
    blockquote { margin: 16px 0; padding: 16px 20px; background: #f7f7f7; border-left: 4px solid #07c160; }
    blockquote p { margin: 0; text-indent: 0; color: #666; }
    pre { background: #282c34; color: #abb2bf; padding: 16px 20px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 14px; }
    code { font-family: monospace; font-size: 14px; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; color: #e83e8c; }
    pre code { background: transparent; padding: 0; color: inherit; }
    ul { margin: 12px 0; padding-left: 24px; }
    ul li { position: relative; padding-left: 16px; margin: 8px 0; }
    ul li::before { content: ""; position: absolute; left: 0; top: 10px; width: 6px; height: 6px; background: #07c160; border-radius: 50%; }
    ol { margin: 12px 0; padding-left: 24px; }
    img { max-width: 100%; height: auto; display: block; margin: 16px auto; border-radius: 8px; }
    strong { color: #d32f2f; }
    a { color: #576b95; text-decoration: none; border-bottom: 1px solid #576b95; }
  </style>
</head>
<body>
${parseMarkdown(content.content_markdown)}
</body>
</html>`;
      await navigator.clipboard.writeText(htmlContent);
      setCopiedFormat("html");
      showToastMessage("success", "HTML 已复制到剪贴板");
      setTimeout(() => setCopiedFormat(null), 2000);
    } catch {
      showToastMessage("error", "复制失败，请手动选择复制");
    }
  };

  const parsedHtml = parseMarkdown(content.content_markdown);

  return (
    <div className="bg-white rounded-xl overflow-hidden shadow-lg">
      {/* Toast 提示 */}
      {showToast && (
        <div
          className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-lg shadow-xl ${
            showToast.type === "success" ? "bg-green-500" : "bg-red-500"
          } text-white font-medium`}
          style={{ animation: "toast-fade-in 0.3s ease" }}
        >
          {showToast.message}
        </div>
      )}

      {/* 文章头部 */}
      <div className="bg-gradient-to-r from-green-600 to-emerald-500 px-6 py-8 text-white">
        <h1 className="text-2xl font-bold text-center mb-4">{title || "微信公众号文章"}</h1>
        <div className="flex items-center justify-center gap-4 text-sm text-white/80">
          <span>📝 {content.word_count.toLocaleString()} 字</span>
          {content.structure?.sections && (
            <span>📑 {content.structure.sections.length} 个章节</span>
          )}
        </div>
      </div>

      {/* 标签 */}
      {content.tags && content.tags.length > 0 && (
        <div className="px-6 py-4 border-b border-gray-100">
          <div className="wechat-tags">
            {content.tags.map((tag, index) => (
              <span key={index} className="wechat-tag">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 文章内容 - 可滚动 */}
      <div className="wechat-article px-6 py-8 overflow-y-auto" style={{ maxHeight: "60vh" }}>
        <div dangerouslySetInnerHTML={{ __html: parsedHtml }} />
      </div>

      {/* 导出按钮 */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">导出文章</span>
          <div className="export-buttons">
            <button
              onClick={handleCopyMarkdown}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                copiedFormat === "markdown"
                  ? "bg-green-500 text-white"
                  : "bg-slate-700 hover:bg-slate-600 text-white"
              }`}
            >
              {copiedFormat === "markdown" ? "✓ 已复制" : "📋 复制 Markdown"}
            </button>
            <button
              onClick={handleCopyHTML}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                copiedFormat === "html"
                  ? "bg-green-500 text-white"
                  : "bg-slate-700 hover:bg-slate-600 text-white"
              }`}
            >
              {copiedFormat === "html" ? "✓ 已复制" : "🌐 复制 HTML"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 实时进度组件
interface LiveProgressProps {
  nodes: NodeState[];
  taskStatus: string;
}

export function LiveProgress({ nodes, taskStatus }: LiveProgressProps) {
  const completedCount = nodes.filter((n) => n.status === "completed").length;
  const progress = Math.round((completedCount / nodes.length) * 100);
  const isRunning = taskStatus === "running" || nodes.some((n) => n.status === "running");

  return (
    <div className="bg-slate-800/80 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
      {/* 进度条 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-white">执行进度</span>
          <span className={`text-sm ${isRunning ? "text-cyan-400" : "text-gray-400"}`}>
            {completedCount}/{nodes.length} 完成
          </span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isRunning ? "bg-gradient-to-r from-cyan-500 to-green-500 wechat-progress-animated" : "bg-green-500"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="text-center mt-2">
          <span className={`text-2xl font-bold ${isRunning ? "text-cyan-400" : "text-green-400"}`}>
            {progress}%
          </span>
          {isRunning && <span className="text-gray-400 text-sm ml-2 animate-pulse">实时更新中...</span>}
        </div>
      </div>

      {/* 节点状态列表 */}
      <div className="space-y-3">
        {nodes.map((node, index) => (
          <div
            key={node.node_id}
            className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
              node.status === "running"
                ? "bg-blue-900/50 border border-blue-500/50"
                : node.status === "completed"
                ? "bg-green-900/30 border border-green-500/30"
                : node.status === "failed"
                ? "bg-red-900/30 border border-red-500/30"
                : "bg-slate-700/50 border border-slate-600/50"
            }`}
          >
            {/* 序号 */}
            <span className="w-6 h-6 rounded-full bg-slate-600 text-xs flex items-center justify-center text-gray-300">
              {index + 1}
            </span>

            {/* 状态图标 */}
            <span className="text-xl">
              {node.status === "completed" ? "✅" : node.status === "running" ? "⚡" : node.status === "failed" ? "❌" : "⏳"}
            </span>

            {/* 节点名称和摘要 */}
            <div className="flex-1 min-w-0">
              <div className={`font-medium ${node.status === "running" ? "text-blue-400" : node.status === "completed" ? "text-green-400" : node.status === "failed" ? "text-red-400" : "text-gray-400"}`}>
                {node.name}
              </div>
              {node.output_summary && (
                <div className="text-xs text-gray-500 truncate mt-0.5">{node.output_summary}</div>
              )}
              {node.error && (
                <div className="text-xs text-red-400 truncate mt-0.5">{node.error}</div>
              )}
            </div>

            {/* 耗时 */}
            {node.elapsed_seconds !== null && (
              <span className="text-xs text-gray-500">{node.elapsed_seconds.toFixed(1)}s</span>
            )}

            {/* 降级标记 */}
            {node.degraded && (
              <span className="text-xs px-2 py-0.5 bg-orange-900/50 text-orange-400 rounded">降级</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
