"use client";

import ReactECharts from "echarts-for-react";

export function SlippageCurve({ slippage }: { slippage: Record<string, number> }) {
  const notionals = Object.keys(slippage);
  return (
    <ReactECharts
      style={{ height: 260 }}
      option={{
        backgroundColor: "transparent",
        xAxis: { type: "category", data: notionals },
        yAxis: { type: "value" },
        series: [
          {
            type: "bar",
            data: notionals.map((key) => Math.abs(slippage[key])),
            itemStyle: { color: "#fcd535", borderRadius: [4, 4, 0, 0] }
          }
        ]
      }}
    />
  );
}
