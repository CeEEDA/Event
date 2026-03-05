import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { downloadSharedFile, uploadToShare } from "../lib/api";
import axios from "axios";
import { 
  Download, 
  Upload, 
  Lock, 
  FileText, 
  AlertCircle,
  CheckCircle,
  Zap,
  Calendar,
  HardDrive
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function SharedFilePage() {
  const { token } = useParams();
  const [shareInfo, setShareInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [password, setPassword] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  useEffect(() => {
    const loadShareInfo = async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/public/share/${token}`);
        setShareInfo(response.data);
      } catch (err) {
        if (err.response?.status === 404) {
          setError("Link nicht gefunden");
        } else if (err.response?.status === 410) {
          setError("Link abgelaufen");
        } else {
          setError("Fehler beim Laden");
        }
      } finally {
        setLoading(false);
      }
    };

    loadShareInfo();
  }, [token]);

  const handleDownload = async () => {
    if (shareInfo.password_protected && !password) {
      toast.error("Bitte Passwort eingeben");
      return;
    }

    setDownloading(true);
    try {
      const response = await downloadSharedFile(
        token, 
        shareInfo.password_protected ? password : null
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", shareInfo.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success("Download gestartet");
    } catch (err) {
      if (err.response?.status === 401) {
        toast.error("Falsches Passwort");
      } else {
        toast.error("Download fehlgeschlagen");
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) {
      toast.error("Bitte Datei auswählen");
      return;
    }

    if (shareInfo.password_protected && !password) {
      toast.error("Bitte Passwort eingeben");
      return;
    }

    setUploading(true);
    try {
      await uploadToShare(
        token, 
        uploadFile, 
        shareInfo.password_protected ? password : null
      );
      toast.success("Datei hochgeladen");
      setUploadSuccess(true);
      setUploadFile(null);
    } catch (err) {
      if (err.response?.status === 401) {
        toast.error("Falsches Passwort");
      } else if (err.response?.status === 413) {
        toast.error("Datei zu groß");
      } else {
        toast.error("Upload fehlgeschlagen");
      }
    } finally {
      setUploading(false);
    }
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (isoString) => {
    return new Date(isoString).toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-pulse text-primary">Laden...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="bg-card border border-border rounded-sm p-8 max-w-md w-full text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-destructive" />
          </div>
          <h1 className="text-2xl font-bold">{error}</h1>
          <p className="text-muted-foreground">
            Der angeforderte Share-Link ist nicht verfügbar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background grid-lines flex items-center justify-center p-4" data-testid="shared-file-page">
      <div className="bg-card border border-border rounded-sm p-8 max-w-lg w-full space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-sm bg-primary flex items-center justify-center">
            <Zap className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-xl font-bold">FileShare</h1>
            <p className="text-xs text-muted-foreground">Eventenergie Deutschland</p>
          </div>
        </div>

        {/* File Info */}
        <div className="bg-muted/30 rounded-sm p-4 space-y-3">
          <div className="flex items-start gap-3">
            <div className="w-12 h-12 rounded-sm bg-primary/10 flex items-center justify-center flex-shrink-0">
              <FileText className="w-6 h-6 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold truncate" data-testid="shared-filename">
                {shareInfo.filename}
              </h2>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground mt-1">
                <span className="flex items-center gap-1">
                  <HardDrive className="w-3 h-3" />
                  {formatSize(shareInfo.size)}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Gültig bis {formatDate(shareInfo.expires_at)}
                </span>
              </div>
            </div>
          </div>

          {shareInfo.password_protected && (
            <div className="flex items-center gap-2 text-sm text-secondary">
              <Lock className="w-4 h-4" />
              Passwortgeschützt
            </div>
          )}
        </div>

        {/* Password Input */}
        {shareInfo.password_protected && (
          <div className="space-y-2">
            <Label className="text-sm font-medium uppercase tracking-wide">
              Passwort
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="password"
                placeholder="Passwort eingeben"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pl-10 bg-background"
                data-testid="share-password-input"
              />
            </div>
          </div>
        )}

        {/* Download Button */}
        {shareInfo.allow_download && (
          <Button
            onClick={handleDownload}
            disabled={downloading}
            className="w-full h-12 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold uppercase tracking-wide"
            data-testid="download-shared-btn"
          >
            {downloading ? (
              "Wird heruntergeladen..."
            ) : (
              <>
                <Download className="w-5 h-5 mr-2" />
                Herunterladen
              </>
            )}
          </Button>
        )}

        {/* Upload Section */}
        <div className="border-t border-border pt-6 space-y-4">
          <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Datei hochladen
          </h3>

          {uploadSuccess ? (
            <div className="bg-green-500/10 border border-green-500/30 rounded-sm p-4 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-green-500">Datei erfolgreich hochgeladen!</span>
            </div>
          ) : (
            <>
              <div className="border-2 border-dashed border-muted rounded-sm p-6 text-center">
                <input
                  type="file"
                  id="upload-input"
                  className="hidden"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  data-testid="share-upload-input"
                />
                <label 
                  htmlFor="upload-input" 
                  className="cursor-pointer block space-y-2"
                >
                  <Upload className="w-8 h-8 mx-auto text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    {uploadFile ? uploadFile.name : "Klicken zum Auswählen"}
                  </p>
                </label>
              </div>

              <Button
                onClick={handleUpload}
                disabled={uploading || !uploadFile}
                variant="outline"
                className="w-full"
                data-testid="upload-to-share-btn"
              >
                {uploading ? (
                  "Wird hochgeladen..."
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Hochladen
                  </>
                )}
              </Button>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-muted-foreground pt-4 border-t border-border">
          &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
        </div>
      </div>
    </div>
  );
}
