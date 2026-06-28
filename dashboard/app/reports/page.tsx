"use client";

import { EmptyState } from "@/components/EmptyState";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { displayReportType, displayText } from "@/lib/display";
import type { ReportArtifact } from "@/types/api";

export default function ReportsPage() {
  const { data } = useApi<ReportArtifact[]>("/api/reports", []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">报告</h2>
        <p className="mt-2 text-sm text-muted">统一查看 Markdown、HTML、CSV 和其他实验产物。</p>
      </div>
      {data.length === 0 ? (
        <EmptyState title="暂无报告产物" description="当前还没有生成本地报告文件。" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {data.map((report) => (
            <Card key={`${report.path}-${report.hash}`} className="p-5">
              <p className="text-sm text-muted">{displayReportType(report.report_type)}</p>
              <p className="mt-2 text-lg font-semibold">{report.experiment_id ?? "未关联实验的产物"}</p>
              <p className="mt-1 text-sm text-muted">
                {report.strategy ?? "-"} · {displayText(report.split)}
              </p>
              <p className="mt-2 break-all text-xs text-muted">{report.path}</p>
              {report.url ? (
                <a className="mt-4 inline-flex text-sm text-accent" href={report.url}>
                  打开产物
                </a>
              ) : (
                <p className="mt-4 text-sm text-muted">产物链接不可用</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
