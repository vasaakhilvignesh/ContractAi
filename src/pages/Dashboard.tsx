import { useNavigate } from "react-router-dom";
import { contracts, risks, obligations } from "../data/mock";
import { RiskBadge, StatusBadge } from "../components/ui/Badge";

function KpiCard({ label, value, secondary, accent, icon }: {
  label: string;
  value: string;
  secondary: string;
  accent?: "blue" | "amber" | "red" | "green";
  icon: React.ReactNode;
}) {
  const accentBar: Record<string, string> = {
    blue: "bg-[var(--accent)]",
    amber: "bg-amber-500",
    red: "bg-red-500",
    green: "bg-green-500",
  };
  return (
    <div className="bg-white border border-[var(--border)] rounded-lg p-5 flex flex-col gap-3 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className={`w-9 h-9 rounded flex items-center justify-center ${
          accent === "red" ? "bg-red-50 text-red-600" :
          accent === "amber" ? "bg-amber-50 text-amber-600" :
          accent === "green" ? "bg-green-50 text-green-600" :
          "bg-blue-50 text-blue-600"
        }`}>
          {icon}
        </div>
        <div className={`w-1 h-8 rounded-full ${accentBar[accent ?? "blue"]}`} />
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-900 tracking-tight">{value}</div>
        <div className="text-xs font-medium text-slate-500 mt-0.5">{label}</div>
      </div>
      <div className="text-xs text-slate-400 border-t border-[var(--border)] pt-2.5">{secondary}</div>
    </div>
  );
}

function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {action && (
        <button onClick={onAction} className="text-xs text-[var(--accent)] hover:text-blue-800 font-medium transition-colors">
          {action} →
        </button>
      )}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const highRiskContracts = contracts.filter(c => c.riskLevel === "critical" || c.riskLevel === "high");
  const upcomingRenewals = contracts
    .filter(c => c.status === "active")
    .sort((a, b) => new Date(a.renewalDate).getTime() - new Date(b.renewalDate).getTime())
    .slice(0, 4);
  const recentContracts = [...contracts].sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()).slice(0, 5);
  const openRisks = risks.filter(r => r.status === "open").slice(0, 4);
  const dueObligations = obligations.filter(o => o.status === "due_soon" || o.status === "overdue").slice(0, 4);

  const riskDist = {
    critical: risks.filter(r => r.severity === "critical").length,
    high: risks.filter(r => r.severity === "high").length,
    medium: risks.filter(r => r.severity === "medium").length,
    low: risks.filter(r => r.severity === "low").length,
  };
  const totalRisks = riskDist.critical + riskDist.high + riskDist.medium + riskDist.low;

  function daysTill(dateStr: string) {
    const diff = Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000);
    if (diff < 0) return "Expired";
    if (diff === 0) return "Today";
    return `${diff}d`;
  }

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      {/* Page header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Contract Intelligence Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">Portfolio status as of January 10, 2024</p>
        </div>
        <button
          onClick={() => navigate("/contracts/upload")}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded hover:bg-[#16304f] transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v8M4 4l3-3 3 3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Upload Contract
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Total Contracts"
          value="42"
          secondary="3 added this month"
          accent="blue"
          icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9 1H3a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V6L9 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M9 1v5h5" stroke="currentColor" strokeWidth="1.5"/></svg>}
        />
        <KpiCard
          label="Active Obligations"
          value="86"
          secondary="12 due within 30 days"
          accent="green"
          icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="1" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
        />
        <KpiCard
          label="High Risk Contracts"
          value="7"
          secondary="2 require immediate attention"
          accent="red"
          icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1L1 13h14L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>}
        />
        <KpiCard
          label="Upcoming Renewals"
          value="5"
          secondary="Within the next 30 days"
          accent="amber"
          icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-3 gap-4">
        {/* Left column (2/3) */}
        <div className="col-span-2 space-y-4">
          {/* Recent Contracts */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Recent Contracts" action="View All" onAction={() => navigate("/contracts")} />
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">CONTRACT</th>
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">TYPE</th>
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">STATUS</th>
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">RISK</th>
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">RENEWAL</th>
                </tr>
              </thead>
              <tbody>
                {recentContracts.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/contracts/${c.id}`)}
                  >
                    <td className="py-2.5 pr-4">
                      <div className="font-medium text-slate-900 text-xs">{c.name}</div>
                      <div className="text-slate-400 text-xs">{c.vendor}</div>
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-slate-500">{c.type}</td>
                    <td className="py-2.5 pr-4"><StatusBadge status={c.status} /></td>
                    <td className="py-2.5 pr-4"><RiskBadge level={c.riskLevel} size="sm" /></td>
                    <td className="py-2.5 text-xs text-slate-500 font-mono">{c.renewalDate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Open Risk Signals */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Open Risk Signals" action="View Risk Monitor" onAction={() => navigate("/risks")} />
            <div className="space-y-2.5">
              {openRisks.map((risk) => (
                <div
                  key={risk.id}
                  className="flex items-start gap-3 p-3 rounded border border-[var(--border)] hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => navigate("/risks")}
                >
                  <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                    risk.severity === "critical" ? "bg-red-500" :
                    risk.severity === "high" ? "bg-orange-500" :
                    risk.severity === "medium" ? "bg-amber-500" : "bg-green-500"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-slate-800">{risk.type}</span>
                      <RiskBadge level={risk.severity} size="sm" />
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{risk.contractName}</p>
                    <p className="text-xs text-slate-400 mt-0.5 truncate italic">"{risk.extractedFact}"</p>
                  </div>
                  <span className="text-xs text-slate-400 flex-shrink-0">{risk.detectedDate}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column (1/3) */}
        <div className="space-y-4">
          {/* Risk Distribution */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Risk Distribution" action="View Monitor" onAction={() => navigate("/risks")} />
            <div className="space-y-2.5">
              {[
                { label: "Critical", count: riskDist.critical, color: "bg-red-500", total: totalRisks },
                { label: "High", count: riskDist.high, color: "bg-orange-500", total: totalRisks },
                { label: "Medium", count: riskDist.medium, color: "bg-amber-500", total: totalRisks },
                { label: "Low", count: riskDist.low, color: "bg-green-500", total: totalRisks },
              ].map((r) => (
                <div key={r.label}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-slate-600 font-medium">{r.label}</span>
                    <span className="text-slate-400 font-mono">{r.count}</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${r.color} transition-all`}
                      style={{ width: `${(r.count / r.total) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Upcoming Renewals */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Upcoming Renewals" />
            <div className="space-y-2">
              {upcomingRenewals.map((c) => {
                const days = daysTill(c.renewalDate);
                const isUrgent = typeof days === "string" && days !== "Expired" && parseInt(days) <= 30;
                return (
                  <div
                    key={c.id}
                    className="flex items-center justify-between p-2.5 rounded border border-[var(--border)] hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/contracts/${c.id}`)}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <p className="text-xs font-medium text-slate-800 truncate">{c.vendor}</p>
                      <p className="text-xs text-slate-400">{c.renewalDate}</p>
                    </div>
                    <span className={`text-xs font-mono font-semibold flex-shrink-0 ${isUrgent ? "text-red-600" : "text-slate-500"}`}>
                      {days}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Obligation Status */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Obligations Requiring Action" action="View All" onAction={() => navigate("/obligations")} />
            <div className="space-y-2">
              {dueObligations.map((ob) => (
                <div
                  key={ob.id}
                  className="p-2.5 rounded border border-[var(--border)] hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => navigate("/obligations")}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-medium text-slate-800 leading-snug line-clamp-2">{ob.description}</p>
                    <StatusBadge status={ob.status} />
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{ob.vendor} · Due {ob.dueDate}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-4 bg-white border border-[var(--border)] rounded-lg p-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Quick Actions</p>
        <div className="flex flex-wrap gap-2">
          {[
            { label: "Upload Contract", route: "/contracts/upload", accent: true },
            { label: "View All Contracts", route: "/contracts" },
            { label: "Risk Monitor", route: "/risks" },
            { label: "Obligations", route: "/obligations" },
            { label: "Compare Contracts", route: "/compare" },
            { label: "AI Analyst", route: "/analyst" },
          ].map((a) => (
            <button
              key={a.label}
              onClick={() => navigate(a.route)}
              className={`px-3.5 py-1.5 text-sm font-medium rounded border transition-colors ${
                a.accent
                  ? "bg-[var(--accent)] text-white border-[var(--accent)] hover:bg-blue-700"
                  : "bg-white text-slate-700 border-[var(--border)] hover:bg-slate-50"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
