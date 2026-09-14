/**
 * ContractIQ — Audit Log Page
 */

import { useState } from "react";
import { auditEvents } from "../data/mock";

export default function Audit() {
  const [search, setSearch] = useState("");

  const filtered = auditEvents.filter(
    (e) =>
      e.user.toLowerCase().includes(search.toLowerCase()) ||
      e.action.toLowerCase().includes(search.toLowerCase()) ||
      e.resource.toLowerCase().includes(search.toLowerCase()) ||
      e.userEmail.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-screen-xl mx-auto flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Audit Log</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Immutable audit record of all user activities, contract access, and system operations
          </p>
        </div>
      </div>

      <div className="bg-white border border-[var(--border)] rounded-lg p-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by user, action, or resource..."
          className="w-full max-w-md px-3.5 py-2 text-sm border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent outline-none transition-all"
        />
      </div>

      <div className="bg-white border border-[var(--border)] rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-[var(--border)] text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="px-5 py-3">Timestamp</th>
              <th className="px-5 py-3">User</th>
              <th className="px-5 py-3">Action</th>
              <th className="px-5 py-3">Resource</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">IP Address</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {filtered.map((event) => (
              <tr key={event.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-5 py-3 font-mono text-xs text-slate-500 whitespace-nowrap">
                  {event.timestamp}
                </td>
                <td className="px-5 py-3">
                  <div className="font-medium text-slate-900">{event.user}</div>
                  <div className="text-[11px] text-slate-400">{event.userEmail}</div>
                </td>
                <td className="px-5 py-3">
                  <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-100 text-slate-700">
                    {event.action}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-700 font-mono text-xs">{event.resource}</td>
                <td className="px-5 py-3">
                  <span
                    className={`px-2 py-0.5 text-xs font-semibold rounded uppercase ${
                      event.status === "success"
                        ? "bg-green-50 text-green-700"
                        : event.status === "failed"
                        ? "bg-red-50 text-red-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {event.status}
                  </span>
                </td>
                <td className="px-5 py-3 font-mono text-xs text-slate-400">{event.ip}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
