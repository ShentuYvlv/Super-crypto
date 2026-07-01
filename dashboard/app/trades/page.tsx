"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/EmptyState";
import { TradeTable } from "@/components/tables/TradeTable";
import { EMPTY_TRADE_DETAIL, TradeDetailPanel } from "@/components/trades/TradeDetailPanel";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Trade, TradeDetail } from "@/types/api";

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
    EMPTY_TRADE_DETAIL
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
          <TradeTable
            data={trades.data}
            activeTradeId={selectedTradeId}
            onRowClick={(row) => router.push(`/trades?trade=${encodeURIComponent(row.trade_id)}`)}
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
