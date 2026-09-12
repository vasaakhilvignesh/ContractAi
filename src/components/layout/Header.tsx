import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const breadcrumbMap: Record<string, string[]> = {
  "/dashboard": ["Dashboard"],
  "/contracts": ["Contracts"],
  "/contracts/upload": ["Contracts", "Upload"],
  "/obligations": ["Obligations"],
  "/risks": ["Risk Monitor"],
  "/compare": ["Compare"],
  "/analyst": ["AI Analyst"],
  "/audit": ["Audit Log"],
};

export function Header() {
  const [search, setSearch] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const crumbs = breadcrumbMap[location.pathname] ?? ["ContractIQ"];

  return (
    <header className="h-16 flex-shrink-0 flex items-center px-6 gap-4 border-b border-[var(--border)] bg-white">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm flex-shrink-0">
        {crumbs.map((crumb, i) => (
          <span key={crumb} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-slate-300">/</span>}
            <span className={i === crumbs.length - 1 ? "text-slate-900 font-medium" : "text-slate-400"}>
              {crumb}
            </span>
          </span>
        ))}
      </div>

      {/* Global Search */}
      <div className="flex-1 max-w-lg mx-auto relative">
        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-slate-400">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 10l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search contracts, clauses, vendors or obligations..."
          className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-[var(--border)] rounded-md text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent transition-all"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute inset-y-0 right-3 flex items-center text-slate-400 hover:text-slate-600"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative w-8 h-8 flex items-center justify-center text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors"
            aria-label="Notifications"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 1a5 5 0 015 5v3l1.5 2.5H1.5L3 9V6a5 5 0 015-5z" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M6.5 13a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-white" />
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-10 w-80 bg-white border border-[var(--border)] rounded-lg shadow-lg z-50">
              <div className="px-4 py-3 border-b border-[var(--border)]">
                <p className="font-semibold text-sm text-slate-900">Notifications</p>
              </div>
              {[
                { title: "Renewal alert — Salesforce MSA", time: "2h ago", type: "warning" },
                { title: "Critical risk detected — Accenture PSA", time: "4h ago", type: "danger" },
                { title: "Obligation overdue — Accenture deliverable", time: "1d ago", type: "danger" },
              ].map((n, i) => (
                <div key={i} className="px-4 py-3 border-b border-[var(--border)] last:border-0 hover:bg-slate-50 cursor-pointer">
                  <div className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${n.type === "danger" ? "bg-red-500" : "bg-amber-500"}`} />
                    <div>
                      <p className="text-sm text-slate-800 font-medium">{n.title}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{n.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Upload CTA */}
        <button
          onClick={() => navigate("/contracts/upload")}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent)] text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v8M4 4l3-3 3 3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Upload
        </button>
      </div>
    </header>
  );
}
