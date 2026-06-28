"use client";

import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/EmptyState";
import { ExperimentTable } from "@/components/tables/ExperimentTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { Experiment } from "@/types/api";

export default function ExperimentsPage() {
  const router = useRouter();
  const { data } = useApi<Experiment[]>("/api/experiments", []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">实验</h2>
        <p className="mt-2 text-sm text-muted">
          先比较配置哈希、成本压力、交易数和拒绝原因，再判断回测是否可信。
        </p>
      </div>
      <Card className="p-5">
        {data.length === 0 ? (
          <EmptyState title="暂无实验运行" description="先跑流水线，实验表会自动读取 SQLite 中的最新结果。" />
        ) : (
          <ExperimentTable
            data={data}
            onRowClick={(row) => router.push(`/backtest?experiment=${encodeURIComponent(row.experiment_id)}`)}
          />
        )}
      </Card>
    </div>
  );
}
