"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { KlinePanel, type TradeChartMarker } from "@/components/charts/KlinePanel";
import { EmptyState } from "@/components/EmptyState";
import { TradeTable } from "@/components/tables/TradeTable";
import { EMPTY_TRADE_DETAIL, TradeDetailPanel } from "@/components/trades/TradeDetailPanel";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Trade, TradeDetail } from "@/types/api";

type CandleRow = {
  open_time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

type SymbolKlinePayload = {
  klines: CandleRow[];
};

function tradeToMarker(trade: Trade): TradeChartMarker {
  return {
    trade_id: trade.trade_id,
    side: trade.side,
    entry_time: trade.entry_time,
    exit_time: trade.exit_time,
    entry_price: trade.entry_price,
    exit_price: trade.exit_price,
    net_return: trade.net_return,
    gross_return: trade.gross_return,
    fee_cost: trade.fee_cost,
    slippage_cost: trade.slippage_cost,
    funding_cost: trade.funding_cost
  };
}

function TradesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const trades = useApi<Trade[]>("/api/trades?source=all", []);
  const symbols = useMemo(
    () => Array.from(new Set(trades.data.map((trade) => trade.symbol))).sort(),
    [trades.data]
  );
  const selectedTradeId = useMemo(
    () => searchParams.get("trade") ?? trades.data[0]?.trade_id ?? "",
    [searchParams, trades.data]
  );
  const selectedTrade = useMemo(
    () => trades.data.find((trade) => trade.trade_id === selectedTradeId) ?? trades.data[0],
    [selectedTradeId, trades.data]
  );
  const selectedSymbol = searchParams.get("symbol") ?? selectedTrade?.symbol ?? symbols[0] ?? "";
  const symbolTrades = useMemo(
    () => trades.data.filter((trade) => trade.symbol === selectedSymbol),
    [selectedSymbol, trades.data]
  );
  const symbolKlines = useApi<SymbolKlinePayload>(
    selectedSymbol ? `/api/symbols/${encodeURIComponent(selectedSymbol)}` : "/api/symbols/__none__",
    { klines: [] }
  );
  const detail = useApi<TradeDetail>(
    selectedTradeId ? `/api/trades/${encodeURIComponent(selectedTradeId)}` : "/api/trades/__none__",
    EMPTY_TRADE_DETAIL
  );
  const markers = useMemo(() => symbolTrades.map(tradeToMarker), [symbolTrades]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">交易</h2>
        <p className="mt-2 text-sm text-muted">这里展示的净收益均已扣除手续费、滑点和资金费。</p>
      </div>
      <Card className="p-5">
        <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h3 className="text-2xl font-semibold">全部交易 K 线</h3>
            <p className="mt-1 text-sm text-muted">
              当前展示 {selectedSymbol || "-"} 的全部交易；红色为开空，绿色/红色为平仓盈亏。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {symbols.map((symbol) => (
              <button
                key={symbol}
                type="button"
                onClick={() => router.push(`/trades?symbol=${encodeURIComponent(symbol)}`)}
                className={`rounded-md border px-3 py-2 text-sm transition ${
                  symbol === selectedSymbol
                    ? "border-accent bg-accent text-black"
                    : "border-border bg-surface2 text-muted hover:text-text"
                }`}
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>
        {selectedSymbol && symbolKlines.data.klines.length > 0 ? (
          <KlinePanel
            rows={symbolKlines.data.klines}
            tradeMarkers={markers}
            activeTradeId={selectedTradeId}
            height={420}
          />
        ) : (
          <EmptyState title="暂无 K 线" description="当前标的缺少本地 K 线，无法绘制全部交易。" />
        )}
      </Card>
      <Card className="p-5">
        {trades.data.length === 0 ? (
          <EmptyState title="暂无交易记录" description="当前没有回测或模拟交易记录。" />
        ) : (
          <TradeTable
            data={trades.data}
            activeTradeId={selectedTradeId}
            onRowClick={(row) =>
              router.push(`/trades?symbol=${encodeURIComponent(row.symbol)}&trade=${encodeURIComponent(row.trade_id)}`)
            }
          />
        )}
      </Card>
      {selectedTradeId ? <TradeDetailPanel detail={detail.data} loading={detail.loading} /> : null}
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
