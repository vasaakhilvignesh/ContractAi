import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";

const pipelineSteps = [
  "File validation",
  "PDF text extraction",
  "Document segmentation",
  "Chunking",
  "Embedding generation",
  "Vector indexing",
  "Keyword indexing",
  "Clause extraction",
  "Obligation extraction",
  "Risk analysis",
  "Processing complete",
];

export default function UploadContract() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<"upload" | "metadata" | "processing" | "done">("upload");
  const [processingStep, setProcessingStep] = useState(0);
  const [metadata, setMetadata] = useState({
    name: "",
    vendor: "",
    type: "MSA",
    effectiveDate: "",
    expirationDate: "",
    tags: "",
  });

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      setFile(dropped);
      setStage("metadata");
      setMetadata((m) => ({ ...m, name: dropped.name.replace(".pdf", "") }));
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setStage("metadata");
      setMetadata((m) => ({ ...m, name: selected.name.replace(".pdf", "") }));
    }
  }

  function startProcessing() {
    setStage("processing");
    setProcessingStep(0);
    const interval = setInterval(() => {
      setProcessingStep((prev) => {
        if (prev >= pipelineSteps.length - 1) {
          clearInterval(interval);
          setTimeout(() => setStage("done"), 600);
          return prev;
        }
        return prev + 1;
      });
    }, 600);
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate("/contracts")} className="text-slate-400 hover:text-slate-600 transition-colors">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Upload Contract</h1>
          <p className="text-sm text-slate-500">PDF contracts are automatically analyzed for clauses, obligations, and risk signals.</p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center gap-2 mb-6">
        {["Upload PDF", "Add Metadata", "Processing", "Complete"].map((step, i) => {
          const stageIndex = ["upload", "metadata", "processing", "done"].indexOf(stage);
          const isActive = i === stageIndex;
          const isDone = i < stageIndex;
          return (
            <div key={step} className="flex items-center">
              <div className={`flex items-center gap-2 text-xs font-medium ${isActive ? "text-[var(--accent)]" : isDone ? "text-green-600" : "text-slate-400"}`}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  isActive ? "bg-[var(--accent)] text-white" : isDone ? "bg-green-100 text-green-600" : "bg-slate-100 text-slate-400"
                }`}>
                  {isDone ? "✓" : i + 1}
                </div>
                <span className="hidden sm:inline">{step}</span>
              </div>
              {i < 3 && <div className={`w-12 h-px mx-2 ${isDone ? "bg-green-300" : "bg-slate-200"}`} />}
            </div>
          );
        })}
      </div>

      {/* Stage: Upload */}
      {stage === "upload" && (
        <div
          className={`border-2 border-dashed rounded-xl p-16 text-center transition-colors cursor-pointer ${
            dragging ? "border-[var(--accent)] bg-blue-50" : "border-[var(--border)] bg-white hover:border-blue-300 hover:bg-slate-50"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={handleFileSelect} />
          <div className="flex flex-col items-center gap-4">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${dragging ? "bg-blue-100" : "bg-slate-100"}`}>
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                <path d="M14 4v16M8 10l6-6 6 6M6 20v3a1 1 0 001 1h14a1 1 0 001-1v-3" stroke={dragging ? "#2563EB" : "#94A3B8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold text-slate-800">Drag and drop your contract PDF</p>
              <p className="text-sm text-slate-400 mt-1">or click to browse files</p>
            </div>
            <p className="text-xs text-slate-400 bg-slate-50 px-3 py-1.5 rounded border border-[var(--border)]">PDF only · Max 50MB</p>
          </div>
        </div>
      )}

      {/* Stage: Metadata */}
      {stage === "metadata" && file && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-6">
          {/* File info */}
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-[var(--border)]">
            <div className="w-10 h-10 bg-red-50 rounded flex items-center justify-center flex-shrink-0">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M10 1H4a1 1 0 00-1 1v14a1 1 0 001 1h10a1 1 0 001-1V6L10 1z" stroke="#EF4444" strokeWidth="1.5" strokeLinejoin="round"/>
                <path d="M10 1v5h5" stroke="#EF4444" strokeWidth="1.5"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">{file.name}</p>
              <p className="text-xs text-slate-400">{(file.size / 1024 / 1024).toFixed(1)} MB · PDF</p>
            </div>
            <button onClick={() => { setFile(null); setStage("upload"); }} className="ml-auto text-slate-400 hover:text-red-500 transition-colors">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Contract Name <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={metadata.name}
                  onChange={(e) => setMetadata((m) => ({ ...m, name: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Vendor / Party <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={metadata.vendor}
                  onChange={(e) => setMetadata((m) => ({ ...m, vendor: e.target.value }))}
                  placeholder="e.g. Salesforce Inc."
                  className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Contract Type</label>
                <select
                  value={metadata.type}
                  onChange={(e) => setMetadata((m) => ({ ...m, type: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  {["MSA", "SaaS", "NDA", "PSA", "DPA", "License", "Consulting", "SOW", "Other"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Effective Date</label>
                <input type="date" value={metadata.effectiveDate} onChange={(e) => setMetadata((m) => ({ ...m, effectiveDate: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Expiration Date</label>
                <input type="date" value={metadata.expirationDate} onChange={(e) => setMetadata((m) => ({ ...m, expirationDate: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Tags</label>
              <input type="text" value={metadata.tags} onChange={(e) => setMetadata((m) => ({ ...m, tags: e.target.value }))}
                placeholder="e.g. procurement, software, renewal-2024"
                className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              />
            </div>
          </div>

          <div className="flex justify-between mt-6 pt-4 border-t border-[var(--border)]">
            <button onClick={() => { setFile(null); setStage("upload"); }} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-800 border border-[var(--border)] rounded hover:bg-slate-50 transition-colors">
              Back
            </button>
            <button
              onClick={startProcessing}
              disabled={!metadata.name || !metadata.vendor}
              className="px-5 py-2 bg-[var(--accent)] text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Start Processing
            </button>
          </div>
        </div>
      )}

      {/* Stage: Processing */}
      {stage === "processing" && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="font-semibold text-slate-900">Processing Contract</h3>
              <p className="text-xs text-slate-400 mt-0.5">{metadata.name}</p>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Step {Math.min(processingStep + 1, pipelineSteps.length)} / {pipelineSteps.length}
            </div>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-slate-100 rounded-full mb-6 overflow-hidden">
            <div
              className="h-full bg-[var(--accent)] rounded-full transition-all duration-500"
              style={{ width: `${((processingStep + 1) / pipelineSteps.length) * 100}%` }}
            />
          </div>

          <div className="space-y-2">
            {pipelineSteps.map((step, i) => {
              const isDone = i < processingStep;
              const isActive = i === processingStep;
              return (
                <div key={step} className={`flex items-center gap-3 px-3 py-2 rounded transition-colors ${isActive ? "bg-blue-50 border border-blue-100" : isDone ? "opacity-60" : "opacity-30"}`}>
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isDone ? "bg-green-100 text-green-600" : isActive ? "bg-[var(--accent)] text-white" : "bg-slate-100 text-slate-400"
                  }`}>
                    {isDone ? (
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    ) : isActive ? (
                      <svg className="animate-spin" width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M5 1a4 4 0 010 8" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    ) : (
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                    )}
                  </div>
                  <span className={`text-sm ${isActive ? "text-[var(--accent)] font-medium" : isDone ? "text-slate-500" : "text-slate-400"}`}>{step}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Stage: Done */}
      {stage === "done" && (
        <div className="bg-white border border-[var(--border)] rounded-lg p-10 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M6 14l5.5 6L22 8" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h3 className="text-xl font-bold text-slate-900 mb-2">Processing Complete</h3>
          <p className="text-sm text-slate-500 mb-1">{metadata.name}</p>
          <p className="text-sm text-slate-400 mb-6">Contract analyzed · Clauses extracted · Risk signals identified · Obligations catalogued</p>
          <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto mb-6">
            {[
              { label: "Clauses", value: "8" },
              { label: "Obligations", value: "5" },
              { label: "Risk Signals", value: "2" },
            ].map((s) => (
              <div key={s.label} className="text-center bg-slate-50 rounded border border-[var(--border)] py-2">
                <div className="text-xl font-bold text-slate-900">{s.value}</div>
                <div className="text-xs text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => navigate("/contracts")}
              className="px-4 py-2 border border-[var(--border)] text-sm text-slate-700 font-medium rounded hover:bg-slate-50 transition-colors"
            >
              Back to Contracts
            </button>
            <button
              onClick={() => navigate("/contracts/c001")}
              className="px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded hover:bg-[#16304f] transition-colors"
            >
              Open Contract
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
