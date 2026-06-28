"use client";

import { useEffect, useRef } from "react";
import { createChart, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";

type CandleRow = {
  open_time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export function KlinePanel({ rows }: { rows: CandleRow[] }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || rows.length === 0) {
      return;
    }
    const chart = createChart(ref.current, {
      layout: {
        background: { color: "#161a20" },
        textColor: "#8a929e"
      },
      grid: {
        vertLines: { color: "#1e2329" },
        horzLines: { color: "#1e2329" }
      },
      width: ref.current.clientWidth,
      height: 320
    });
    const series = chart.addCandlestickSeries({
      upColor: "#0ecb81",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#0ecb81",
      wickDownColor: "#f6465d"
    }) as ISeriesApi<"Candlestick">;
    series.setData(
      rows.map((row) => ({
        time: (row.open_time ? Math.floor(new Date(row.open_time).getTime() / 1000) : 0) as UTCTimestamp,
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close
      }))
    );
    return () => chart.remove();
  }, [rows]);

  return <div ref={ref} className="h-80 w-full" />;
}
