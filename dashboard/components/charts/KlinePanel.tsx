"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  type ISeriesApi,
  type SeriesMarker,
  type UTCTimestamp
} from "lightweight-charts";

type CandleRow = {
  open_time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type TradeChartMarker = {
  trade_id: string;
  side: "SHORT";
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity_base: number;
  entry_notional_usdt: number;
  exit_notional_usdt: number;
  pnl_usdt: number;
  net_return: number;
  notional_usdt: number;
};

function toChartTime(value: string | undefined): UTCTimestamp {
  return (value ? Math.floor(new Date(value).getTime() / 1000) : 0) as UTCTimestamp;
}

function nearestCandleTime(target: UTCTimestamp, candidates: UTCTimestamp[]): UTCTimestamp {
  if (candidates.length === 0) {
    return target;
  }
  return candidates.reduce((nearest, current) =>
    Math.abs(Number(current) - Number(target)) < Math.abs(Number(nearest) - Number(target))
      ? current
      : nearest
  );
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function formatQuantity(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6
  }).format(value);
}

function markerTooltip(marker: TradeChartMarker): string {
  const pnlClass = marker.pnl_usdt >= 0 ? "text-positive" : "text-negative";
  return `
    <div class="rounded-lg border border-border bg-[#0b0e11]/95 p-3 shadow-panel">
      <div class="mb-2 flex items-center justify-between gap-4">
        <span class="text-xs text-muted">完整开平仓</span>
        <span class="font-mono text-xs text-accent">${marker.trade_id.slice(0, 10)}</span>
      </div>
      <div class="grid gap-1.5 text-xs text-text">
        <div>开仓卖出：<span class="font-mono">${formatQuantity(marker.quantity_base)}</span> @ <span class="font-mono">${marker.entry_price.toFixed(6)}</span></div>
        <div>平仓买入：<span class="font-mono">${formatQuantity(marker.quantity_base)}</span> @ <span class="font-mono">${marker.exit_price.toFixed(6)}</span></div>
        <div>名义本金：<span class="font-mono">${formatUsd(marker.notional_usdt)}</span></div>
        <div>PNL：<span class="font-mono ${pnlClass}">${formatUsd(marker.pnl_usdt)} / ${(marker.net_return * 100).toFixed(2)}%</span></div>
      </div>
    </div>
  `;
}

export function KlinePanel({
  rows,
  tradeMarker
}: {
  rows: CandleRow[];
  tradeMarker?: TradeChartMarker;
}) {
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
    const candleData = rows.map((row) => ({
      time: toChartTime(row.open_time),
      open: row.open,
      high: row.high,
      low: row.low,
      close: row.close
    }));
    const candleTimes = candleData.map((row) => row.time);
    const series = chart.addCandlestickSeries({
      upColor: "#0ecb81",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#0ecb81",
      wickDownColor: "#f6465d"
    }) as ISeriesApi<"Candlestick">;
    series.setData(candleData);

    const tooltip = document.createElement("div");
    tooltip.style.position = "absolute";
    tooltip.style.display = "none";
    tooltip.style.pointerEvents = "none";
    tooltip.style.zIndex = "20";
    tooltip.style.minWidth = "260px";
    ref.current.appendChild(tooltip);

    let markerTimes: UTCTimestamp[] = [];
    if (tradeMarker) {
      const entryTime = nearestCandleTime(toChartTime(tradeMarker.entry_time), candleTimes);
      const exitTime = nearestCandleTime(toChartTime(tradeMarker.exit_time), candleTimes);
      markerTimes = [entryTime, exitTime];
      const markers: SeriesMarker<UTCTimestamp>[] = [
        {
          time: entryTime,
          position: "aboveBar",
          shape: "arrowDown",
          color: "#f6465d",
          text: "开仓卖出",
          size: 1.6
        },
        {
          time: exitTime,
          position: "belowBar",
          shape: "arrowUp",
          color: "#0ecb81",
          text: "平仓买入",
          size: 1.6
        }
      ];
      series.setMarkers(markers);
    }

    chart.subscribeCrosshairMove((param) => {
      if (!tradeMarker || !param.point || param.time === undefined) {
        tooltip.style.display = "none";
        return;
      }
      const hoveredTime = Number(param.time);
      const nearTradeMarker = markerTimes.some((time) => Math.abs(Number(time) - hoveredTime) <= 60);
      if (!nearTradeMarker) {
        tooltip.style.display = "none";
        return;
      }
      tooltip.innerHTML = markerTooltip(tradeMarker);
      tooltip.style.display = "block";
      const left = Math.min(param.point.x + 16, ref.current!.clientWidth - 280);
      const top = Math.max(param.point.y - 96, 12);
      tooltip.style.left = `${Math.max(left, 12)}px`;
      tooltip.style.top = `${top}px`;
    });

    return () => {
      tooltip.remove();
      chart.remove();
    };
  }, [rows, tradeMarker]);

  return <div ref={ref} className="relative h-80 w-full" />;
}
