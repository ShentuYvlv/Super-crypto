"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { SignalReasonTags } from "@/components/SignalReasonTags";
import { StatusBadge } from "@/components/StatusBadge";
import { displayText } from "@/lib/display";
import type { Signal } from "@/types/api";

const columnHelper = createColumnHelper<Signal>();

const columns = [
  columnHelper.accessor("signal_time", {
    header: "信号时间",
    cell: ({ getValue }) => new Date(getValue()).toLocaleString()
  }),
  columnHelper.accessor("symbol", { header: "标的" }),
  columnHelper.accessor("strategy", { header: "策略" }),
  columnHelper.accessor("entry_reference", {
    header: "入场",
    cell: ({ getValue }) => displayText(getValue())
  }),
  columnHelper.accessor("confidence", {
    header: "置信度",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("manipulation_score_bucket", {
    header: "分组",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("reason", {
    header: "原因",
    cell: ({ getValue }) => <SignalReasonTags reasons={getValue()} />
  }),
  columnHelper.accessor("status", {
    header: "状态",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("orderbook_slippage_bps", {
    header: "滑点",
    cell: ({ getValue }) => {
      const value = getValue();
      return value == null ? "-" : `${value.toFixed(1)} 基点`;
    }
  })
];

export function SignalTable({
  data,
  onRowClick,
  editing = false,
  selectedSignalIds = new Set<string>(),
  onToggleSignal
}: {
  data: Signal[];
  onRowClick?: (row: Signal) => void;
  editing?: boolean;
  selectedSignalIds?: Set<string>;
  onToggleSignal?: (signalId: string) => void;
}) {
  const tableColumns = editing
    ? [
        columnHelper.display({
          id: "selection",
          header: "选择",
          cell: ({ row }) => (
            <input
              type="checkbox"
              checked={selectedSignalIds.has(row.original.signal_id)}
              onChange={() => onToggleSignal?.(row.original.signal_id)}
              onClick={(event) => event.stopPropagation()}
              className="h-4 w-4 rounded border-border bg-canvas accent-accent"
              aria-label={`选择信号 ${row.original.signal_id}`}
            />
          )
        }),
        ...columns
      ]
    : columns;
  return <DataTable data={data} columns={tableColumns} onRowClick={editing ? undefined : onRowClick} />;
}
