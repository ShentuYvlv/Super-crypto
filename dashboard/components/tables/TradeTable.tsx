"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { displayReason } from "@/lib/display";
import type { Trade } from "@/types/api";

const columnHelper = createColumnHelper<Trade>();

const columns = [
  columnHelper.accessor("entry_time", {
    header: "入场时间",
    cell: ({ getValue }) => new Date(getValue()).toLocaleString()
  }),
  columnHelper.accessor("symbol", { header: "标的" }),
  columnHelper.accessor("source", {
    header: "来源",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("exit_reason", {
    header: "退出",
    cell: ({ getValue }) => displayReason(getValue())
  }),
  columnHelper.accessor("net_return", {
    header: "净收益",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("fee_cost", {
    header: "手续费",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("slippage_cost", {
    header: "滑点",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("funding_cost", {
    header: "资金费",
    cell: ({ getValue }) => `${(getValue() * 100).toFixed(1)}%`
  }),
  columnHelper.accessor("holding_minutes", {
    header: "持仓",
    cell: ({ getValue }) => `${Math.round(getValue())} 分钟`
  }),
  columnHelper.accessor("orderbook_snapshot_status", {
    header: "盘口",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  })
];

export function TradeTable({
  data,
  onRowClick,
  activeTradeId
}: {
  data: Trade[];
  onRowClick?: (row: Trade) => void;
  activeTradeId?: string;
}) {
  return (
    <DataTable
      data={data}
      columns={columns}
      onRowClick={onRowClick}
      isRowActive={(row) => row.trade_id === activeTradeId}
    />
  );
}
