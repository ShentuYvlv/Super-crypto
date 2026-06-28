"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { HashBadge } from "@/components/HashBadge";
import { StatusBadge } from "@/components/StatusBadge";
import type { Experiment } from "@/types/api";

const columnHelper = createColumnHelper<Experiment>();

const columns = [
  columnHelper.accessor("experiment_id", {
    header: "Experiment",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("strategy", { header: "Strategy" }),
  columnHelper.accessor("engine", { header: "Engine" }),
  columnHelper.accessor("split", { header: "Split" }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor((row) => row.metrics.net_return, {
    id: "net_return",
    header: "Net Return",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor((row) => row.metrics.trade_count, {
    id: "trade_count",
    header: "Trades"
  }),
  columnHelper.accessor((row) => row.metrics.sharpe, {
    id: "sharpe",
    header: "Sharpe",
    cell: ({ getValue }) => getValue().toFixed(2)
  }),
  columnHelper.accessor((row) => row.metrics.max_drawdown, {
    id: "max_drawdown",
    header: "MDD",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor((row) => row.metrics.win_rate, {
    id: "win_rate",
    header: "Win Rate",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("config_hash", {
    header: "Config Hash",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("split_hash", {
    header: "Split Hash",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("data_snapshot_hash", {
    header: "Snapshot",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("git_commit_hash", {
    header: "Git",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("failure_reason", {
    header: "Risk",
    cell: ({ getValue, row }) => getValue() ?? (row.original.metrics.trade_count < 20 ? "low_trade_count" : "-")
  })
];

export function ExperimentTable({
  data,
  onRowClick
}: {
  data: Experiment[];
  onRowClick?: (row: Experiment) => void;
}) {
  return <DataTable data={data} columns={columns} onRowClick={onRowClick} />;
}
