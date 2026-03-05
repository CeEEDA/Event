import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FileList } from "../components/FileList";
import { UploadModal } from "../components/UploadModal";
import { ShareModal } from "../components/ShareModal";
import { SharesPanel } from "../components/SharesPanel";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import api, { uploadFile, downloadFile } from "../lib/api";
import { 
  Upload, 
  FolderPlus, 
  RefreshCw, 
  LayoutGrid, 
  List,
  ArrowLeft,
  FolderOpen,
  Link2
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [currentPath, setCurrentPath] = useState("/");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("list");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [activeTab, setActiveTab] = useState("files");

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const [filesRes, foldersRes] = await Promise.all([
        api.get("/files", { params: { folder_path: currentPath } }),
        api.get("/folders", { params: { path: currentPath } })
      ]);
      setFiles(filesRes.data);
      setFolders(foldersRes.data.filter(f => {
        const parentPath = f.path.substring(0, f.path.lastIndexOf("/")) || "/";
        return parentPath === currentPath;
      }));
    } catch (error) {
      toast.error("Fehler beim Laden der Dateien");
    } finally {
      setLoading(false);
    }
  }, [currentPath]);

  useEffect(() => {
    if (activeTab === "files") {
      loadFiles();
    }
  }, [loadFiles, activeTab]);

  const handleUpload = async (files) => {
    let successCount = 0;
    for (const file of files) {
      try {
        await uploadFile(file, currentPath);
        successCount++;
      } catch (error) {
        const message = error.response?.data?.detail || `Fehler bei ${file.name}`;
        toast.error(message);
      }
    }
    if (successCount > 0) {
      toast.success(`${successCount} Datei(en) hochgeladen`);
      loadFiles();
    }
    setUploadModalOpen(false);
  };

  const handleDownload = async (file) => {
    try {
      await downloadFile(file.id, file.original_filename);
      toast.success("Download gestartet");
    } catch (error) {
      toast.error("Fehler beim Herunterladen");
    }
  };

  const handleDelete = async (file) => {
    if (!window.confirm(`"${file.original_filename}" wirklich löschen?`)) return;
    
    try {
      await api.delete(`/files/${file.id}`);
      toast.success("Datei gelöscht");
      loadFiles();
    } catch (error) {
      toast.error("Fehler beim Löschen");
    }
  };

  const handleShare = (file) => {
    setSelectedFile(file);
    setShareModalOpen(true);
  };

  const handleCreateFolder = async () => {
    const name = window.prompt("Ordnername eingeben:");
    if (!name) return;
    
    try {
      await api.post("/folders", { name, parent_path: currentPath });
      toast.success("Ordner erstellt");
      loadFiles();
    } catch (error) {
      const message = error.response?.data?.detail || "Fehler beim Erstellen";
      toast.error(message);
    }
  };

  const handleDeleteFolder = async (folder) => {
    if (!window.confirm(`Ordner "${folder.name}" und alle Inhalte löschen?`)) return;
    
    try {
      await api.delete(`/folders/${folder.id}`);
      toast.success("Ordner gelöscht");
      loadFiles();
    } catch (error) {
      toast.error("Fehler beim Löschen");
    }
  };

  const navigateToFolder = (path) => {
    setCurrentPath(path);
  };

  const navigateUp = () => {
    if (currentPath === "/") return;
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf("/")) || "/";
    setCurrentPath(parentPath);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="dashboard-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/hub")}
              className="text-gray-600 hover:text-orange-500"
              data-testid="back-to-hub-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">FileShare</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-purple-600 to-green-500 flex items-center justify-center">
              <span className="text-white font-bold text-xs">EE</span>
            </div>
            <span className="text-sm font-bold text-gray-900 hidden sm:inline">Eventenergie</span>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto flex">
          <button
            onClick={() => setActiveTab("files")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "files" 
                ? "border-orange-500 text-orange-600" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            data-testid="tab-files"
          >
            <FolderOpen className="w-4 h-4" />
            Meine Dateien
          </button>
          <button
            onClick={() => setActiveTab("shares")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "shares" 
                ? "border-orange-500 text-orange-600" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            data-testid="tab-shares"
          >
            <Link2 className="w-4 h-4" />
            Geteilte Links
          </button>
        </div>
      </div>

      {/* Toolbar */}
      {activeTab === "files" && (
        <div className="bg-white border-b border-gray-200 py-3 px-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="font-mono">{currentPath}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={loadFiles}
                className="text-gray-500"
                data-testid="refresh-btn"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
              <div className="hidden sm:flex border border-gray-200 rounded overflow-hidden">
                <Button
                  variant={viewMode === "list" ? "secondary" : "ghost"}
                  size="icon"
                  onClick={() => setViewMode("list")}
                  className="rounded-none h-8 w-8"
                  data-testid="list-view-btn"
                >
                  <List className="w-4 h-4" />
                </Button>
                <Button
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  size="icon"
                  onClick={() => setViewMode("grid")}
                  className="rounded-none h-8 w-8"
                  data-testid="grid-view-btn"
                >
                  <LayoutGrid className="w-4 h-4" />
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCreateFolder}
                className="hidden sm:flex text-gray-600"
                data-testid="create-folder-btn"
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                Ordner
              </Button>
              <Button
                onClick={() => setUploadModalOpen(true)}
                className="bg-orange-500 hover:bg-orange-600 text-white"
                data-testid="upload-btn"
              >
                <Upload className="w-4 h-4 mr-2" />
                <span className="hidden sm:inline">Hochladen</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Content Area */}
      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          {activeTab === "files" ? (
            <FileList
              files={files}
              folders={folders}
              currentPath={currentPath}
              viewMode={viewMode}
              loading={loading}
              onNavigate={navigateToFolder}
              onNavigateUp={navigateUp}
              onDownload={handleDownload}
              onDelete={handleDelete}
              onShare={handleShare}
              onDeleteFolder={handleDeleteFolder}
            />
          ) : (
            <SharesPanel />
          )}
        </div>
      </main>

      {/* Modals */}
      <UploadModal
        open={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUpload={handleUpload}
        maxSizeMB={user?.max_upload_size_mb || 100}
      />

      <ShareModal
        open={shareModalOpen}
        onClose={() => {
          setShareModalOpen(false);
          setSelectedFile(null);
        }}
        file={selectedFile}
        onShareCreated={loadFiles}
      />
    </div>
  );
}
