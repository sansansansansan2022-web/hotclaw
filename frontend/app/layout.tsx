import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HotClaw 编辑部",
  description: "多智能体公众号内容生产平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
