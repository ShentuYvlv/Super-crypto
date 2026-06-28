"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { KlinePanel } from "@/components/charts/KlinePanel";
import { EmptyState } from "@/components/EmptyState";
import { TradeTable } from "@/components/tables/TradeTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Trade, TradeDetail } from "@/types/api";

const EMPTY_TRADE: TradeDetail = {
  trade_id: "",
  signal_id: "",
  symbol: "",
  strategy: "V4A",
  split: "train_validation",
  source: "backtest",
  side: "SHORT",
  entry_time: "",
  entry_price: 0,
  exit_time: "",
  exit_price: 0,
  gross_return: 0,
  fee_cost: 0,
  slippage_cost: 0,
  funding_cost: 0,
  net_return: 0,
  exit_reason: "",
  holding_minutes: 0,
  mae: 0,
  mfe: 0,
  orderbook_snapshot_status: "partial",
  is_top5_trade: false,
  kline_context: []
};

function TradesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const trades = useApi<Trade[]>("/api/trades?source=all", []);
  const selectedTradeId = useMemo(
    () => searchParams.get("trade") ?? trades.data[0]?.trade_id ?? "",
    [searchParams, trades.data]
  );
  const detail = useApi<TradeDetail>(
    selectedTradeId ? `/api/trades/${encodeURIComponent(selectedTradeId)}` : "/api/trades/__none__",
    EMPTY_TRADE
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">Trades</h2>
        <p className="mt-2 text-sm text-muted">Every net return shown here is after fee, slippage, and funding.</p>
      </div>
      <Card className="p-5">
        {trades.data.length === 0 ? (
          <EmptyState title="No trade record" description="当前没有 backtest / paper trade 记录。" />
        ) : (
          <TradeTable data={trades.data} onRowClick={(row) => router.push(`/trades?trade=${encodeURIComponent(row.trade_id)}`)} />
        )}
      </Card>
      {selectedTradeId ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">Source</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.source}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Net Return</p>
              <p className={`mt-3 text-2xl font-semibold ${detail.data.net_return >= 0 ? "text-positive" : "text-negative"}`}>
                {(detail.data.net_return * 100).toFixed(1)}%
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Holding</p>
              <p className="mt-3 text-2xl font-semibold">{Math.round(detail.data.holding_minutes)}m</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Top 5 Trade</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.is_top5_trade ? "Yes" : "No"}</p>
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">Cost Breakdown</h3>
            <div className="grid gap-4 md:grid-cols-4 text-sm">
              <div className="rounded-lg bg-[#11161d] p-4">Gross: {(detail.data.gross_return * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">Fee: {(detail.data.fee_cost * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">Slippage: {(detail.data.slippage_cost * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">Funding: {(detail.data.funding_cost * 100).toFixed(1)}%</div>
            </div>
          </Card>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">Trade Kline Context</h3>
            {detail.data.kline_context.length === 0 ? (
              <EmptyState title="No kline context" description="该交易缺少本地 K 线窗口。" />
            ) : (
              <KlinePanel rows={detail.data.kline_context as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>} />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default function TradesPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading trades...</div>}>
      <TradesContent />
    </Suspense>
  );
}
