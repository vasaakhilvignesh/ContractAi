/**
 * ContractIQ — AI Analyst Page (Phase 10 & 14E)
 */

import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { contractsApi, analystApi } from "../api/services";
import type { ContractResponse, AnalystQueryResponse } from "../api/types";
import { ApiError } from "../api/client";

export default function Analyst() {
  const [searchParams] = useSearchParams();
  const initialContractId = searchParams.get("contractId");

  const [contracts, setContracts] = useState<ContractResponse[]>([]);
  const [selectedContractIds, setSelectedContractIds] = useState<string[]>(
    initialContractId ? [initialContractId] : []
  );
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalystQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);

  useEffect(() => {
    contractsApi
      .list({ limit: 100 })
      .then((res) => {
        setContracts(res.items);
        if (!initialContractId && res.items.length > 0) {
          setSelectedContractIds([res.items[0].id]);
        }
      })
      .catch((err) => console.error("Failed to load contracts for analyst", err));
  }, [initialContractId]);

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

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || selectedContractIds.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await analystApi.query({
        contract_ids: selectedContractIds,
        query: query.trim(),
        include_debug: true,
      });
      setResult(response);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to query AI Analyst. Ensure documents are chunked and embedded.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-screen-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">AI Contract Analyst</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Ask questions against single or multiple agreements with verified 6-tier citations
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Scope Selector & Suggested Queries */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white border border-[var(--border)] rounded-lg p-4">
            <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
              Document Scope ({selectedContractIds.length}/10 selected)
            </h3>
            {contracts.length === 0 ? (
              <p className="text-xs text-slate-400">No contracts found in workspace.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
                {contracts.map((c) => {
                  const isSelected = selectedContractIds.includes(c.id);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleContractSelection(c.id)}
                      className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors flex items-center justify-between ${
                        isSelected
                          ? "bg-[var(--accent)] text-white font-medium"
                          : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      <span className="truncate flex-1 mr-2">{c.title}</span>
                      {isSelected && (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M2.5 6l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-slate-400 mt-2">
              Select 1 for in-depth single contract analysis, or 2–10 for cross-contract comparison.
            </p>
          </div>

          <div className="bg-white border border-[var(--border)] rounded-lg p-4">
            <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
              Suggested Questions
            </h3>
            <div className="space-y-1.5">
              {[
                "What is the required notice period for termination?",
                "What are the auto-renewal terms and opt-out deadlines?",
                "What is the limitation of liability cap?",
                "Which jurisdiction and governing law applies?",
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuery(q)}
                  className="w-full text-left p-2 rounded bg-slate-50 hover:bg-slate-100 text-xs text-slate-700 transition-colors"
                >
                  "{q}"
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Chat/Query & Grounded Response */}
        <div className="lg:col-span-3 space-y-4">
          <form onSubmit={handleAsk} className="bg-white border border-[var(--border)] rounded-lg p-4">
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Ask Legal & Compliance Question
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask about renewal terms, notice periods, liability, obligations..."
                className="flex-1 px-3.5 py-2 text-sm border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent outline-none transition-all"
              />
              <button
                type="submit"
                disabled={loading || !query.trim() || selectedContractIds.length === 0}
                className="px-5 py-2 bg-[var(--primary)] hover:bg-[#16304f] text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <span>Ask Analyst</span>
                )}
              </button>
            </div>
          </form>

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

          {result && (
            <div className="bg-white border border-[var(--border)] rounded-lg p-6 space-y-6">
              {/* Answer Header */}
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-xs font-semibold uppercase bg-blue-50 text-blue-700">
                      Grounded Response
                    </span>
                    <span className="text-xs text-slate-400">
                      Confidence: {(result.confidence_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-slate-900 mt-1.5">{result.query}</h2>
                </div>
                {result.retrieval_debug && (
                  <button
                    type="button"
                    onClick={() => setShowDebug(!showDebug)}
                    className="text-xs text-slate-500 hover:text-slate-800 underline"
                  >
                    {showDebug ? "Hide Debug Info" : "View Retrieval Debug"}
                  </button>
                )}
              </div>

              {/* Main Answer Text */}
              <div className="text-sm text-slate-800 leading-relaxed bg-slate-50/70 p-4 rounded-lg border border-slate-100">
                {result.answer}
              </div>

              {/* Claims Breakdown */}
              {result.claims && result.claims.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2.5">
                    Structured Factual Claims & Citations
                  </h4>
                  <div className="space-y-2">
                    {result.claims.map((claim, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-md border text-xs flex items-start justify-between gap-3 ${
                          claim.is_supported
                            ? "bg-white border-[var(--border)]"
                            : "bg-amber-50/50 border-amber-200"
                        }`}
                      >
                        <div className="flex-1">
                          <p className="text-slate-800 font-medium">{claim.claim_text}</p>
                          <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-slate-500">
                            <span>Evidence References:</span>
                            {claim.citation_indices && claim.citation_indices.length > 0 ? (
                              claim.citation_indices.map((ci) => (
                                <span
                                  key={ci}
                                  className="px-1.5 py-0.2 bg-slate-200 text-slate-700 rounded font-mono"
                                >
                                  [{ci}]
                                </span>
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
                  <div className="space-y-2">
                    {result.citations.map((cit, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 rounded border border-slate-200 text-xs">
                        <div className="flex items-center justify-between text-slate-600 mb-1">
                          <span className="font-semibold text-slate-900">
                            [{cit.citation_index ?? idx + 1}] Page {cit.page_number ?? "N/A"}
                          </span>
                          <span className="text-[11px] text-slate-400 font-mono">
                            Contract: {cit.contract_id.substring(0, 8)}...
                          </span>
                        </div>
                        <p className="text-slate-700 italic border-l-2 border-slate-300 pl-2.5 py-0.5">
                          "{cit.snippet}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Retrieval Debug Panel */}
              {showDebug && result.retrieval_debug && (
                <div className="p-4 bg-slate-900 text-slate-200 rounded-lg text-xs space-y-2 font-mono overflow-x-auto">
                  <div className="text-slate-400 font-bold mb-1">Retrieval Diagnostic Information</div>
                  <pre>{JSON.stringify(result.retrieval_debug, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
