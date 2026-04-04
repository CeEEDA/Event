import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Upload, FolderOpen, FileText, Receipt, Car, Shield,
  Truck, Landmark, Folder, X, ChevronRight, Eye, Trash2, MoveRight,
  Loader2, Brain, Calendar, Euro, Hash, Building2, Tag, Clock,
  FolderPlus, Pencil, Check
} from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${API}/api` });

const FOLDER_ICONS = {
  receipt: Receipt, car: Car, shield: Shield, "file-text": FileText,
  truck: Truck, landmark: Landmark, folder: Folder,
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
      setUploadProgress(`${i + 1}/${files.length}: ${file.name}`);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("folder_id", activeFolder || "sonstiges");
      try {
        const r = await api.post("/documents/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 120000,
        });
        if (r.data.ai_status === "completed") {
          const meta = r.data.ai_metadata || {};
          toast.success(`"${file.name}" erkannt: ${meta.subject || r.data.folder_id}`);
        } else {
          toast.success(`"${file.name}" hochgeladen`);
        }
        successCount++;
      } catch (err) {
        toast.error(`Fehler: ${file.name} - ${err?.response?.data?.detail || "Upload fehlgeschlagen"}`);
      }
    }
    setUploading(false);
    setUploadProgress("");
    if (successCount > 0) { loadFolders(); loadDocuments(activeFolder); }
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

  const handleMove = async (docId, folderId) => {
    try {
      await api.put(`/documents/${docId}/move?folder_id=${folderId}`);
      toast.success("Verschoben");
      setMoveTarget(null);
      loadFolders();
      loadDocuments(activeFolder);
    } catch { toast.error("Fehler beim Verschieben"); }
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
    const files = e.dataTransfer?.files;
    if (files) handleUpload(Array.from(files));
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="document-management-page">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
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
          <input ref={fileInput} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.tiff" className="hidden" onChange={e => handleUpload(Array.from(e.target.files))} />
        </div>
      </header>

      <div className="flex-1 flex max-w-7xl mx-auto w-full">
        {/* Folder Sidebar */}
        <aside className="w-64 flex-shrink-0 bg-white border-r border-gray-200 p-4 space-y-1">
          <button
            onClick={() => { setActiveFolder(null); setIsSearching(false); setSearchQuery(""); }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              !activeFolder && !isSearching ? "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-300" : "text-gray-700 hover:bg-gray-100"
            }`}
            data-testid="folder-all"
          >
            <FolderOpen className="w-4 h-4" />
            <span className="flex-1 text-left">Alle Dokumente</span>
            <span className="text-xs text-gray-400">{totalDocs}</span>
          </button>

          <div className="h-px bg-gray-200 my-2" />

          {folders.map(f => {
            const Icon = FOLDER_ICONS[f.icon] || Folder;
            const c = FOLDER_COLORS[f.color] || FOLDER_COLORS.gray;
            const isActive = activeFolder === f.id && !isSearching;
            const isEditing = editingFolder === f.id;
            return (
              <div key={f.id} className="group/folder relative">
                {isEditing ? (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <Input
                      value={editFolderName}
                      onChange={e => setEditFolderName(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") handleRenameFolder(f.id); if (e.key === "Escape") setEditingFolder(null); }}
                      className="h-8 text-sm flex-1"
                      autoFocus
                      data-testid={`rename-input-${f.id}`}
                    />
                    <button onClick={() => handleRenameFolder(f.id)} className="p-1 text-emerald-600 hover:bg-emerald-50 rounded" data-testid={`rename-confirm-${f.id}`}><Check className="w-4 h-4" /></button>
                    <button onClick={() => setEditingFolder(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><X className="w-3.5 h-3.5" /></button>
                  </div>
                ) : (
                  <button
                    onClick={() => { setActiveFolder(f.id); setIsSearching(false); setSearchQuery(""); }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                      isActive ? `${c.active} font-medium border` : "text-gray-700 hover:bg-gray-100 border border-transparent"
                    }`}
                    data-testid={`folder-${f.id}`}
                  >
                    <div className={`w-7 h-7 rounded-md ${c.bg} flex items-center justify-center flex-shrink-0`}>
                      <Icon className={`w-3.5 h-3.5 ${c.text}`} />
                    </div>
                    <span className="flex-1 text-left truncate">{f.name}</span>
                    <span className="text-xs text-gray-400">{f.count}</span>
                    {f.is_custom && (
                      <div className="hidden group-hover/folder:flex items-center gap-0.5 ml-1" onClick={e => e.stopPropagation()}>
                        <button onClick={() => { setEditingFolder(f.id); setEditFolderName(f.name); }} className="p-0.5 text-gray-300 hover:text-gray-600 rounded" title="Umbenennen" data-testid={`edit-folder-${f.id}`}><Pencil className="w-3 h-3" /></button>
                        <button onClick={() => handleDeleteFolder(f.id, f.name)} className="p-0.5 text-gray-300 hover:text-red-600 rounded" title="Löschen" data-testid={`delete-folder-${f.id}`}><Trash2 className="w-3 h-3" /></button>
                      </div>
                    )}
                  </button>
                )}
              </div>
            );
          })}

          <div className="h-px bg-gray-200 my-2" />

          {showNewFolder ? (
            <div className="flex items-center gap-1 px-2 py-1.5">
              <Input
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") handleCreateFolder(); if (e.key === "Escape") { setShowNewFolder(false); setNewFolderName(""); } }}
                placeholder="Ordnername..."
                className="h-8 text-sm flex-1"
                autoFocus
                data-testid="new-folder-input"
              />
              <button onClick={handleCreateFolder} className="p-1 text-emerald-600 hover:bg-emerald-50 rounded" data-testid="new-folder-confirm"><Check className="w-4 h-4" /></button>
              <button onClick={() => { setShowNewFolder(false); setNewFolderName(""); }} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><X className="w-3.5 h-3.5" /></button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewFolder(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              data-testid="new-folder-btn"
            >
              <FolderPlus className="w-4 h-4" />
              <span>Neuer Ordner</span>
            </button>
          )}
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-4" onDragOver={e => e.preventDefault()} onDrop={handleDrop}>
          {isSearching && (
            <div className="mb-4 flex items-center gap-2 text-sm text-gray-600">
              <Search className="w-4 h-4" />
              <span>Suchergebnisse für "<strong>{searchQuery}</strong>" — {documents.length} Treffer</span>
            </div>
          )}

          {documents.length === 0 && !uploading ? (
            <div className="flex flex-col items-center justify-center py-20 text-center"
              onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-fuchsia-400", "bg-fuchsia-50"); }}
              onDragLeave={e => { e.currentTarget.classList.remove("border-fuchsia-400", "bg-fuchsia-50"); }}
              onDrop={handleDrop}
            >
              <div className="w-20 h-20 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
                <Upload className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-medium text-gray-700 mb-1">
                {isSearching ? "Keine Treffer" : "Noch keine Dokumente"}
              </h3>
              <p className="text-sm text-gray-500 mb-4 max-w-xs">
                {isSearching ? "Versuchen Sie andere Suchbegriffe." : "Ziehen Sie Dateien hierher oder klicken Sie auf \"Hochladen\". Die KI erkennt automatisch Typ und Ordner."}
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
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 hover:shadow-sm transition-all group cursor-pointer"
                    onClick={() => handleViewDoc(doc.id)}
                    data-testid={`doc-${doc.id}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg ${fc.bg} flex items-center justify-center flex-shrink-0`}>
                        <FIcon className={`w-5 h-5 ${fc.text}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <h3 className="text-sm font-semibold text-gray-900 truncate">{meta.subject || doc.original_filename}</h3>
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
                        <button onClick={() => setMoveTarget(doc)} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600" title="Verschieben" data-testid={`move-${doc.id}`}>
                          <MoveRight className="w-4 h-4" />
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

        {/* Document Detail Sidebar */}
        {selectedDoc && (
          <aside className="w-80 flex-shrink-0 bg-white border-l border-gray-200 overflow-y-auto">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Details</h3>
              <button onClick={() => setSelectedDoc(null)} className="text-gray-400 hover:text-gray-600" data-testid="close-detail"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 space-y-4">
              {/* Preview */}
              {selectedDoc.content_type?.startsWith("image/") && (
                <div className="rounded-lg overflow-hidden border border-gray-200">
                  <img src={`${API}/api/documents/${selectedDoc.id}/file`} alt="" className="w-full" />
                </div>
              )}
              {selectedDoc.content_type === "application/pdf" && (
                <div className="rounded-lg overflow-hidden border border-gray-200 bg-gray-50 h-48 flex items-center justify-center">
                  <a href={`${API}/api/documents/${selectedDoc.id}/file`} target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline text-sm flex items-center gap-1">
                    <FileText className="w-5 h-5" /> PDF anzeigen
                  </a>
                </div>
              )}

              {/* Filename */}
              <div>
                <p className="text-[11px] text-gray-400 mb-0.5">Dateiname</p>
                <p className="text-sm text-gray-900 font-medium">{selectedDoc.original_filename}</p>
              </div>

              {/* AI Metadata */}
              {selectedDoc.ai_status === "completed" && selectedDoc.ai_metadata && (
                <>
                  <div className="flex items-center gap-1.5 text-emerald-600 text-xs font-medium">
                    <Brain className="w-3.5 h-3.5" /> KI-Analyse abgeschlossen
                  </div>
                  {selectedDoc.ai_metadata.subject && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Betreff</p><p className="text-sm text-gray-900">{selectedDoc.ai_metadata.subject}</p></div>
                  )}
                  {selectedDoc.ai_metadata.document_type && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Dokumententyp</p><p className="text-sm text-gray-900 capitalize">{selectedDoc.ai_metadata.document_type}</p></div>
                  )}
                  {selectedDoc.ai_metadata.sender && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Absender</p><p className="text-sm text-gray-900">{selectedDoc.ai_metadata.sender}</p></div>
                  )}
                  {selectedDoc.ai_metadata.date && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Dokumentdatum</p><p className="text-sm text-gray-900">{formatDate(selectedDoc.ai_metadata.date)}</p></div>
                  )}
                  {selectedDoc.ai_metadata.amount != null && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Betrag</p><p className="text-sm text-gray-900 font-semibold">{selectedDoc.ai_metadata.amount.toFixed(2)} {selectedDoc.ai_metadata.currency || "EUR"}</p></div>
                  )}
                  {selectedDoc.ai_metadata.tax_amount != null && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">MwSt</p><p className="text-sm text-gray-900">{selectedDoc.ai_metadata.tax_amount.toFixed(2)} EUR</p></div>
                  )}
                  {selectedDoc.ai_metadata.invoice_number && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Rechnungsnummer</p><p className="text-sm text-gray-900">{selectedDoc.ai_metadata.invoice_number}</p></div>
                  )}
                  {selectedDoc.ai_metadata.reference && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Referenz / Verwendungszweck</p><p className="text-sm text-gray-900">{selectedDoc.ai_metadata.reference}</p></div>
                  )}
                  {selectedDoc.ai_metadata.iban && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">IBAN</p><p className="text-sm text-gray-900 font-mono text-xs">{selectedDoc.ai_metadata.iban}</p></div>
                  )}
                  {selectedDoc.ai_metadata.due_date && (
                    <div><p className="text-[11px] text-gray-400 mb-0.5">Fälligkeitsdatum</p><p className="text-sm text-gray-900">{formatDate(selectedDoc.ai_metadata.due_date)}</p></div>
                  )}
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
                <Button variant="outline" size="sm" className="w-full text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleDelete(selectedDoc.id)} data-testid="detail-delete-btn">
                  <Trash2 className="w-4 h-4 mr-1" /> Löschen
                </Button>
              </div>
            </div>
          </aside>
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
