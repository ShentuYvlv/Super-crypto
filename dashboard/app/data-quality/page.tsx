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
        <h2 className="text-4xl font-semibold">Data Quality</h2>
        <p className="mt-2 text-sm text-muted">Missing, stale, blocked, and cache health are surfaced here on purpose.</p>
      </div>
      <Card className="p-5">
        {data.length === 0 ? (
          <EmptyState title="No data quality snapshot" description="当前没有生成 source health 数据。" />
        ) : (
          <DataQualityTable data={data} />
        )}
      </Card>
    </div>
  );
}
