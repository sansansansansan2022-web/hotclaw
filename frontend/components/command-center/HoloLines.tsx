/**
 * HoloLines — 全息连接线
 *
 * 【设计理念】
 * 用 SVG 绘制节点之间的连接线，表示数据在流水线中的传递方向。
 * 每条线由两层构成：
 * 1. 背景线 — 静态的连接线段
 * 2. 流动粒子 — 动画效果，表示数据正在传输
 *
 * 【贝塞尔曲线】
 * 使用二次贝塞尔曲线 (Q) 而非直线 (L)：
 * - M cx1 cy1: 从起点出发
 * - Q mx my cx2 cy2: 曲线经过 mx/my 控制点，到达终点
 * - 控制点在连线中点偏上方，制造微微上拱的弧线效果
 *
 * 【流动动画原理】
 * stroke-dasharray: 实线长度 虚线长度（控制粒子形状）
 * stroke-dashoffset: 偏移量（控制粒子位置）
 * CSS animation: dashoffset 从 60→0 → 粒子向右流动
 *
 * 面试点：
 * - SVG path 贝塞尔曲线
 * - stroke-dasharray / stroke-dashoffset 动画
 * - CSS @keyframes
 */

"use client";

import { type NodeStatus } from "@/types";

/** 节点位置类型 */
interface NodePosition {
  node_id: string;
  status: NodeStatus;
  cx: number;  // 视口宽度百分比（50 = 中心）
  cy: number;  // 视口高度百分比（50 = 中心）
}

interface HoloLinesProps {
  nodes: NodePosition[];
}

export default function HoloLines({ nodes }: HoloLinesProps) {
  // 构建所有连线
  const lines: React.ReactNode[] = [];

  // 遍历相邻节点对
  for (let i = 0; i < nodes.length - 1; i++) {
    const from = nodes[i];     // 起点节点
    const to = nodes[i + 1];   // 终点节点

    // 【连线状态】由起点节点的状态决定
    // 例如：起点 DONE，终点 ACTIVE → 连线为 DONE 状态（青色）
    // 这样当一个节点完成时，连线立即变色
    const lineStatus: NodeStatus =
      from.status === "completed" ? "completed" :
      from.status === "running" ? "running" :
      from.status === "failed" ? "failed" :
      "pending";

    // CSS 类名：固定类 + 状态类
    // .cc-holo-line: 基础样式
    // .cc-holo-line.active/.done/.error: 状态变色
    const lineClass = `cc-holo-line ${lineStatus !== "pending" ? lineStatus : ""}`;

    // 流动粒子类名
    // .cc-holo-flow.active: 快速流动（绿灯）
    // .cc-holo-flow.done: 慢速流动（青灯）
    const flowClass = `cc-holo-flow ${lineStatus !== "pending" ? lineStatus : ""}`;

    // 计算控制点坐标（用于贝塞尔曲线上拱）
    const mx = (from.cx + to.cx) / 2;
    const my = (from.cy + to.cy) / 2 - 1.5;  // 向上偏移 1.5%

    lines.push(
      <g key={`line-${i}`}>
        {/*
         * 背景连线
         * stroke: 青色描边
         * fill: none（不填充）
         * opacity: 透明度
         */}
        <path
          d={`M ${from.cx} ${from.cy} Q ${mx} ${my} ${to.cx} ${to.cy}`}
          className={lineClass}
        />

        {/*
         * 流动粒子
         * 仅在非 pending 状态显示
         * stroke-dasharray 控制粒子形状：
         *   running: 5 10 → 5px 实线 + 10px 空隙（快节奏）
         *   done: 4 14 → 4px 实线 + 14px 空隙（慢节奏）
         */}
        {lineStatus !== "pending" && (
          <path
            d={`M ${from.cx} ${from.cy} Q ${mx} ${my} ${to.cx} ${to.cy}`}
            className={flowClass}
            // CSS animation 通过 stroke-dashoffset 实现流动效果
            strokeDasharray={lineStatus === "running" ? "5 10" : "4 14"}
          />
        )}
      </g>
    );
  }

  return (
    /*
     * SVG 全屏覆盖层
     * position: fixed 覆盖整个视口
     * zIndex: 5 在背景上方，节点下方
     * viewBox 可以省略，因为我们用百分比坐标
     */
    <svg
      className="cc-holo-lines"
      style={{ position: "fixed", inset: 0, width: "100%", height: "100%", zIndex: 5 }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {lines}
    </svg>
  );
}
