"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AppLocale, AppSession, ToastTone } from "@/types";

interface ToastItem {
  id: string;
  title: string;
  message?: string;
  tone: ToastTone;
}

interface AppStore {
  session: AppSession | null;
  locale: AppLocale;
  mobileNavOpen: boolean;
  toasts: ToastItem[];
  signIn: (email: string) => void;
  signOut: () => void;
  setLocale: (locale: AppLocale) => void;
  setMobileNavOpen: (open: boolean) => void;
  pushToast: (toast: Omit<ToastItem, "id">) => void;
  dismissToast: (id: string) => void;
}

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      session: null,
      locale: "en",
      mobileNavOpen: false,
      toasts: [],
      signIn: (email) =>
        set({
          session: {
            email,
            displayName: email.split("@")[0],
            provider: "local_adapter",
          },
        }),
      signOut: () => set({ session: null }),
      setLocale: (locale) => set({ locale }),
      setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
      pushToast: (toast) =>
        set((state) => ({
          toasts: [
            ...state.toasts,
            {
              ...toast,
              id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            },
          ],
        })),
      dismissToast: (id) =>
        set((state) => ({
          toasts: state.toasts.filter((toast) => toast.id !== id),
        })),
    }),
    {
      name: "hotclaw-app-store",
      partialize: (state) => ({
        session: state.session,
        locale: state.locale,
      }),
    },
  ),
);
