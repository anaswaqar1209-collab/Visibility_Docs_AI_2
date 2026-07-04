"use client";

import { useState, useRef, useCallback } from "react";

async function safeJson(res: Response) {
  try {
    const text = await res.text();
    return JSON.parse(text);
  } catch {
    let txt = "";
    try { txt = (await res.text()) || ""; } catch {}
    return { detail: txt ? txt.substring(0, 300) : `HTTP ${res.status}` };
  }
}

const ORG = "default-org";
const API = "http://127.0.0.1:8000";

export default function Home() {
  const [msg, setMsg] = useState("");
  const [msgType, setMsgType] = useState<"info"|"error"|"success">("info");
  const pushMsg = (m: string, type: "info"|"error"|"success" = "info") => { setMsg(m); setMsgType(type); setTimeout(() => setMsg(""), 5000); };
  const [sidebar, setSidebar] = useState<"docs"|"workflow"|"validations">("docs");
  const [classPopup, setClassPopup] = useState<{name:string;type:string;conf:number} | null>(null);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">V</div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 leading-tight">Visibility Docs AI</h1>
            <p className="text-xs text-gray-400">Enterprise Document Intelligence</p>
          </div>
        </div>
        <nav className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
          {(["docs","workflow","validations"] as const).map(k => (
            <button key={k} onClick={() => setSidebar(k)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all capitalize ${
                sidebar === k ? "bg-white text-blue-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}>{k === "docs" ? "Documents" : k}</button>
          ))}
        </nav>
      </header>

      {msg && (
        <div className={`mx-6 mt-3 px-4 py-2.5 rounded-lg text-sm flex items-center gap-2 border shrink-0 ${
          msgType === "error" ? "bg-red-50 border-red-200 text-red-700" :
          msgType === "success" ? "bg-green-50 border-green-200 text-green-700" :
          "bg-blue-50 border-blue-200 text-blue-700"
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            msgType === "error" ? "bg-red-500" : msgType === "success" ? "bg-green-500" : "bg-blue-500"
          }`} />
          {msg}
        </div>
      )}

      {classPopup && (
        <ClassPopup name={classPopup.name} type={classPopup.type} conf={classPopup.conf}
          onClose={() => setClassPopup(null)} />
      )}

      <div className="flex-1 flex gap-0 overflow-hidden">
        {sidebar === "docs" && <AllDocumentsPage onMsg={pushMsg} onClassify={(n,t,c) => setClassPopup({name:n,type:t,conf:c})} />}
        {sidebar === "workflow" && <WorkflowSection onMsg={pushMsg} />}
        {sidebar === "validations" && <ValidationsSection onMsg={pushMsg} />}
        <ChatSection onMsg={pushMsg} />
      </div>
    </div>
  );
}

const CATEGORIES = [
  "invoice", "purchase_order", "contract", "quotation", "certificate",
  "hr_document", "audit_report", "financial_statement", "sop",
  "engineering_drawing", "quality_report", "maintenance_report", "other",
];

function DocTypeBadge({ type }: { type?: string }) {
  const colors: Record<string, string> = {
    invoice: "bg-green-100 text-green-700 border-green-200",
    purchase_order: "bg-blue-100 text-blue-700 border-blue-200",
    contract: "bg-purple-100 text-purple-700 border-purple-200",
    quotation: "bg-yellow-100 text-yellow-700 border-yellow-200",
    certificate: "bg-orange-100 text-orange-700 border-orange-200",
    hr_document: "bg-pink-100 text-pink-700 border-pink-200",
    audit_report: "bg-red-100 text-red-700 border-red-200",
    financial_statement: "bg-indigo-100 text-indigo-700 border-indigo-200",
    sop: "bg-teal-100 text-teal-700 border-teal-200",
    engineering_drawing: "bg-cyan-100 text-cyan-700 border-cyan-200",
    quality_report: "bg-violet-100 text-violet-700 border-violet-200",
    maintenance_report: "bg-amber-100 text-amber-700 border-amber-200",
  };
  const t = type || "unknown";
  const cls = colors[t] || "bg-gray-100 text-gray-600 border-gray-200";
  return <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${cls}`}>{t.replace(/_/g, " ")}</span>;
}

function ClassPopup({ name, type, conf, onClose }: { name:string; type:string; conf:number; onClose:()=>void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-white font-bold text-sm">Classification Result</h2>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white text-lg leading-none">&times;</button>
        </div>
        <div className="px-6 py-4">
          <div className="text-xs text-gray-500 mb-1 truncate">{name}</div>
          <div className="flex items-center gap-3 mb-2">
            <DocTypeBadge type={type} />
            <span className="text-xs text-gray-400">{(conf * 100).toFixed(0)}% confidence</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${Math.min(conf * 100, 100)}%` }} />
          </div>
        </div>
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 flex justify-end">
          <button onClick={onClose} className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 transition">OK</button>
        </div>
      </div>
    </div>
  );
}

