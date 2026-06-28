export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface/70 p-8 text-center">
      <p className="text-lg font-semibold">{title}</p>
      <p className="mt-2 text-sm text-muted">{description}</p>
    </div>
  );
}

