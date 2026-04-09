"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/console/icons";
import { LanguageSwitcher } from "@/components/console/language-switcher";
import { Badge } from "@/components/console/ui";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";

const navItems = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: "dashboard" as const },
  { href: "/workspace", labelKey: "nav.workspace", icon: "workspace" as const },
  { href: "/accounts", labelKey: "nav.accounts", icon: "accounts" as const },
  { href: "/drafts", labelKey: "nav.drafts", icon: "drafts" as const },
  { href: "/publish-logs", labelKey: "nav.publishLogs", icon: "publish" as const },
  { href: "/tasks/history", labelKey: "nav.taskHistory", icon: "history" as const },
  { href: "/settings", labelKey: "nav.settings", icon: "settings" as const },
];

function pathLabel(pathname: string): string {
  const item = navItems.find((entry) => pathname === entry.href || pathname.startsWith(`${entry.href}/`));
  if (item?.href === "/workspace") {
    return pathname.startsWith("/workspace") ? "__debug_workspace__" : item.labelKey;
  }
  return item?.labelKey ?? "HotClaw";
}

export function ToastViewport() {
  const toasts = useAppStore((state) => state.toasts);
  const dismissToast = useAppStore((state) => state.dismissToast);
  const timeoutMap = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  useEffect(() => {
    const activeIds = new Set(toasts.map((toast) => toast.id));

    for (const toast of toasts) {
      if (timeoutMap.current.has(toast.id)) {
        continue;
      }

      const timeoutId = setTimeout(() => {
        dismissToast(toast.id);
        timeoutMap.current.delete(toast.id);
      }, 5000);

      timeoutMap.current.set(toast.id, timeoutId);
    }

    for (const [toastId, timeoutId] of timeoutMap.current.entries()) {
      if (activeIds.has(toastId)) {
        continue;
      }

      clearTimeout(timeoutId);
      timeoutMap.current.delete(toastId);
    }
  }, [dismissToast, toasts]);

  useEffect(() => {
    return () => {
      for (const timeoutId of timeoutMap.current.values()) {
        clearTimeout(timeoutId);
      }
      timeoutMap.current.clear();
    };
  }, []);

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[80] flex w-full max-w-sm flex-col gap-3">
      {toasts.slice(-4).map((toast) => (
        <div key={toast.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">{toast.title}</p>
              {toast.message ? <p className="mt-1 text-sm text-slate-500">{toast.message}</p> : null}
            </div>
            <button type="button" onClick={() => dismissToast(toast.id)} className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <Icon name="close" className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const session = useAppStore((state) => state.session);
  const mobileNavOpen = useAppStore((state) => state.mobileNavOpen);
  const setMobileNavOpen = useAppStore((state) => state.setMobileNavOpen);
  const { locale, t } = useI18n();

  const title = useMemo(() => {
    const key = pathLabel(pathname);
    if (key === "__debug_workspace__") {
      return pathname.startsWith("/workspace") ? (locale === "zh-CN" ? "调试工作台" : "Debug Workspace") : "HotClaw";
    }
    return key === "HotClaw" ? "HotClaw" : t(key);
  }, [locale, pathname, t]);
  const displayName = session?.displayName || "HotClaw Operator";
  const email = session?.email || "local-adapter@hotclaw.dev";

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.08),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.06),_transparent_24%),_var(--color-shell-background)] text-slate-900">
      <div className="lg:hidden">
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          className="fixed left-4 top-4 z-[65] rounded-2xl border border-slate-200 bg-white p-3 shadow-lg"
        >
          <Icon name="menu" className="h-5 w-5" />
        </button>
      </div>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] w-72 border-r border-white/70 bg-white/90 px-5 py-6 shadow-xl backdrop-blur lg:translate-x-0 lg:bg-white/80",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full transition-transform lg:transition-none",
        )}
      >
        <div className="mb-8 flex items-center justify-between gap-3">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-lg shadow-brand-600/20">
              <Icon name="paw" className="h-5 w-5" />
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-950">HotClaw</p>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Console</p>
            </div>
          </Link>
          <button type="button" onClick={() => setMobileNavOpen(false)} className="rounded-full p-2 text-slate-400 hover:bg-slate-100 lg:hidden">
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>

        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileNavOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition",
                  active
                    ? "border border-brand-200 bg-brand-50 text-brand-700 shadow-sm"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
                >
                <Icon name={item.icon} className="h-4 w-4" />
                <span>{item.href === "/workspace" ? (locale === "zh-CN" ? "调试工作台" : "Debug Workspace") : t(item.labelKey)}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-8 rounded-3xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{t("shell.workingMode")}</p>
          <p className="mt-2 text-sm font-medium text-slate-900">{t("shell.workingSummary")}</p>
          <p className="mt-1 text-sm text-slate-500">{t("shell.workingDescription")}</p>
        </div>

        <div className="mt-auto hidden rounded-3xl border border-slate-200 bg-white p-4 shadow-sm lg:block">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {displayName.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
              <p className="truncate text-xs text-slate-500">{email}</p>
            </div>
          </div>
        </div>
      </aside>

      {mobileNavOpen ? <div className="fixed inset-0 z-[60] bg-slate-950/30 backdrop-blur-sm lg:hidden" onClick={() => setMobileNavOpen(false)} /> : null}

      <div className="lg:pl-72">
        <header className="sticky top-0 z-50 border-b border-white/70 bg-white/70 backdrop-blur">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-6 py-4 lg:px-8">
            <div className="hidden min-w-0 md:block">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{t("shell.activeArea")}</p>
              <div className="mt-1 flex items-center gap-3">
                <h1 className="truncate text-xl font-semibold text-slate-950">{title}</h1>
                <Badge tone="success">{t("shell.connected")}</Badge>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-3">
              <LanguageSwitcher compact />
              <label className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 md:flex">
                <Icon name="search" className="h-4 w-4 text-slate-400" />
                <input
                  readOnly
                  value=""
                  placeholder={t("shell.searchPlaceholder")}
                  className="w-72 bg-transparent text-sm text-slate-600 outline-none placeholder:text-slate-400"
                />
              </label>
              <button type="button" className="relative rounded-2xl border border-slate-200 bg-white p-3 text-slate-500 hover:text-slate-900">
                <Icon name="bell" className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-brand-500" />
              </button>
              <div className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 md:flex">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                  {displayName.slice(0, 1).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
                  <p className="truncate text-xs text-slate-500">{email}</p>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1440px] px-6 py-8 lg:px-8">{children}</main>
      </div>
      <ToastViewport />
    </div>
  );
}
