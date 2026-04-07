"use client";

import { useEffect, useRef } from "react";
import { getSystemConfigValue } from "@/lib/api";
import { normalizeLocale } from "@/lib/i18n";
import { useAppStore } from "@/store/appStore";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const locale = useAppStore((state) => state.locale);
  const setLocale = useAppStore((state) => state.setLocale);
  const synced = useRef(false);

  useEffect(() => {
    document.documentElement.lang = locale === "zh-CN" ? "zh-CN" : "en";
  }, [locale]);

  useEffect(() => {
    if (synced.current) {
      return;
    }

    synced.current = true;
    void (async () => {
      try {
        const value = await getSystemConfigValue("ui_language", "en");
        const nextLocale = normalizeLocale(value);
        if (nextLocale !== locale) {
          setLocale(nextLocale);
        }
      } catch {
        // Keep the persisted client locale if the backend setting is unavailable.
      }
    })();
  }, [locale, setLocale]);

  return <>{children}</>;
}
