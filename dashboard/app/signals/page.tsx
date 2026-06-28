"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { KlinePanel } from "@/components/charts/KlinePanel";
import { EmptyState } from "@/components/EmptyState";
import { SignalReasonTags } from "@/components/SignalReasonTags";
import { SignalTable } from "@/components/tables/SignalTable";
import { TradeTable } from "@/components/tables/TradeTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Signal, SignalDetail } from "@/types/api";

const EMPTY_DETAIL: SignalDetail = {
  signal_id: "",
  symbol: "",
  strategy: "V4A",
  side: "SHORT",
  signal_time: "",
  decision_time: "",
  data_cutoff_time: "",
  entry_reference: "",
  stop_loss: 0,
  trailing_stop: 0,
  confidence: 0,
  manipulation_score_bucket: "low",
  reason: [],
  data_quality: "partial",
  missing_fields: [],
  stale_fields: [],
  status: "open",
  backtest_trades: [],
  kline_context: [],
  funding_series: [],
  open_interest_series: [],
  orderbook_snapshot: {},
  webhook_payload: {}
};

function SignalsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const list = useApi<Signal[]>("/api/signals", []);
  const selectedId = useMemo(
    () => searchParams.get("signal") ?? list.data[0]?.signal_id ?? "",
    [list.data, searchParams]
  );
  const detail = useApi<SignalDetail>(
    selectedId ? `/api/signals/${encodeURIComponent(selectedId)}` : "/api/signals/__none__",
    EMPTY_DETAIL
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">Signals</h2>
        <p className="mt-2 text-sm text-muted">Confidence is a structured score, not a profit promise.</p>
      </div>
      <Card className="p-5">
        {list.data.length === 0 ? (
          <EmptyState title="No signal yet" description="当前没有落库信号，这说明系统没有强行凑信号。" />
        ) : (
          <SignalTable data={list.data} onRowClick={(row) => router.push(`/signals?signal=${encodeURIComponent(row.signal_id)}`)} />
        )}
      </Card>
      {selectedId ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">Symbol</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.symbol}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Strategy</p>
              <p className="mt-3 text-2xl font-semibold text-negative">{detail.data.strategy} SHORT</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Confidence</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.confidence * 100).toFixed(0)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">Orderbook Slip</p>
              <p className="mt-3 text-2xl font-semibold">
                {detail.data.orderbook_slippage_bps == null ? "-" : `${detail.data.orderbook_slippage_bps.toFixed(1)}bps`}
              </p>
            </Card>
          </div>
          <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">Kline Context</h3>
              {detail.data.kline_context.length === 0 ? (
                <EmptyState title="No kline context" description="该信号缺少本地 K 线上下文。" />
              ) : (
                <KlinePanel rows={detail.data.kline_context as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>} />
              )}
            </Card>
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">Reason & Payload</h3>
              <SignalReasonTags reasons={detail.data.reason} />
              <div className="mt-4 space-y-2 text-sm text-muted">
                <p>Data quality: {detail.data.data_quality}</p>
                <p>Missing: {detail.data.missing_fields.length ? detail.data.missing_fields.join(", ") : "-"}</p>
                <p>Stale: {detail.data.stale_fields.length ? detail.data.stale_fields.join(", ") : "-"}</p>
                <p>
                  Spread: {detail.data.orderbook_snapshot.spread_bps == null ? "-" : `${detail.data.orderbook_snapshot.spread_bps.toFixed(2)}bps`}
                </p>
              </div>
              <pre className="mt-4 overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
                {JSON.stringify(detail.data.webhook_payload, null, 2)}
              </pre>
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">Related Trades</h3>
            {detail.data.backtest_trades.length === 0 ? (
              <EmptyState title="No backtest trade" description="这个信号没有对应回测成交，页面明确展示为空。" />
            ) : (
              <TradeTable data={detail.data.backtest_trades} />
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading signals...</div>}>
      <SignalsContent />
    </Suspense>
  );
}
