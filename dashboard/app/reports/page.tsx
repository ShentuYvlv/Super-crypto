"use client";

import { EmptyState } from "@/components/EmptyState";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { ReportArtifact } from "@/types/api";

export default function ReportsPage() {
  const { data } = useApi<ReportArtifact[]>("/api/reports", []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">Reports</h2>
        <p className="mt-2 text-sm text-muted">Markdown, HTML, CSV, and other artifacts are linked from one place.</p>
      </div>
      {data.length === 0 ? (
        <EmptyState title="No report artifact" description="当前还没有生成本地报告文件。" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {data.map((report) => (
            <Card key={`${report.path}-${report.hash}`} className="p-5">
              <p className="text-sm text-muted">{report.report_type.toUpperCase()}</p>
              <p className="mt-2 text-lg font-semibold">{report.experiment_id ?? "unscoped artifact"}</p>
              <p className="mt-1 text-sm text-muted">
                {report.strategy ?? "-"} · {report.split ?? "-"}
              </p>
              <p className="mt-2 break-all text-xs text-muted">{report.path}</p>
              {report.url ? (
                <a className="mt-4 inline-flex text-sm text-accent" href={report.url}>
                  Open artifact
                </a>
              ) : (
                <p className="mt-4 text-sm text-muted">Artifact URL unavailable</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
