import { Badge } from "@/components/ui/badge";

export function SignalReasonTags({ reasons }: { reasons: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {reasons.map((reason) => (
        <Badge key={reason} tone="accent">
          {reason}
        </Badge>
      ))}
    </div>
  );
}

