import type { SVGProps } from "react";

type IconName =
  | "dashboard"
  | "workspace"
  | "accounts"
  | "drafts"
  | "publish"
  | "history"
  | "settings"
  | "chevronRight"
  | "menu"
  | "search"
  | "bell"
  | "plus"
  | "play"
  | "edit"
  | "download"
  | "check"
  | "close"
  | "arrowUpRight"
  | "warning"
  | "refresh"
  | "filter"
  | "paw";

const paths: Record<IconName, string> = {
  dashboard: "M4 13h7V4H4v9Zm9 7h7V11h-7v9ZM4 20h7v-5H4v5Zm9-9h7V4h-7v7Z",
  workspace: "M3 4h18v4H3V4Zm0 6h10v10H3V10Zm12 0h6v10h-6V10Z",
  accounts: "M16 11c1.66 0 2.99-1.79 2.99-4S17.66 3 16 3s-3 1.79-3 4 1.34 4 3 4Zm-8 0c1.66 0 2.99-1.79 2.99-4S9.66 3 8 3 5 4.79 5 7s1.34 4 3 4Zm0 2c-2.33 0-7 1.17-7 3.5V21h14v-4.5C15 14.17 10.33 13 8 13Zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.95 1.97 3.45V21h6v-4.5c0-2.33-4.67-3.5-7-3.5Z",
  drafts: "M6 2h9l5 5v15a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 1.5V8h4.5",
  publish: "M3 12 21 3l-5 18-4-7-7-2Z",
  history: "M13 3a9 9 0 1 0 8.95 10h-2.02A7 7 0 1 1 13 5a6.96 6.96 0 0 1 4.95 2.05L15 10h7V3l-2.63 2.63A8.96 8.96 0 0 0 13 3Zm-1 5v6l4 2 .9-1.79-2.9-1.46V8H12Z",
  settings: "M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.1 7.1 0 0 0-1.63-.94l-.36-2.54a.49.49 0 0 0-.49-.42h-3.84a.49.49 0 0 0-.49.42l-.36 2.54c-.58.23-1.12.54-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.7 8.84a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.63-.06.94 0 .31.02.63.06.94L2.82 14.52a.5.5 0 0 0-.12.64l1.92 3.32a.5.5 0 0 0 .6.22l2.39-.96c.51.4 1.05.71 1.63.94l.36 2.54c.04.24.25.42.49.42h3.84c.24 0 .45-.18.49-.42l.36-2.54c.58-.23 1.12-.54 1.63-.94l2.39.96a.5.5 0 0 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z",
  chevronRight: "m9 18 6-6-6-6",
  menu: "M3 6h18M3 12h18M3 18h18",
  search: "m21 21-4.35-4.35M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z",
  bell: "M15 17h5l-1.4-1.4a1 1 0 0 1-.3-.7V10a6.3 6.3 0 0 0-1.6-4.2A5.6 5.6 0 0 0 13 4.1V3a1 1 0 1 0-2 0v1.1A5.6 5.6 0 0 0 7.3 5.8 6.3 6.3 0 0 0 5.7 10v4.9a1 1 0 0 1-.3.7L4 17h5m6 0a3 3 0 1 1-6 0",
  plus: "M12 5v14M5 12h14",
  play: "M8 5v14l11-7-11-7Z",
  edit: "m4 20 4.5-1 10-10a2.12 2.12 0 1 0-3-3l-10 10L4 20Z",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M4 19h16",
  check: "M5 12.5 9 16l10-10",
  close: "M6 6 18 18M18 6 6 18",
  arrowUpRight: "M7 17 17 7M9 7h8v8",
  warning: "M12 3 2 21h20L12 3Zm0 6v5m0 4h.01",
  refresh: "M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6",
  filter: "M4 6h16M7 12h10m-7 6h4",
  paw: "M9 11c0 1.1-.67 2-1.5 2S6 12.1 6 11s.67-2 1.5-2S9 9.9 9 11Zm4-3.5c0 1.1-.67 2-1.5 2S10 8.6 10 7.5s.67-2 1.5-2 1.5.9 1.5 2Zm5 3.5c0 1.1-.67 2-1.5 2S15 12.1 15 11s.67-2 1.5-2 1.5.9 1.5 2Zm-6 3c-3 0-5 2-5 4 0 1 1 2 2.5 2h5c1.5 0 2.5-1 2.5-2 0-2-2-4-5-4Z",
};

export function Icon({
  name,
  className,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
