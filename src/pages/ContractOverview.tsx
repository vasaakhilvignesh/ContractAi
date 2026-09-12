import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { contracts, risks, obligations } from "../data/mock";
import { RiskBadge, StatusBadge, PriorityBadge } from "../components/ui/Badge";

const tabs = ["Overview", "Clauses", "Obligations", "Risks", "AI Analyst", "Evidence"];

const sampleClauses = [
  { type: "Renewal", summary: "Auto-renewal for 12-month terms unless 30-day written notice provided.", risk: "high" as const, page: 12, confidence: 0.97 },
  { type: "Termination", summary: "Either party may terminate for convenience with 30-day notice. Immediate termination for material breach.", risk: "medium" as const, page: 34, confidence: 0.94 },
  { type: "Liability", summary: "Liability limited to fees paid in the preceding 12 months. No consequential damages.", risk: "low" as const, page: 41, confidence: 0.96 },
  { type: "Confidentiality", summary: "5-year confidentiality obligation surviving termination. Excludes publicly available information.", risk: "none" as const, page: 27, confidence: 0.98 },
  { type: "Indemnification", summary: "Mutual indemnification for IP infringement claims. No cap specified for IP indemnification.", risk: "high" as const, page: 41, confidence: 0.91 },
  { type: "Governing Law", summary: "Governed by the laws of the State of California. Disputes resolved via arbitration in San Francisco.", risk: "none" as const, page: 52, confidence: 0.99 },
  { type: "Payment", summary: "Net-30 payment terms. 1.5% monthly interest on late payments after 30-day grace period.", risk: "medium" as const, page: 19, confidence: 0.95 },
  { type: "Data Protection", summary: "Data processing in accordance with applicable laws. Annual security assessment required.", risk: "low" as const, page: 38, confidence: 0.93 },
];

