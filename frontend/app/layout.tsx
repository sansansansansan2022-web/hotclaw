import type { Metadata } from "next";
import { AppProvider } from "@/components/providers/app-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HotClaw",
  description: "Multi-agent content production platform for WeChat official accounts",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const runtimeApiOrigin = process.env.HOTCLAW_API_ORIGIN ?? process.env.NEXT_PUBLIC_HOTCLAW_API_ORIGIN ?? "";

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__HOTCLAW_API_ORIGIN__ = ${JSON.stringify(runtimeApiOrigin)};`,
          }}
        />
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
