import type { Metadata } from "next";
import { AppProvider } from "@/components/providers/app-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HotClaw",
  description: "Multi-agent content production platform for WeChat official accounts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
