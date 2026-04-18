import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, Upload, FileText, Trash2, Download, Eye,
  FolderOpen, ClipboardCheck, Map, Camera, FileBox, ChevronRight, X,
  Archive,
} from "lucide-react";

import CameraCapture from "../components/CameraCapture";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const KATEGORIEN = [
  { key: "messprotokolle", label: "Messprotokolle", icon: ClipboardCheck, color: "blue" },
  { key: "plaene",         label: "Plaene",         icon: Map,            color: "emerald" },
  { key: "fotos",          label: "Fotos",          icon: Camera,         color: "amber" },
  { key: "sonstiges",      label: "Sonstiges",      icon: FileBox,        color: "gray" },
];

const COLOR_MAP = {
  blue:    { bg: "bg-blue-50",    text: "text-blue-600",    border: "border-blue-200",    hoverBg: "hover:bg-blue-50" },
  emerald: { bg: "bg-emerald-50", text: "text-emerald-600", border: "border-emerald-200", hoverBg: "hover:bg-emerald-50" },
  amber:   { bg: "bg-amber-50",   text: "text-amber-600",   border: "border-amber-200",   hoverBg: "hover:bg-amber-50" },
  gray:    { bg: "bg-gray-50",    text: "text-gray-600",    border: "border-gray-200",    hoverBg: "hover:bg-gray-50" },
};

