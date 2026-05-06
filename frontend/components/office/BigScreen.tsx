/** Big screen dashboard on the office wall. Shows account stats (demo data). */

"use client";

import { useState, useEffect } from "react";
import type { DashboardStats } from "@/types";

// Demo data that slowly increments to feel alive
const BASE_STATS: DashboardStats = {
  account_name: "HotClaw 编辑部",
  followers: 128456,
  total_reads: 3842910,
  avg_reads: 12800,
  articles_count: 287,
  weekly_growth: 2.3,
};

function formatNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + "万";
  return n.toLocaleString();
}

export default function BigScreen() {
  const [stats, setStats] = useState(BASE_STATS);

  // Simulate live data ticking
  useEffect(() => {
    const timer = setInterval(() => {
      setStats((prev) => ({
        ...prev,
        followers: prev.followers + Math.floor(Math.random() * 3),
        total_reads: prev.total_reads + Math.floor(Math.random() * 50),
      }));
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative">
      {/* Screen frame */}
      <div className="bg-gray-700 p-[3px] rounded-sm shadow-[0_0_20px_rgba(59,130,246,0.15)]">
        <div className="bg-[#0a1628] w-[280px] h-[160px] rounded-sm relative overflow-hidden p-3">
          {/* Scanline overlay */}
          <div
            className="absolute inset-0 pointer-events-none opacity-5"
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.05) 2px, rgba(255,255,255,0.05) 4px)",
            }}
          />

          {/* Content */}
          <div className="relative z-10 h-full flex flex-col">
            {/* Title */}
            <div className="text-center mb-2">
              <span className="text-[10px] font-mono text-cyan-400 tracking-widest">
                ▸ {stats.account_name} ◂
              </span>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 flex-1">
              <StatItem label="粉丝数" value={formatNum(stats.followers)} color="text-green-400" />
              <StatItem label="总阅读" value={formatNum(stats.total_reads)} color="text-blue-400" />
              <StatItem label="篇均阅读" value={formatNum(stats.avg_reads)} color="text-yellow-400" />
              <StatItem label="文章数" value={String(stats.articles_count)} color="text-purple-400" />
            </div>

            {/* Bottom bar */}
            <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-700/50">
              <span className="text-[8px] font-mono text-gray-500">周增长</span>
              <span className="text-[9px] font-mono text-green-400">
                +{stats.weekly_growth}%
              </span>
              <span className="text-[8px] font-mono text-gray-600">
                LIVE
              </span>
              <span className="w-[5px] h-[5px] rounded-full bg-green-500 animate-pulse" />
            </div>
          </div>
        </div>
      </div>

      {/* Screen mount bracket */}
      <div className="flex justify-center">
        <div className="w-[6px] h-[10px] bg-gray-600" />
      </div>
    </div>
  );
}

function StatItem({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[7px] font-mono text-gray-500">{label}</span>
      <span className={`text-[12px] font-mono ${color} font-bold leading-tight`}>{value}</span>
    </div>
  );
}
