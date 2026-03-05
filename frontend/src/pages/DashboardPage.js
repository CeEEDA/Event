import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { Sidebar } from "../components/Sidebar";
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
  Menu,
  X
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [currentPath, setCurrentPath] = useState("/");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("list");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [activeView, setActiveView] = useState("files");
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
    if (activeView === "files") {
      loadFiles();
    }
  }, [loadFiles, activeView]);

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
    <div className="flex h-screen overflow-hidden bg-background" data-testid="dashboard-page">
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed md:relative inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
      `}>
        <Sidebar 
          activeView={activeView} 
          onViewChange={(view) => {
            setActiveView(view);
            setSidebarOpen(false);
          }}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setSidebarOpen(true)}
              data-testid="mobile-menu-btn"
            >
              <Menu className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-lg font-semibold">
                {activeView === "files" ? "Meine Dateien" : "Geteilte Links"}
              </h1>
              {activeView === "files" && (
                <p className="text-xs text-muted-foreground font-mono">
                  {currentPath}
                </p>
              )}
            </div>
          </div>

          {activeView === "files" && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={loadFiles}
                className="hidden sm:flex"
                data-testid="refresh-btn"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
              <div className="hidden sm:flex border border-border rounded-sm overflow-hidden">
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
                className="hidden sm:flex"
                data-testid="create-folder-btn"
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                Ordner
              </Button>
              <Button
                onClick={() => setUploadModalOpen(true)}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                data-testid="upload-btn"
              >
                <Upload className="w-4 h-4 mr-2" />
                <span className="hidden sm:inline">Hochladen</span>
              </Button>
            </div>
          )}
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 grid-lines">
          {activeView === "files" ? (
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
        </main>
      </div>

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
