import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { contractsApi, comparisonApi } from "../api/services";
import type { ContractResponse, ContractComparisonResponse } from "../api/types";
import { contracts as mockContracts } from "../data/mock";
import { RiskBadge } from "../components/ui/Badge";

const fallbackCategories = [
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
  const [availableContracts, setAvailableContracts] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showOnlyDiff, setShowOnlyDiff] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<ContractComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    contractsApi
      .list({ limit: 50 })
      .then((res) => {
        if (res.items && res.items.length >= 2) {
          setAvailableContracts(
            res.items.map((c: ContractResponse) => ({
              id: c.id,
              vendor: c.vendor || c.title,
              type: c.contract_type || "General",
              riskLevel: c.risk_level || "none",
            }))
          );
          setSelectedIds([res.items[0].id, res.items[1].id]);
        } else {
          setAvailableContracts(mockContracts);
          setSelectedIds(["c001", "c007", "c008"]);
        }
      })
      .catch(() => {
        setAvailableContracts(mockContracts);
        setSelectedIds(["c001", "c007", "c008"]);
      });
  }, []);

  useEffect(() => {
    if (selectedIds.length < 2) {
      setComparisonResult(null);
      return;
    }

    // Check if these are real UUIDs
    const isRealUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(selectedIds[0]);

    if (isRealUUID) {
      setLoading(true);
      comparisonApi
        .compare({ contract_ids: selectedIds })
        .then((res) => setComparisonResult(res))
        .catch(() => setComparisonResult(null))
        .finally(() => setLoading(false));
    } else {
      setComparisonResult(null);
    }
  }, [selectedIds]);

  function toggleContract(id: string) {
    if (selectedIds.includes(id)) {
      if (selectedIds.length > 2) setSelectedIds((prev) => prev.filter((i) => i !== id));
    } else {
      if (selectedIds.length < 5) setSelectedIds((prev) => [...prev, id]);
    }
  }

  const selectedContracts = availableContracts.filter((c) => selectedIds.includes(c.id));

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Contract Comparison</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Compare contract terms, identify deterministic variance, and inspect evidence
        </p>
      </div>

      {/* Contract Selection */}
      <div className="bg-white border border-[var(--border)] rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Select Contracts (2–5)</p>
          <span className="text-xs text-slate-400">{selectedIds.length} selected</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {availableContracts.map((c) => {
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
                onChange={(e) => setShowOnlyDiff(e.target.checked)}
                className="rounded"
              />
              Show differences only
            </label>
            <span className="text-xs text-slate-400">
              {comparisonResult
                ? `${comparisonResult.different_fields_count} differences found across ${comparisonResult.fields.length} categories`
                : `${fallbackCategories.filter((c) => c.different).length} differences found across ${fallbackCategories.length} categories`}
            </span>
          </div>

          {/* Comparison Table */}
          <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden shadow-sm">
            {loading ? (
              <div className="py-16 text-center text-slate-400 flex flex-col items-center gap-2">
                <div className="w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
                <p className="text-xs">Evaluating cross-contract variance...</p>
              </div>
            ) : comparisonResult ? (
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)] bg-slate-50">
                  <tr>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3 w-48">FIELD / CATEGORY</th>
                    {comparisonResult.contracts.map((c) => (
                      <th key={c.contract_id} className="text-left px-4 py-3">
                        <button
                          className="text-xs font-semibold text-slate-900 hover:text-[var(--accent)] transition-colors text-left"
                          onClick={() => navigate(`/contracts/${c.contract_id}`)}
                        >
                          {c.title || c.vendor}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparisonResult.fields
                    .filter((row) => !showOnlyDiff || row.is_different)
                    .map((row) => (
                      <tr
                        key={row.field_name}
                        className={`border-b border-[var(--border)] last:border-0 ${
                          row.is_different ? "" : "opacity-70"
                        }`}
                      >
                        <td className="px-4 py-3 align-top">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-slate-700">{row.display_label}</span>
                            {row.is_different && (
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" title="Values differ" />
                            )}
                          </div>
                        </td>
                        {comparisonResult.contracts.map((c) => {
                          const valObj = row.values[c.contract_id];
                          const formatted = valObj?.formatted_value || "—";
                          return (
                            <td key={c.contract_id} className="px-4 py-3 align-top text-xs text-slate-700">
                              <p>{formatted}</p>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)] bg-slate-50">
                  <tr>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3 w-44">CATEGORY</th>
                    {selectedContracts.map((c) => (
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
                  {fallbackCategories
                    .filter((c) => !showOnlyDiff || c.different)
                    .map((row) => (
                      <tr key={row.key} className={`border-b border-[var(--border)] last:border-0 ${row.different ? "" : "opacity-70"}`}>
                        <td className="px-4 py-3 align-top">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-slate-700">{row.category}</span>
                            {row.different && (
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" title="Values differ" />
                            )}
                          </div>
                        </td>
                        {selectedContracts.map((c) => (
                          <td key={c.id} className="px-4 py-3 align-top">
                            <p className="text-xs text-slate-700 leading-relaxed">
                              {(row.values as Record<string, string>)[c.id] ?? "—"}
                            </p>
                          </td>
                        ))}
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
