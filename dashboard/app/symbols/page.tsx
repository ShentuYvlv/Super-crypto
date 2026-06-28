"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { KlinePanel } from "@/components/charts/KlinePanel";
import { OrderbookDepthPanel } from "@/components/charts/OrderbookDepthPanel";
import { SlippageCurve } from "@/components/charts/SlippageCurve";
import { EmptyState } from "@/components/EmptyState";
import { SymbolScoreTable } from "@/components/tables/SymbolScoreTable";
import { TradeTable } from "@/components/tables/TradeTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { SymbolDetail, SymbolSummary } from "@/types/api";

const EMPTY_SYMBOL: SymbolDetail = {
  symbol: "",
  manipulation_score: 0,
  score_bucket: "low",
  cycle_count: 0,
  avg_pump_return: 0,
  avg_dump_return: 0,
  median_duration_hours: 0,
  latest_funding: 0,
  oi_change_1h: 0,
  oi_change_6h: 0,
  oi_change_24h: 0,
  quote_volume_24h: 0,
  data_completeness: 0,
  orderbook_depth_status: "partial",
  latest_signal_label: "none",
  trade_count: 0,
  paper_trade_count: 0,
  latest_orderbook: {},
  klines: [],
  cycles: [],
  funding_series: [],
  open_interest_series: [],
  signals: [],
  trades: [],
  paper_trades: [],
  orderbook_depth: []
};

function SymbolsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const list = useApi<SymbolSummary[]>("/api/symbols", []);
  const selectedSymbol = useMemo(
    () => searchParams.get("symbol") ?? list.data[0]?.symbol ?? "",
    [list.data, searchParams]
  );
  const detail = useApi<SymbolDetail>(
    selectedSymbol ? `/api/symbols/${encodeURIComponent(selectedSymbol)}` : "/api/symbols/__none__",
    EMPTY_SYMBOL
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">Symbols</h2>
        <p className="mt-2 text-sm text-muted">Point-in-time scoreboards for manipulation frequency and tradability.</p>
      </div>
      <Card className="p-5">
        {list.data.length === 0 ? (
          <EmptyState title="No symbol universe" description="当前没有本地 score / ohlcv 数据。" />
        ) : (
          <SymbolScoreTable data={list.data} onRowClick={(row) => router.push(`/symbols?symbol=${encodeURIComponent(row.symbol)}`)} />
        )}
      </Card>
      {selectedSymbol ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">Score</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.manipulation_score.toFixed(1)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Cycles</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.cycle_count}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Funding</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.latest_funding * 100).toFixed(2)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">OI 24h</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.oi_change_24h * 100).toFixed(1)}%</p>
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">Symbol Detail</h3>
            {detail.data.klines.length === 0 ? (
              <EmptyState title="No symbol kline" description="当前币种没有本地 K 线，无法展示 detail。" />
            ) : (
              <KlinePanel rows={detail.data.klines as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>} />
            )}
          </Card>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">Orderbook Depth</h3>
              {detail.data.orderbook_depth.length === 0 ? (
                <EmptyState title="No orderbook snapshot" description="没有盘口快照时，信号可信度会下降。" />
              ) : (
                <OrderbookDepthPanel rows={detail.data.orderbook_depth} />
              )}
            </Card>
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">Slippage Curve</h3>
              {detail.data.latest_orderbook.slippage_bps_sell ? (
                <SlippageCurve slippage={detail.data.latest_orderbook.slippage_bps_sell} />
              ) : (
                <EmptyState title="No slippage curve" description="当前币种没有可用的滑点估算。" />
              )}
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">Trades</h3>
            {detail.data.trades.length === 0 ? (
              <EmptyState title="No historical trades" description="当前币种没有回测交易记录。" />
            ) : (
              <TradeTable data={detail.data.trades} />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default function SymbolsPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading symbols...</div>}>
      <SymbolsContent />
    </Suspense>
  );
}
