import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Upload, FolderOpen, FileText, Receipt, Car, Shield,
  Truck, Landmark, Folder, X, ChevronRight, Eye, Trash2, MoveRight, Ban,
  Loader2, Brain, Calendar, Euro, Hash, Building2, Tag, Clock,
  FolderPlus, Pencil, Check, Send, ChevronDown, Plus, Maximize2, HelpCircle,
  Mail, AlertCircle, AlertTriangle, Sparkles
} from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${API}/api` });

const FOLDER_ICONS = {
  receipt: Receipt, car: Car, shield: Shield, "file-text": FileText,
  truck: Truck, landmark: Landmark, folder: Folder, "help-circle": HelpCircle,
};
const FOLDER_COLORS = {
  emerald: { bg: "bg-emerald-100", text: "text-emerald-600", border: "border-emerald-300", active: "bg-emerald-50 border-emerald-400" },
  blue: { bg: "bg-blue-100", text: "text-blue-600", border: "border-blue-300", active: "bg-blue-50 border-blue-400" },
  amber: { bg: "bg-amber-100", text: "text-amber-600", border: "border-amber-300", active: "bg-amber-50 border-amber-400" },
  fuchsia: { bg: "bg-fuchsia-100", text: "text-fuchsia-600", border: "border-fuchsia-300", active: "bg-fuchsia-50 border-fuchsia-400" },
  orange: { bg: "bg-orange-100", text: "text-orange-600", border: "border-orange-300", active: "bg-orange-50 border-orange-400" },
  purple: { bg: "bg-purple-100", text: "text-purple-600", border: "border-purple-300", active: "bg-purple-50 border-purple-400" },
  gray: { bg: "bg-gray-100", text: "text-gray-600", border: "border-gray-300", active: "bg-gray-50 border-gray-400" },
};

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }); } catch { return iso; }
}

function FolderTree({ folders, activeFolder, isSearching, expandedFolders, toggleExpand, setActiveFolder,
  editingFolder, editFolderName, setEditFolderName, setEditingFolder, handleRenameFolder, handleDeleteFolder,
  addSubfolderTo, setAddSubfolderTo, subfolderName, setSubfolderName, handleCreateSubfolder,
  onDropDoc }) {

  const [hoverFolderId, setHoverFolderId] = useState(null);

  // Build tree: root folders (no parent_id) with children
  const rootFolders = folders.filter(f => !f.parent_id);
  const childrenOf = (parentId) => folders.filter(f => f.parent_id === parentId);
  const hasChildren = (folderId) => folders.some(f => f.parent_id === folderId);

  // Monatsname -> Nummer fuer chronologische Sortierung (Umlaut- und ASCII-Variante)
  const MONTH_ORDER = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
  };
  const sortChildren = (arr) => {
    const monthItems = [];
    const yearItems = [];
    const otherItems = [];
    for (const f of arr) {
      const monthIdx = MONTH_ORDER[(f.name || "").trim().toLowerCase()];
      if (monthIdx) monthItems.push({ f, idx: monthIdx });
      else if (/^\d{4}$/.test((f.name || "").trim())) yearItems.push({ f, idx: parseInt(f.name, 10) });
      else otherItems.push(f);
    }
    monthItems.sort((a, b) => a.idx - b.idx);
    yearItems.sort((a, b) => b.idx - a.idx);   // neueste Jahre oben
    otherItems.sort((a, b) => (a.name || "").localeCompare(b.name || "", "de"));
    return [...yearItems.map(x => x.f), ...monthItems.map(x => x.f), ...otherItems];
  };

  const renderFolder = (f, depth = 0) => {
    const Icon = FOLDER_ICONS[f.icon] || Folder;
    const c = FOLDER_COLORS[f.color] || FOLDER_COLORS.gray;
    const isActive = activeFolder === f.id && !isSearching;
    const isEditing = editingFolder === f.id;
    const children = childrenOf(f.id);
    const expanded = expandedFolders[f.id];
    const hasKids = hasChildren(f.id);
    const pl = 8 + depth * 16;
    const isHighlight = hoverFolderId === f.id;
    const isUnbekannt = f.id === "unbekannt";

    return (
      <div key={f.id}>
        {isEditing ? (
          <div className="flex items-center gap-1 px-2 py-1" style={{ paddingLeft: pl }}>
            <Input value={editFolderName} onChange={e => setEditFolderName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleRenameFolder(f.id); if (e.key === "Escape") setEditingFolder(null); }}
              className="h-6 text-xs flex-1" autoFocus data-testid={`rename-input-${f.id}`} />
            <button onClick={() => handleRenameFolder(f.id)} className="p-0.5 text-emerald-600 hover:bg-emerald-50 rounded"><Check className="w-3 h-3" /></button>
            <button onClick={() => setEditingFolder(null)} className="p-0.5 text-gray-400 hover:bg-gray-100 rounded"><X className="w-3 h-3" /></button>
          </div>
        ) : (
          <div
            className={`group/folder flex items-center transition-all ${isHighlight ? "bg-emerald-50 ring-2 ring-emerald-400 rounded-md" : ""}`}
            style={{ paddingLeft: pl }}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = "move"; setHoverFolderId(f.id); }}
            onDragLeave={(e) => { e.stopPropagation(); setHoverFolderId(null); }}
            onDrop={(e) => {
              e.preventDefault(); e.stopPropagation();
              setHoverFolderId(null);
              const docId = e.dataTransfer.getData("application/x-doc-id");
              if (docId && onDropDoc) onDropDoc(docId, f.id);
            }}
          >
            {/* Expand toggle */}
            <button
              onClick={(e) => { e.stopPropagation(); if (hasKids) toggleExpand(f.id); }}
              className={`w-4 h-4 flex items-center justify-center flex-shrink-0 ${hasKids ? "text-gray-400 hover:text-gray-600" : "text-transparent"}`}
            >
              <ChevronRight className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`} />
            </button>
            {/* Folder button */}
            <button
              onClick={() => setActiveFolder(f.id)}
              className={`flex-1 flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-colors min-w-0 ${
                isActive ? `${c.active} font-medium border` : isUnbekannt ? "text-amber-700 hover:bg-amber-50 border border-transparent font-medium" : "text-gray-700 hover:bg-gray-50 border border-transparent"
              }`}
              data-testid={`folder-${f.id}`}
            >
              <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${c.bg}`}>
                <Icon className={`w-2.5 h-2.5 ${c.text}`} />
              </div>
              <span className="flex-1 text-left truncate">{f.name}</span>
              {f.count > 0 && <span className={`text-[10px] flex-shrink-0 ${isUnbekannt ? "text-amber-600 font-semibold" : "text-gray-400"}`}>{f.count}</span>}
            </button>
            {/* Actions */}
            <div className="hidden group-hover/folder:flex items-center flex-shrink-0 mr-1" onClick={e => e.stopPropagation()}>
              <button onClick={() => setAddSubfolderTo(f.id)} className="p-0.5 text-gray-300 hover:text-fuchsia-600 rounded" title="Unterordner"><Plus className="w-3 h-3" /></button>
              {f.is_custom && (
                <>
                  <button onClick={() => { setEditingFolder(f.id); setEditFolderName(f.name); }} className="p-0.5 text-gray-300 hover:text-gray-600 rounded" title="Umbenennen"><Pencil className="w-2.5 h-2.5" /></button>
                  <button onClick={() => handleDeleteFolder(f.id, f.name)} className="p-0.5 text-gray-300 hover:text-red-600 rounded" title="Löschen"><Trash2 className="w-2.5 h-2.5" /></button>
                </>
              )}
            </div>
          </div>
        )}
        {/* Add subfolder input */}
        {addSubfolderTo === f.id && (
          <div className="flex items-center gap-1 py-1" style={{ paddingLeft: pl + 20 }}>
            <Input value={subfolderName} onChange={e => setSubfolderName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleCreateSubfolder(f.id); if (e.key === "Escape") { setAddSubfolderTo(null); setSubfolderName(""); } }}
              placeholder="Unterordner..." className="h-6 text-xs flex-1" autoFocus data-testid={`subfolder-input-${f.id}`} />
            <button onClick={() => handleCreateSubfolder(f.id)} className="p-0.5 text-emerald-600 hover:bg-emerald-50 rounded"><Check className="w-3 h-3" /></button>
            <button onClick={() => { setAddSubfolderTo(null); setSubfolderName(""); }} className="p-0.5 text-gray-400 hover:bg-gray-100 rounded"><X className="w-3 h-3" /></button>
          </div>
        )}
        {/* Children */}
        {expanded && sortChildren(children).map(child => renderFolder(child, depth + 1))}
      </div>
    );
  };

  // Sort: 'unbekannt' immer ganz oben, dann Rest
  const sortedRoots = [...rootFolders].sort((a, b) => {
    if (a.id === "unbekannt") return -1;
    if (b.id === "unbekannt") return 1;
    return 0;
  });

  return <div className="space-y-0.5">{sortedRoots.map(f => renderFolder(f, 0))}</div>;
}


/**
 * Inline-editierbares AI-Metadatenfeld.
 * Klick auf den Stift oeffnet ein Input-Feld; Save schickt PATCH /api/documents/{id}/metadata.
 */
function EditableMetaField({ docId, fieldKey, label, value, type = "text", format, valueClass = "", capitalize = false, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    let raw = value ?? "";
    if (type === "date" && typeof raw === "string" && raw.length > 10) raw = raw.slice(0, 10);
    setDraft(String(raw));
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      let outVal = draft;
      if (type === "number") {
        const n = parseFloat(String(draft).replace(",", "."));
        outVal = isNaN(n) ? null : n;
      }
      const { data } = await api.patch(`/documents/${docId}/metadata`, { [fieldKey]: outVal });
      onSaved && onSaved(data.ai_metadata);
      toast.success(`${label} aktualisiert`);
      setEditing(false);
    } catch (e) {
      toast.error(`Speichern fehlgeschlagen: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => { setEditing(false); setDraft(""); };

  if (editing) {
    return (
      <div data-testid={`edit-field-${fieldKey}`}>
        <p className="text-[11px] text-gray-400 mb-0.5">{label}</p>
        <div className="flex items-center gap-1">
          <input
            type={type === "date" ? "date" : type === "number" ? "number" : "text"}
            value={draft}
            step={type === "number" ? "0.01" : undefined}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") cancel(); }}
            autoFocus
            className="flex-1 h-7 text-sm border border-gray-300 rounded px-2 focus:outline-none focus:ring-2 focus:ring-emerald-400"
            data-testid={`edit-input-${fieldKey}`}
          />
          <button onClick={save} disabled={saving} className="h-7 w-7 rounded bg-emerald-500 text-white flex items-center justify-center hover:bg-emerald-600 disabled:opacity-50" title="Speichern" data-testid={`save-${fieldKey}`}>
            <Check className="w-3.5 h-3.5" />
          </button>
          <button onClick={cancel} className="h-7 w-7 rounded bg-gray-200 text-gray-700 flex items-center justify-center hover:bg-gray-300" title="Abbrechen">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  const displayValue = format ? format(value) : String(value ?? "");
  return (
    <div className="group" data-testid={`field-${fieldKey}`}>
      <p className="text-[11px] text-gray-400 mb-0.5">{label}</p>
      <div className="flex items-center gap-1.5">
        <p className={`text-sm text-gray-900 flex-1 ${capitalize ? "capitalize" : ""} ${valueClass}`}>{displayValue}</p>
        <button
          onClick={startEdit}
          className="p-1 rounded text-gray-300 hover:text-emerald-600 hover:bg-emerald-50 opacity-0 group-hover:opacity-100 transition-opacity"
          title={`${label} bearbeiten`}
          data-testid={`edit-btn-${fieldKey}`}
        >
          <Pencil className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}


export default function DocumentManagementPage() {
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const [folders, setFolders] = useState([]);
  const [totalDocs, setTotalDocs] = useState(0);
  const [activeFolder, setActiveFolder] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [moveTarget, setMoveTarget] = useState(null);
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [editingFolder, setEditingFolder] = useState(null);
  const [editFolderName, setEditFolderName] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [expandedFolders, setExpandedFolders] = useState({});
  const [addSubfolderTo, setAddSubfolderTo] = useState(null);
  const [subfolderName, setSubfolderName] = useState("");
  const loadFolders = useCallback(async () => {
    try {
      const r = await api.get("/documents/folders");
      setFolders(r.data.folders);
      setTotalDocs(r.data.total);
    } catch { /* ignore */ }
  }, []);

  const loadDocuments = useCallback(async (folderId) => {
    try {
      const url = folderId ? `/documents/list?folder_id=${folderId}` : "/documents/list";
      const r = await api.get(url);
      setDocuments(r.data.documents);
    } catch { toast.error("Fehler beim Laden"); }
  }, []);

  useEffect(() => { loadFolders(); }, [loadFolders]);
  useEffect(() => { if (!isSearching) loadDocuments(activeFolder); }, [activeFolder, isSearching, loadDocuments]);

  // ── Mailbridge: Status + Refresh-Trigger ──────────────────────────
  const [mailbridge, setMailbridge] = useState(null);
  const [mailbridgeLoading, setMailbridgeLoading] = useState(false);

  const loadMailbridgeStatus = useCallback(async () => {
    try {
      const r = await api.get("/mailbridge/status");
      setMailbridge(r.data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadMailbridgeStatus(); }, [loadMailbridgeStatus]);

  const handleMailbridgeRefresh = async () => {
    if (mailbridgeLoading) return;
    if (!mailbridge?.password_set) {
      toast.error("IMAP-Passwort fehlt in der backend/.env");
      return;
    }
    setMailbridgeLoading(true);
    try {
      const r = await api.post("/mailbridge/run-now");
      const s = r.data?.stats || {};
      const msg = s.attachments_uploaded > 0
        ? `${s.attachments_uploaded} Anhang/Anhänge aus ${s.fetched} Mail(s) importiert`
        : s.fetched > 0
          ? `${s.fetched} Mail(s) gelesen – keine unterstützten Anhänge`
          : "Keine neuen Mails";
      toast.success(msg);
      await loadMailbridgeStatus();
      await loadFolders();
      await loadDocuments(activeFolder);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Mailbridge-Abruf fehlgeschlagen");
    } finally {
      setMailbridgeLoading(false);
    }
  };

  const mailbridgeLastRunText = (() => {
    if (!mailbridge?.last_run_at) return null;
    const d = new Date(mailbridge.last_run_at);
    const today = new Date();
    const isToday = d.toDateString() === today.toDateString();
    return isToday
      ? d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr"
      : d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) + " Uhr";
  })();

  // ── PDF/Image Preview als Blob laden (umgeht Cloudflare iframe-Block) ──
  const [previewBlobUrl, setPreviewBlobUrl] = useState(null);

  useEffect(() => {
    if (!selectedDoc?.id) {
      setPreviewBlobUrl(null);
      return;
    }
    const isPdf = selectedDoc.content_type === "application/pdf";
    const isImg = selectedDoc.content_type?.startsWith("image/");
    if (!isPdf && !isImg) {
      setPreviewBlobUrl(null);
      return;
    }
    let objectUrl = null;
    let cancelled = false;
    api.get(`/documents/${selectedDoc.id}/file`, { responseType: "blob" })
      .then(resp => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(resp.data);
        setPreviewBlobUrl(objectUrl);
      })
      .catch(() => { if (!cancelled) setPreviewBlobUrl(null); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedDoc?.id, selectedDoc?.content_type]);

  const handleSearch = async (q) => {
    setSearchQuery(q);
    if (!q || q.length < 2) { setIsSearching(false); return; }
    setIsSearching(true);
    try {
      const r = await api.get(`/documents/search?q=${encodeURIComponent(q)}`);
      setDocuments(r.data.documents);
    } catch { /* ignore */ }
  };

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    let successCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const isZip = /\.zip$/i.test(file.name) || file.type === "application/zip" || file.type === "application/x-zip-compressed";
      setUploadProgress(`${i + 1}/${files.length}: ${file.name}${isZip ? " (ZIP wird entpackt…)" : ""}`);
      const formData = new FormData();
      formData.append("file", file);
      if (!isZip) formData.append("folder_id", activeFolder || "unbekannt");
      try {
        const endpoint = isZip ? "/documents/upload-zip" : "/documents/upload";
        const r = await api.post(endpoint, formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 180000,
        });
        if (isZip) {
          const merged = r.data.teba_merged;
          const single = r.data.individually_uploaded || [];
          if (merged) {
            toast.success(`ZIP entpackt: TEBA Nr. ${merged.invoice_number} als Sammel-PDF (${merged.source_files.length} Seiten) → ${merged.folder_id} 📦`);
          }
          if (single.length) {
            toast.success(`+ ${single.length} weitere PDF${single.length > 1 ? "s" : ""} einzeln importiert`);
          }
          if (!merged && !single.length) {
            toast.info("ZIP enthielt keine verwertbaren PDFs");
          }
        } else if (r.data.ai_status === "completed") {
          const meta = r.data.ai_metadata || {};
          toast.success(`"${file.name}" erkannt: ${meta.subject || r.data.folder_id}`);
        } else {
          toast.success(`"${file.name}" hochgeladen - KI-Analyse läuft...`);
        }
        successCount++;
      } catch (err) {
        toast.error(`Fehler: ${file.name} - ${err?.response?.data?.detail || "Upload fehlgeschlagen"}`);
      }
    }
    setUploading(false);
    setUploadProgress("");
    if (successCount > 0) {
      loadFolders();
      loadDocuments(activeFolder);
      // Poll for AI analysis completion
      let pollCount = 0;
      const pollInterval = setInterval(async () => {
        pollCount++;
        await loadFolders();
        await loadDocuments(activeFolder);
        // Stop after 60s (12 polls x 5s)
        if (pollCount >= 12) clearInterval(pollInterval);
        // Or stop when no more pending docs
        try {
          const r = await api.get("/documents/list");
          const hasPending = r.data.documents.some(d => d.ai_status === "pending");
          if (!hasPending) clearInterval(pollInterval);
        } catch { /* ignore */ }
      }, 5000);
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm("Dokument wirklich löschen?")) return;
    try {
      await api.delete(`/documents/${docId}`);
      toast.success("Gelöscht");
      loadFolders();
      loadDocuments(activeFolder);
      if (selectedDoc?.id === docId) setSelectedDoc(null);
    } catch { toast.error("Fehler beim Löschen"); }
  };

  const handleMarkAsSpam = async (docId) => {
    if (!window.confirm("Dieses Dokument als Spam markieren?\n\nDer Absender wird auf die Blacklist gesetzt und künftige Mails automatisch gefiltert. Das Dokument wird endgültig gelöscht.")) return;
    try {
      const r = await api.post(`/documents/${docId}/mark-as-spam`);
      if (r.data.blacklisted) {
        const target = r.data.sender_email || r.data.sender_domain;
        toast.success(`Als Spam markiert – "${target}" geblockt 🛡️`);
      } else {
        toast.success("Als Spam markiert (kein Absender erkannt – nur gelöscht)");
      }
      loadFolders();
      loadDocuments(activeFolder);
      if (selectedDoc?.id === docId) setSelectedDoc(null);
    } catch { toast.error("Fehler beim Spam-Markieren"); }
  };

  const handleMove = async (docId, folderId) => {
    try {
      const r = await api.put(`/documents/${docId}/move?folder_id=${folderId}`);
      if (r.data.trained) {
        toast.success("Verschoben - KI hat gelernt 🧠");
      } else {
        toast.success("Verschoben");
      }
      setMoveTarget(null);
      loadFolders();
      loadDocuments(activeFolder);
    } catch { toast.error("Fehler beim Verschieben"); }
  };

  const handleReanalyze = async (docId) => {
    try {
      await api.post(`/documents/${docId}/reanalyze`);
      toast.success("KI analysiert neu…");
      // Status in der Liste sofort aktualisieren
      setDocuments(docs => docs.map(d => d.id === docId ? { ...d, ai_status: "pending" } : d));
      if (selectedDoc?.id === docId) setSelectedDoc({ ...selectedDoc, ai_status: "pending" });
      // Nach 3 s einmal refreshen
      setTimeout(() => { loadFolders(); loadDocuments(activeFolder); }, 3500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Neuanalyse fehlgeschlagen");
    }
  };

  const handleViewDoc = async (docId) => {
    try {
      const r = await api.get(`/documents/${docId}`);
      setSelectedDoc(r.data);
    } catch { toast.error("Fehler"); }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await api.post("/documents/folders", { name: newFolderName.trim(), icon: "folder", color: "gray" });
      toast.success(`Ordner "${newFolderName}" erstellt`);
      setNewFolderName("");
      setShowNewFolder(false);
      loadFolders();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Erstellen");
    }
  };

  const handleCreateSubfolder = async (parentId) => {
    if (!subfolderName.trim()) return;
    try {
      await api.post("/documents/folders", { name: subfolderName.trim(), icon: "folder", color: "gray", parent_id: parentId });
      toast.success(`Unterordner "${subfolderName}" erstellt`);
      setSubfolderName("");
      setAddSubfolderTo(null);
      setExpandedFolders(prev => ({ ...prev, [parentId]: true }));
      loadFolders();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Erstellen");
    }
  };

  const toggleExpand = (folderId) => {
    setExpandedFolders(prev => ({ ...prev, [folderId]: !prev[folderId] }));
  };

  const handleRenameFolder = async (folderId) => {
    if (!editFolderName.trim()) return;
    try {
      await api.put(`/documents/folders/${folderId}`, { name: editFolderName.trim() });
      toast.success("Ordner umbenannt");
      setEditingFolder(null);
      setEditFolderName("");
      loadFolders();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler");
    }
  };

  const handleDeleteFolder = async (folderId, folderName) => {
    if (!window.confirm(`Ordner "${folderName}" löschen? Dokumente werden nach "Sonstiges" verschoben.`)) return;
    try {
      await api.delete(`/documents/folders/${folderId}`);
      toast.success(`Ordner "${folderName}" gelöscht`);
      if (activeFolder === folderId) setActiveFolder(null);
      loadFolders();
      loadDocuments(activeFolder === folderId ? null : activeFolder);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer?.files;
    if (files) handleUpload(Array.from(files));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="document-management-page">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200">
        <div className="px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")} className="text-gray-600 hover:text-fuchsia-600 flex-shrink-0" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Verwaltung
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <h1 className="text-base font-semibold text-gray-900">Dokumentenverwaltung</h1>
          <span className="text-xs text-gray-400 ml-1">{totalDocs} Dokumente</span>
          <div className="flex-1" />
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Suchen (Verwendungszweck, Firma, IBAN...)"
              value={searchQuery}
              onChange={e => handleSearch(e.target.value)}
              className="pl-9 h-9 text-sm"
              data-testid="search-input"
            />
            {searchQuery && (
              <button onClick={() => { setSearchQuery(""); setIsSearching(false); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <Button size="sm" onClick={() => fileInput.current?.click()} disabled={uploading} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="upload-btn">
            {uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />}
            {uploading ? uploadProgress : "Hochladen"}
          </Button>
          {/* Mailbridge-Refresh: holt neue Mails aus post@eventenergie.app */}
          {mailbridge?.configured && (
            <div className="flex items-center gap-1.5 pl-2 ml-1 border-l border-gray-200" data-testid="mailbridge-section">
              <Button
                size="sm"
                variant="outline"
                onClick={handleMailbridgeRefresh}
                disabled={mailbridgeLoading}
                className={`text-xs ${mailbridge.password_set ? "text-fuchsia-600 border-fuchsia-200 hover:bg-fuchsia-50" : "text-amber-600 border-amber-200"}`}
                title={mailbridge.password_set
                  ? `Postfach ${mailbridge.user} jetzt prüfen`
                  : "IMAP-Passwort fehlt in backend/.env"}
                data-testid="mailbridge-refresh-btn"
              >
                {mailbridgeLoading
                  ? <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  : mailbridge.password_set
                    ? <Mail className="w-4 h-4 mr-1" />
                    : <AlertCircle className="w-4 h-4 mr-1" />}
                {mailbridgeLoading ? "Prüfe..." : "Postfach prüfen"}
              </Button>
              {mailbridgeLastRunText && (
                <div className="hidden xl:flex items-center gap-1 text-[10px] text-gray-400" title="Letzter IMAP-Abruf">
                  <Clock className="w-3 h-3" />
                  <span>{mailbridgeLastRunText}</span>
                </div>
              )}
            </div>
          )}
          <input ref={fileInput} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.tiff,.zip" className="hidden" onChange={e => handleUpload(Array.from(e.target.files))} />
        </div>
      </header>

      <div className="flex-1 flex w-full overflow-hidden" style={{ maxHeight: "calc(100vh - 57px)" }}>
        {/* Folder Sidebar */}
        <aside className="w-56 lg:w-64 flex-shrink-0 bg-white border-r border-gray-200 p-3 overflow-y-auto">
          <button
            onClick={() => { setActiveFolder(null); setIsSearching(false); setSearchQuery(""); }}
            className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              !activeFolder && !isSearching ? "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-300" : "text-gray-700 hover:bg-gray-100"
            }`}
            data-testid="folder-all"
          >
            <FolderOpen className="w-4 h-4" />
            <span className="flex-1 text-left">Alle Dokumente</span>
            <span className="text-xs text-gray-400">{totalDocs}</span>
          </button>

          <div className="h-px bg-gray-200 my-2" />

          <FolderTree
            folders={folders}
            activeFolder={activeFolder}
            isSearching={isSearching}
            expandedFolders={expandedFolders}
            toggleExpand={toggleExpand}
            setActiveFolder={(id) => { setActiveFolder(id); setIsSearching(false); setSearchQuery(""); }}
            editingFolder={editingFolder}
            editFolderName={editFolderName}
            setEditFolderName={setEditFolderName}
            setEditingFolder={setEditingFolder}
            handleRenameFolder={handleRenameFolder}
            handleDeleteFolder={handleDeleteFolder}
            addSubfolderTo={addSubfolderTo}
            setAddSubfolderTo={setAddSubfolderTo}
            subfolderName={subfolderName}
            setSubfolderName={setSubfolderName}
            handleCreateSubfolder={handleCreateSubfolder}
            onDropDoc={handleMove}
          />

          <div className="h-px bg-gray-200 my-2" />

          {showNewFolder ? (
            <div className="flex items-center gap-1 px-2 py-1.5">
              <Input
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") handleCreateFolder(); if (e.key === "Escape") { setShowNewFolder(false); setNewFolderName(""); } }}
                placeholder="Ordnername..."
                className="h-7 text-xs flex-1"
                autoFocus
                data-testid="new-folder-input"
              />
              <button onClick={handleCreateFolder} className="p-1 text-emerald-600 hover:bg-emerald-50 rounded" data-testid="new-folder-confirm"><Check className="w-3.5 h-3.5" /></button>
              <button onClick={() => { setShowNewFolder(false); setNewFolderName(""); }} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><X className="w-3 h-3" /></button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewFolder(true)}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              data-testid="new-folder-btn"
            >
              <FolderPlus className="w-4 h-4" />
              <span>Neuer Ordner</span>
            </button>
          )}
        </aside>

        {/* Main Content */}
        <main className="flex-1 min-w-0 p-4 overflow-y-auto" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
          {/* Drop Zone */}
          <div
            onClick={() => fileInput.current?.click()}
            className={`mb-4 border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
              dragOver
                ? "border-fuchsia-400 bg-fuchsia-50"
                : uploading
                ? "border-blue-300 bg-blue-50"
                : "border-gray-200 bg-white hover:border-fuchsia-300 hover:bg-fuchsia-50/30"
            }`}
            data-testid="drop-zone"
          >
            {uploading ? (
              <div className="flex items-center justify-center gap-3">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                <span className="text-sm text-blue-600 font-medium">{uploadProgress}</span>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <Upload className={`w-5 h-5 ${dragOver ? "text-fuchsia-500" : "text-gray-400"}`} />
                <span className={`text-sm ${dragOver ? "text-fuchsia-600 font-medium" : "text-gray-500"}`}>
                  {dragOver ? "Dateien hier ablegen" : "PDF · Bilder · ZIP hierher ziehen oder klicken zum Hochladen"}
                </span>
                <span className="text-xs text-gray-400">PDF, JPEG, PNG, WebP, TIFF</span>
              </div>
            )}
          </div>
          {isSearching && (
            <div className="mb-4 flex items-center gap-2 text-sm text-gray-600">
              <Search className="w-4 h-4" />
              <span>Suchergebnisse für „<strong>{searchQuery}</strong>&ldquo; — {documents.length} Treffer</span>
            </div>
          )}

          {documents.length === 0 && !uploading ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <h3 className="text-base font-medium text-gray-500 mb-1">
                {isSearching ? "Keine Treffer" : "Noch keine Dokumente in diesem Ordner"}
              </h3>
              <p className="text-sm text-gray-400">
                {isSearching ? "Versuchen Sie andere Suchbegriffe." : "Laden Sie Dokumente über die Zone oben hoch."}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map(doc => {
                const meta = doc.ai_metadata || {};
                const folderInfo = folders.find(f => f.id === doc.folder_id);
                const FIcon = folderInfo ? (FOLDER_ICONS[folderInfo.icon] || Folder) : Folder;
                const fc = folderInfo ? (FOLDER_COLORS[folderInfo.color] || FOLDER_COLORS.gray) : FOLDER_COLORS.gray;
                return (
                  <div
                    key={doc.id}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/x-doc-id", doc.id);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 hover:shadow-sm transition-all group cursor-pointer active:cursor-grabbing"
                    onClick={() => handleViewDoc(doc.id)}
                    data-testid={`doc-${doc.id}`}
                    title="Ziehe diese Datei auf einen Ordner in der Seitenleiste, um sie zu verschieben"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg ${fc.bg} flex items-center justify-center flex-shrink-0`}>
                        <FIcon className={`w-5 h-5 ${fc.text}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <h3 className="text-sm font-semibold text-gray-900 truncate">{(meta.subject && !["Analyse fehlgeschlagen", "Nicht erkannt"].includes(meta.subject)) ? meta.subject : doc.original_filename}</h3>
                          {doc.ai_status === "completed" && (
                            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-medium flex-shrink-0">
                              <Brain className="w-3 h-3" /> KI erkannt
                            </span>
                          )}
                          {doc.ai_status === "pending" && (
                            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-medium flex-shrink-0">
                              <Loader2 className="w-3 h-3 animate-spin" /> Analyse...
                            </span>
                          )}
                          {doc.ai_status === "failed" && (
                            <span
                              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-rose-50 text-rose-600 text-[10px] font-medium flex-shrink-0 cursor-help"
                              title={doc.ai_error || "KI-Analyse fehlgeschlagen"}
                              data-testid={`ai-failed-badge-${doc.id}`}
                            >
                              <AlertTriangle className="w-3 h-3" /> KI-Fehler
                            </span>
                          )}
                          {doc.datev_forwarded && (
                            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 text-[10px] font-medium flex-shrink-0">
                              <Send className="w-3 h-3" /> DATEV
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-500">
                          {meta.sender && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{meta.sender}</span>}
                          {meta.date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(meta.date)}</span>}
                          {meta.amount && <span className="flex items-center gap-1"><Euro className="w-3 h-3" />{meta.amount.toFixed(2)} {meta.currency || "EUR"}</span>}
                          {meta.invoice_number && <span className="flex items-center gap-1"><Hash className="w-3 h-3" />{meta.invoice_number}</span>}
                          {meta.reference && <span className="flex items-center gap-1"><Tag className="w-3 h-3" />{meta.reference}</span>}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-400">
                          <span>{doc.original_filename}</span>
                          <span>{formatFileSize(doc.size)}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDate(doc.created_at)}</span>
                          {folderInfo && <span className={`px-1.5 py-0.5 rounded ${fc.bg} ${fc.text} text-[10px] font-medium`}>{folderInfo.name}</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                        <button onClick={() => handleViewDoc(doc.id)} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600" title="Ansehen" data-testid={`view-${doc.id}`}>
                          <Eye className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleReanalyze(doc.id)} className="p-1.5 rounded-md hover:bg-violet-50 text-gray-400 hover:text-violet-600" title="KI neu analysieren" data-testid={`reanalyze-${doc.id}`}>
                          <Sparkles className="w-4 h-4" />
                        </button>
                        <button onClick={() => setMoveTarget(doc)} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600" title="Verschieben" data-testid={`move-${doc.id}`}>
                          <MoveRight className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleMarkAsSpam(doc.id)} className="p-1.5 rounded-md hover:bg-orange-50 text-gray-400 hover:text-orange-600" title="Als Spam markieren (Absender blocken)" data-testid={`spam-${doc.id}`}>
                          <Ban className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleDelete(doc.id)} className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600" title="Löschen" data-testid={`delete-${doc.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </main>

        {/* Document Detail Sidebar - Overlay */}
        {selectedDoc && (
          <>
            <div className="fixed inset-0 bg-black/20 z-30" onClick={() => setSelectedDoc(null)} />
            <aside className="fixed top-0 right-0 h-full w-96 bg-white border-l border-gray-200 overflow-y-auto z-40 shadow-2xl animate-in slide-in-from-right duration-200">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Details</h3>
              <button onClick={() => setSelectedDoc(null)} className="text-gray-400 hover:text-gray-600" data-testid="close-detail"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 space-y-4">
              {/* Preview */}
              {selectedDoc.content_type?.startsWith("image/") && previewBlobUrl && (
                <div className="rounded-lg overflow-hidden border border-gray-200">
                  <img src={previewBlobUrl} alt="" className="w-full" />
                </div>
              )}
              {selectedDoc.content_type === "application/pdf" && (
                <div className="rounded-lg overflow-hidden border border-gray-200 bg-gray-100">
                  {previewBlobUrl ? (
                    <object
                      data={previewBlobUrl}
                      type="application/pdf"
                      className="w-full bg-white block"
                      style={{ height: "360px" }}
                      data-testid="pdf-preview-iframe"
                    >
                      <iframe
                        src={previewBlobUrl}
                        title="PDF Vorschau"
                        className="w-full bg-white"
                        style={{ height: "360px", border: 0 }}
                      />
                    </object>
                  ) : (
                    <div className="flex items-center justify-center h-[360px] text-xs text-gray-400">
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Vorschau wird geladen...
                    </div>
                  )}
                  <div className="border-t border-gray-200 px-3 py-1.5 flex justify-end gap-3">
                    {previewBlobUrl && (
                      <a href={previewBlobUrl} target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline text-xs flex items-center gap-1">
                        <Maximize2 className="w-3 h-3" /> In neuem Tab
                      </a>
                    )}
                    <a href={`${API}/api/documents/${selectedDoc.id}/file`} target="_blank" rel="noreferrer" className="text-gray-500 hover:text-fuchsia-600 hover:underline text-xs flex items-center gap-1" data-testid="pdf-open-new-tab">
                      Direkt-Download
                    </a>
                  </div>
                </div>
              )}

              {/* Filename */}
              <div>
                <p className="text-[11px] text-gray-400 mb-0.5">Dateiname</p>
                <p className="text-sm text-gray-900 font-medium">{selectedDoc.original_filename}</p>
              </div>

              {/* AI Failed Banner */}
              {selectedDoc.ai_status === "failed" && (
                <div className="bg-rose-50 border border-rose-200 rounded-lg p-3" data-testid="ai-failed-banner">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-rose-700">KI-Analyse fehlgeschlagen</p>
                      <p className="text-xs text-rose-600 mt-0.5 break-words">{selectedDoc.ai_error || "Unbekannter Fehler bei der Analyse."}</p>
                      <p className="text-[11px] text-rose-500 mt-1.5">Klicke unten auf &quot;KI neu analysieren&quot;, sobald der KI-Server wieder antwortet.</p>
                    </div>
                  </div>
                </div>
              )}

              {/* AI Metadata */}
              {selectedDoc.ai_status === "completed" && selectedDoc.ai_metadata && (
                <>
                  <div className="flex items-center gap-1.5 text-emerald-600 text-xs font-medium">
                    <Brain className="w-3.5 h-3.5" /> KI-Analyse abgeschlossen
                    {selectedDoc.ai_metadata.manually_edited && (
                      <>
                        <span className="ml-1 text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full" data-testid="manually-edited-badge">manuell korrigiert</span>
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              const { data } = await api.post(`/documents/${selectedDoc.id}/save-as-training-sample`);
                              toast.success(`Als Trainings-Beispiel gespeichert (ID ${data.id.slice(0, 8)}...)`);
                            } catch (e) {
                              toast.error(`Fehlgeschlagen: ${e?.response?.data?.detail || e.message}`);
                            }
                          }}
                          className="ml-1 text-[10px] text-violet-600 bg-violet-50 hover:bg-violet-100 px-1.5 py-0.5 rounded-full flex items-center gap-1 transition-colors"
                          title="Diese Korrektur als KI-Trainingsbeispiel speichern - hilft dem Modell aehnliche Faelle kuenftig richtig zu erkennen"
                          data-testid="save-training-sample-btn"
                        >
                          <Sparkles className="w-3 h-3" /> Als Beispiel lernen
                        </button>
                      </>
                    )}
                  </div>
                  {selectedDoc.datev_forwarded && (
                    <div className="flex items-center gap-1.5 text-blue-600 text-xs font-medium">
                      <Send className="w-3.5 h-3.5" /> An DATEV weitergeleitet
                      {selectedDoc.datev_forwarded_at && <span className="text-gray-400 ml-1">({formatDate(selectedDoc.datev_forwarded_at)})</span>}
                    </div>
                  )}
                  {[
                    { key: "subject", label: "Betreff", type: "text",
                      skip: (v) => ["Analyse fehlgeschlagen", "Nicht erkannt"].includes(v) },
                    { key: "document_type", label: "Dokumententyp", type: "text", capitalize: true },
                    { key: "sender", label: "Absender", type: "text" },
                    { key: "recipient", label: "Empfänger", type: "text" },
                    { key: "date", label: "Dokumentdatum", type: "date", format: formatDate },
                    { key: "amount", label: "Betrag", type: "number",
                      format: (v) => `${Number(v).toFixed(2)} ${selectedDoc.ai_metadata.currency || "EUR"}`, valueClass: "font-semibold" },
                    { key: "tax_amount", label: "MwSt", type: "number", format: (v) => `${Number(v).toFixed(2)} EUR` },
                    { key: "invoice_number", label: "Rechnungsnummer", type: "text" },
                    { key: "reference", label: "Referenz / Verwendungszweck", type: "text" },
                    { key: "iban", label: "IBAN", type: "text", valueClass: "font-mono text-xs" },
                    { key: "due_date", label: "Fälligkeitsdatum", type: "date", format: formatDate },
                  ].map((f) => {
                    const val = selectedDoc.ai_metadata[f.key];
                    if (val == null || val === "") return null;
                    if (f.skip && f.skip(val)) return null;
                    return (
                      <EditableMetaField
                        key={f.key}
                        docId={selectedDoc.id}
                        fieldKey={f.key}
                        label={f.label}
                        value={val}
                        type={f.type}
                        format={f.format}
                        valueClass={f.valueClass || ""}
                        capitalize={f.capitalize}
                        onSaved={(newMeta) => setSelectedDoc((d) => d ? { ...d, ai_metadata: newMeta } : d)}
                      />
                    );
                  })}
                  {selectedDoc.keywords?.length > 0 && (
                    <div>
                      <p className="text-[11px] text-gray-400 mb-1">Stichwörter</p>
                      <div className="flex flex-wrap gap-1">
                        {selectedDoc.keywords.map((k, i) => (
                          <span key={i} className="px-2 py-0.5 bg-gray-100 rounded-full text-[11px] text-gray-600">{k}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Full Text Preview */}
              {selectedDoc.full_text && (
                <div>
                  <p className="text-[11px] text-gray-400 mb-1">Extrahierter Text</p>
                  <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 max-h-40 overflow-y-auto font-mono whitespace-pre-wrap">
                    {selectedDoc.full_text.substring(0, 1000)}{selectedDoc.full_text.length > 1000 ? "..." : ""}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="pt-2 space-y-2">
                <a href={`${API}/api/documents/${selectedDoc.id}/file`} target="_blank" rel="noreferrer" className="block">
                  <Button variant="outline" size="sm" className="w-full" data-testid="download-doc-btn">
                    <Eye className="w-4 h-4 mr-1" /> Datei öffnen
                  </Button>
                </a>
                <Button variant="outline" size="sm" className="w-full text-violet-600 hover:text-violet-700 hover:bg-violet-50" onClick={() => handleReanalyze(selectedDoc.id)} data-testid="detail-reanalyze-btn">
                  <Sparkles className="w-4 h-4 mr-1" /> KI neu analysieren
                </Button>
                <Button variant="outline" size="sm" className="w-full text-orange-600 hover:text-orange-700 hover:bg-orange-50" onClick={() => handleMarkAsSpam(selectedDoc.id)} data-testid="detail-spam-btn">
                  <Ban className="w-4 h-4 mr-1" /> Als Spam markieren
                </Button>
                <Button variant="outline" size="sm" className="w-full text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleDelete(selectedDoc.id)} data-testid="detail-delete-btn">
                  <Trash2 className="w-4 h-4 mr-1" /> Löschen
                </Button>
              </div>
            </div>
          </aside>
          </>
        )}
      </div>

      {/* Move Modal */}
      {moveTarget && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setMoveTarget(null)} data-testid="move-modal">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 text-sm">Verschieben nach...</h3>
              <button onClick={() => setMoveTarget(null)} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-3 space-y-1">
              {folders.map(f => {
                const Icon = FOLDER_ICONS[f.icon] || Folder;
                const c = FOLDER_COLORS[f.color] || FOLDER_COLORS.gray;
                return (
                  <button
                    key={f.id}
                    onClick={() => handleMove(moveTarget.id, f.id)}
                    disabled={f.id === moveTarget.folder_id}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                      f.id === moveTarget.folder_id ? "bg-gray-50 text-gray-400 cursor-not-allowed" : "hover:bg-gray-100 text-gray-700"
                    }`}
                    data-testid={`move-to-${f.id}`}
                  >
                    <div className={`w-7 h-7 rounded-md ${c.bg} flex items-center justify-center`}>
                      <Icon className={`w-3.5 h-3.5 ${c.text}`} />
                    </div>
                    <span className="flex-1 text-left">{f.name}</span>
                    {f.id === moveTarget.folder_id && <span className="text-xs text-gray-400">aktuell</span>}
                    {f.id !== moveTarget.folder_id && <ChevronRight className="w-4 h-4 text-gray-300" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
