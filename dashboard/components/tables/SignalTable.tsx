"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { SignalReasonTags } from "@/components/SignalReasonTags";
import { StatusBadge } from "@/components/StatusBadge";
import type { Signal } from "@/types/api";

const columnHelper = createColumnHelper<Signal>();

const columns = [
  columnHelper.accessor("signal_time", {
    header: "Signal Time",
    cell: ({ getValue }) => new Date(getValue()).toLocaleString()
  }),
  columnHelper.accessor("symbol", { header: "Symbol" }),
  columnHelper.accessor("strategy", { header: "Strategy" }),
  columnHelper.accessor("entry_reference", { header: "Entry" }),
  columnHelper.accessor("confidence", {
    header: "Confidence",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("manipulation_score_bucket", {
    header: "Bucket",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("reason", {
    header: "Reason",
    cell: ({ getValue }) => <SignalReasonTags reasons={getValue()} />
  }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("orderbook_slippage_bps", {
    header: "Slip",
    cell: ({ getValue }) => {
      const value = getValue();
      return value == null ? "-" : `${value.toFixed(1)}bps`;
    }
  })
];

export function SignalTable({
  data,
  onRowClick
}: {
  data: Signal[];
  onRowClick?: (row: Signal) => void;
}) {
  return <DataTable data={data} columns={columns} onRowClick={onRowClick} />;
}
