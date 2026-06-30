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
import { displayText } from "@/lib/display";
import type { DataQualityRow, SymbolDetail, SymbolSummary } from "@/types/api";

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
  orderbook_depth: [],
  data_sources: []
};

function SourceHealthGrid({ rows }: { rows: DataQualityRow[] }) {
  if (rows.length === 0) {
    return <EmptyState title="暂无数据源明细" description="当前标的还没有生成 ingest 产物。" />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-separate border-spacing-0 text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="border-b border-border px-3 py-3">数据源</th>
            <th className="border-b border-border px-3 py-3">状态</th>
            <th className="border-b border-border px-3 py-3">文件</th>
            <th className="border-b border-border px-3 py-3">新鲜度</th>
            <th className="border-b border-border px-3 py-3">最新时间</th>
            <th className="border-b border-border px-3 py-3">备注</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.source_name}-${row.path}`} className="border-b border-border">
              <td className="border-b border-border px-3 py-3 font-medium text-text">{displayText(row.source_name)}</td>
              <td className="border-b border-border px-3 py-3">
                <span className={row.status === "healthy" ? "text-positive" : "text-warning"}>
                  {displayText(row.status)}
                </span>
              </td>
              <td className="border-b border-border px-3 py-3 font-mono">{row.file_count}</td>
              <td className="border-b border-border px-3 py-3">{row.freshness ?? "-"}</td>
              <td className="border-b border-border px-3 py-3 font-mono text-xs">
                {row.latest_timestamp ? String(row.latest_timestamp).slice(0, 19) : "-"}
              </td>
              <td className="border-b border-border px-3 py-3 text-muted">
                {row.notes?.length ? row.notes.map(displayText).join(", ") : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
        <h2 className="text-4xl font-semibold">数据</h2>
        <p className="mt-2 text-sm text-muted">按标的集中查看 K 线、Funding、OI、盘口、CoinGlass 缓存和策略证据。</p>
      </div>
      <Card className="p-5">
        {list.data.length === 0 ? (
          <EmptyState title="暂无标的池" description="当前没有本地评分或 K 线数据。" />
        ) : (
          <SymbolScoreTable data={list.data} onRowClick={(row) => router.push(`/symbols?symbol=${encodeURIComponent(row.symbol)}`)} />
        )}
      </Card>
      {selectedSymbol ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-sm text-muted">评分</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.manipulation_score.toFixed(1)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">周期数</p>
              <p className="mt-3 text-2xl font-semibold">{detail.data.cycle_count}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">资金费</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.latest_funding * 100).toFixed(2)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">持仓量 24 小时</p>
              <p className="mt-3 text-2xl font-semibold">{(detail.data.oi_change_24h * 100).toFixed(1)}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted">数据源</p>
              <p className="mt-3 text-2xl font-semibold">
                {detail.data.data_source_summary?.healthy_sources ?? 0}/{detail.data.data_source_summary?.total_sources ?? 0}
              </p>
            </Card>
          </div>
          <Card className="p-5">
            <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
              <div>
                <h3 className="text-2xl font-semibold">Ingest 数据</h3>
                <p className="mt-1 text-sm text-muted">
                  覆盖率 {(detail.data.data_completeness * 100).toFixed(0)}% · 最新数据 {detail.data.data_source_summary?.latest_timestamp ? String(detail.data.data_source_summary.latest_timestamp).slice(0, 19) : "-"}
                </p>
              </div>
              <p className="text-sm text-muted">{displayText(detail.data.data_source_summary?.status ?? "partial")}</p>
            </div>
            <SourceHealthGrid rows={detail.data.data_sources ?? []} />
          </Card>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">标的详情</h3>
            {detail.data.klines.length === 0 ? (
              <EmptyState title="暂无标的 K 线" description="当前币种没有本地 K 线，无法展示详情。" />
            ) : (
              <KlinePanel rows={detail.data.klines as Array<{ open_time?: string; open: number; high: number; low: number; close: number }>} />
            )}
          </Card>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className="p-5">
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                  <h3 className="text-2xl font-semibold">盘口深度</h3>
                  <p className="mt-1 text-sm text-muted">
                    状态：{detail.data.orderbook_depth_status} · 买卖盘不平衡：
                    {detail.data.latest_orderbook.imbalance?.toFixed(2) ?? "-"}
                  </p>
                </div>
                <p className="font-mono text-sm text-muted">
                  Spread {detail.data.latest_orderbook.spread_bps?.toFixed(2) ?? "-"} bps
                </p>
              </div>
              {detail.data.orderbook_depth.length === 0 ? (
                <EmptyState title="暂无盘口快照" description="没有盘口快照时，信号可信度会下降。" />
              ) : (
                <OrderbookDepthPanel rows={detail.data.orderbook_depth} />
              )}
            </Card>
            <Card className="p-5">
              <div className="mb-4">
                <h3 className="text-2xl font-semibold">滑点曲线</h3>
                <p className="mt-1 text-sm text-muted">用于判断该标的能不能承受回测里的单笔名义本金。</p>
              </div>
              {detail.data.latest_orderbook.slippage_bps_sell ? (
                <SlippageCurve slippage={detail.data.latest_orderbook.slippage_bps_sell} />
              ) : (
                <EmptyState title="暂无滑点曲线" description="当前币种没有可用的滑点估算。" />
              )}
            </Card>
          </div>
          <Card className="p-5">
            <h3 className="mb-4 text-2xl font-semibold">交易</h3>
            {detail.data.trades.length === 0 ? (
              <EmptyState title="暂无历史交易" description="当前币种没有回测交易记录。" />
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
    <Suspense fallback={<div className="text-sm text-muted">正在加载标的...</div>}>
      <SymbolsContent />
    </Suspense>
  );
}
