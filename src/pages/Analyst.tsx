/**
 * ContractIQ — AI Analyst Page (Phase 10 & Phase 15A–15D)
 *
 * Evidence-first natural language contract interrogation.
 * Features:
 *  - 15A: Single & multi-contract selection (1–10 contracts) with query history and suggested templates
 *  - 15B: Grounded answers with claim-by-claim verification and clickable citation links
 *  - 15C: Traceable citations resolving to contract title, page number, chunk ID, and exact verbatim snippet
 *  - 15D: Clean expandable retrieval diagnostic panel showing strategy, retrieved chunks, RRF/vector metrics, context size, and latency
 */

import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { contractsApi, analystApi } from "../api/services";
import type { ContractResponse, AnalystQueryResponse } from "../api/types";
import { ApiError } from "../api/client";

interface QueryHistoryItem {
  id: string;
  query: string;
  timestamp: string;
  contractIds: string[];
  status: string;
  confidence: number;
}

export default function Analyst() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialContractId = searchParams.get("contractId");

  const [contracts, setContracts] = useState<ContractResponse[]>([]);
  const [contractsMap, setContractsMap] = useState<Record<string, ContractResponse>>({});
  const [selectedContractIds, setSelectedContractIds] = useState<string[]>(
    initialContractId ? [initialContractId] : []
  );
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalystQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  // Recent query history stored in localStorage for session continuity
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>(() => {
    try {
      const saved = localStorage.getItem("contractiq_analyst_history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    contractsApi
      .list({ limit: 100 })
      .then((res) => {
        setContracts(res.items);
        const map: Record<string, ContractResponse> = {};
        res.items.forEach((c) => {
          map[c.id] = c;
        });
        setContractsMap(map);

        if (!initialContractId && res.items.length > 0 && selectedContractIds.length === 0) {
          setSelectedContractIds([res.items[0].id]);
        }
      })
      .catch((err) => console.error("Failed to load contracts for analyst", err));
  }, [initialContractId]);

  // Sync selected contract to URL if single contract
  useEffect(() => {
    if (selectedContractIds.length === 1) {
      setSearchParams({ contractId: selectedContractIds[0] }, { replace: true });
    } else if (selectedContractIds.length === 0) {
      setSearchParams({}, { replace: true });
    }
  }, [selectedContractIds, setSearchParams]);

  const toggleContractSelection = (id: string) => {
    setSelectedContractIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((item) => item !== id);
      }
      if (prev.length >= 10) {
        return prev;
      }
      return [...prev, id];
    });
  };

  const selectAllContracts = () => {
    const top10 = contracts.slice(0, 10).map((c) => c.id);
    setSelectedContractIds(top10);
  };

  const clearSelection = () => {
    setSelectedContractIds([]);
  };

  const handleAsk = async (e?: React.FormEvent, customQuery?: string) => {
    if (e) e.preventDefault();
    const queryText = (customQuery || query).trim();
    if (!queryText || selectedContractIds.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setActiveCitation(null);

    try {
      const response = await analystApi.query({
        contract_ids: selectedContractIds,
        query: queryText,
        include_debug: true,
      });
      setResult(response);

      // Save to recent query history
      const newHistoryItem: QueryHistoryItem = {
        id: Date.now().toString(),
        query: queryText,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        contractIds: [...selectedContractIds],
        status: response.status,
        confidence: response.confidence_score,
      };

      setQueryHistory((prev) => {
        const filtered = prev.filter((h) => h.query.toLowerCase() !== queryText.toLowerCase());
        const updated = [newHistoryItem, ...filtered].slice(0, 10);
        try {
          localStorage.setItem("contractiq_analyst_history", JSON.stringify(updated));
        } catch {}
        return updated;
      });
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to query AI Analyst. Ensure documents have been extracted and embedded.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHistory = (item: QueryHistoryItem) => {
    setQuery(item.query);
    // If contracts are still in list, select them
    const validIds = item.contractIds.filter((cid) => contracts.some((c) => c.id === cid));
    if (validIds.length > 0) {
      setSelectedContractIds(validIds);
    }
    handleAsk(undefined, item.query);
  };

  const isInsufficientEvidence =
    result &&
    (result.status === "insufficient_evidence" ||
      result.confidence_score === 0 ||
      result.citations.length === 0 ||
      result.answer.toLowerCase().includes("no sufficient evidence") ||
      result.answer.toLowerCase().includes("not found in the provided contract"));

  return (
    <div className="p-6 max-w-screen-xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">AI Contract Analyst</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Grounded multi-contract intelligence powered by hybrid retrieval & 6-tier citation verification
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/compare")}
            className="px-3 py-1.5 text-xs font-medium border border-[var(--border)] rounded text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Structured Compare
          </button>
          <button
            onClick={() => navigate("/contracts")}
            className="px-3 py-1.5 text-xs font-medium border border-[var(--border)] rounded text-slate-600 hover:bg-slate-50 transition-colors"
          >
            Contract Library
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Scope Selector & Suggestions */}
        <div className="lg:col-span-1 space-y-4">
          {/* Scope Selector */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                Document Scope ({selectedContractIds.length}/10)
              </h3>
              <div className="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  onClick={selectAllContracts}
                  className="text-[var(--accent)] hover:underline"
                >
                  All (up to 10)
                </button>
                <span className="text-slate-300">·</span>
                <button
                  type="button"
                  onClick={clearSelection}
                  className="text-slate-400 hover:text-slate-600"
                >
                  Clear
                </button>
              </div>
            </div>

            {contracts.length === 0 ? (
              <p className="text-xs text-slate-400 py-2">No contracts found in workspace.</p>
            ) : (
              <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
                {contracts.map((c) => {
                  const isSelected = selectedContractIds.includes(c.id);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleContractSelection(c.id)}
                      className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors flex items-center justify-between border ${
                        isSelected
                          ? "bg-[var(--accent)] text-white border-[var(--accent)] font-medium"
                          : "bg-slate-50 text-slate-700 border-slate-100 hover:bg-slate-100"
                      }`}
                    >
                      <span className="truncate flex-1 mr-2">{c.title}</span>
                      {isSelected && (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="flex-shrink-0">
                          <path d="M2.5 6l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-slate-400 mt-2.5 leading-relaxed">
              Select 1 contract for focused clause analysis, or 2–10 for cross-contract synthesis.
            </p>
          </div>

          {/* Quick Legal Questions */}
          <div className="bg-white border border-[var(--border)] rounded-lg p-4 shadow-sm">
            <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2.5">
              Suggested Questions
            </h3>
            <div className="space-y-1.5">
              {[
                "What is the required notice period for termination?",
                "What are the auto-renewal terms and opt-out deadlines?",
                "What is the limitation of liability cap?",
                "Which jurisdiction and governing law applies?",
                "What are the vendor's confidentiality and data protection obligations?",
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => {
                    setQuery(q);
                    handleAsk(undefined, q);
                  }}
                  className="w-full text-left p-2 rounded bg-slate-50 hover:bg-slate-100 border border-slate-100 text-xs text-slate-700 transition-colors leading-snug"
                >
                  "{q}"
                </button>
              ))}
            </div>
          </div>

          {/* Query History */}
          {queryHistory.length > 0 && (
            <div className="bg-white border border-[var(--border)] rounded-lg p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                  Recent Inquiries
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    setQueryHistory([]);
                    localStorage.removeItem("contractiq_analyst_history");
                  }}
                  className="text-[11px] text-slate-400 hover:text-slate-600"
                >
                  Clear
                </button>
              </div>
              <div className="space-y-1.5">
                {queryHistory.slice(0, 5).map((h) => (
                  <button
                    key={h.id}
                    type="button"
                    onClick={() => handleSelectHistory(h)}
                    className="w-full text-left p-2 rounded bg-slate-50/70 hover:bg-slate-100 text-xs text-slate-600 transition-colors truncate block"
                    title={h.query}
                  >
                    <span className="truncate block font-medium">{h.query}</span>
                    <span className="text-[10px] text-slate-400 mt-0.5 block">
                      {h.timestamp} · {h.contractIds.length} doc(s)
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Query Form & Grounded Answer */}
        <div className="lg:col-span-3 space-y-4">
          {/* Query Form */}
          <form onSubmit={handleAsk} className="bg-white border border-[var(--border)] rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Ask Legal & Compliance Question
              </label>
              <span className="text-xs text-slate-400">
                {selectedContractIds.length === 0 ? (
                  <span className="text-amber-600 font-medium">Select at least 1 document</span>
                ) : (
                  <span>
                    Searching <strong className="text-slate-700">{selectedContractIds.length}</strong> contract{selectedContractIds.length > 1 ? "s" : ""}
                  </span>
                )}
              </span>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask about renewal terms, notice periods, liability caps, indemnification, dispute resolution..."
                className="flex-1 px-3.5 py-2.5 text-sm border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent outline-none transition-all placeholder:text-slate-400"
              />
              <button
                type="submit"
                disabled={loading || !query.trim() || selectedContractIds.length === 0}
                className="px-5 py-2.5 bg-[var(--primary)] hover:bg-[#16304f] text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 flex-shrink-0"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M13 1L6 8M13 1L8.5 13 6 8 1 5.5 13 1z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>Ask Analyst</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2.5">
              <svg className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="font-semibold">Analysis Failed</p>
                <p className="text-xs mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Insufficient Evidence Warning Banner */}
          {isInsufficientEvidence && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-start gap-3 shadow-sm">
              <svg className="w-5 h-5 flex-shrink-0 text-amber-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div className="flex-1">
                <div className="font-semibold text-amber-900">Insufficient Evidence In Scope</div>
                <div className="text-xs text-amber-700 mt-0.5 leading-relaxed">
                  ContractIQ strictly answers only from verifiable contract text. No operative clause or evidence was found matching this question in the selected document scope. The engine does not extrapolate or fabricate terms.
                </div>
              </div>
            </div>
          )}

          {/* Grounded Response Panel */}
          {result && (
            <div className="bg-white border border-[var(--border)] rounded-lg p-6 space-y-6 shadow-sm">
              {/* Answer Header */}
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                        isInsufficientEvidence
                          ? "bg-amber-100 text-amber-800"
                          : "bg-blue-50 text-blue-700"
                      }`}
                    >
                      {isInsufficientEvidence ? "Unresolved / No Evidence" : "Grounded Response"}
                    </span>
                    <span className="text-xs text-slate-400">
                      Confidence: {(result.confidence_score * 100).toFixed(0)}%
                    </span>
                    <span className="text-xs text-slate-300">·</span>
                    <span className="text-xs text-slate-400">
                      {result.queried_contract_ids?.length || selectedContractIds.length} Document(s) Queried
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-slate-900 mt-1">{result.query}</h2>
                </div>
                {result.retrieval_debug && (
                  <button
                    type="button"
                    onClick={() => setShowDebug(!showDebug)}
                    className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1 font-medium"
                  >
                    <span>{showDebug ? "Hide Diagnostics" : "Retrieval Diagnostics"}</span>
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      className={`transition-transform ${showDebug ? "rotate-180" : ""}`}
                    >
                      <path d="M2.5 4.5l3.5 3.5 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                )}
              </div>

              {/* Main Answer Text */}
              <div className="text-sm text-slate-800 leading-relaxed bg-slate-50/70 p-4 rounded-lg border border-slate-100">
                {result.answer}
              </div>

              {/* Factual Claims Breakdown */}
              {result.claims && result.claims.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                      Structured Factual Claims ({result.claims.length})
                    </h4>
                    <span className="text-[11px] text-slate-400">
                      Click citation numbers to highlight source evidence
                    </span>
                  </div>
                  <div className="space-y-2">
                    {result.claims.map((claim, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-md border text-xs flex items-start justify-between gap-3 transition-colors ${
                          claim.is_supported
                            ? "bg-white border-[var(--border)]"
                            : "bg-amber-50/50 border-amber-200"
                        }`}
                      >
                        <div className="flex-1">
                          <p className="text-slate-800 font-medium leading-snug">{claim.claim_text}</p>
                          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-slate-500 flex-wrap">
                            <span>Evidence:</span>
                            {claim.citation_indices && claim.citation_indices.length > 0 ? (
                              claim.citation_indices.map((ci) => (
                                <button
                                  key={ci}
                                  type="button"
                                  onClick={() => setActiveCitation(activeCitation === ci ? null : ci)}
                                  className={`px-2 py-0.5 rounded font-mono text-xs transition-colors ${
                                    activeCitation === ci
                                      ? "bg-[var(--accent)] text-white font-bold"
                                      : "bg-blue-50 text-[var(--accent)] hover:bg-blue-100"
                                  }`}
                                  title="Jump to supporting citation"
                                >
                                  [{ci}]
                                </button>
                              ))
                            ) : (
                              <span className="text-amber-600 italic">No citation linked</span>
                            )}
                          </div>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase flex-shrink-0 ${
                            claim.is_supported
                              ? "bg-green-50 text-green-700"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {claim.is_supported ? "Verified Claim" : "Unverified"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Citations List */}
              {result.citations && result.citations.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2.5">
                    Supporting Contract Evidence ({result.citations.length})
                  </h4>
                  <div className="space-y-2.5">
                    {result.citations.map((cit, idx) => {
                      const citationIndex = cit.citation_index ?? idx + 1;
                      const isHighlighted = activeCitation === citationIndex;
                      const parentContract = contractsMap[cit.contract_id];

                      return (
                        <div
                          key={idx}
                          className={`p-3 rounded border text-xs transition-all ${
                            isHighlighted
                              ? "bg-blue-50/70 border-[var(--accent)] ring-1 ring-[var(--accent)] shadow-sm"
                              : "bg-slate-50 border-slate-200"
                          }`}
                        >
                          <div className="flex items-center justify-between text-slate-600 mb-1.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                                [{citationIndex}] Page {cit.page_number ?? "N/A"}
                              </span>
                              {parentContract && (
                                <button
                                  type="button"
                                  onClick={() => navigate(`/contracts/${parentContract.id}`)}
                                  className="text-[var(--accent)] hover:underline font-medium truncate max-w-xs"
                                >
                                  {parentContract.title}
                                </button>
                              )}
                            </div>
                            {cit.chunk_id && (
                              <span className="text-[10px] text-slate-400 font-mono">
                                Chunk: {cit.chunk_id.substring(0, 8)}...
                              </span>
                            )}
                          </div>
                          <blockquote className="text-slate-700 italic border-l-2 border-slate-300 pl-3 py-1 bg-white/60 rounded-r leading-relaxed">
                            "{cit.snippet}"
                          </blockquote>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Retrieval Diagnostics Section (15D) */}
              {showDebug && result.retrieval_debug && (
                <div className="border border-slate-200 rounded-lg p-4 bg-slate-900 text-slate-200 space-y-3 font-mono text-xs">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="font-bold text-blue-400 uppercase tracking-wider">
                      Retrieval Pipeline Diagnostics
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Latency: {result.retrieval_debug.execution_time_ms ? `${result.retrieval_debug.execution_time_ms.toFixed(1)} ms` : "—"}
                    </span>
                  </div>

                  {/* Summary Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    <div className="bg-slate-800/80 p-2 rounded">
                      <span className="text-slate-400 block">Method:</span>
                      <span className="text-white font-semibold">{result.retrieval_debug.retrieval_method}</span>
                    </div>
                    <div className="bg-slate-800/80 p-2 rounded">
                      <span className="text-slate-400 block">Contracts Searched:</span>
                      <span className="text-white font-semibold">{result.retrieval_debug.total_contracts_searched}</span>
                    </div>
                    <div className="bg-slate-800/80 p-2 rounded">
                      <span className="text-slate-400 block">Chunks Considered:</span>
                      <span className="text-white font-semibold">{result.retrieval_debug.total_chunks_considered}</span>
                    </div>
                    <div className="bg-slate-800/80 p-2 rounded">
                      <span className="text-slate-400 block">Context Length:</span>
                      <span className="text-white font-semibold">{result.retrieval_debug.context_char_count} chars</span>
                    </div>
                  </div>

                  {/* Selected Chunks Table */}
                  {result.retrieval_debug.selected_chunks && result.retrieval_debug.selected_chunks.length > 0 && (
                    <div className="mt-3">
                      <div className="text-slate-400 font-semibold mb-1 text-[11px]">
                        Injected Context Chunks ({result.retrieval_debug.selected_chunks.length}):
                      </div>
                      <div className="overflow-x-auto max-h-48 border border-slate-800 rounded">
                        <table className="w-full text-left text-[11px]">
                          <thead className="bg-slate-800 text-slate-300">
                            <tr>
                              <th className="p-1.5">Page</th>
                              <th className="p-1.5">RRF Score</th>
                              <th className="p-1.5">Semantic Rank</th>
                              <th className="p-1.5">Keyword Rank</th>
                              <th className="p-1.5">Length</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800">
                            {result.retrieval_debug.selected_chunks.map((chk: any, i: number) => (
                              <tr key={i} className="hover:bg-slate-800/50">
                                <td className="p-1.5 font-bold text-blue-300">P.{chk.page_number}</td>
                                <td className="p-1.5 text-emerald-400">{chk.hybrid_score?.toFixed(4) ?? "—"}</td>
                                <td className="p-1.5">{chk.semantic_rank ? `#${chk.semantic_rank}` : "—"}</td>
                                <td className="p-1.5">{chk.keyword_rank ? `#${chk.keyword_rank}` : "—"}</td>
                                <td className="p-1.5 text-slate-400">{chk.char_length} chars</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <div className="text-[10px] text-slate-500 pt-1">
                    Rule 12: Zero raw embeddings or secrets exposed. Provenance strictly tracked to contract chunks.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
