import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { contractsApi } from "../api/services";
import type { ContractResponse } from "../api/types";
import { contracts as mockContracts, risks as mockRisks, obligations as mockObligations } from "../data/mock";
import { RiskBadge, StatusBadge } from "../components/ui/Badge";

function KpiCard({
  label,
  value,
  secondary,
  accent,
  icon,
}: {
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
        <div
          className={`w-9 h-9 rounded flex items-center justify-center ${
            accent === "red"
              ? "bg-red-50 text-red-600"
              : accent === "amber"
              ? "bg-amber-50 text-amber-600"
              : accent === "green"
              ? "bg-green-50 text-green-600"
              : "bg-blue-50 text-blue-600"
          }`}
        >
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
  const [contractsList, setContractsList] = useState<any[]>(mockContracts);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    contractsApi
      .list({ limit: 100 })
      .then((res) => {
        if (res.items && res.items.length > 0) {
          const mapped = res.items.map((c: ContractResponse) => ({
            id: c.id,
            name: c.title,
            vendor: c.vendor || c.title,
            type: c.contract_type || "General",
            status: c.status || "active",
            riskLevel: c.risk_level || "none",
            renewalDate: c.expiry_date || "2026-12-31",
            effectiveDate: c.effective_date || "2026-01-01",
            expirationDate: c.expiry_date || "2026-12-31",
            obligations: 0,
            lastUpdated: c.updated_at ? c.updated_at.split("T")[0] : "—",
            processingStatus: c.processing_status,
            pages: c.page_count || 1,
            value: c.contract_value ? `$${c.contract_value.toLocaleString()}` : "—",
            noticePeriod: "30 days",
          }));
          setContractsList(mapped);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalCount = contractsList.length;
  const highRiskContracts = contractsList.filter((c) => c.riskLevel === "critical" || c.riskLevel === "high");
  const upcomingRenewals = contractsList
    .filter((c) => c.status === "active")
    .sort((a, b) => new Date(a.renewalDate).getTime() - new Date(b.renewalDate).getTime())
    .slice(0, 4);
  const recentContracts = [...contractsList]
    .sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime())
    .slice(0, 5);

  const openRisks = mockRisks.filter((r) => r.status === "open").slice(0, 4);
  const dueObligations = mockObligations.filter((o) => o.status === "due_soon" || o.status === "overdue").slice(0, 4);

  const riskDist = {
    critical: contractsList.filter((c) => c.riskLevel === "critical").length,
    high: contractsList.filter((c) => c.riskLevel === "high").length,
    medium: contractsList.filter((c) => c.riskLevel === "medium").length,
    low: contractsList.filter((c) => c.riskLevel === "low").length,
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
          <p className="text-sm text-slate-500 mt-0.5">
            Active portfolio monitoring & deterministic risk intelligence
          </p>
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
          value={String(totalCount)}
          secondary={`${contractsList.filter((c) => c.status === "active").length} currently active`}
          accent="blue"
          icon={
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M9 1H3a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V6L9 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M9 1v5h5" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          }
        />
        <KpiCard
          label="Active Obligations"
          value={String(mockObligations.length)}
          secondary="12 due within 30 days"
          accent="green"
          icon={
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="1" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          }
        />
        <KpiCard
          label="High Risk Contracts"
          value={String(highRiskContracts.length)}
          secondary="Flagged by deterministic rules"
          accent="red"
          icon={
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L1 13h14L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          }
        />
        <KpiCard
          label="Upcoming Renewals"
          value={String(upcomingRenewals.length)}
          secondary="Review opt-out windows"
          accent="amber"
          icon={
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          }
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
                  <th className="text-left text-xs font-medium text-slate-400 pb-2">VENDOR</th>
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
                    <td className="py-2.5 font-medium text-slate-900 text-xs truncate max-w-xs">{c.name}</td>
                    <td className="py-2.5 text-xs text-slate-600">{c.vendor}</td>
                    <td className="py-2.5">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="py-2.5">
                      <RiskBadge level={c.riskLevel} size="sm" />
                    </td>
                    <td className="py-2.5 text-xs font-mono text-slate-500">{c.renewalDate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Critical & High Risk Alerts */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Open Risk Signals" action="View All" onAction={() => navigate("/risks")} />
            <div className="space-y-2.5">
              {openRisks.map((r) => (
                <div
                  key={r.id}
                  className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border)] hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => navigate("/risks")}
                >
                  <div
                    className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                      r.severity === "critical"
                        ? "bg-red-500"
                        : r.severity === "high"
                        ? "bg-orange-500"
                        : "bg-amber-500"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-semibold text-slate-900 truncate">{r.contractName}</span>
                      <RiskBadge level={r.severity} size="sm" />
                      <span className="text-[11px] text-slate-400 ml-auto font-mono">Page {r.sourcePage}</span>
                    </div>
                    <p className="text-xs text-slate-600 leading-snug">{r.summary}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column (1/3) */}
        <div className="space-y-4">
          {/* Upcoming Renewals */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Upcoming Renewals" action="View All" onAction={() => navigate("/contracts")} />
            <div className="space-y-3">
              {upcomingRenewals.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-0 hover:bg-slate-50 px-1 rounded cursor-pointer transition-colors"
                  onClick={() => navigate(`/contracts/${c.id}`)}
                >
                  <div className="min-w-0 flex-1 mr-2">
                    <div className="text-xs font-medium text-slate-900 truncate">{c.name}</div>
                    <div className="text-[11px] text-slate-400">{c.vendor}</div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className="text-xs font-mono font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      {daysTill(c.renewalDate)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Obligations Due Soon */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-5">
            <SectionHeader title="Obligations Due Soon" action="View All" onAction={() => navigate("/obligations")} />
            <div className="space-y-2.5">
              {dueObligations.map((o) => (
                <div
                  key={o.id}
                  className="p-2.5 rounded border border-[var(--border)] hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => navigate("/obligations")}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-slate-800 truncate">{o.vendor}</span>
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase ${
                        o.status === "overdue"
                          ? "bg-red-50 text-red-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {o.status.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 leading-snug">{o.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
