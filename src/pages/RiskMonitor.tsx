import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { risks } from "../data/mock";
import { RiskBadge, StatusBadge } from "../components/ui/Badge";

export default function RiskMonitor() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");

  const counts = {
    critical: risks.filter(r => r.severity === "critical").length,
    high: risks.filter(r => r.severity === "high").length,
    medium: risks.filter(r => r.severity === "medium").length,
    low: risks.filter(r => r.severity === "low").length,
  };

  const filtered = risks.filter(r => {
    const matchSev = filterSeverity === "all" || r.severity === filterSeverity;
    const matchStatus = filterStatus === "all" || r.status === filterStatus;
    return matchSev && matchStatus;
  });

  const selectedRisk = risks.find(r => r.id === selected);

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Risk Monitor</h1>
          <p className="text-sm text-slate-500 mt-0.5">Deterministic risk signals detected across your contract portfolio</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Critical", count: counts.critical, color: "red", bg: "bg-red-50", text: "text-red-700", border: "border-red-200", bar: "bg-red-500" },
          { label: "High", count: counts.high, color: "orange", bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200", bar: "bg-orange-500" },
          { label: "Medium", count: counts.medium, color: "amber", bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", bar: "bg-amber-500" },
          { label: "Low", count: counts.low, color: "green", bg: "bg-green-50", text: "text-green-700", border: "border-green-200", bar: "bg-green-500" },
        ].map((s) => (
          <button
            key={s.label}
            onClick={() => setFilterSeverity(filterSeverity === s.label.toLowerCase() ? "all" : s.label.toLowerCase())}
            className={`${s.bg} border ${s.border} rounded-lg p-4 text-left hover:shadow-sm transition-all ${filterSeverity === s.label.toLowerCase() ? "ring-2 ring-offset-1 " + (s.label === "Critical" ? "ring-red-400" : s.label === "High" ? "ring-orange-400" : s.label === "Medium" ? "ring-amber-400" : "ring-green-400") : ""}`}
          >
            <div className={`text-3xl font-bold ${s.text} leading-none`}>{s.count}</div>
            <div className={`text-xs font-semibold ${s.text} mt-1`}>{s.label} Risk</div>
            <div className={`h-1 ${s.bar} rounded-full mt-3 opacity-60`} style={{ width: `${(s.count / risks.length) * 100}%` }} />
          </button>
        ))}
      </div>

      <div className="flex gap-4">
        {/* Risk Table */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-3 mb-3 flex items-center gap-3">
            <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}
              className="px-3 py-1.5 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]">
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]">
              <option value="all">All Statuses</option>
              <option value="open">Open</option>
              <option value="reviewed">Reviewed</option>
              <option value="accepted">Accepted</option>
              <option value="resolved">Resolved</option>
            </select>
            <span className="text-xs text-slate-400 ml-auto">{filtered.length} signals</span>
          </div>

          <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-[var(--border)]">
                <tr>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">RISK</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">CONTRACT</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">SEVERITY</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">STATUS</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">DETECTED</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((risk) => (
                  <tr
                    key={risk.id}
                    className={`border-b border-[var(--border)] last:border-0 cursor-pointer transition-colors ${selected === risk.id ? "bg-blue-50" : "hover:bg-slate-50"}`}
                    onClick={() => setSelected(selected === risk.id ? null : risk.id)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-xs text-slate-900">{risk.type}</div>
                      <div className="text-xs text-slate-400 mt-0.5 truncate max-w-xs">{risk.summary.substring(0, 60)}...</div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="text-xs text-[var(--accent)] hover:underline font-medium"
                        onClick={(e) => { e.stopPropagation(); navigate(`/contracts/${risk.contractId}`); }}
                      >
                        {risk.vendor}
                      </button>
                    </td>
                    <td className="px-4 py-3"><RiskBadge level={risk.severity} size="sm" /></td>
                    <td className="px-4 py-3"><StatusBadge status={risk.status} /></td>
                    <td className="px-4 py-3 text-xs text-slate-400 font-mono">{risk.detectedDate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Risk Detail Panel */}
        {selectedRisk && (
          <div className="w-96 flex-shrink-0">
            <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden sticky top-4">
              {/* Header */}
              <div className={`px-4 py-3 border-b border-[var(--border)] ${
                selectedRisk.severity === "critical" ? "bg-red-50" :
                selectedRisk.severity === "high" ? "bg-orange-50" :
                selectedRisk.severity === "medium" ? "bg-amber-50" : "bg-green-50"
              }`}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <RiskBadge level={selectedRisk.severity} />
                      <StatusBadge status={selectedRisk.status} />
                    </div>
                    <h3 className="font-semibold text-slate-900 text-sm">{selectedRisk.type}</h3>
                  </div>
                  <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600 ml-2">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                </div>
              </div>

              <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-280px)]">
                {/* Summary */}
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Risk Summary</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedRisk.summary}</p>
                </div>

                {/* Why flagged */}
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Triggered Rule</p>
                  <div className="bg-slate-50 border border-[var(--border)] rounded px-3 py-2">
                    <code className="text-xs text-slate-700 font-mono">{selectedRisk.rule}</code>
                  </div>
                </div>

                {/* Extracted Fact */}
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Extracted Fact</p>
                  <p className="text-sm font-medium text-slate-800">{selectedRisk.extractedFact}</p>
                </div>

                {/* Evidence */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Evidence</p>
                    <span className="text-xs text-slate-400 font-mono">Page {selectedRisk.sourcePage}</span>
                  </div>
                  <div className="text-xs text-slate-500 mb-1 font-medium">{selectedRisk.sourceClause}</div>
                  <blockquote className="text-sm text-slate-700 italic bg-amber-50 border-l-4 border-amber-400 px-3 py-2.5 rounded-r leading-relaxed">
                    {selectedRisk.evidenceSnippet}
                  </blockquote>
                </div>

                {/* Recommended Action */}
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Recommended Action</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedRisk.recommendedAction}</p>
                </div>

                {/* Actions */}
                <div className="border-t border-[var(--border)] pt-4 flex gap-2">
                  <button
                    onClick={() => navigate(`/contracts/${selectedRisk.contractId}`)}
                    className="flex-1 px-3 py-2 text-xs font-medium border border-[var(--border)] rounded text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Open Contract
                  </button>
                  <button className="flex-1 px-3 py-2 text-xs font-medium bg-[var(--primary)] text-white rounded hover:bg-[#16304f] transition-colors">
                    Mark Reviewed
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
