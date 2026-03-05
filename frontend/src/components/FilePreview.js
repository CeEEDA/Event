import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { X, Download, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import api from "../lib/api";
import { downloadFile } from "../lib/api";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const FilePreview = ({ open, onClose, file, files }) => {
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);

  // Previewable files from the list
  const previewableFiles = files?.filter(f => 
    f.content_type?.startsWith("image/") || f.content_type === "application/pdf"
  ) || [];
  const currentIndex = previewableFiles.findIndex(f => f.id === file?.id);

  useEffect(() => {
    if (!open || !file) {
      setPreviewUrl(null);
      return;
    }
    loadPreview(file);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, file?.id]);

  const loadPreview = async (f) => {
    if (!f) return;
    const ct = f.content_type || "";
    if (!ct.startsWith("image/") && ct !== "application/pdf") return;

    setLoading(true);
    try {
      const res = await api.get(`/files/${f.id}/preview`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: ct }));
      setPreviewUrl(url);
    } catch {
      toast.error("Vorschau konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      await downloadFile(file.id, file.original_filename);
    } catch {
      toast.error("Download fehlgeschlagen");
    }
  };

  const navigate = (dir) => {
    if (previewableFiles.length <= 1) return;
    const newIdx = (currentIndex + dir + previewableFiles.length) % previewableFiles.length;
    const newFile = previewableFiles[newIdx];
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    loadPreview(newFile);
    // Trigger parent to change the file (handled via onNavigate if needed)
    if (onClose._onNavigate) onClose._onNavigate(newFile);
  };

  if (!file) return null;

  const isImage = file.content_type?.startsWith("image/");
  const isPdf = file.content_type === "application/pdf";
  const canPreview = isImage || isPdf;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-4xl max-h-[90vh] p-0 overflow-hidden" data-testid="file-preview-modal">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3 min-w-0">
            <FileText className="w-5 h-5 text-fuchsia-600 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-900 truncate">{file.original_filename}</span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {previewableFiles.length > 1 && (
              <>
                <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="h-8 w-8" data-testid="preview-prev">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-xs text-gray-500">{currentIndex + 1}/{previewableFiles.length}</span>
                <Button variant="ghost" size="icon" onClick={() => navigate(1)} className="h-8 w-8" data-testid="preview-next">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </>
            )}
            <Button variant="ghost" size="icon" onClick={handleDownload} className="h-8 w-8 text-gray-500 hover:text-fuchsia-600" data-testid="preview-download">
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Preview Area */}
        <div className="flex items-center justify-center min-h-[400px] max-h-[75vh] overflow-auto bg-gray-100 p-4">
          {loading ? (
            <div className="animate-pulse text-gray-500">Laden...</div>
          ) : !canPreview ? (
            <div className="text-center text-gray-500">
              <FileText className="w-16 h-16 mx-auto mb-3 text-gray-300" />
              <p>Keine Vorschau verfügbar</p>
            </div>
          ) : isImage && previewUrl ? (
            <img
              src={previewUrl}
              alt={file.original_filename}
              className="max-w-full max-h-[70vh] object-contain rounded shadow-lg"
              data-testid="preview-image"
            />
          ) : isPdf && previewUrl ? (
            <iframe
              src={previewUrl}
              title={file.original_filename}
              className="w-full h-[70vh] rounded border border-gray-200"
              data-testid="preview-pdf"
            />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
};
