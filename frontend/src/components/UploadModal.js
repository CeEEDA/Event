import { useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Upload, X, FileText, AlertCircle } from "lucide-react";

export const UploadModal = ({ open, onClose, onUpload, maxSizeMB }) => {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...droppedFiles]);
  }, []);

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files || []);
    setFiles(prev => [...prev, ...selectedFiles]);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setUploading(true);
    await onUpload(files);
    setFiles([]);
    setUploading(false);
  };

  const handleClose = () => {
    if (!uploading) {
      setFiles([]);
      onClose();
    }
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getTotalSize = () => {
    return files.reduce((acc, file) => acc + file.size, 0);
  };

  const isOverLimit = (file) => {
    return file.size > maxSizeMB * 1024 * 1024;
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-card border-border sm:max-w-lg" data-testid="upload-modal">
        <DialogHeader>
          <DialogTitle>Dateien hochladen</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              border-2 border-dashed rounded-sm p-8 text-center transition-colors
              ${isDragging ? "border-primary bg-primary/5" : "border-muted"}
            `}
          >
            <input
              type="file"
              id="file-input"
              multiple
              className="hidden"
              onChange={handleFileSelect}
              data-testid="file-input"
            />
            <label htmlFor="file-input" className="cursor-pointer block">
              <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
              <p className="text-sm font-medium mb-1">
                Dateien hierher ziehen
              </p>
              <p className="text-xs text-muted-foreground">
                oder <span className="text-primary">klicken</span> zum Auswählen
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Max. {maxSizeMB} MB pro Datei
              </p>
            </label>
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin">
              {files.map((file, index) => {
                const overLimit = isOverLimit(file);
                return (
                  <div
                    key={`${file.name}-${index}`}
                    className={`
                      flex items-center gap-3 p-3 rounded-sm bg-muted/30
                      ${overLimit ? "border border-destructive/50" : ""}
                    `}
                    data-testid={`upload-file-${index}`}
                  >
                    {overLimit ? (
                      <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0" />
                    ) : (
                      <FileText className="w-5 h-5 text-primary flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className={`text-xs font-mono ${overLimit ? "text-destructive" : "text-muted-foreground"}`}>
                        {formatSize(file.size)}
                        {overLimit && " - Zu groß!"}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeFile(index)}
                      className="h-8 w-8 flex-shrink-0"
                      disabled={uploading}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Summary & Actions */}
          {files.length > 0 && (
            <div className="flex items-center justify-between pt-2 border-t border-border">
              <p className="text-sm text-muted-foreground">
                {files.length} Datei(en) · {formatSize(getTotalSize())}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleClose}
                  disabled={uploading}
                >
                  Abbrechen
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={uploading || files.every(isOverLimit)}
                  className="bg-primary hover:bg-primary/90"
                  data-testid="confirm-upload-btn"
                >
                  {uploading ? "Wird hochgeladen..." : "Hochladen"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
