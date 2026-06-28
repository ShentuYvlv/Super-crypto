export function HashBadge({ value }: { value: string }) {
  const label = value.length > 14 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
  return (
    <span title={value} className="mono-hash inline-flex max-w-[11rem] truncate rounded border border-border px-2 py-1">
      {label}
    </span>
  );
}
