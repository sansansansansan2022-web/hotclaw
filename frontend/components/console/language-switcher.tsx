"use client";

import { startTransition, useState } from "react";
import { Button } from "@/components/console/ui";
import { updateGlobalLanguage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAppStore } from "@/store/appStore";
import type { AppLocale } from "@/types";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const pushToast = useAppStore((state) => state.pushToast);
  const { locale, setLocale, t } = useI18n();
  const [saving, setSaving] = useState<AppLocale | null>(null);

  const applyLocale = async (nextLocale: AppLocale) => {
    if (nextLocale === locale || saving) {
      return;
    }

    const previousLocale = locale;
    startTransition(() => setLocale(nextLocale));
    setSaving(nextLocale);

    try {
      await updateGlobalLanguage(nextLocale);
      pushToast({
        tone: "success",
        title: t("language.toast.successTitle"),
        message: t("language.toast.successMessage", { language: t(`locale.${nextLocale}`) }),
      });
    } catch (error) {
      startTransition(() => setLocale(previousLocale));
      pushToast({
        tone: "danger",
        title: t("language.toast.errorTitle"),
        message: error instanceof Error ? error.message : t("language.toast.errorMessage"),
      });
    } finally {
      setSaving(null);
    }
  };

  if (compact) {
    return (
      <div className="hidden items-center gap-1 rounded-2xl border border-slate-200 bg-white p-1 md:flex">
        {([
          ["en", "EN"],
          ["zh-CN", "中文"],
        ] as Array<[AppLocale, string]>).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => void applyLocale(value)}
            disabled={Boolean(saving)}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              locale === value ? "bg-brand-600 text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold text-slate-900">{t("language.title")}</p>
        <p className="mt-1 text-sm text-slate-500">{t("language.description")}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        {([
          ["en", t("locale.en")],
          ["zh-CN", t("locale.zh-CN")],
        ] as Array<[AppLocale, string]>).map(([value, label]) => (
          <Button
            key={value}
            variant={locale === value ? "primary" : "secondary"}
            disabled={Boolean(saving)}
            onClick={() => void applyLocale(value)}
          >
            {saving === value ? `${label}...` : label}
          </Button>
        ))}
      </div>
      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{t("language.persisted")}</p>
    </div>
  );
}
