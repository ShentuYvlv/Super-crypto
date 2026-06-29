"use client";

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable
} from "@tanstack/react-table";

export function DataTable<TData>({
  data,
  columns,
  onRowClick,
  isRowActive
}: {
  data: TData[];
  columns: ColumnDef<TData, any>[];
  onRowClick?: (row: TData) => void;
  isRowActive?: (row: TData) => boolean;
}) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-surface2 text-left text-muted">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-3 py-3 font-medium">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border bg-surface">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className={[
                  onRowClick ? "cursor-pointer" : "",
                  isRowActive?.(row.original)
                    ? "bg-surface2/80 ring-1 ring-inset ring-accent/40"
                    : "hover:bg-surface2/60"
                ].join(" ")}
                onClick={() => onRowClick?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-3 align-top">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