function UploadBox({ onUploadDone, onMsg, onClassify }: { onUploadDone: () => void; onMsg: (m: string, t?: "info"|"error"|"success") => void; onClassify: (name: string, type: string, conf: number) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({current:0, total:0, currentName:""});
  const [dragOver, setDragOver] = useState(false);
  const [processingDocs, setProcessingDocs] = useState<{id:string;name:string;status:string;type?:string}[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRefs = useRef<{[key:string]:ReturnType<typeof setInterval>}>({});
  const notifiedRef = useRef<{[key:string]:boolean}>({});

  const stopPoll = (id: string) => {
    if (pollRefs.current[id]) { clearInterval(pollRefs.current[id]); delete pollRefs.current[id]; }
  };

  const startPoll = (docId: string, fileName: string) => {
    stopPoll(docId);
    pollRefs.current[docId] = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/v1/documents/${docId}?organization_id=${ORG}`);
        if (!r.ok) { stopPoll(docId); return; }
        const d = await safeJson(r as any);
        setProcessingDocs(prev => prev.map(p => p.id === docId ? {...p, status: d.status, type: d.document_type} : p));
        // Fire classify popup once when type is set
        if (d.document_type && !notifiedRef.current[docId] && d.status !== "uploaded" && d.status !== "processing") {
          notifiedRef.current[docId] = true;
          onClassify(fileName, d.document_type, d.confidence || 0.85);
        }
        if (d.status === "processed" || d.status === "failed") {
          stopPoll(docId);
          setTimeout(() => {
            setProcessingDocs(prev => prev.filter(p => p.id !== docId));
            onUploadDone();
          }, 3000);
        }
      } catch { stopPoll(docId); }
    }, 2000);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(f => {
      const ext = f.name.split(".").pop()?.toLowerCase();
      return ["pdf","jpg","jpeg","png","tiff","tif","docx","xlsx","pptx"].includes(ext || "");
    });
    if (dropped.length) setFiles(prev => [...prev, ...dropped]);
  }, []);

  const uploadSingle = async (file: File): Promise<boolean> => {
    try {
      const form = new FormData();
      form.append("file", file); form.append("organization_id", ORG); form.append("title", file.name);
      const res = await fetch(`${API}/api/v1/documents/upload`, { method: "POST", body: form });
      const data = await safeJson(res as any);
      if (!res.ok) {
        if (res.status === 409) {
          onMsg(`Duplicate: ${data.detail || "file already exists"}`, "error");
        } else {
          onMsg(`Upload failed: ${file.name}`, "error");
        }
        return false;
      }
      setProcessingDocs(prev => [...prev, {id: data.id, name: file.name, status: "processing"}]);
      startPoll(data.id, file.name);
      return true;
    } catch {
      onMsg(`Cannot reach server (is backend running?)`, "error");
      return false;
    }
  };

  const handleUploadAll = async () => {
    if (!files.length) return;
    setLoading(true);
    let success = 0;
    for (let i = 0; i < files.length; i++) {
      setProgress({ current: i + 1, total: files.length, currentName: files[i].name });
      if (await uploadSingle(files[i])) success++;
    }
    setLoading(false);
    setProgress({ current: 0, total: 0, currentName: "" });
    setFiles([]);
    if (success === 0) onUploadDone();
  };

  const procColor = (s: string) =>
    s === "processed" ? "text-green-600" :
    s === "failed" ? "text-red-600" :
    "text-yellow-600";

  return (
    <div className="mb-4">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Upload</div>
      <div
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${dragOver ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}
        onDrop={handleDrop} onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" multiple className="hidden" accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.docx,.xlsx,.pptx"
          onChange={e => { const f = Array.from(e.target.files || []); if (f.length) setFiles(prev => [...prev, ...f]); }} />
        <div className="text-2xl mb-1 text-gray-400">{dragOver ? "📥" : "📂"}</div>
        <p className="text-xs text-gray-500 font-medium">{files.length ? `${files.length} selected` : (dragOver ? "Drop" : "Click or drop")}</p>
      </div>

      {files.length > 0 && (
        <div className="mt-2 space-y-1 max-h-24 overflow-y-auto">
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between bg-gray-50 px-2 py-1.5 rounded text-xs">
              <span className="truncate text-gray-700">{f.name}</span>
              <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600 ml-1">&times;</button>
            </div>
          ))}
        </div>
      )}

      {loading && progress.total > 0 && (
        <div className="mt-2">
          <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
            <span className="truncate">{progress.currentName.substring(0, 30)}</span>
            <span>{progress.current}/{progress.total}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div className="bg-blue-600 h-1.5 rounded-full transition-all" style={{ width: `${(progress.current / progress.total) * 100}%` }} />
          </div>
        </div>
      )}

      {processingDocs.length > 0 && (
        <div className="mt-2 space-y-1.5">
          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Processing</div>
          {processingDocs.map((p) => (
            <div key={p.id} className="flex items-center justify-between bg-yellow-50/50 px-2 py-1.5 rounded text-xs">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {p.status !== "processed" && p.status !== "failed" ? (
                  <span className="w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin shrink-0" />
                ) : p.status === "processed" ? (
                  <span className="text-green-500 shrink-0">✓</span>
                ) : (
                  <span className="text-red-500 shrink-0">✗</span>
                )}
                <span className="truncate text-gray-700">{p.name}</span>
              </div>
              <span className={`shrink-0 ml-1 font-medium ${procColor(p.status)}`}>
                {["processing","uploaded","ocr_done","classified","extracted","embedded"].includes(p.status) ? "processing..." : p.status}
              </span>
            </div>
          ))}
        </div>
      )}

      <button onClick={handleUploadAll} disabled={!files.length || loading}
        className="mt-2 w-full py-2 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition">
        {loading ? `Uploading ${progress.current}/${progress.total}...` : `Upload & Process${files.length > 1 ? ` (${files.length})` : ""}`}
      </button>
    </div>
  );
}

function DocDetail({ doc, onMsg, onClose }: { doc: any; onMsg: (m: string, t?: "info"|"error"|"success") => void; onClose?: () => void }) {
  const [detail, setDetail] = useState<any>(null);
  const [similar, setSimilar] = useState<any[]>([]);

  const loadDetail = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([
        fetch(`${API}/api/v1/documents/${doc.id}?organization_id=${ORG}`),
        fetch(`${API}/api/v1/search/similar/${doc.id}?organization_id=${ORG}&limit=3`),
      ]);
      const d = await safeJson(r as any);
      if ((r as any).ok) setDetail(d);
      const sd = await safeJson(s as any);
      if ((s as any).ok) setSimilar(sd.results || []);
    } catch {}
  }, [doc.id]);

  useState(() => { loadDetail(); });

  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-medium text-gray-800 truncate">{doc.title}</div>
        <div className="flex items-center gap-1 shrink-0">
          <a href={`${API}/api/v1/documents/${doc.id}/file?organization_id=${ORG}`} target="_blank"
            className="text-[10px] px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 no-underline">Open</a>
          {onClose && <button onClick={onClose} className="text-[10px] px-1.5 py-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded">&times;</button>}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-gray-500 mb-1">
        <div>Type: <span className="text-gray-700">{doc.document_type || "N/A"}</span></div>
        <div>Status: <span className={`${doc.status === "processed" ? "text-green-600" : doc.status === "failed" ? "text-red-600" : "text-yellow-600"}`}>{doc.status}</span></div>
        <div>Pages: {doc.page_count || "?"}</div>
        <div>Size: {doc.file_size ? `${(doc.file_size/1024).toFixed(0)} KB` : "?"}</div>
      </div>
      {detail?.raw_text && (
        <details className="mb-2">
          <summary className="cursor-pointer text-[10px] text-gray-500 font-medium">OCR Preview</summary>
          <pre className="mt-1 p-2 bg-gray-50 rounded text-[10px] max-h-24 overflow-y-auto whitespace-pre-wrap text-gray-600">{detail.raw_text.substring(0, 1000)}</pre>
        </details>
      )}
      {similar.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 font-medium mb-1">Similar Docs</div>
          {similar.map((s, i) => (
            <div key={i} className="text-[10px] py-0.5 flex items-center justify-between">
              <span className="text-blue-600 truncate">{s.document_title || s.document_id?.substring(0, 12)}</span>
              <span className="text-gray-400 shrink-0 ml-1">{(s.score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AllDocumentsPage({ onMsg, onClassify }: { onMsg: (m: string, t?: "info"|"error"|"success") => void; onClassify: (name: string, type: string, conf: number) => void }) {
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [allDocs, setAllDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const refreshRef = useRef(0);

  const loadDocs = useCallback(async (q = "") => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/documents?organization_id=${ORG}&q=${encodeURIComponent(q)}&limit=200`);
      const d = await safeJson(r as any);
      if ((r as any).ok) setAllDocs(d.documents || []);
    } catch { onMsg("Failed to load documents", "error"); }
    finally { setLoading(false); }
  }, [onMsg]);

  useState(() => { loadDocs(); });

  const handleDelete = async (docId: string) => {
    if (!confirm("Delete this document permanently?")) return;
    setDeleting(docId);
    try {
      const r = await fetch(`${API}/api/v1/documents/${docId}?organization_id=${ORG}`, { method: "DELETE" });
      if (r.ok) {
        onMsg("Document deleted", "success");
        setAllDocs(prev => prev.filter(d => d.id !== docId));
        if (selectedDoc?.id === docId) setSelectedDoc(null);
      } else {
        const d = await safeJson(r as any);
        onMsg(`Delete failed: ${d.detail || "error"}`, "error");
      }
    } catch { onMsg("Delete failed: server error", "error"); }
    finally { setDeleting(null); }
  };

  const filtered = allDocs.filter(d =>
    !search || d.title?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-80 lg:w-96 bg-white border-r border-gray-200 flex flex-col overflow-hidden shrink-0">
      <div className="p-4 border-b border-gray-100">
        <UploadBox onUploadDone={() => { refreshRef.current++; loadDocs(); }} onMsg={onMsg} onClassify={onClassify} />
      </div>
      <div className="p-4 border-b border-gray-100">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">All Documents ({allDocs.length})</div>
        <input value={search} onChange={e => { setSearch(e.target.value); loadDocs(e.target.value); }}
          placeholder="Filter by title..." className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-200 bg-gray-50" />
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading && allDocs.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-xs text-gray-400">No documents found</div>
        ) : (
          <div className="divide-y divide-gray-50">
            {filtered.map((d) => (
              <div key={d.id}
                className={`px-4 py-3 cursor-pointer hover:bg-blue-50 transition-colors ${selectedDoc?.id === d.id ? "bg-blue-50 border-l-2 border-blue-500" : ""}`}
                onClick={() => setSelectedDoc(d)}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-gray-800 truncate">{d.title}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <DocTypeBadge type={d.document_type} />
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        d.status === "processed" ? "bg-green-100 text-green-700" :
                        d.status === "failed" ? "bg-red-100 text-red-700" :
                        d.status === "uploaded" ? "bg-gray-100 text-gray-600" :
                        "bg-yellow-100 text-yellow-700"
                      }`}>{d.status}</span>
                    </div>
                    <div className="text-[10px] text-gray-400 mt-1">
                      {d.file_size ? `${(d.file_size/1024).toFixed(0)} KB` : ""}
                      {d.created_at ? ` · ${new Date(d.created_at).toLocaleDateString()}` : ""}
                    </div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); handleDelete(d.id); }} disabled={deleting === d.id}
                    className="shrink-0 px-2 py-1 text-[10px] text-red-500 hover:bg-red-50 rounded transition disabled:opacity-50">
                    {deleting === d.id ? "..." : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {selectedDoc && (
        <div className="border-t border-gray-200 p-4 max-h-64 overflow-y-auto">
          <DocDetail doc={selectedDoc} onMsg={onMsg} onClose={() => setSelectedDoc(null)} />
        </div>
      )}
    </div>
  );
}

function WorkflowSection({ onMsg }: { onMsg: (m: string, t?: "info"|"error"|"success") => void }) {
  const [pending, setPending] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadPending = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/documents/workflows/pending?organization_id=${ORG}`);
      const d = await safeJson(r as any);
      if ((r as any).ok) setPending(d.pending_approvals || []);
    } catch {}
    finally { setLoading(false); }
  };

  const approve = async (docId: string) => {
    await fetch(`${API}/api/v1/documents/${docId}/workflow/approve?organization_id=${ORG}&approver=admin&notes=Approved+from+UI`, { method: "POST" });
    onMsg("Document approved", "success");
    loadPending();
  };

  const reject = async (docId: string) => {
    const reason = prompt("Rejection reason:");
    if (!reason) return;
    await fetch(`${API}/api/v1/documents/${docId}/workflow/reject?organization_id=${ORG}&approver=admin&reason=${encodeURIComponent(reason)}`, { method: "POST" });
    onMsg("Document rejected", "error");
    loadPending();
  };

  return (
    <div className="w-72 lg:w-80 bg-white border-r border-gray-200 p-4 overflow-y-auto shrink-0">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Approvals</div>
        <button onClick={loadPending} className="text-xs px-2.5 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">{loading ? "..." : "Refresh"}</button>
      </div>
      {pending.length === 0 && !loading && <p className="text-xs text-gray-400 text-center py-8">No pending approvals</p>}
      <div className="space-y-2">
        {pending.map((w, i) => (
          <div key={i} className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-700">{w.document_id?.substring(0, 12)}...</span>
              <div className="flex gap-1">
                <button onClick={() => approve(w.document_id)} className="px-2 py-0.5 text-[10px] bg-green-600 text-white rounded hover:bg-green-700">Approve</button>
                <button onClick={() => reject(w.document_id)} className="px-2 py-0.5 text-[10px] bg-red-600 text-white rounded hover:bg-red-700">Reject</button>
              </div>
            </div>
            <div className="text-[10px] text-gray-500">Stage: <span className="text-blue-600 font-medium">{w.current_stage}</span></div>
            <div className="text-[10px] text-gray-400">{w.workflow_type} &middot; {w.approvals_obtained}/{w.approvals_required}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ValidationsSection({ onMsg }: { onMsg: (m: string, t?: "info"|"error"|"success") => void }) {
  const [validations, setValidations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/documents/validations/list?organization_id=${ORG}&limit=50`);
      const d = await safeJson(r as any);
      if ((r as any).ok) setValidations(d.validations || []);
    } catch {}
    finally { setLoading(false); }
  };

  return (
    <div className="w-72 lg:w-80 bg-white border-r border-gray-200 p-4 overflow-y-auto shrink-0">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Validations</div>
        <button onClick={load} className="text-xs px-2.5 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">{loading ? "..." : "Refresh"}</button>
      </div>
      {validations.length === 0 && !loading && <p className="text-xs text-gray-400 text-center py-8">No validation results</p>}
      <div className="space-y-1.5 max-h-[calc(100vh-160px)] overflow-y-auto">
        {validations.map((v, i) => (
          <div key={i} className={`border-l-4 p-2.5 rounded-r-lg text-xs ${v.severity === "error" ? "border-l-red-500 bg-red-50" : v.severity === "warning" ? "border-l-yellow-500 bg-yellow-50" : "border-l-green-500 bg-green-50"}`}>
            <div className="font-medium text-gray-800">{v.validation_type?.replace(/_/g, " ")}</div>
            <div className="text-gray-500 mt-0.5">{v.discrepancy_details || `${v.source_field}: ${v.expected_value} → ${v.actual_value || "N/A"}`}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatSection({ onMsg }: { onMsg: (m: string, t?: "info"|"error"|"success") => void }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<{role:string;content:string}[]>([]);
  const [loading, setLoading] = useState(false);
  const [docQuery, setDocQuery] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [sources, setSources] = useState<any[]>([]);
  const chatEnd = useRef<HTMLDivElement>(null);
  const timerRef = useRef<any>(null);

  const searchDocs = async (q: string) => {
    if (!q.trim()) { setDocs([]); return; }
    setSearching(true);
    try {
      const r = await fetch(`${API}/api/v1/documents?organization_id=${ORG}&q=${encodeURIComponent(q)}&limit=20`);
      const d = await safeJson(r as any);
      if ((r as any).ok) { setDocs(d.documents || []); } else { setDocs([]); }
    } catch { setDocs([]); }
    finally { setSearching(false); }
  };

  const ask = async () => {
    if (!question.trim()) return;
    setLoading(true);
    const userMsg = question;
    setQuestion("");
    setMessages(prev => [...prev, {role:"user", content:userMsg}]);
    try {
      const docId = selectedDoc?.id || "";
      const sessionId = selectedDoc ? `doc_${docId}` : "all_docs";
      const body = { question: userMsg, organization_id: ORG, document_id: docId || "all", session_id: sessionId };
      const endpoint = docId ? `${API}/api/v1/chat` : `${API}/api/v1/chat/all`;
      const r = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await safeJson(r as any);
      if ((r as any).ok) {
        setMessages(prev => [...prev, {role:"assistant", content:d.answer || "No answer"}]);
        if (d.history && d.history.length > 0) setMessages(d.history);
        setSources(d.sources || []);
      } else {
        setMessages(prev => [...prev, {role:"assistant", content:`Error: ${d.detail}`}]);
      }
    } catch (e: any) {
      setMessages(prev => [...prev, {role:"assistant", content:`Error: ${e.message}`}]);
    }
    finally { setLoading(false); setTimeout(() => chatEnd.current?.scrollIntoView({behavior:"smooth"}), 100); }
  };

  return (
    <div className="flex-1 flex flex-col bg-white">
      <div className="border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0">
        <div className="relative flex-1 max-w-md">
          <input value={docQuery} onChange={e => { const v=e.target.value; setDocQuery(v); setSelectedDoc(null); setMessages([]); setSources([]); if (timerRef.current) clearTimeout(timerRef.current); timerRef.current = setTimeout(() => searchDocs(v), 300); }}
            placeholder={selectedDoc ? selectedDoc.title : "Search & select a document (blank = all docs)..."}
            className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-200 bg-gray-50" />
          {searching && <span className="absolute right-2.5 top-2 text-xs text-gray-400">...</span>}
          {docs.length > 0 && (
            <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
              {docs.map((d, i) => (
                <div key={i} onClick={() => { setSelectedDoc(d); setDocQuery(d.title); setDocs([]); setMessages([]); setSources([]); }}
                     className="px-3 py-2.5 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-0 text-xs">
                  <span className="font-medium text-blue-700">{d.title}</span>
                  <span className="text-gray-400 ml-2">{d.document_type}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {selectedDoc && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-blue-600 font-medium truncate max-w-[120px]">{selectedDoc.title}</span>
            <button onClick={() => { setSelectedDoc(null); setDocQuery(""); setMessages([]); setSources([]); }}
              className="text-gray-400 hover:text-red-500">&times;</button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4" style={{maxHeight: "calc(100vh - 160px)"}}>
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-4xl mb-3 text-gray-300">💬</div>
              <p className="text-sm text-gray-400 font-medium">{selectedDoc ? `Ask about "${selectedDoc.title}"` : "Select a document or ask across all documents"}</p>
              <p className="text-xs text-gray-300 mt-1">Type a question below to start</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[75%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-50 border border-gray-100 text-gray-800 rounded-bl-sm"
                }`}>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-50 border border-gray-100 rounded-xl rounded-bl-sm px-4 py-3 text-sm text-gray-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full" style={{animation:"bounce 1.4s infinite",animationDelay:"0ms"}} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full" style={{animation:"bounce 1.4s infinite",animationDelay:"200ms"}} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full" style={{animation:"bounce 1.4s infinite",animationDelay:"400ms"}} />
                </div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>
        )}
      </div>

      {sources.length > 0 && (
        <div className="px-6 py-2 border-t border-gray-100 bg-gray-50">
          <details className="text-xs text-gray-500">
            <summary className="cursor-pointer font-medium">Sources ({sources.length})</summary>
            <div className="mt-1 space-y-0.5">
              {sources.slice(0, 3).map((s, i) => (
                <p key={i} className="text-blue-600">
                  {s.document_title || s.document_id?.substring(0, 12)} ({s.score ? `${(s.score * 100).toFixed(0)}%` : "direct"})
                </p>
              ))}
            </div>
          </details>
        </div>
      )}

      <div className="border-t border-gray-200 px-6 py-3 shrink-0">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <input value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask a question about the selected document..."
            className="flex-1 px-4 py-2.5 text-sm border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-300 bg-gray-50"
            onKeyDown={e => e.key === "Enter" && ask()} />
          <button onClick={ask} disabled={loading || !question.trim()}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-1.5">
            {loading ? "..." : <><span>Send</span><span className="text-base">→</span></>}
          </button>
        </div>
      </div>
    </div>
  );
}