export default function OrderDocumentsPage() {
  const { pk } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const [showCamera, setShowCamera] = useState(false);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [activeFolder, setActiveFolder] = useState(null);
  const [previewDoc, setPreviewDoc] = useState(null);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [dragging, setDragging] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [docsRes, meRes] = await Promise.all([
        api.get(`/orders/order-documents/${pk}`),
        api.get("/auth/me"),
      ]);
      setDocs(docsRes.data);
      setIsAdmin(meRes.data?.role === "admin");
    } catch {
      toast.error("Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [pk]);

  useEffect(() => { loadData(); }, [loadData]);

  const detectKategorie = (file) => {
    if (file.type?.startsWith("image/")) return "fotos";
    const n = (file.name || "").toLowerCase();
    if (/mess|protokoll|pru[eü]f|test|messung|abnahme|zertifikat/.test(n)) return "messprotokolle";
    if (/plan|lage|schema|zeichnung|grundriss|skizze|layout|aufbau/.test(n)) return "plaene";
    return "sonstiges";
  };

  const handleFilesSelected = (files, forceKat) => {
    const allowed = ["application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"];
    const valid = Array.from(files).filter(f => allowed.includes(f.type));
    if (valid.length === 0) { toast.error("Nur PDF und Bilder erlaubt"); return; }
    const pending = valid.map(f => ({
      file: f,
      kategorie: forceKat || activeFolder || detectKategorie(f),
      detected: detectKategorie(f),
    }));
    setPendingFiles(pending);
  };

  const handleDrop = (e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files?.length) handleFilesSelected(e.dataTransfer.files); };
  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  const uploadPendingFiles = async () => {
    setUploading(true);
    let uploaded = 0;
    for (const pf of pendingFiles) {
      try {
        const formData = new FormData();
        formData.append("file", pf.file);
        formData.append("kategorie", pf.kategorie);
        await api.post(`/orders/order-documents/${pk}`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        uploaded++;
      } catch (err) {
        toast.error(`${pf.file.name}: ${getErrorMsg(err, "Fehler")}`);
      }
    }
    if (uploaded > 0) {
      toast.success(`${uploaded} Dokument${uploaded > 1 ? "e" : ""} hochgeladen`);
      loadData();
    }
    setPendingFiles([]);
    setUploading(false);
  };

  const handleChangeKategorie = async (docId, newKat) => {
    try {
      await api.put(`/orders/order-documents/${pk}/${docId}`, { kategorie: newKat });
      setDocs(prev => prev.map(d => d.id === docId ? { ...d, kategorie: newKat } : d));
      toast.success("Kategorie geaendert");
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const handleDelete = async (docId, name) => {
    if (!window.confirm(`"${name}" wirklich loeschen?`)) return;
    try {
      await api.delete(`/orders/order-documents/${pk}/${docId}`);
      toast.success("Geloescht");
      setDocs(prev => prev.filter(d => d.id !== docId));
      if (previewDoc?.id === docId) setPreviewDoc(null);
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const downloadZip = () => {
    const token = localStorage.getItem("token");
    window.open(`${BACKEND}/api/orders/order-documents/${pk}/zip?token=${token}`, "_blank");
  };

  const getFileUrl = (doc) =>
    `${BACKEND}/api/orders/order-documents/${pk}/${doc.id}/file?token=${localStorage.getItem("token")}`;
  const isImage = (doc) => doc.content_type?.startsWith("image/");
  const isPdf = (doc) => doc.content_type === "application/pdf";
  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  const katLabel = (key) => KATEGORIEN.find(k => k.key === key)?.label || key;

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;

  const folderDocs = activeFolder ? docs.filter(d => d.kategorie === activeFolder) : [];
  const activeKat = KATEGORIEN.find(k => k.key === activeFolder);
  const colors = activeKat ? COLOR_MAP[activeKat.color] : null;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="order-documents-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => activeFolder ? setActiveFolder(null) : navigate(`/orders/${pk}`)}
              className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> {activeFolder ? "Ordner" : "Zurück"}
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <div>
              <h1 className="text-base font-semibold text-gray-900">{activeFolder ? katLabel(activeFolder) : "Dokumentenablage"}</h1>
              <p className="text-xs text-gray-500">{activeFolder ? `${folderDocs.length} Dokument${folderDocs.length !== 1 ? "e" : ""}` : `${docs.length} Dokumente gesamt`}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Camera button */}
            <Button variant="outline" size="sm" onClick={() => setShowCamera(true)}
              className="text-gray-600" data-testid="camera-btn">
              <Camera className="w-4 h-4 mr-1" /> Foto
            </Button>
            {/* ZIP download */}
            {docs.length > 0 && (
              <Button variant="outline" size="sm" onClick={downloadZip} className="text-gray-600" data-testid="zip-btn">
                <Archive className="w-4 h-4 mr-1" /> ZIP
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {!activeFolder ? (
          <>
            <div onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${dragging ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-300 hover:border-fuchsia-400"}`}
              data-testid="upload-dropzone">
              <Upload className={`w-7 h-7 mx-auto mb-2 ${dragging ? "text-fuchsia-500" : "text-gray-400"}`} />
              <p className="text-sm text-gray-600 font-medium">Dateien hierher ziehen — automatische Zuordnung</p>
              <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG, WebP, GIF - max. 20 MB</p>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.gif" className="hidden"
                onChange={e => { if (e.target.files?.length) handleFilesSelected(e.target.files); e.target.value = ""; }} data-testid="file-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {KATEGORIEN.map(kat => {
                const c = COLOR_MAP[kat.color]; const Icon = kat.icon;
                const count = docs.filter(d => d.kategorie === kat.key).length;
                return (
                  <div key={kat.key} className={`bg-white border ${c.border} rounded-xl p-4 cursor-pointer ${c.hoverBg} transition-all hover:shadow-sm`}
                    onClick={() => setActiveFolder(kat.key)} data-testid={`folder-${kat.key}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 ${c.bg} rounded-lg flex items-center justify-center`}><Icon className={`w-5 h-5 ${c.text}`} /></div>
                        <div><p className="text-sm font-semibold text-gray-900">{kat.label}</p><p className="text-xs text-gray-500">{count} Dokument{count !== 1 ? "e" : ""}</p></div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <>
            <div onDrop={handleDrop} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${dragging ? `${colors.border} ${colors.bg}` : "border-gray-300 hover:border-gray-400"}`}
              data-testid="folder-upload-dropzone">
              <Upload className={`w-6 h-6 mx-auto mb-1 ${dragging ? colors.text : "text-gray-400"}`} />
              <p className="text-sm text-gray-600">In <strong>{katLabel(activeFolder)}</strong> hochladen</p>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.gif" className="hidden"
                onChange={e => { if (e.target.files?.length) handleFilesSelected(e.target.files); e.target.value = ""; }} data-testid="folder-file-input" />
            </div>
            {folderDocs.length === 0 ? (
              <div className="text-center py-10 text-gray-400"><FolderOpen className="w-10 h-10 mx-auto mb-2 text-gray-300" /><p className="text-sm">Ordner ist leer</p></div>
            ) : (
              <div className="space-y-2">
                {folderDocs.map(doc => (
                  <DocRow key={doc.id} doc={doc} isAdmin={isAdmin} onDelete={handleDelete} onPreview={setPreviewDoc}
                    onChangeKat={handleChangeKategorie} getFileUrl={getFileUrl} isImage={isImage} isPdf={isPdf} formatSize={formatSize} />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* Pending Files Dialog */}
      {pendingFiles.length > 0 && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="pending-dialog">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">{pendingFiles.length} Datei{pendingFiles.length !== 1 ? "en" : ""} zuordnen</h3>
              <button onClick={() => setPendingFiles([])} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4 space-y-3 max-h-[55vh] overflow-y-auto">
              {pendingFiles.map((pf, idx) => (
                <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{pf.file.name}</p>
                    <p className="text-xs text-gray-400">{formatSize(pf.file.size)}</p>
                  </div>
                  <select value={pf.kategorie}
                    onChange={e => { const u = [...pendingFiles]; u[idx] = { ...pf, kategorie: e.target.value }; setPendingFiles(u); }}
                    className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 bg-white focus:ring-2 focus:ring-fuchsia-500"
                    data-testid={`pending-kat-${idx}`}>
                    {KATEGORIEN.map(k => <option key={k.key} value={k.key}>{k.label}{k.key === pf.detected ? " (erkannt)" : ""}</option>)}
                  </select>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-gray-200 flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setPendingFiles([])} disabled={uploading}>Abbrechen</Button>
              <Button onClick={uploadPendingFiles} disabled={uploading} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="upload-confirm-btn">
                {uploading ? "Wird hochgeladen..." : `${pendingFiles.length} Datei${pendingFiles.length !== 1 ? "en" : ""} hochladen`}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal (Images + PDFs) */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setPreviewDoc(null)} data-testid="preview-modal">
          <div className="relative max-w-4xl max-h-[90vh] w-full bg-white rounded-lg overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="absolute top-3 right-3 z-10 flex gap-2">
              <a href={getFileUrl(previewDoc)} download={previewDoc.original_name}
                className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-emerald-600 shadow" data-testid="preview-download">
                <Download className="w-5 h-5" />
              </a>
              <button onClick={() => setPreviewDoc(null)}
                className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-gray-900 shadow" data-testid="preview-close">
                <X className="w-5 h-5" />
              </button>
            </div>
            {isImage(previewDoc) ? (
              <img src={getFileUrl(previewDoc)} alt={previewDoc.original_name}
                className="w-full h-auto max-h-[85vh] object-contain" />
            ) : (
              <iframe src={getFileUrl(previewDoc)} title={previewDoc.original_name}
                className="w-full" style={{ height: "85vh" }} />
            )}
            <div className="p-2 text-center bg-gray-50 border-t">
              <p className="text-sm text-gray-700">{previewDoc.original_name}</p>
            </div>
          </div>
        </div>
      )}

      {/* Camera Capture */}
      {showCamera && (
        <CameraCapture
          onClose={() => setShowCamera(false)}
          onCapture={(file) => {
            setShowCamera(false);
            handleFilesSelected([file], "fotos");
          }}
        />
      )}
    </div>
  );
}

function DocRow({ doc, isAdmin, onDelete, onPreview, onChangeKat, getFileUrl, isImage: checkImage, isPdf: checkPdf, formatSize: fmtSize }) {
  const img = checkImage(doc);
  const pdf = checkPdf(doc);
  return (
    <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors" data-testid={`doc-${doc.id}`}>
      <div className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer" onClick={() => onPreview(doc)}>
        {img ? (
          <img src={`${getFileUrl(doc)}${getFileUrl(doc).includes("?") ? "&" : "?"}thumbnail=1&size=120`} loading="lazy" alt="" className="w-12 h-12 rounded-lg object-cover flex-shrink-0" />
        ) : (
          <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-red-500" />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{doc.original_name}</p>
          <p className="text-[10px] text-gray-400">{fmtSize(doc.size)} · {new Date(doc.uploaded_at).toLocaleDateString("de-DE")} · {doc.uploaded_by}</p>
          {(img || pdf) && <p className="text-[10px] text-fuchsia-500 mt-0.5">Klicken fuer Vorschau</p>}
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <select value={doc.kategorie || "sonstiges"} onChange={e => onChangeKat(doc.id, e.target.value)}
          className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-600 mr-1" data-testid={`kat-select-${doc.id}`}>
          {KATEGORIEN.map(k => <option key={k.key} value={k.key}>{k.label}</option>)}
        </select>
        <button onClick={() => onPreview(doc)} className="p-2 text-gray-400 hover:text-fuchsia-600" data-testid={`preview-${doc.id}`}>
          <Eye className="w-4 h-4" />
        </button>
        <a href={getFileUrl(doc)} target="_blank" rel="noreferrer" className="p-2 text-gray-400 hover:text-emerald-600" data-testid={`download-${doc.id}`}>
          <Download className="w-4 h-4" />
        </a>
        {isAdmin && (
          <button onClick={() => onDelete(doc.id, doc.original_name)} className="p-2 text-gray-400 hover:text-red-500" data-testid={`delete-${doc.id}`}>
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
