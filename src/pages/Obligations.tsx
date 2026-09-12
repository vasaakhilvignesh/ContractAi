import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { obligations } from "../data/mock";
import { StatusBadge, PriorityBadge } from "../components/ui/Badge";

export default function Obligations() {
  const navigate = useNavigate();
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const counts = {
    total: obligations.length,
    due_soon: obligations.filter(o => o.status === "due_soon").length,
    overdue: obligations.filter(o => o.status === "overdue").length,
    completed: obligations.filter(o => o.status === "completed").length,
  };

  const filtered = obligations.filter(o => {
    const matchStatus = filterStatus === "all" || o.status === filterStatus;
    const matchPriority = filterPriority === "all" || o.priority === filterPriority;
    return matchStatus && matchPriority;
  });

  const selectedOb = obligations.find(o => o.id === selected);

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Obligation Center</h1>
        <p className="text-sm text-slate-500 mt-0.5">Track and manage contractual obligations across your portfolio</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Total Obligations", count: counts.total, color: "text-slate-900", bg: "bg-white", border: "border-[var(--border)]" },
          { label: "Due Soon", count: counts.due_soon, color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
          { label: "Overdue", count: counts.overdue, color: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
          { label: "Completed", count: counts.completed, color: "text-green-700", bg: "bg-green-50", border: "border-green-200" },
        ].map((s) => (
          <div key={s.label} className={`${s.bg} border ${s.border} rounded-lg p-4`}>
            <div className={`text-3xl font-bold ${s.color} leading-none`}>{s.count}</div>
            <div className="text-xs text-slate-500 mt-1 font-medium">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-4">
        {/* Table */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-3 mb-3 flex items-center gap-3">
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]">
              <option value="all">All Statuses</option>
              <option value="overdue">Overdue</option>
              <option value="due_soon">Due Soon</option>
              <option value="pending">Pending</option>
              <option value="completed">Completed</option>
            </select>
            <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)}
              className="px-3 py-1.5 text-sm border border-[var(--border)] rounded bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]">
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <span className="text-xs text-slate-400 ml-auto">{filtered.length} obligations</span>
          </div>

          <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-[var(--border)]">
                <tr>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">OBLIGATION</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">CONTRACT</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">RESPONSIBLE</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">DUE DATE</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">PRIORITY</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((ob) => (
                  <tr
                    key={ob.id}
                    className={`border-b border-[var(--border)] last:border-0 cursor-pointer transition-colors ${selected === ob.id ? "bg-blue-50" : "hover:bg-slate-50"}`}
                    onClick={() => setSelected(selected === ob.id ? null : ob.id)}
                  >
                    <td className="px-4 py-3 max-w-xs">
                      <p className="text-xs font-medium text-slate-900 leading-snug line-clamp-2">{ob.description}</p>
                    </td>
                    <td className="px-4 py-3">
                      <button className="text-xs text-[var(--accent)] hover:underline font-medium" onClick={e => { e.stopPropagation(); navigate(`/contracts/${ob.contractId}`); }}>
                        {ob.vendor}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">{ob.responsibleParty}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-mono font-medium ${ob.status === "overdue" ? "text-red-600" : ob.status === "due_soon" ? "text-amber-600" : "text-slate-600"}`}>
                        {ob.dueDate}
                      </span>
                    </td>
                    <td className="px-4 py-3"><PriorityBadge priority={ob.priority} /></td>
                    <td className="px-4 py-3"><StatusBadge status={ob.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail Panel */}
        {selectedOb && (
          <div className="w-88 flex-shrink-0" style={{ width: "352px" }}>
            <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden sticky top-4">
              <div className="px-4 py-3 border-b border-[var(--border)] bg-slate-50">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <PriorityBadge priority={selectedOb.priority} />
                    <StatusBadge status={selectedOb.status} />
                  </div>
                  <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                </div>
              </div>
              <div className="p-4 space-y-4">
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Obligation</p>
                  <p className="text-sm font-medium text-slate-900 leading-snug">{selectedOb.description}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {[
                    { label: "Contract", value: selectedOb.vendor },
                    { label: "Responsible", value: selectedOb.responsibleParty },
                    { label: "Due Date", value: selectedOb.dueDate },
                    { label: "Frequency", value: selectedOb.frequency },
                  ].map(f => (
                    <div key={f.label}>
                      <p className="text-slate-400 mb-0.5">{f.label}</p>
                      <p className="font-medium text-slate-800">{f.value}</p>
                    </div>
                  ))}
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Source Clause</p>
                  <p className="text-xs font-medium text-slate-700">{selectedOb.sourceClause}</p>
                  <p className="text-xs text-slate-400">Page {selectedOb.sourcePage}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Evidence</p>
                  <blockquote className="text-xs text-slate-600 italic bg-blue-50 border-l-4 border-[var(--accent)] px-3 py-2 rounded-r leading-relaxed">
                    "{selectedOb.evidence}"
                  </blockquote>
                </div>
                <div className="border-t border-[var(--border)] pt-3 flex gap-2">
                  <button onClick={() => navigate(`/contracts/${selectedOb.contractId}`)}
                    className="flex-1 px-3 py-1.5 text-xs border border-[var(--border)] rounded text-slate-700 hover:bg-slate-50 transition-colors font-medium">
                    View Contract
                  </button>
                  <button className="flex-1 px-3 py-1.5 text-xs bg-[var(--primary)] text-white rounded hover:bg-[#16304f] transition-colors font-medium">
                    Mark Complete
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
