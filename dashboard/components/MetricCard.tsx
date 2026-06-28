import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";

export function MetricCard({
  label,
  value,
  sublabel,
  badge
}: {
  label: string;
  value: string;
  sublabel: string;
  badge?: string;
}) {
  return (
    <Card className="p-4">
      <div className="mb-5 flex items-start justify-between gap-3">
        <p className="text-sm text-muted">{label}</p>
        {badge ? <StatusBadge value={badge} /> : null}
      </div>
      <div className="metric-value">{value}</div>
      <p className="mt-2 text-sm text-muted">{sublabel}</p>
    </Card>
  );
}

