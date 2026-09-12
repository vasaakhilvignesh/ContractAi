import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { contracts } from "../data/mock";
import { RiskBadge } from "../components/ui/Badge";

const comparisonCategories = [
  {
    category: "Contract Duration",
    key: "duration",
    values: {
      c001: "2 years (Mar 2022 – Mar 2024)",
      c007: "1 year (Mar 2023 – Mar 2024)",
      c008: "1 year (May 2023 – May 2024)",
    },
    different: true,
  },
  {
    category: "Auto-Renewal",
    key: "renewal",
    values: {
      c001: "Yes — 12-month automatic renewal",
      c007: "Yes — 12-month automatic renewal",
      c008: "No auto-renewal",
    },
    different: true,
  },
  {
    category: "Notice Period",
    key: "notice",
    values: {
      c001: "30 days written notice",
      c007: "30 days written notice",
      c008: "45 days written notice",
    },
    different: true,
  },
  {
    category: "Termination for Convenience",
    key: "termination",
    values: {
      c001: "Yes — 30-day notice, no penalty",
      c007: "Yes — 30-day notice, no penalty",
      c008: "Yes — 45-day notice + 25% termination fee",
    },
    different: true,
    riskNote: { c008: "High risk: 25% early termination fee" },
  },
  {
    category: "Payment Terms",
    key: "payment",
    values: {
      c001: "Net-30 from invoice",
      c007: "Net-30 from invoice",
      c008: "Net-30 from invoice",
    },
    different: false,
  },
  {
    category: "Liability Cap",
    key: "liability",
    values: {
      c001: "12 months of fees paid",
      c007: "No cap for IP indemnification claims",
      c008: "Total fees paid under the SOW",
    },
    different: true,
    riskNote: { c007: "High risk: uncapped IP liability" },
  },
  {
    category: "Indemnification",
    key: "indemnification",
    values: {
      c001: "Mutual — standard IP infringement",
      c007: "Mutual — uncapped for IP",
      c008: "One-sided — vendor indemnifies client",
    },
    different: true,
  },
  {
    category: "Confidentiality Period",
    key: "confidentiality",
    values: {
      c001: "5 years post-termination",
      c007: "3 years post-termination",
      c008: "Perpetual",
    },
    different: true,
  },
  {
    category: "Data Protection",
    key: "data",
    values: {
      c001: "GDPR compliant, annual audit",
      c007: "GDPR compliant, no audit requirement",
      c008: "Not specified",
    },
    different: true,
    riskNote: { c008: "Missing data protection clause" },
  },
  {
    category: "Governing Law",
    key: "law",
    values: {
      c001: "California, USA",
      c007: "Washington State, USA",
      c008: "New York, USA",
    },
    different: true,
  },
];

