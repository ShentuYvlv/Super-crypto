"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { OrderbookDepthPanel } from "@/components/charts/OrderbookDepthPanel";
import { SlippageCurve } from "@/components/charts/SlippageCurve";
import { EmptyState } from "@/components/EmptyState";
import { SymbolScoreTable } from "@/components/tables/SymbolScoreTable";
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

function OrderbookContent() {
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
        <h2 className="text-4xl font-semibold">Orderbook</h2>
        <p className="mt-2 text-sm text-muted">Depth and slippage are first-class inputs, not report footnotes.</p>
      </div>
      <Card className="p-5">
        {list.data.length === 0 ? (
          <EmptyState title="No symbol list" description="当前没有 symbol / orderbook 数据。" />
        ) : (
          <SymbolScoreTable data={list.data} onRowClick={(row) => router.push(`/orderbook?symbol=${encodeURIComponent(row.symbol)}`)} />
        )}
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Depth Snapshot</h3>
          {detail.data.orderbook_depth.length === 0 ? (
            <EmptyState title="No depth snapshot" description="没有盘口快照时，这个页面不会假装有流动性证据。" />
          ) : (
            <OrderbookDepthPanel rows={detail.data.orderbook_depth} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Slippage Curve</h3>
          {detail.data.latest_orderbook.slippage_bps_sell ? (
            <SlippageCurve slippage={detail.data.latest_orderbook.slippage_bps_sell} />
          ) : (
            <EmptyState title="No slippage estimate" description="当前币种没有可用的盘口滑点估算。" />
          )}
        </Card>
      </div>
    </div>
  );
}

export default function OrderbookPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading orderbook...</div>}>
      <OrderbookContent />
    </Suspense>
  );
}
