import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FileList } from "../components/FileList";
import { UploadModal } from "../components/UploadModal";
import { ShareModal } from "../components/ShareModal";
import { SharesPanel } from "../components/SharesPanel";
import { CreateFolderModal } from "../components/CreateFolderModal";
import { Button } from "../components/ui/button";
import { Logo } from "../components/Logo";
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
  Link2,
  Users,
  Globe
} from "lucide-react";

export default function DashboardPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const viewUserId = searchParams.get("view_user");
  
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [currentPath, setCurrentPath] = useState("/");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("list");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [shareType, setShareType] = useState("file");
  const [activeTab, setActiveTab] = useState("files");
  const [storageArea, setStorageArea] = useState("personal"); // personal or shared

  // Check permissions
  const canWrite = isAdmin || user?.apps?.filesharing?.can_write;
  const canDelete = isAdmin || user?.apps?.filesharing?.can_delete;
  const maxUploadSize = isAdmin ? 10000 : (user?.apps?.filesharing?.max_upload_size_mb || 100);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = { folder_path: currentPath, storage_area: storageArea };
      if (viewUserId && isAdmin) {
        params.view_user_id = viewUserId;
      }
      
      const [filesRes, foldersRes] = await Promise.all([
        api.get("/files", { params }),
        api.get("/folders", { params: { path: currentPath, storage_area: storageArea, view_user_id: viewUserId } })
      ]);
      setFiles(filesRes.data);
      // Filter folders to only show direct children
      setFolders(foldersRes.data.filter(f => {
        const parentPath = f.path.substring(0, f.path.lastIndexOf("/")) || "/";
        return parentPath === currentPath;
      }));
    } catch (error) {
      toast.error("Fehler beim Laden der Dateien");
    } finally {
      setLoading(false);
    }
  }, [currentPath, storageArea, viewUserId, isAdmin]);

  useEffect(() => {
    if (activeTab === "files") {
      loadFiles();
    }
  }, [loadFiles, activeTab]);

  const handleUpload = async (uploadFiles) => {
    // Check permission for shared area
    if (storageArea === "shared" && !canWrite) {
      toast.error("Keine Schreibberechtigung für gemeinsamen Bereich");
      return;
    }
    
    let successCount = 0;
    for (const file of uploadFiles) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("folder_path", currentPath);
        formData.append("storage_area", storageArea);
        
        await api.post("/files/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
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
    // Check permission
    const isOwner = file.owner_id === user?.id;
    if (!isOwner && !isAdmin && !(storageArea === "shared" && canDelete)) {
      toast.error("Keine Berechtigung zum Löschen");
      return;
    }
    
    if (!window.confirm(`"${file.original_filename}" wirklich löschen?`)) return;
    
    try {
      await api.delete(`/files/${file.id}`);
      toast.success("Datei gelöscht");
      loadFiles();
    } catch (error) {
      toast.error("Fehler beim Löschen");
    }
  };

  const handleShareFile = (file) => {
    setSelectedItem(file);
    setShareType("file");
    setShareModalOpen(true);
  };

  const handleShareFolder = (folder) => {
    setSelectedItem(folder);
    setShareType("folder");
    setShareModalOpen(true);
  };

  const handleCreateFolder = async (name) => {
    // Check permission for shared area
    if (storageArea === "shared" && !canWrite) {
      toast.error("Keine Schreibberechtigung für gemeinsamen Bereich");
      throw new Error("No permission");
    }
    
    await api.post("/folders", { 
      name: name, 
      parent_path: currentPath,
      storage_area: storageArea
    });
    toast.success("Ordner erstellt");
    loadFiles();
  };

  const handleDeleteFolder = async (folder) => {
    // Check permission
    const isOwner = folder.owner_id === user?.id;
    if (!isOwner && !isAdmin && !(storageArea === "shared" && canDelete)) {
      toast.error("Keine Berechtigung zum Löschen");
      return;
    }
    
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

  const switchStorageArea = (area) => {
    setStorageArea(area);
    setCurrentPath("/");
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
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-hub-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">
              FileShare
              {viewUserId && isAdmin && (
                <span className="ml-2 text-sm font-normal text-fuchsia-600">(Admin-Ansicht)</span>
              )}
            </h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      {/* Storage Area Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto flex">
          <button
            onClick={() => switchStorageArea("personal")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              storageArea === "personal" 
                ? "border-fuchsia-600 text-fuchsia-700" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            data-testid="storage-personal"
          >
            <Users className="w-4 h-4" />
            Mein Bereich
          </button>
          <button
            onClick={() => switchStorageArea("shared")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              storageArea === "shared" 
                ? "border-fuchsia-600 text-fuchsia-700" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            data-testid="storage-shared"
          >
            <Globe className="w-4 h-4" />
            Gemeinsamer Bereich
          </button>
        </div>
      </div>

      {/* Sub Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto flex">
          <button
            onClick={() => setActiveTab("files")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "files" 
                ? "border-fuchsia-600 text-fuchsia-700" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            data-testid="tab-files"
          >
            <FolderOpen className="w-4 h-4" />
            Dateien
          </button>
          <button
            onClick={() => setActiveTab("shares")}
            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "shares" 
                ? "border-fuchsia-600 text-fuchsia-700" 
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
              {storageArea === "shared" && !canWrite && (
                <span className="ml-2 text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                  Nur Lesen
                </span>
              )}
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
              {(storageArea === "personal" || canWrite) && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFolderModalOpen(true)}
                    className="hidden sm:flex text-gray-600"
                    data-testid="create-folder-btn"
                  >
                    <FolderPlus className="w-4 h-4 mr-2" />
                    Ordner
                  </Button>
                  <Button
                    onClick={() => setUploadModalOpen(true)}
                    className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                    data-testid="upload-btn"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    <span className="hidden sm:inline">Hochladen</span>
                  </Button>
                </>
              )}
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
              onShare={handleShareFile}
              onShareFolder={handleShareFolder}
              onDeleteFolder={handleDeleteFolder}
              canWrite={storageArea === "personal" || canWrite}
              canDelete={storageArea === "personal" || canDelete || isAdmin}
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
        maxSizeMB={maxUploadSize}
      />

      <ShareModal
        open={shareModalOpen}
        onClose={() => {
          setShareModalOpen(false);
          setSelectedItem(null);
        }}
        item={selectedItem}
        shareType={shareType}
        onShareCreated={loadFiles}
      />

      <CreateFolderModal
        open={folderModalOpen}
        onClose={() => setFolderModalOpen(false)}
        onCreateFolder={handleCreateFolder}
      />
    </div>
  );
}
