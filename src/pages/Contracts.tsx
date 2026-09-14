import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { contractsApi } from "../api/services";
import type { ContractResponse } from "../api/types";
import { contracts as mockContracts } from "../data/mock";
import { RiskBadge, StatusBadge } from "../components/ui/Badge";

export default function Contracts() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterRisk, setFilterRisk] = useState("all");
  const [sortBy, setSortBy] = useState("lastUpdated");
  const [contractsList, setContractsList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    contractsApi
      .list({ limit: 100 })
      .then((res) => {
        if (res.items && res.items.length > 0) {
          const mapped = res.items.map((c: ContractResponse) => ({
            id: c.id,
            name: c.title,
            vendor: c.vendor || "Unknown Vendor",
            type: c.contract_type || "General",
            status: c.status || "active",
            riskLevel: c.risk_level || "none",
            renewalDate: c.expiry_date || "—",
            effectiveDate: c.effective_date || "—",
            expirationDate: c.expiry_date || "—",
            obligations: 0,
            lastUpdated: c.updated_at ? c.updated_at.split("T")[0] : "—",
            processingStatus: c.processing_status,
            pages: c.page_count || 1,
            value: c.contract_value ? `$${c.contract_value.toLocaleString()}` : "—",
            noticePeriod: "30 days",
          }));
          setContractsList(mapped);
        } else {
          setContractsList(mockContracts);
        }
      })
      .catch(() => {
        // Fallback to mock data if API is not yet loaded with records
        setContractsList(mockContracts);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = contractsList
    .filter((c) => {
      const q = search.toLowerCase();
      const matchesSearch =
        !q ||
        c.name.toLowerCase().includes(q) ||
        c.vendor.toLowerCase().includes(q) ||
        c.type.toLowerCase().includes(q);
      const matchesType = filterType === "all" || c.type === filterType;
      const matchesRisk = filterRisk === "all" || c.riskLevel === filterRisk;
      return matchesSearch && matchesType && matchesRisk;
    })
    .sort((a, b) => {
      if (sortBy === "lastUpdated") return new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime();
      if (sortBy === "renewal") return new Date(a.renewalDate).getTime() - new Date(b.renewalDate).getTime();
      if (sortBy === "vendor") return a.vendor.localeCompare(b.vendor);
      if (sortBy === "risk") {
        const order = ["critical", "high", "medium", "low", "none"];
        return order.indexOf(a.riskLevel) - order.indexOf(b.riskLevel);
      }
      return 0;
    });

  const types = [...new Set(contractsList.map((c) => c.type))];

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Contract Library</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {contractsList.length} contracts · {contractsList.filter((c) => c.status === "active").length} active
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

      {/* Toolbar */}
      <div className="bg-white border border-[var(--border)] rounded-lg p-4 mb-4 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <div className="absolute inset-y-0 left-3 flex items-center text-slate-400">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M9.5 9.5l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search contracts..."
            className="w-full pl-8 pr-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        >
          <option value="all">All Types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={filterRisk}
          onChange={(e) => setFilterRisk(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        >
          <option value="all">All Risk Levels</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="none">None</option>
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        >
          <option value="lastUpdated">Recently Updated</option>
          <option value="renewal">Upcoming Renewal</option>
          <option value="vendor">Vendor Name</option>
          <option value="risk">Highest Risk</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden shadow-sm">
        {loading ? (
          <div className="py-16 text-center text-slate-400 flex flex-col items-center gap-2">
            <div className="w-6 h-6 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
            <p className="text-xs">Loading contract portfolio...</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-[var(--border)] text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                {["Contract Name", "Vendor", "Type", "Status", "Risk Level", "Renewal Date", "Obligations", "Last Updated", ""].map((h, i) => (
                  <th key={i} className="px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                        <circle cx="14" cy="14" r="10" stroke="#CBD5E1" strokeWidth="2"/>
                        <path d="M21 21l7 7" stroke="#CBD5E1" strokeWidth="2" strokeLinecap="round"/>
                      </svg>
                      <p className="font-medium text-slate-500">No contracts found</p>
                      <p className="text-xs">Try adjusting your search or filters</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50 cursor-pointer transition-colors group"
                    onClick={() => navigate(`/contracts/${c.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900 text-xs leading-snug max-w-xs">{c.name}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">{c.vendor}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono">{c.type}</td>
                    <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-4 py-3"><RiskBadge level={c.riskLevel} size="sm" /></td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono">{c.renewalDate}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 text-center">{c.obligations}</td>
                    <td className="px-4 py-3 text-xs text-slate-400 font-mono">{c.lastUpdated}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          className="p-1.5 text-slate-400 hover:text-[var(--accent)] hover:bg-blue-50 rounded transition-colors"
                          title="View overview"
                          onClick={(e) => { e.stopPropagation(); navigate(`/contracts/${c.id}`); }}
                        >
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                            <path d="M6.5 2a4.5 4.5 0 100 9 4.5 4.5 0 000-9z" stroke="currentColor" strokeWidth="1.3"/>
                            <circle cx="6.5" cy="6.5" r="1" fill="currentColor"/>
                          </svg>
                        </button>
                        <button
                          className="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded transition-colors"
                          title="View risks"
                          onClick={(e) => { e.stopPropagation(); navigate("/risks"); }}
                        >
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                            <path d="M6.5 1L1 11h11L6.5 1z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                            <path d="M6.5 5v2.5M6.5 9.5v.25" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}

        {filtered.length > 0 && !loading && (
          <div className="px-4 py-3 border-t border-[var(--border)] flex items-center justify-between bg-slate-50">
            <p className="text-xs text-slate-400">Showing {filtered.length} contracts</p>
            <div className="flex items-center gap-1">
              <button className="px-2.5 py-1 text-xs border border-[var(--border)] rounded text-slate-500 hover:bg-white transition-colors disabled:opacity-40" disabled>← Prev</button>
              <span className="px-2.5 py-1 text-xs bg-[var(--primary)] text-white rounded font-medium">1</span>
              <button className="px-2.5 py-1 text-xs border border-[var(--border)] rounded text-slate-500 hover:bg-white transition-colors" disabled>Next →</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
