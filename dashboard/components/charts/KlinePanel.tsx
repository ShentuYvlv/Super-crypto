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
  quantity_base?: number;
  entry_notional_usdt?: number;
  exit_notional_usdt?: number;
  pnl_usdt?: number;
  net_return: number;
  gross_return?: number;
  fee_cost?: number;
  slippage_cost?: number;
  funding_cost?: number;
  notional_usdt?: number;
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
  const pnlUsdt = marker.pnl_usdt ?? (marker.notional_usdt ? marker.notional_usdt * marker.net_return : null);
  const pnlClass = marker.net_return >= 0 ? "text-positive" : "text-negative";
  const quantity = marker.quantity_base === undefined ? "-" : formatQuantity(marker.quantity_base);
  const notional = marker.notional_usdt ?? marker.entry_notional_usdt;
  return `
    <div class="rounded-lg border border-border bg-[#0b0e11]/95 p-3 shadow-panel">
      <div class="mb-2 flex items-center justify-between gap-4">
        <span class="text-xs text-muted">开平仓</span>
        <span class="font-mono text-xs text-accent">${marker.trade_id.slice(0, 10)}</span>
      </div>
      <div class="grid gap-1.5 text-xs text-text">
        <div>开仓卖出：<span class="font-mono">${quantity}</span> @ <span class="font-mono">${marker.entry_price.toFixed(6)}</span></div>
        <div>平仓买入：<span class="font-mono">${quantity}</span> @ <span class="font-mono">${marker.exit_price.toFixed(6)}</span></div>
        <div>名义本金：<span class="font-mono">${notional === undefined ? "-" : formatUsd(notional)}</span></div>
        <div>PNL：<span class="font-mono ${pnlClass}">${pnlUsdt === null ? "-" : formatUsd(pnlUsdt)} / ${(marker.net_return * 100).toFixed(2)}%</span></div>
      </div>
    </div>
  `;
}

export function KlinePanel({
  rows,
  tradeMarker,
  tradeMarkers,
  activeTradeId,
  height = 320
}: {
  rows: CandleRow[];
  tradeMarker?: TradeChartMarker;
  tradeMarkers?: TradeChartMarker[];
  activeTradeId?: string;
  height?: number;
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
      height
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

    const normalizedMarkers = tradeMarkers ?? (tradeMarker ? [tradeMarker] : []);
    const markerLookup: Array<{ time: UTCTimestamp; marker: TradeChartMarker }> = [];
    if (normalizedMarkers.length > 0) {
      const markers: SeriesMarker<UTCTimestamp>[] = normalizedMarkers.flatMap((marker) => {
        const entryTime = nearestCandleTime(toChartTime(marker.entry_time), candleTimes);
        const exitTime = nearestCandleTime(toChartTime(marker.exit_time), candleTimes);
        const active = marker.trade_id === activeTradeId;
        markerLookup.push({ time: entryTime, marker }, { time: exitTime, marker });
        return [
          {
            time: entryTime,
            position: "aboveBar",
            shape: "arrowDown",
            color: active ? "#fcd535" : "#f6465d",
            text: active ? "开空 *" : "开空",
            size: active ? 2.1 : 1.4
          },
          {
            time: exitTime,
            position: "belowBar",
            shape: "arrowUp",
            color: marker.net_return >= 0 ? "#0ecb81" : "#f6465d",
            text: `平仓 ${(marker.net_return * 100).toFixed(1)}%`,
            size: active ? 2.1 : 1.4
          }
        ];
      });
      series.setMarkers(markers);
    }

    chart.subscribeCrosshairMove((param) => {
      if (normalizedMarkers.length === 0 || !param.point || param.time === undefined) {
        tooltip.style.display = "none";
        return;
      }
      const hoveredTime = Number(param.time);
      const nearestMarker = markerLookup.find((item) => Math.abs(Number(item.time) - hoveredTime) <= 1800);
      const nearTradeMarker = nearestMarker !== undefined;
      if (!nearTradeMarker) {
        tooltip.style.display = "none";
        return;
      }
      tooltip.innerHTML = markerTooltip(nearestMarker.marker);
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
  }, [rows, tradeMarker, tradeMarkers, activeTradeId, height]);

  return (
    <div className="relative w-full" style={{ height }}>
      <div ref={ref} className="absolute inset-0" />
      <span className="pointer-events-none absolute right-3 top-3 rounded border border-border bg-canvas/80 px-2 py-1 text-xs text-muted">
        价格 USDT
      </span>
      <span className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded border border-border bg-canvas/80 px-2 py-1 text-xs text-muted">
        时间 UTC
      </span>
    </div>
  );
}
