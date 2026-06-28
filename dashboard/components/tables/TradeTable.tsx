"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { Trade } from "@/types/api";

const columnHelper = createColumnHelper<Trade>();

const columns = [
  columnHelper.accessor("entry_time", {
    header: "Entry Time",
    cell: ({ getValue }) => new Date(getValue()).toLocaleString()
  }),
  columnHelper.accessor("symbol", { header: "Symbol" }),
  columnHelper.accessor("source", {
    header: "Source",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("exit_reason", { header: "Exit" }),
  columnHelper.accessor("net_return", {
    header: "Net Return",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("fee_cost", {
    header: "Fee",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("slippage_cost", {
    header: "Slip",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("funding_cost", {
    header: "Funding",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("holding_minutes", {
    header: "Hold",
    cell: ({ getValue }) => `${Math.round(getValue())}m`
  }),
  columnHelper.accessor("orderbook_snapshot_status", {
    header: "OB",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  })
];

export function TradeTable({
  data,
  onRowClick
}: {
  data: Trade[];
  onRowClick?: (row: Trade) => void;
}) {
  return <DataTable data={data} columns={columns} onRowClick={onRowClick} />;
}
