"use client";

import ReactECharts from "echarts-for-react";

export function DrawdownChart({
  points
}: {
  points: Array<{ exit_time?: string; drawdown?: number }>;
}) {
  return (
    <ReactECharts
      style={{ height: 220 }}
      option={{
        backgroundColor: "transparent",
        grid: { left: 24, right: 24, top: 24, bottom: 24 },
        xAxis: { type: "category", data: points.map((point) => point.exit_time?.slice(5, 16) ?? "") },
        yAxis: { type: "value", splitLine: { lineStyle: { color: "#1e2329" } } },
        series: [
          {
            type: "line",
            data: points.map((point) => point.drawdown ?? 0),
            lineStyle: { color: "#f6465d", width: 2 },
            areaStyle: { color: "rgba(246, 70, 93, 0.08)" }
          }
        ]
      }}
    />
  );
}
