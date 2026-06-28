"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { SymbolSummary } from "@/types/api";

const columnHelper = createColumnHelper<SymbolSummary>();

const columns = [
  columnHelper.accessor("symbol", { header: "Symbol" }),
  columnHelper.accessor("manipulation_score", { header: "Score" }),
  columnHelper.accessor("score_bucket", {
    header: "Bucket",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("cycle_count", { header: "Cycles" }),
  columnHelper.accessor("median_duration_hours", {
    header: "Median H",
    cell: ({ getValue }) => getValue().toFixed(1)
  }),
  columnHelper.accessor("oi_change_1h", {
    header: "OI 1h",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("oi_change_6h", {
    header: "OI 6h",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("oi_change_24h", {
    header: "OI 24h",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("latest_funding", {
    header: "Funding",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(2)}%`
  }),
  columnHelper.accessor("data_completeness", {
    header: "Coverage",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("latest_signal_label", { header: "Latest Signal" })
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
