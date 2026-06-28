import { Badge } from "@/components/ui/badge";
import { displayReason } from "@/lib/display";

export function SignalReasonTags({ reasons }: { reasons: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {reasons.map((reason) => (
        <Badge key={reason} tone="accent">
          {displayReason(reason)}
        </Badge>
      ))}
    </div>
  );
}
