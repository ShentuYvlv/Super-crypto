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
        grid: { left: 64, right: 28, top: 36, bottom: 52 },
        xAxis: {
          type: "category",
          data: points.map((point) => point.exit_time?.slice(5, 16) ?? ""),
          name: "平仓时间",
          nameLocation: "middle",
          nameGap: 32,
          axisLine: { lineStyle: { color: "#2b3139" } }
        },
        yAxis: {
          type: "value",
          name: "累计权益",
          nameGap: 42,
          min: (value: { min: number }) => Math.min(0, Math.floor(value.min * 10) / 10),
          axisLabel: {
            formatter: (value: number) => `${((value - 1) * 100).toFixed(0)}%`
          },
          axisLine: { show: false },
          splitLine: { lineStyle: { color: "#1e2329" } }
        },
        series: [
          {
            type: "line",
            data: points.map((point) => point.equity ?? 0),
            name: "累计权益",
            smooth: true,
            lineStyle: { color: "#fcd535", width: 2 },
            areaStyle: { color: "rgba(252, 213, 53, 0.08)" }
          }
        ],
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: number) => `${((value - 1) * 100).toFixed(2)}%`
        }
      }}
    />
  );
}
