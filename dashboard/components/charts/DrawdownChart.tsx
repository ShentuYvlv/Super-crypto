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
          grid: { left: 64, right: 28, top: 36, bottom: 52 },
        xAxis: {
          type: "category",
          data: points.map((point) => point.exit_time?.slice(5, 16) ?? ""),
          name: "平仓时间",
          nameLocation: "middle",
          nameGap: 32
        },
        yAxis: {
          type: "value",
          name: "回撤",
          nameGap: 42,
          max: 0,
          axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(0)}%` },
          splitLine: { lineStyle: { color: "#1e2329" } }
        },
        series: [
          {
            type: "line",
            name: "回撤",
            data: points.map((point) => point.drawdown ?? 0),
            lineStyle: { color: "#f6465d", width: 2 },
            areaStyle: { color: "rgba(246, 70, 93, 0.08)" }
          }
        ],
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: number) => `${(value * 100).toFixed(2)}%`
        }
      }}
    />
  );
}
