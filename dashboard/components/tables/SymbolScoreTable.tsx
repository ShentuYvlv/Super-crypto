"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { displayText } from "@/lib/display";
import type { SymbolSummary } from "@/types/api";

const columnHelper = createColumnHelper<SymbolSummary>();

const columns = [
  columnHelper.accessor("symbol", { header: "标的" }),
  columnHelper.accessor("manipulation_score", { header: "评分" }),
  columnHelper.accessor("score_bucket", {
    header: "分组",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("cycle_count", { header: "周期数" }),
  columnHelper.accessor("median_duration_hours", {
    header: "中位小时",
    cell: ({ getValue }) => getValue().toFixed(1)
  }),
  columnHelper.accessor("oi_change_1h", {
    header: "持仓量 1 小时",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("oi_change_6h", {
    header: "持仓量 6 小时",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("oi_change_24h", {
    header: "持仓量 24 小时",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("latest_funding", {
    header: "资金费",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(2)}%`
  }),
  columnHelper.accessor("data_completeness", {
    header: "覆盖率",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("latest_signal_label", {
    header: "最新信号",
    cell: ({ getValue }) => displayText(getValue())
  })
];

export function SymbolScoreTable({
  data,
  onRowClick
}: {
  data: SymbolSummary[];
  onRowClick?: (row: SymbolSummary) => void;
}) {
  return <DataTable data={data} columns={columns} onRowClick={onRowClick} />;
}