export default function ContractOverview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Overview");
  const [expandedRisk, setExpandedRisk] = useState<string | null>(null);

  const contract = contracts.find((c) => c.id === id) ?? contracts[0];
  const contractRisks = risks.filter((r) => r.contractId === contract.id);
  const contractObligations = obligations.filter((o) => o.contractId === contract.id);

  return (
    <div className="p-6 max-w-screen-xl mx-auto">
      {/* Contract Header */}
      <div className="bg-white border border-[var(--border)] rounded-lg p-5 mb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <button onClick={() => navigate("/contracts")} className="text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <h1 className="text-lg font-bold text-slate-900 tracking-tight truncate">{contract.name}</h1>
              <RiskBadge level={contract.riskLevel} />
              <StatusBadge status={contract.status} />
            </div>
            <div className="flex items-center gap-5 text-sm text-slate-500 flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Vendor:</span>
                <span className="font-medium text-slate-700">{contract.vendor}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Type:</span>
                <span className="font-mono text-slate-600">{contract.type}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Effective:</span>
                <span className="font-mono text-slate-600">{contract.effectiveDate}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Expires:</span>
                <span className="font-mono text-slate-600">{contract.expirationDate}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Value:</span>
                <span className="font-medium text-slate-700">{contract.value}</span>
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded text-slate-600 hover:bg-slate-50 transition-colors">
              Compare
            </button>
            <button
              onClick={() => navigate("/analyst")}
              className="px-3 py-1.5 text-sm font-medium bg-[var(--accent)] text-white rounded hover:bg-blue-700 transition-colors"
            >
              Ask AI Analyst
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-5 gap-3 mt-4 pt-4 border-t border-[var(--border)]">
          {[
            { label: "Overall Risk", value: contract.riskLevel.charAt(0).toUpperCase() + contract.riskLevel.slice(1), color: contract.riskLevel === "critical" ? "text-red-600" : contract.riskLevel === "high" ? "text-orange-600" : "text-slate-700" },
            { label: "Renewal Date", value: contract.renewalDate, color: "text-slate-700" },
            { label: "Notice Period", value: contract.noticePeriod, color: "text-slate-700" },
            { label: "Active Obligations", value: String(contractObligations.length || contract.obligations), color: "text-slate-700" },
            { label: "Risk Signals", value: String(contractRisks.length), color: contractRisks.length > 0 ? "text-orange-600" : "text-slate-700" },
          ].map((item) => (
            <div key={item.label} className="text-center px-3 py-2 bg-slate-50 rounded border border-[var(--border)]">
              <div className={`text-base font-bold ${item.color}`}>{item.value}</div>
              <div className="text-xs text-slate-400 mt-0.5">{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-[var(--border)] mb-4 bg-white rounded-t-lg px-4">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? "border-[var(--accent)] text-[var(--accent)]"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "Overview" && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 space-y-4">
            {/* Contract Summary */}
            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Contract Summary</h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                This {contract.type} between the Company and {contract.vendor} governs the provision of professional services
                for a term of {Math.round((new Date(contract.expirationDate).getTime() - new Date(contract.effectiveDate).getTime()) / (365.25 * 86400000))} year(s),
                valued at {contract.value}. The agreement includes auto-renewal provisions, liability limitations,
                mutual confidentiality obligations, and standard termination rights. {contractRisks.length} risk signal(s) have been identified requiring review.
              </p>
            </div>

            {/* Key Terms */}
            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Key Terms</h3>
              <div className="divide-y divide-[var(--border)]">
                {[
                  { label: "Contract Value", value: contract.value },
                  { label: "Payment Terms", value: "Net-30" },
                  { label: "Auto-Renewal", value: "Yes — 12-month terms" },
                  { label: "Notice Period", value: contract.noticePeriod },
                  { label: "Liability Cap", value: "12 months of fees paid" },
                  { label: "Confidentiality Term", value: "5 years post-termination" },
                  { label: "Governing Law", value: "California, USA" },
                  { label: "Dispute Resolution", value: "Binding Arbitration — San Francisco" },
                ].map((term) => (
                  <div key={term.label} className="flex items-center justify-between py-2">
                    <span className="text-xs text-slate-500 font-medium">{term.label}</span>
                    <span className="text-xs text-slate-800 font-medium">{term.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {/* Important Dates */}
            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Important Dates</h3>
              <div className="space-y-2.5">
                {[
                  { label: "Effective Date", value: contract.effectiveDate, icon: "📅" },
                  { label: "Expiration Date", value: contract.expirationDate, urgent: true },
                  { label: "Renewal Date", value: contract.renewalDate, urgent: true },
                  { label: "Notice Deadline", value: "2024-02-14", urgent: true },
                  { label: "Last Updated", value: contract.lastUpdated },
                ].map((date) => (
                  <div key={date.label} className={`flex justify-between items-center px-2 py-1.5 rounded ${date.urgent ? "bg-amber-50 border border-amber-100" : ""}`}>
                    <span className="text-xs text-slate-500">{date.label}</span>
                    <span className={`text-xs font-mono font-medium ${date.urgent ? "text-amber-700" : "text-slate-700"}`}>{date.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Signals */}
            {contractRisks.length > 0 && (
              <div className="bg-white border border-[var(--border)] rounded-lg p-5">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Risk Signals</h3>
                <div className="space-y-2">
                  {contractRisks.map((r) => (
                    <div key={r.id} className="p-2.5 rounded border border-[var(--border)] hover:bg-slate-50 cursor-pointer" onClick={() => setActiveTab("Risks")}>
                      <div className="flex items-center gap-2 mb-1">
                        <RiskBadge level={r.severity} size="sm" />
                        <span className="text-xs font-medium text-slate-700">{r.type}</span>
                      </div>
                      <p className="text-xs text-slate-500 leading-snug">{r.summary.substring(0, 80)}...</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "Clauses" && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 mb-4">
            <select className="px-3 py-1.5 text-xs border border-[var(--border)] rounded text-slate-700 bg-white focus:outline-none">
              <option>All Clause Types</option>
            </select>
            <select className="px-3 py-1.5 text-xs border border-[var(--border)] rounded text-slate-700 bg-white focus:outline-none">
              <option>All Risk Levels</option>
            </select>
          </div>
          {sampleClauses.map((clause, i) => (
            <div key={i} className="bg-white border border-[var(--border)] rounded-lg p-4 hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-slate-900 font-mono bg-slate-100 px-2 py-0.5 rounded">{clause.type}</span>
                    <RiskBadge level={clause.risk} size="sm" />
                    <span className="text-xs text-slate-400">Page {clause.page}</span>
                    <span className="text-xs text-slate-400">·</span>
                    <span className="text-xs text-slate-400">Confidence: {(clause.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <p className="text-sm text-slate-700 leading-relaxed">{clause.summary}</p>
                </div>
                <button className="flex-shrink-0 text-xs text-[var(--accent)] hover:text-blue-700 font-medium border border-blue-100 bg-blue-50 px-2.5 py-1 rounded transition-colors">
                  View Source
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === "Obligations" && (
        <div className="space-y-3">
          {contractObligations.length === 0 ? (
            <div className="bg-white border border-[var(--border)] rounded-lg p-12 text-center text-slate-400">
              <p className="font-medium text-slate-500">No obligations found for this contract</p>
            </div>
          ) : (
            contractObligations.map((ob) => (
              <div key={ob.id} className="bg-white border border-[var(--border)] rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <PriorityBadge priority={ob.priority} />
                      <StatusBadge status={ob.status} />
                    </div>
                    <p className="text-sm font-medium text-slate-800 mb-1">{ob.description}</p>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span>Responsible: <span className="font-medium text-slate-700">{ob.responsibleParty}</span></span>
                      <span>Due: <span className="font-mono font-medium text-slate-700">{ob.dueDate}</span></span>
                      <span>Freq: <span className="font-medium text-slate-700">{ob.frequency}</span></span>
                    </div>
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-[var(--border)]">
                  <div className="flex items-start gap-2">
                    <span className="text-xs font-medium text-slate-400 flex-shrink-0">Evidence:</span>
                    <p className="text-xs text-slate-600 italic leading-relaxed">"{ob.evidence}"</p>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{ob.sourceClause} · Page {ob.sourcePage}</div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "Risks" && (
        <div className="space-y-3">
          {contractRisks.length === 0 ? (
            <div className="bg-white border border-[var(--border)] rounded-lg p-12 text-center">
              <p className="font-medium text-green-600">No risk signals detected for this contract</p>
            </div>
          ) : (
            contractRisks.map((risk) => (
              <div key={risk.id} className="bg-white border border-[var(--border)] rounded-lg overflow-hidden">
                <div
                  className="flex items-start gap-3 p-4 cursor-pointer hover:bg-slate-50 transition-colors"
                  onClick={() => setExpandedRisk(expandedRisk === risk.id ? null : risk.id)}
                >
                  <div className={`w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0 ${
                    risk.severity === "critical" ? "bg-red-500" :
                    risk.severity === "high" ? "bg-orange-500" :
                    risk.severity === "medium" ? "bg-amber-500" : "bg-green-500"
                  }`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-slate-900">{risk.type}</span>
                      <RiskBadge level={risk.severity} size="sm" />
                      <StatusBadge status={risk.status} />
                    </div>
                    <p className="text-sm text-slate-600">{risk.summary}</p>
                  </div>
                  <svg width="14" height="14" className={`text-slate-400 flex-shrink-0 transition-transform ${expandedRisk === risk.id ? "rotate-180" : ""}`} viewBox="0 0 14 14" fill="none">
                    <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                {expandedRisk === risk.id && (
                  <div className="border-t border-[var(--border)] bg-slate-50 p-4 space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Triggered Rule</p>
                      <p className="text-sm text-slate-700 font-mono bg-white border border-[var(--border)] px-3 py-2 rounded">{risk.rule}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Extracted Fact</p>
                      <p className="text-sm text-slate-700 font-medium">{risk.extractedFact}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Evidence · {risk.sourceClause} · Page {risk.sourcePage}</p>
                      <blockquote className="text-sm text-slate-600 italic bg-amber-50 border-l-4 border-amber-400 px-3 py-2.5 rounded-r">
                        {risk.evidenceSnippet}
                      </blockquote>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Recommended Action</p>
                      <p className="text-sm text-slate-700">{risk.recommendedAction}</p>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "AI Analyst" && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-6 text-center">
          <div className="max-w-md mx-auto">
            <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M10 2l2 5 5.5.5-4 4 1 5.5L10 14 5.5 17l1-5.5-4-4L8 7l2-5z" stroke="#2563EB" strokeWidth="1.5" strokeLinejoin="round"/>
              </svg>
            </div>
            <p className="text-slate-700 font-medium mb-1">Ask about this contract</p>
            <p className="text-sm text-slate-500 mb-4">Questions are answered using evidence extracted from this specific contract.</p>
            <button onClick={() => navigate("/analyst")} className="px-4 py-2 bg-[var(--accent)] text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors">
              Open AI Analyst
            </button>
          </div>
        </div>
      )}

      {activeTab === "Evidence" && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-6 text-center">
          <p className="text-sm text-slate-500">Evidence viewer — select a risk signal or clause to trace evidence to its source page.</p>
        </div>
      )}
    </div>
  );
}
