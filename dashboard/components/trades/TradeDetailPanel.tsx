"use client";

import { KlinePanel } from "@/components/charts/KlinePanel";
import { EmptyState } from "@/components/EmptyState";
import { Card } from "@/components/ui/card";
import { displayStatus } from "@/lib/display";
import type { TradeDetail } from "@/types/api";

export const EMPTY_TRADE_DETAIL: TradeDetail = {
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

type CandleRow = {
  open_time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function TradeDetailPanel({
  detail,
  loading = false
}: {
  detail: TradeDetail;
  loading?: boolean;
}) {
  if (!detail.trade_id) {
    return (
      <EmptyState
        title="选择一笔交易"
        description="点击实验里的交易行后，这里会显示 K 线上下文和开平仓标记。"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted">交易</p>
          <p className="mt-3 truncate font-mono text-lg font-semibold">{detail.trade_id}</p>
          <p className="mt-2 text-xs text-muted">{loading ? "正在刷新上下文" : detail.symbol}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">净收益</p>
          <p className={`mt-3 text-2xl font-semibold ${detail.net_return >= 0 ? "text-positive" : "text-negative"}`}>
            {pct(detail.net_return)}
          </p>
          <p className="mt-2 text-xs text-muted">{displayStatus(detail.source)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">持仓时长</p>
          <p className="mt-3 text-2xl font-semibold">{Math.round(detail.holding_minutes)} 分钟</p>
          <p className="mt-2 text-xs text-muted">{detail.exit_reason}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">前 5 笔交易</p>
          <p className="mt-3 text-2xl font-semibold">{detail.is_top5_trade ? "是" : "否"}</p>
          <p className="mt-2 text-xs text-muted">用于检查少数交易支配收益</p>
        </Card>
      </div>

      <Card className="p-5">
        <h3 className="mb-4 text-2xl font-semibold">成本拆分</h3>
        <div className="grid gap-4 text-sm md:grid-cols-4">
          <div className="rounded-lg bg-[#11161d] p-4">毛收益：{pct(detail.gross_return)}</div>
          <div className="rounded-lg bg-[#11161d] p-4">手续费：{pct(detail.fee_cost)}</div>
          <div className="rounded-lg bg-[#11161d] p-4">滑点：{pct(detail.slippage_cost)}</div>
          <div className="rounded-lg bg-[#11161d] p-4">资金费：{pct(detail.funding_cost)}</div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-2xl font-semibold">交易 K 线上下文</h3>
            <p className="mt-1 text-sm text-muted">包含入场、出场附近窗口和交易标记。</p>
          </div>
          <p className="text-xs text-muted">图上数量按单笔名义本金估算，PNL 已扣成本。</p>
        </div>
        {detail.kline_context.length === 0 ? (
          <EmptyState title="暂无 K 线上下文" description="该交易缺少本地 K 线窗口。" />
        ) : (
          <KlinePanel rows={detail.kline_context as CandleRow[]} tradeMarker={detail.trade_marker} />
        )}
      </Card>
    </div>
  );
}
