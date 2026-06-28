"use client";

import ReactECharts from "echarts-for-react";

export function OrderbookDepthPanel({
  rows
}: {
  rows: Array<{ price: number; bid: number; ask: number }>;
}) {
  return (
    <ReactECharts
      style={{ height: 280 }}
      option={{
        backgroundColor: "transparent",
        legend: { textStyle: { color: "#8a929e" } },
        xAxis: { type: "category", data: rows.map((row) => row.price.toFixed(4)) },
        yAxis: { type: "value" },
        series: [
          {
            name: "Bid Depth",
            type: "bar",
            data: rows.map((row) => row.bid),
            itemStyle: { color: "#0ecb81" }
          },
          {
            name: "Ask Depth",
            type: "bar",
            data: rows.map((row) => row.ask),
            itemStyle: { color: "#f6465d" }
          }
        ]
      }}
    />
  );
}
