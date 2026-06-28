import { Badge } from "@/components/ui/badge";

export function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone =
    normalized.includes("run") || normalized.includes("healthy") || normalized.includes("accepted")
      ? "positive"
      : normalized.includes("reject") || normalized.includes("fail") || normalized.includes("blocked")
        ? "negative"
        : normalized.includes("partial") || normalized.includes("stale") || normalized.includes("idle")
          ? "warning"
          : normalized.includes("local")
            ? "info"
            : "accent";
  return <Badge tone={tone}>{value}</Badge>;
}