export default function Compare() {
  const navigate = useNavigate();
  const [selectedIds, setSelectedIds] = useState<string[]>(["c001", "c007", "c008"]);
  const [showOnlyDiff, setShowOnlyDiff] = useState(false);

  const selectedContracts = contracts.filter(c => selectedIds.includes(c.id));

  function toggleContract(id: string) {
    if (selectedIds.includes(id)) {
      if (selectedIds.length > 2) setSelectedIds(prev => prev.filter(i => i !== id));
    } else {
      if (selectedIds.length < 5) setSelectedIds(prev => [...prev, id]);
    }
  }

  const displayedCategories = showOnlyDiff ? comparisonCategories.filter(c => c.different) : comparisonCategories;

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Contract Comparison</h1>
        <p className="text-sm text-slate-500 mt-0.5">Compare contract terms, identify differences, and inspect evidence</p>
      </div>

      {/* Contract Selection */}
      <div className="bg-white border border-[var(--border)] rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Select Contracts (2–5)</p>
          <span className="text-xs text-slate-400">{selectedIds.length} selected</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {contracts.map((c) => {
            const isSelected = selectedIds.includes(c.id);
            return (
              <button
                key={c.id}
                onClick={() => toggleContract(c.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                  isSelected
                    ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                    : "bg-white text-slate-600 border-[var(--border)] hover:border-slate-400"
                }`}
              >
                {isSelected && (
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5l2 2.5L8 2.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
                {c.vendor}
                <RiskBadge level={c.riskLevel} size="sm" />
              </button>
            );
          })}
        </div>
      </div>

      {selectedIds.length < 2 ? (
        <div className="bg-white border border-[var(--border)] rounded-lg p-12 text-center text-slate-400">
          <p className="font-medium text-slate-500">Select at least 2 contracts to compare</p>
        </div>
      ) : (
        <>
          {/* Comparison Controls */}
          <div className="flex items-center gap-3 mb-3">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showOnlyDiff}
                onChange={e => setShowOnlyDiff(e.target.checked)}
                className="rounded"
              />
              Show differences only
            </label>
            <span className="text-xs text-slate-400">
              {comparisonCategories.filter(c => c.different).length} differences found across {comparisonCategories.length} categories
            </span>
          </div>

          {/* Comparison Table */}
          <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-[var(--border)] bg-slate-50">
                <tr>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3 w-44">CATEGORY</th>
                  {selectedContracts.map(c => (
                    <th key={c.id} className="text-left px-4 py-3">
                      <div className="flex items-start gap-2">
                        <div>
                          <button
                            className="text-xs font-semibold text-slate-900 hover:text-[var(--accent)] transition-colors text-left"
                            onClick={() => navigate(`/contracts/${c.id}`)}
                          >
                            {c.vendor}
                          </button>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-xs text-slate-400 font-mono">{c.type}</span>
                            <RiskBadge level={c.riskLevel} size="sm" />
                          </div>
                        </div>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayedCategories.map((row) => {
                  const isDifferent = row.different;
                  return (
                    <tr key={row.key} className={`border-b border-[var(--border)] last:border-0 ${isDifferent ? "" : "opacity-70"}`}>
                      <td className="px-4 py-3 align-top">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold text-slate-700">{row.category}</span>
                          {isDifferent && (
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" title="Values differ" />
                          )}
                        </div>
                      </td>
                      {selectedContracts.map((c) => {
                        const val = (row.values as Record<string, string>)[c.id] ?? "—";
                        const riskNote = (row.riskNote as Record<string, string> | undefined)?.[c.id];
                        return (
                          <td key={c.id} className={`px-4 py-3 align-top ${riskNote ? "bg-orange-50" : ""}`}>
                            <p className="text-xs text-slate-700 leading-relaxed">{val}</p>
                            {riskNote && (
                              <div className="flex items-center gap-1 mt-1">
                                <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                                  <path d="M5.5 1L1 9.5h9L5.5 1z" stroke="#EA580C" strokeWidth="1.2" strokeLinejoin="round"/>
                                  <path d="M5.5 4.5v2M5.5 8v.25" stroke="#EA580C" strokeWidth="1.2" strokeLinecap="round"/>
                                </svg>
                                <span className="text-xs text-orange-700 font-medium">{riskNote}</span>
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* AI Explanation */}
          <div className="mt-4 bg-blue-50 border border-blue-100 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 bg-[var(--accent)] rounded flex items-center justify-center flex-shrink-0">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M6.5 1l1.2 3.8 3.8.2-3 2.5.8 3.8-3.3-2.2-3.3 2.2.8-3.8-3-2.5 3.8-.2L6.5 1z" stroke="white" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
              </div>
              <div>
                <p className="text-xs font-semibold text-[var(--primary)] mb-1">AI Analyst Summary</p>
                <p className="text-sm text-slate-700 leading-relaxed">
                  The McKinsey Consulting Agreement carries the highest termination risk due to its 25% early termination fee — a significant exposure on a $480K engagement.
                  The Microsoft Enterprise License has an uncapped IP indemnification liability that warrants legal review.
                  All three contracts share Net-30 payment terms. The Salesforce and Microsoft agreements have identical 30-day notice periods and auto-renewal provisions.
                </p>
                <button onClick={() => navigate("/analyst")} className="mt-2 text-xs text-[var(--accent)] hover:text-blue-700 font-medium transition-colors">
                  Ask a follow-up question →
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
