import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import { downloadSharedFile, uploadToShare } from "../lib/api";
import axios from "axios";
import { 
  Download, 
  Upload, 
  Lock, 
  FileText, 
  Folder,
  AlertCircle,
  CheckCircle,
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
      } else if (err.response?.status === 403) {
        toast.error("Upload nicht erlaubt");
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
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-pulse text-orange-500">Laden...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <header className="p-6 flex justify-center border-b border-gray-100">
          <Logo size="normal" />
        </header>
        <main className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-8 max-w-md w-full text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto">
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{error}</h1>
            <p className="text-gray-500">
              Der angeforderte Share-Link ist nicht verfügbar.
            </p>
          </div>
        </main>
      </div>
    );
  }

  const isFolder = shareInfo.share_type === "folder";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="shared-file-page">
      {/* Header */}
      <header className="bg-white p-6 flex justify-center border-b border-gray-200">
        <Logo size="normal" />
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-4">
        <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-8 max-w-lg w-full space-y-6">
          <div className="text-center">
            <h1 className="text-xl font-bold text-gray-900">Dateifreigabe</h1>
            <p className="text-sm text-gray-500 mt-1">Eventenergie Deutschland</p>
          </div>

          {/* File/Folder Info */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center flex-shrink-0">
                {isFolder ? (
                  <Folder className="w-6 h-6 text-orange-500" />
                ) : (
                  <FileText className="w-6 h-6 text-orange-500" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-gray-900 truncate" data-testid="shared-filename">
                  {isFolder ? shareInfo.folder_name : shareInfo.filename}
                </h2>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-500 mt-1">
                  {!isFolder && shareInfo.size && (
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3 h-3" />
                      {formatSize(shareInfo.size)}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    Gültig bis {formatDate(shareInfo.expires_at)}
                  </span>
                </div>
              </div>
            </div>

            {shareInfo.password_protected && (
              <div className="flex items-center gap-2 text-sm text-orange-600">
                <Lock className="w-4 h-4" />
                Passwortgeschützt
              </div>
            )}

            {/* Permissions info */}
            <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
              {shareInfo.allow_download && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Download</span>
              )}
              {shareInfo.allow_upload && (
                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">Upload</span>
              )}
              {shareInfo.allow_edit && (
                <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded">Bearbeiten</span>
              )}
            </div>
          </div>

          {/* Password Input */}
          {shareInfo.password_protected && (
            <div className="space-y-2">
              <Label className="text-gray-700">Passwort</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <Input
                  type="password"
                  placeholder="Passwort eingeben"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 border-gray-300"
                  data-testid="share-password-input"
                />
              </div>
            </div>
          )}

          {/* Download Button - only for files */}
          {!isFolder && shareInfo.allow_download && (
            <Button
              onClick={handleDownload}
              disabled={downloading}
              className="w-full h-12 bg-orange-500 hover:bg-orange-600 text-white font-semibold"
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

          {/* Folder info */}
          {isFolder && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-700">
              <p>Dies ist ein freigegebener Ordner. Sie können Dateien hochladen.</p>
            </div>
          )}

          {/* Upload Section - if allowed */}
          {shareInfo.allow_upload && (
            <div className="border-t border-gray-200 pt-6 space-y-4">
              <h3 className="text-sm font-medium text-gray-500">
                Datei hochladen
              </h3>

              {uploadSuccess ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="text-green-700">Datei erfolgreich hochgeladen!</span>
                </div>
              ) : (
                <>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-orange-300 transition-colors">
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
                      <Upload className="w-8 h-8 mx-auto text-gray-400" />
                      <p className="text-sm text-gray-500">
                        {uploadFile ? uploadFile.name : "Klicken zum Auswählen"}
                      </p>
                    </label>
                  </div>

                  <Button
                    onClick={handleUpload}
                    disabled={uploading || !uploadFile}
                    variant="outline"
                    className="w-full border-gray-300"
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
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
