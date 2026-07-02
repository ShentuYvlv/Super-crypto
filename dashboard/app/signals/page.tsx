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
import { displayField, displayStatus, localizeValue } from "@/lib/display";
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
        <h2 className="text-4xl font-semibold">信号</h2>
        <p className="mt-2 text-sm text-muted">置信度是结构化评分，不是收益承诺。</p>
      </div>
      <Card className="p-5">
        {list.data.length === 0 ? (
          <EmptyState title="暂无信号" description="当前没有落库信号，这说明系统没有强行凑信号。" />
        ) : (
          <SignalTable data={list.data} onRowClick={(row) => router.push(`/signals?signal=${encodeURIComponent(row.signal_id)}`)} />
        )}
      </Card>
      {selectedId ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">标的</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.symbol}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">策略</p>
              <p className="mt-3 text-2xl font-semibold text-negative">{detail.data.strategy} 做空</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">置信度</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.confidence * 100).toFixed(0)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">盘口滑点</p>
              <p className="mt-3 text-2xl font-semibold">
                {detail.data.orderbook_slippage_bps == null ? "-" : `${detail.data.orderbook_slippage_bps.toFixed(1)} 基点`}
              </p>
            </Card>
          </div>
          <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">K 线上下文</h3>
              {detail.data.kline_context.length === 0 ? (
                <EmptyState title="暂无 K 线上下文" description="该信号缺少本地 K 线上下文。" />
              ) : (
                <KlinePanel
                  rows={detail.data.kline_context as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>}
                  signalMarker={{
                    signal_id: detail.data.signal_id,
                    signal_time: detail.data.signal_time,
                    side: detail.data.side,
                    confidence: detail.data.confidence,
                    reason: detail.data.reason
                  }}
                />
              )}
            </Card>
            <Card className="p-5">
              <h3 className="mb-4 text-2xl font-semibold">原因与载荷</h3>
              <SignalReasonTags reasons={detail.data.reason} />
              <div className="mt-4 space-y-2 text-sm text-muted">
                <p>数据质量： {displayStatus(detail.data.data_quality)}</p>
                <p>缺失： {detail.data.missing_fields.length ? detail.data.missing_fields.map(displayField).join(", ") : "-"}</p>
                <p>过期： {detail.data.stale_fields.length ? detail.data.stale_fields.map(displayField).join(", ") : "-"}</p>
                <p>
                  价差： {detail.data.orderbook_snapshot.spread_bps == null ? "-" : `${detail.data.orderbook_snapshot.spread_bps.toFixed(2)} 基点`}
                </p>
              </div>
              <pre className="mt-4 overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
                {JSON.stringify(localizeValue(detail.data.webhook_payload), null, 2)}
              </pre>
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">关联交易</h3>
            {detail.data.backtest_trades.length === 0 ? (
              <EmptyState title="暂无回测交易" description="这个信号没有对应回测成交，页面明确展示为空。" />
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
    <Suspense fallback={<div className="text-sm text-muted">正在加载信号...</div>}>
      <SignalsContent />
    </Suspense>
  );
}
