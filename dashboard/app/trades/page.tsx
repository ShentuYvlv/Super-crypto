"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { KlinePanel } from "@/components/charts/KlinePanel";
import { EmptyState } from "@/components/EmptyState";
import { TradeTable } from "@/components/tables/TradeTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { displayStatus } from "@/lib/display";
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
        <h2 className="text-4xl font-semibold">交易</h2>
        <p className="mt-2 text-sm text-muted">这里展示的净收益均已扣除手续费、滑点和资金费。</p>
      </div>
      <Card className="p-5">
        {trades.data.length === 0 ? (
          <EmptyState title="暂无交易记录" description="当前没有回测或模拟交易记录。" />
        ) : (
          <TradeTable data={trades.data} onRowClick={(row) => router.push(`/trades?trade=${encodeURIComponent(row.trade_id)}`)} />
        )}
      </Card>
      {selectedTradeId ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">来源</p>
              <p className="mt-3 text-2xl font-semibold">{displayStatus(detail.data.source)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">净收益</p>
              <p className={`mt-3 text-2xl font-semibold ${detail.data.net_return >= 0 ? "text-positive" : "text-negative"}`}>
                {(detail.data.net_return * 100).toFixed(1)}%
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">持仓时长</p>
              <p className="mt-3 text-2xl font-semibold">{Math.round(detail.data.holding_minutes)} 分钟</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">前 5 笔交易</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.is_top5_trade ? "是" : "否"}</p>
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">成本拆分</h3>
            <div className="grid gap-4 md:grid-cols-4 text-sm">
              <div className="rounded-lg bg-[#11161d] p-4">毛收益： {(detail.data.gross_return * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">手续费： {(detail.data.fee_cost * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">滑点： {(detail.data.slippage_cost * 100).toFixed(1)}%</div>
              <div className="rounded-lg bg-[#11161d] p-4">资金费： {(detail.data.funding_cost * 100).toFixed(1)}%</div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
              <h3 className="text-2xl font-semibold">交易 K 线上下文</h3>
              <p className="text-xs text-muted">图上数量按单笔名义本金估算，PNL 已扣成本。</p>
            </div>
            {detail.data.kline_context.length === 0 ? (
              <EmptyState title="暂无 K 线上下文" description="该交易缺少本地 K 线窗口。" />
            ) : (
              <KlinePanel
                rows={detail.data.kline_context as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>}
                tradeMarker={detail.data.trade_marker}
              />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default function TradesPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">正在加载交易...</div>}>
      <TradesContent />
    </Suspense>
  );
}
