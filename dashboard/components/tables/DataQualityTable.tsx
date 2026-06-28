"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { displayText } from "@/lib/display";
import type { DataQualityRow } from "@/types/api";

const columnHelper = createColumnHelper<DataQualityRow>();

const columns = [
  columnHelper.accessor("source_name", {
    header: "数据源",
    cell: ({ getValue }) => displayText(getValue())
  }),
  columnHelper.accessor("status", {
    header: "状态",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("file_count", { header: "文件数" }),
  columnHelper.accessor("freshness", { header: "新鲜度" }),
  columnHelper.accessor("notes", {
    header: "备注",
    cell: ({ getValue }) => (getValue()?.length ? getValue()?.map(displayText).join(", ") : "-")
  })
];

export function DataQualityTable({ data }: { data: DataQualityRow[] }) {
  return <DataTable data={data} columns={columns} />;
}
