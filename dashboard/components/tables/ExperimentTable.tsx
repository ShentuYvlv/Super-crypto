"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { HashBadge } from "@/components/HashBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { displayDateTime, displayText } from "@/lib/display";
import type { Experiment } from "@/types/api";

const columnHelper = createColumnHelper<Experiment>();

const columns = [
  columnHelper.accessor("experiment_id", {
    header: "实验",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("strategy", { header: "策略" }),
  columnHelper.accessor("engine", {
    header: "引擎",
    cell: ({ getValue }) => displayText(getValue())
  }),
  columnHelper.accessor("split", {
    header: "切分",
    cell: ({ getValue }) => displayText(getValue())
  }),
  columnHelper.accessor("status", {
    header: "状态",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("created_at", {
    header: "运行时间",
    cell: ({ getValue }) => displayDateTime(getValue())
  }),
  columnHelper.accessor((row) => row.metrics.net_return, {
    id: "net_return",
    header: "净收益",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor((row) => row.metrics.trade_count, {
    id: "trade_count",
    header: "交易数"
  }),
  columnHelper.accessor((row) => row.metrics.sharpe, {
    id: "sharpe",
    header: "夏普",
    cell: ({ getValue }) => getValue().toFixed(2)
  }),
  columnHelper.accessor((row) => row.metrics.max_drawdown, {
    id: "max_drawdown",
    header: "最大回撤",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor((row) => row.metrics.win_rate, {
    id: "win_rate",
    header: "胜率",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(0)}%`
  }),
  columnHelper.accessor("config_hash", {
    header: "配置哈希",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("split_hash", {
    header: "切分哈希",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("data_snapshot_hash", {
    header: "快照",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("git_commit_hash", {
    header: "Git",
    cell: ({ getValue }) => <HashBadge value={getValue()} />
  }),
  columnHelper.accessor("failure_reason", {
    header: "结论",
    cell: ({ getValue, row }) => displayText(getValue() ?? (row.original.metrics.trade_count < 20 ? "low_trade_count" : "-"))
  })
];

export function ExperimentTable({
  data,
  onRowClick,
  activeExperimentId
}: {
  data: Experiment[];
  onRowClick?: (row: Experiment) => void;
  activeExperimentId?: string;
}) {
  return (
    <DataTable
      data={data}
      columns={columns}
      onRowClick={onRowClick}
      isRowActive={(row) => row.experiment_id === activeExperimentId}
    />
  );
}
