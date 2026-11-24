import { type ReactNode } from "react";
import type { IconName } from "../types";

const paths: Record<IconName, ReactNode> = {
  shop: (
    <>
      <path d="M4 10h16v10H4z" />
      <path d="M3 10l2-6h14l2 6M8 20v-6h5v6" />
      <path d="M3 10c0 2 3 2 3 0 0 2 4 2 4 0 0 2 4 2 4 0 0 2 4 2 4 0 0 2 3 2 3 0" />
    </>
  ),
  crown: (
    <>
      <path d="M4 18h16l-1-10-5 4-2-7-2 7-5-4z" />
      <path d="M5 21h14" />
    </>
  ),
  box: (
    <>
      <path d="M4 7l8-4 8 4-8 4z" />
      <path d="M4 7v10l8 4 8-4V7M12 11v10" />
    </>
  ),
  hand: (
    <path d="M7 12V7a2 2 0 014 0v4-6a2 2 0 014 0v6-5a2 2 0 014 0v6-3a2 2 0 014 0v6c0 4-3 7-7 7h-1c-3 0-5-1-7-4l-2-3a2 2 0 013-3l2 2" />
  ),
  speaker: (
    <>
      <path d="M5 10v4h4l5 4V6l-5 4z" />
      <path d="M17 9c2 2 2 4 0 6M20 6c4 4 4 8 0 12" />
    </>
  ),
  logout: (
    <>
      <path d="M10 4H5v16h5M14 8l4 4-4 4M18 12H9" />
    </>
  ),
  sale: (
    <>
      <path d="M4 5h2l2 10h10l2-7H7" />
      <circle cx="10" cy="19" r="1" />
      <circle cx="17" cy="19" r="1" />
    </>
  ),
  stock: (
    <>
      <path d="M4 7l8-4 8 4-8 4z" />
      <path d="M4 7v10l8 4 8-4V7M12 11v10" />
      <path d="M17 3v5M14.5 5.5h5" />
    </>
  ),
  wallet: (
    <>
      <path d="M3 6h15a2 2 0 012 2v11H5a2 2 0 01-2-2z" />
      <path d="M16 11h5v5h-5a2 2 0 010-5z" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3L2 21h20z" />
      <path d="M12 9v5M12 18h.01" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0116 0" />
    </>
  ),
  search: (
    <>
      <circle cx="10" cy="10" r="6" />
      <path d="M15 15l6 6" />
    </>
  ),
  bottle: (
    <>
      <path d="M9 3h6v4l2 3v10a2 2 0 01-2 2H9a2 2 0 01-2-2V10l2-3z" />
      <path d="M9 7h6M9 14h6" />
    </>
  ),
  can: (
    <>
      <ellipse cx="12" cy="5" rx="7" ry="3" />
      <path d="M5 5v14c0 1.66 3.13 3 7 3s7-1.34 7-3V5" />
      <path d="M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  minus: (
    <>
      <path d="M5 12h14" />
    </>
  ),
  check: (
    <>
      <polyline points="20 6 9 17 4 12" />
    </>
  ),
  back: (
    <>
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </>
  ),
  forward: (
    <>
      <path d="M5 12h14M12 5l7 7-7 7" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </>
  ),
  receipt: (
    <>
      <path d="M4 2v20l3-2 3 2 3-2 3 2 4-2V2l-4 2-3-2-3 2-3-2z" />
      <line x1="8" y1="8" x2="16" y2="8" />
      <line x1="8" y1="12" x2="16" y2="12" />
      <line x1="8" y1="16" x2="13" y2="16" />
    </>
  ),
  phone: (
    <>
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
    </>
  ),
  home: (
    <>
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </>
  ),
  language: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </>
  ),
  cash: (
    <>
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <circle cx="12" cy="12" r="3" />
      <path d="M6 12h.01M18 12h.01" />
    </>
  ),
  return: (
    <>
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 102.13-9.36L1 10" />
    </>
  ),
  print: (
    <>
      <path d="M7 9V3h10v6M7 18H4V9h16v9h-3M7 14h10v7H7z" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </>
  ),
  trash: (
    <>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
    </>
  ),
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
  refresh: <><path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5m-4 8a8 8 0 0 0 14 3l3-3m0 5v-5h-5" /></>,
  archive: <><path d="M3 4h18v5H3zM5 9v11h14V9m-9 4h4" /></>,
  edit: (
    <>
      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
    </>
  ),
};

export function Icon({ name, size = 30, className = "" }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
