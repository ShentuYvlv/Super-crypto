"use client";

import ReactECharts from "echarts-for-react";

export function EquityChart({
  points
}: {
  points: Array<{ exit_time?: string; equity?: number }>;
}) {
  return (
    <ReactECharts
      style={{ height: 280 }}
      option={{
        backgroundColor: "transparent",
        grid: { left: 24, right: 24, top: 24, bottom: 24 },
        xAxis: {
          type: "category",
          data: points.map((point) => point.exit_time?.slice(5, 16) ?? ""),
          axisLine: { lineStyle: { color: "#2b3139" } }
        },
        yAxis: {
          type: "value",
          axisLine: { show: false },
          splitLine: { lineStyle: { color: "#1e2329" } }
        },
        series: [
          {
            type: "line",
            data: points.map((point) => point.equity ?? 0),
            smooth: true,
            lineStyle: { color: "#fcd535", width: 2 },
            areaStyle: { color: "rgba(252, 213, 53, 0.08)" }
          }
        ],
        tooltip: { trigger: "axis" }
      }}
    />
  );
}
