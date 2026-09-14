import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { contractsApi, obligationsApi } from "../api/services";
import type {
  ContractResponse,
  ObligationDetailResponse,
  RiskSignalResponse,
  ClauseResponse,
  ContractFactResponse,
  DocumentChunkResponse,
} from "../api/types";
import { contracts as mockContracts, risks as mockRisks, obligations as mockObligations } from "../data/mock";
import { RiskBadge, StatusBadge, PriorityBadge } from "../components/ui/Badge";

const tabs = ["Overview", "Document & Evidence", "Clauses", "Obligations", "Risks", "Facts"];

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

  const [contractData, setContractData] = useState<any>(null);
  const [contractObligations, setContractObligations] = useState<any[]>([]);
  const [contractRisks, setContractRisks] = useState<any[]>([]);
  const [contractClauses, setContractClauses] = useState<ClauseResponse[]>([]);
  const [contractFacts, setContractFacts] = useState<ContractFactResponse[]>([]);
  const [contractChunks, setContractChunks] = useState<DocumentChunkResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Document & Evidence Viewer states
  const [selectedPage, setSelectedPage] = useState<number>(1);
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    // Fetch real contract
    contractsApi
      .get(id)
      .then((c: ContractResponse) => {
        setContractData({
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
        });

        // Fetch real obligations
        obligationsApi
          .query(c.id)
          .then((obRes) => {
            if (obRes.obligations && obRes.obligations.length > 0) {
              setContractObligations(
                obRes.obligations.map((o: ObligationDetailResponse) => ({
                  id: o.id,
                  contractId: o.contract_id,
                  description: o.description,
                  responsibleParty: o.responsible_party || "Mutual",
                  dueDate: o.due_date_raw || "—",
                  frequency: o.recurrence_frequency || (o.is_recurring ? "Recurring" : "One-time"),
                  priority: o.priority || "medium",
                  status: o.status || "pending",
                  sourceClause: o.obligation_type || "General",
                  sourcePage: o.evidence_citations?.[0]?.page_number || 1,
                  chunkId: o.evidence_citations?.[0]?.chunk_id || null,
                  evidence: o.evidence_citations?.[0]?.snippet || o.description,
                }))
              );
            }
          })
          .catch(() => {});

        // Fetch real risk signals
        contractsApi
          .getRisks(c.id)
          .then((riskRes) => {
            if (riskRes.signals && riskRes.signals.length > 0) {
              setContractRisks(
                riskRes.signals.map((r: RiskSignalResponse) => ({
                  id: r.id,
                  contractId: r.contract_id,
                  severity: r.severity || "medium",
                  type: r.rule_name || r.category,
                  rule: r.rule_id,
                  summary: r.description,
                  extractedFact: r.reason,
                  sourceClause: r.category,
                  sourcePage: 1,
                  evidenceSnippet: r.reason,
                  status: "open",
                  recommendedAction: r.suggested_action || "Review terms with counsel.",
                }))
              );
            }
          })
          .catch(() => {});

        // Fetch clauses
        contractsApi
          .getClauses(c.id)
          .then((clauseRes) => {
            if (clauseRes.clauses && clauseRes.clauses.length > 0) {
              setContractClauses(clauseRes.clauses);
            }
          })
          .catch(() => {});

        // Fetch facts
        contractsApi
          .getFacts(c.id)
          .then((factRes) => {
            if (factRes.facts && factRes.facts.length > 0) {
              setContractFacts(factRes.facts);
            }
          })
          .catch(() => {});

        // Fetch chunks for document viewer
        contractsApi
          .getChunks(c.id, { limit: 100 })
          .then((chunkRes) => {
            if (chunkRes.items && chunkRes.items.length > 0) {
              setContractChunks(chunkRes.items);
            }
          })
          .catch(() => {});
      })
      .catch(() => {
        // Fallback to mock contracts if not found in database
        const mock = mockContracts.find((c) => c.id === id) ?? mockContracts[0];
        setContractData(mock);
        setContractRisks(mockRisks.filter((r) => r.contractId === mock.id));
        setContractObligations(mockObligations.filter((o) => o.contractId === mock.id));
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading || !contractData) {
    return (
      <div className="p-12 text-center text-slate-500 flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-3 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm">Loading contract intelligence & evidence graph...</p>
      </div>
    );
  }

  const contract = contractData;

  // Derive unique page list from chunks or total pages
  const totalPages = Math.max(
    contract.pages || 1,
    ...contractChunks.map((ch) => ch.page_number),
    ...contractClauses.map((cl) => cl.page_number || 1),
    1
  );
  const pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);

  // Chunks on the currently selected page
  const currentPageChunks = contractChunks.filter((ch) => ch.page_number === selectedPage);

  // Jump to specific page and highlight chunk
  const jumpToEvidence = (pageNumber?: number | null, chunkId?: string | null, entityId?: string) => {
    if (pageNumber && pageNumber >= 1) {
      setSelectedPage(pageNumber);
    }
    if (chunkId) {
      setHighlightedChunkId(chunkId);
    } else {
      setHighlightedChunkId(null);
    }
    if (entityId) {
      setSelectedEntityId(entityId);
    }
    setActiveTab("Document & Evidence");
  };

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
            <button
              onClick={() => navigate("/compare")}
              className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Compare
            </button>
            <button
              onClick={() => navigate(`/analyst?contractId=${contract.id}`)}
              className="px-3.5 py-1.5 text-xs font-medium bg-[var(--primary)] text-white rounded hover:bg-[#16304f] transition-colors flex items-center gap-1.5"
            >
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <path d="M13 1L6 8M13 1L8.5 13 6 8 1 5.5 13 1z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>Ask AI Analyst</span>
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4 pt-4 border-t border-[var(--border)]">
          {[
            { label: "Overall Risk", value: contract.riskLevel.charAt(0).toUpperCase() + contract.riskLevel.slice(1), color: contract.riskLevel === "critical" ? "text-red-600" : contract.riskLevel === "high" ? "text-orange-600" : "text-slate-700" },
            { label: "Renewal Date", value: contract.renewalDate, color: "text-slate-700" },
            { label: "Extracted Clauses", value: String(contractClauses.length || 8), color: "text-slate-700" },
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
      <div className="flex items-center gap-0 border-b border-[var(--border)] mb-4 bg-white rounded-t-lg px-4 shadow-sm">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider border-b-2 -mb-px transition-colors ${
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
            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Contract Summary</h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                This {contract.type} between the Company and {contract.vendor} governs contractual terms and responsibilities,
                valued at {contract.value}. The agreement includes renewal provisions, liability limitations,
                confidentiality obligations, and standard termination rights. {contractRisks.length} risk signal(s) have been identified requiring review.
              </p>
            </div>

            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Key Terms</h3>
              <div className="divide-y divide-[var(--border)]">
                {[
                  { label: "Contract Value", value: contract.value },
                  { label: "Payment Terms", value: "Net-30" },
                  { label: "Auto-Renewal", value: "12-month terms" },
                  { label: "Notice Period", value: contract.noticePeriod },
                  { label: "Liability Cap", value: "12 months of fees paid" },
                  { label: "Confidentiality Term", value: "5 years post-termination" },
                  { label: "Governing Law", value: "Delaware / California" },
                  { label: "Dispute Resolution", value: "Binding Arbitration" },
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
            <div className="bg-white border border-[var(--border)] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Important Dates</h3>
              <div className="space-y-2.5">
                {[
                  { label: "Effective Date", value: contract.effectiveDate },
                  { label: "Expiration Date", value: contract.expirationDate, urgent: true },
                  { label: "Renewal Date", value: contract.renewalDate, urgent: true },
                  { label: "Last Updated", value: contract.lastUpdated },
                ].map((date) => (
                  <div key={date.label} className={`flex justify-between items-center px-2 py-1.5 rounded ${date.urgent ? "bg-amber-50 border border-amber-100" : ""}`}>
                    <span className="text-xs text-slate-500">{date.label}</span>
                    <span className={`text-xs font-mono font-medium ${date.urgent ? "text-amber-700" : "text-slate-700"}`}>{date.value}</span>
                  </div>
                ))}
              </div>
            </div>

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
                <button
                  onClick={() => navigate(`/analyst?contractId=${contract.id}`)}
                  className="flex-shrink-0 text-xs text-[var(--accent)] hover:text-blue-700 font-medium border border-blue-100 bg-blue-50 px-2.5 py-1 rounded transition-colors"
                >
                  Analyze Clause
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

      {/* Tab: Document & Evidence (16D) */}
      {activeTab === "Document & Evidence" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Sub-column: Page & Chunk Navigator */}
          <div className="lg:col-span-4 bg-white border border-[var(--border)] rounded-lg p-4 shadow-sm flex flex-col h-[650px]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <div>
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Document Navigation
                </h3>
                <span className="text-[11px] text-slate-400">
                  {totalPages} Page(s) · {contractChunks.length} Chunk(s)
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  disabled={selectedPage <= 1}
                  onClick={() => setSelectedPage((p) => Math.max(1, p - 1))}
                  className="p-1 rounded border border-slate-200 disabled:opacity-30 hover:bg-slate-50"
                  title="Previous Page"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M7.5 2.5L4 6l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <span className="text-xs font-mono font-semibold px-2 py-0.5 bg-slate-100 rounded">
                  P. {selectedPage}
                </span>
                <button
                  disabled={selectedPage >= totalPages}
                  onClick={() => setSelectedPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1 rounded border border-slate-200 disabled:opacity-30 hover:bg-slate-50"
                  title="Next Page"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M4.5 2.5L8 6l-3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Quick Page Picker Buttons */}
            <div className="flex flex-wrap gap-1.5 mb-3 pb-3 border-b border-slate-100 max-h-24 overflow-y-auto">
              {pageNumbers.map((pg) => {
                const chunksOnPg = contractChunks.filter((c) => c.page_number === pg).length;
                const isSelected = selectedPage === pg;
                return (
                  <button
                    key={pg}
                    onClick={() => {
                      setSelectedPage(pg);
                      setHighlightedChunkId(null);
                    }}
                    className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
                      isSelected
                        ? "bg-[var(--accent)] text-white font-bold"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    Pg {pg} {chunksOnPg > 0 && `(${chunksOnPg})`}
                  </button>
                );
              })}
            </div>

            {/* Evidence Anchors on this page */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                Evidence In Page {selectedPage}
              </h4>

              {/* Linked Clauses on this page */}
              {contractClauses.filter((c) => c.page_number === selectedPage).map((cl) => (
                <div
                  key={cl.id}
                  onClick={() => {
                    setHighlightedChunkId(cl.source_chunk_id);
                    setSelectedEntityId(cl.id);
                  }}
                  className={`p-2 rounded border text-xs cursor-pointer transition-colors ${
                    selectedEntityId === cl.id
                      ? "bg-blue-50 border-[var(--accent)]"
                      : "bg-slate-50/70 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800 uppercase font-mono text-[10px]">
                      Clause: {cl.clause_type}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {(cl.extraction_confidence ? cl.extraction_confidence * 100 : 95).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-slate-600 text-[11px] line-clamp-2 mt-1">"{cl.verbatim_text}"</p>
                </div>
              ))}

              {/* Linked Obligations on this page */}
              {contractObligations.filter((o) => o.sourcePage === selectedPage).map((ob) => (
                <div
                  key={ob.id}
                  onClick={() => {
                    if (ob.chunkId) setHighlightedChunkId(ob.chunkId);
                    setSelectedEntityId(ob.id);
                  }}
                  className={`p-2 rounded border text-xs cursor-pointer transition-colors ${
                    selectedEntityId === ob.id
                      ? "bg-blue-50 border-[var(--accent)]"
                      : "bg-slate-50/70 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800 font-mono text-[10px]">
                      Obligation: {ob.responsibleParty}
                    </span>
                    <PriorityBadge priority={ob.priority} />
                  </div>
                  <p className="text-slate-600 text-[11px] line-clamp-2 mt-1">{ob.description}</p>
                </div>
              ))}

              {contractClauses.filter((c) => c.page_number === selectedPage).length === 0 &&
                contractObligations.filter((o) => o.sourcePage === selectedPage).length === 0 && (
                  <p className="text-xs text-slate-400 italic py-4 text-center">
                    No extracted clauses or obligations anchored directly to Page {selectedPage}.
                  </p>
                )}
            </div>
          </div>

          {/* Right Sub-column: Verbatim Source Chunk Viewer */}
          <div className="lg:col-span-8 bg-white border border-[var(--border)] rounded-lg p-5 shadow-sm flex flex-col h-[650px]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Verbatim Document Chunks · Page {selectedPage}
                </h3>
                <p className="text-xs text-slate-500">
                  Exact normalized contract text extracted from source PDF layer
                </p>
              </div>
              <button
                onClick={() => navigate(`/analyst?contractId=${contract.id}`)}
                className="text-xs px-3 py-1.5 bg-blue-50 text-[var(--accent)] rounded font-medium hover:bg-blue-100 transition-colors"
              >
                Interrogate in AI Analyst
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {currentPageChunks.length === 0 ? (
                <div className="p-12 text-center text-slate-400 border border-dashed border-slate-200 rounded-lg">
                  <p className="font-medium text-slate-600">No raw chunks stored for Page {selectedPage}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    If this document was newly added, ensure text extraction and chunking pipeline finished.
                  </p>
                </div>
              ) : (
                currentPageChunks.map((chunk) => {
                  const isHighlighted = highlightedChunkId === chunk.id;
                  return (
                    <div
                      key={chunk.id}
                      className={`p-4 rounded-lg border transition-all ${
                        isHighlighted
                          ? "bg-amber-50/60 border-amber-400 ring-2 ring-amber-300"
                          : "bg-slate-50/60 border-slate-200"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                            Chunk #{chunk.chunk_index}
                          </span>
                          {chunk.section_header && (
                            <span className="font-semibold text-slate-800 truncate max-w-sm">
                              {chunk.section_header}
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-slate-400 font-mono">
                          ID: {chunk.id.substring(0, 8)}...
                        </span>
                      </div>
                      <div className="text-xs font-mono leading-relaxed text-slate-800 whitespace-pre-wrap bg-white p-3 rounded border border-slate-100">
                        {chunk.text}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Structured Facts (16A/16D) */}
      {activeTab === "Facts" && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Extracted Structured Facts</h3>
              <p className="text-xs text-slate-500">
                Machine-readable contract facts extracted from legal clauses with page citations
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">
              {contractFacts.length} fact records
            </span>
          </div>

          {contractFacts.length === 0 ? (
            <div className="p-8 text-center text-slate-400 border border-dashed border-slate-200 rounded">
              <p className="text-sm">No structured contract facts extracted yet.</p>
              <p className="text-xs mt-1">
                Trigger fact extraction via backend pipeline or check processing status.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {contractFacts.map((fact) => (
                <div key={fact.id} className="py-3 flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono font-semibold text-slate-800 uppercase bg-slate-100 px-2 py-0.5 rounded">
                        {fact.fact_key}
                      </span>
                      <span className="text-xs text-slate-400">
                        Page {fact.page_number ?? "N/A"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-slate-900">{fact.fact_value || "—"}</div>
                    {fact.verbatim_evidence && (
                      <p className="text-xs text-slate-500 italic mt-1">
                        "{fact.verbatim_evidence}"
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => jumpToEvidence(fact.page_number, fact.source_chunk_id, fact.id)}
                    className="text-xs text-[var(--accent)] hover:underline font-medium flex-shrink-0"
                  >
                    View Source →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
