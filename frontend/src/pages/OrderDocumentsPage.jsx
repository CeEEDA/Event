import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { ArrowLeft, Upload, FileText, Image, Trash2, Download, Eye } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function OrderDocumentsPage() {
  const { pk } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [orderName, setOrderName] = useState("");
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [previewDoc, setPreviewDoc] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [docsRes, meRes] = await Promise.all([
        api.get(`/orders/order-documents/${pk}`),
        api.get("/auth/me"),
      ]);
      setDocs(docsRes.data);
      setIsAdmin(meRes.data?.role === "admin");
      setOrderName(meRes.data?.name || "");
    } catch {
      toast.error("Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [pk]);

  useEffect(() => {
    loadData();
    // try to get the order name from session
    const cached = sessionStorage.getItem(`order_${pk}_name`);
    if (cached) setOrderName(cached);
  }, [loadData, pk]);

  const uploadFiles = async (files) => {
    const allowed = ["application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"];
    const valid = Array.from(files).filter(f => allowed.includes(f.type));
    if (valid.length === 0) {
      toast.error("Nur PDF und Bilder (JPG, PNG, WebP, GIF) erlaubt");
      return;
    }
    setUploading(true);
    let uploaded = 0;
    for (const file of valid) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        await api.post(`/orders/order-documents/${pk}`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        uploaded++;
      } catch (err) {
        toast.error(`${file.name}: ${getErrorMsg(err, "Upload fehlgeschlagen")}`);
      }
    }
    if (uploaded > 0) {
      toast.success(`${uploaded} Dokument${uploaded > 1 ? "e" : ""} hochgeladen`);
      loadData();
    }
    setUploading(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.length) uploadFiles(e.dataTransfer.files);
  };
  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  const handleDelete = async (docId, name) => {
    if (!window.confirm(`"${name}" wirklich loeschen?`)) return;
    try {
      await api.delete(`/orders/order-documents/${pk}/${docId}`);
      toast.success("Dokument geloescht");
      setDocs(prev => prev.filter(d => d.id !== docId));
      if (previewDoc?.id === docId) setPreviewDoc(null);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Loeschen"));
    }
  };

  const getFileUrl = (doc) =>
    `${BACKEND}/api/orders/order-documents/${pk}/${doc.id}/file?token=${localStorage.getItem("token")}`;

  const isImage = (doc) => doc.content_type?.startsWith("image/");

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;

  const images = docs.filter(isImage);
  const pdfs = docs.filter(d => !isImage(d));

  return (
    <div className="min-h-screen bg-gray-50" data-testid="order-documents-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate(`/orders/${pk}`)} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurueck
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <div>
              <h1 className="text-base font-semibold text-gray-900">Dokumentenablage</h1>
              <p className="text-xs text-gray-500">{orderName}</p>
            </div>
          </div>
          <span className="text-xs text-gray-400">{docs.length} Dokument{docs.length !== 1 ? "e" : ""}</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Upload Area */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            dragging ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-300 hover:border-fuchsia-400 hover:bg-gray-50"
          }`}
          data-testid="upload-dropzone"
        >
          <Upload className={`w-8 h-8 mx-auto mb-3 ${dragging ? "text-fuchsia-500" : "text-gray-400"}`} />
          <p className="text-sm text-gray-600 font-medium">
            {uploading ? "Wird hochgeladen..." : "Dateien hierher ziehen oder klicken"}
          </p>
          <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG, WebP, GIF - max. 20 MB</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.webp,.gif"
            className="hidden"
            onChange={(e) => { if (e.target.files?.length) uploadFiles(e.target.files); e.target.value = ""; }}
            data-testid="file-input"
          />
        </div>

        {/* Image Gallery */}
        {images.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5" data-testid="image-gallery">
            <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Image className="w-4 h-4 text-fuchsia-500" /> Bilder ({images.length})
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {images.map(doc => (
                <div key={doc.id} className="group relative rounded-lg overflow-hidden border border-gray-200 bg-gray-100" data-testid={`img-${doc.id}`}>
                  <img
                    src={getFileUrl(doc)}
                    alt={doc.original_name}
                    className="w-full h-36 object-cover cursor-pointer"
                    onClick={() => setPreviewDoc(doc)}
                  />
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                    <button onClick={() => setPreviewDoc(doc)} className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-fuchsia-600" data-testid={`preview-${doc.id}`}>
                      <Eye className="w-4 h-4" />
                    </button>
                    {isAdmin && (
                      <button onClick={() => handleDelete(doc.id, doc.original_name)} className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-red-500" data-testid={`delete-img-${doc.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  <p className="text-[10px] text-gray-500 px-2 py-1 truncate">{doc.original_name}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PDF List */}
        {pdfs.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5" data-testid="pdf-list">
            <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-4 h-4 text-fuchsia-500" /> PDFs ({pdfs.length})
            </h2>
            <div className="space-y-2">
              {pdfs.map(doc => (
                <div key={doc.id} className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors" data-testid={`pdf-${doc.id}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 bg-red-50 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText className="w-4 h-4 text-red-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{doc.original_name}</p>
                      <p className="text-[10px] text-gray-400">{formatSize(doc.size)} · {new Date(doc.uploaded_at).toLocaleDateString("de-DE")} · {doc.uploaded_by}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <a href={getFileUrl(doc)} target="_blank" rel="noreferrer" className="p-2 text-gray-400 hover:text-fuchsia-600 transition-colors" data-testid={`open-pdf-${doc.id}`}>
                      <Eye className="w-4 h-4" />
                    </a>
                    <a href={getFileUrl(doc)} download={doc.original_name} className="p-2 text-gray-400 hover:text-emerald-600 transition-colors" data-testid={`download-pdf-${doc.id}`}>
                      <Download className="w-4 h-4" />
                    </a>
                    {isAdmin && (
                      <button onClick={() => handleDelete(doc.id, doc.original_name)} className="p-2 text-gray-400 hover:text-red-500 transition-colors" data-testid={`delete-pdf-${doc.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {docs.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">Noch keine Dokumente vorhanden</p>
            <p className="text-xs mt-1">Lageplan, Fotos oder andere Dateien per Drag & Drop hochladen</p>
          </div>
        )}
      </main>

      {/* Image Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setPreviewDoc(null)} data-testid="preview-modal">
          <div className="relative max-w-4xl max-h-[90vh] w-full" onClick={e => e.stopPropagation()}>
            <img
              src={getFileUrl(previewDoc)}
              alt={previewDoc.original_name}
              className="w-full h-auto max-h-[85vh] object-contain rounded-lg"
            />
            <div className="absolute top-3 right-3 flex gap-2">
              <a href={getFileUrl(previewDoc)} download={previewDoc.original_name}
                className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-emerald-600" data-testid="preview-download">
                <Download className="w-5 h-5" />
              </a>
              <button onClick={() => setPreviewDoc(null)}
                className="p-2 bg-white/90 rounded-full text-gray-700 hover:text-gray-900" data-testid="preview-close">
                X
              </button>
            </div>
            <p className="text-white text-sm text-center mt-3">{previewDoc.original_name}</p>
          </div>
        </div>
      )}
    </div>
  );
}
