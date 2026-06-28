"use client";

import { EmptyState } from "@/components/EmptyState";
import { DataQualityTable } from "@/components/tables/DataQualityTable";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { DataQualityRow } from "@/types/api";

export default function DataQualityPage() {
  const { data } = useApi<DataQualityRow[]>("/api/data-quality", []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">数据质量</h2>
        <p className="mt-2 text-sm text-muted">这里集中展示缺失、过期、阻塞和缓存健康状态。</p>
      </div>
      <Card className="p-5">
        {data.length === 0 ? (
          <EmptyState title="暂无数据质量快照" description="当前没有生成数据源健康数据。" />
        ) : (
          <DataQualityTable data={data} />
        )}
      </Card>
    </div>
  );
}
