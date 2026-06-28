export function ErrorState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-negative/40 bg-negative/10 p-8 text-center">
      <p className="text-lg font-semibold text-negative">{title}</p>
      <p className="mt-2 text-sm text-muted">{description}</p>
    </div>
  );
}
