"use client";

import { createColumnHelper } from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { DataQualityRow } from "@/types/api";

const columnHelper = createColumnHelper<DataQualityRow>();

const columns = [
  columnHelper.accessor("source_name", { header: "Source" }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: ({ getValue }) => <StatusBadge value={getValue()} />
  }),
  columnHelper.accessor("file_count", { header: "Files" }),
  columnHelper.accessor("freshness", { header: "Freshness" }),
  columnHelper.accessor("notes", {
    header: "Notes",
    cell: ({ getValue }) => (getValue()?.length ? getValue()?.join(", ") : "-")
  })
];

export function DataQualityTable({ data }: { data: DataQualityRow[] }) {
  return <DataTable data={data} columns={columns} />;
}
