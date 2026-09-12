import type { RiskLevel } from "../../data/mock";

interface RiskBadgeProps {
  level: RiskLevel;
  size?: "sm" | "md";
}

const riskConfig: Record<RiskLevel, { label: string; classes: string }> = {
  critical: { label: "Critical", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  high: { label: "High", classes: "bg-orange-50 text-orange-700 ring-1 ring-orange-200" },
  medium: { label: "Medium", classes: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  low: { label: "Low", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  none: { label: "None", classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" },
};

export function RiskBadge({ level, size = "md" }: RiskBadgeProps) {
  const cfg = riskConfig[level];
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded ${cfg.classes} ${size === "sm" ? "text-xs px-1.5 py-0.5" : "text-xs px-2 py-1"}`}
    >
      <span
        className={`rounded-full flex-shrink-0 ${size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2"} ${
          level === "critical" ? "bg-red-500" :
          level === "high" ? "bg-orange-500" :
          level === "medium" ? "bg-amber-500" :
          level === "low" ? "bg-green-500" : "bg-slate-400"
        }`}
      />
      {cfg.label}
    </span>
  );
}

interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<string, { label: string; classes: string }> = {
  active: { label: "Active", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  expired: { label: "Expired", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  draft: { label: "Draft", classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" },
  under_review: { label: "Under Review", classes: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  terminated: { label: "Terminated", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  pending: { label: "Pending", classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" },
  due_soon: { label: "Due Soon", classes: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  overdue: { label: "Overdue", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  completed: { label: "Completed", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  waived: { label: "Waived", classes: "bg-slate-50 text-slate-500 ring-1 ring-slate-200" },
  open: { label: "Open", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  reviewed: { label: "Reviewed", classes: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  accepted: { label: "Accepted", classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" },
  resolved: { label: "Resolved", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  success: { label: "Success", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  failed: { label: "Failed", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  warning: { label: "Warning", classes: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  complete: { label: "Complete", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
  processing: { label: "Processing", classes: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  failed_proc: { label: "Failed", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const cfg = statusConfig[status] ?? { label: status, classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" };
  return (
    <span className={`inline-flex items-center font-medium text-xs px-2 py-0.5 rounded ${cfg.classes}`}>
      {cfg.label}
    </span>
  );
}

interface PriorityBadgeProps {
  priority: string;
}

const priorityConfig: Record<string, { label: string; classes: string }> = {
  critical: { label: "Critical", classes: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  high: { label: "High", classes: "bg-orange-50 text-orange-700 ring-1 ring-orange-200" },
  medium: { label: "Medium", classes: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  low: { label: "Low", classes: "bg-green-50 text-green-700 ring-1 ring-green-200" },
};

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const cfg = priorityConfig[priority] ?? { label: priority, classes: "bg-slate-50 text-slate-600 ring-1 ring-slate-200" };
  return (
    <span className={`inline-flex items-center font-medium text-xs px-2 py-0.5 rounded ${cfg.classes}`}>
      {cfg.label}
    </span>
  );
}
