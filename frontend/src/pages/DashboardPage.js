import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FileList } from "../components/FileList";
import { UploadModal } from "../components/UploadModal";
import { ShareModal } from "../components/ShareModal";
import { SharesPanel } from "../components/SharesPanel";
import { CreateFolderModal } from "../components/CreateFolderModal";
import { MoveFileModal } from "../components/MoveFileModal";
import { FilePreview } from "../components/FilePreview";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DownloadLinkDialog } from "../components/DownloadLinkDialog";
import { Button } from "../components/ui/button";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import api, { downloadFile, downloadFolderZip, setDownloadLinkCallback } from "../lib/api";
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
  const [allFolders, setAllFolders] = useState([]);
  const [currentPath, setCurrentPath] = useState("/");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("list");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [moveModalOpen, setMoveModalOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [shareType, setShareType] = useState("file");
  const [moveTarget, setMoveTarget] = useState(null);
  const [previewFile, setPreviewFile] = useState(null);
  const [activeTab, setActiveTab] = useState("files");
  const [storageArea, setStorageArea] = useState("personal");
  const [isDragging, setIsDragging] = useState(false);

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmData, setConfirmData] = useState({ title: "", description: "", onConfirm: null });

  // Download link dialog state (for sandboxed iframe fallback)
  const [dlDialogOpen, setDlDialogOpen] = useState(false);
  const [dlDialogUrl, setDlDialogUrl] = useState("");
  const [dlDialogFilename, setDlDialogFilename] = useState("");

  // Register download link callback for iframe fallback
  useEffect(() => {
    setDownloadLinkCallback((url, filename) => {
      setDlDialogUrl(url);
      setDlDialogFilename(filename);
      setDlDialogOpen(true);
    });
    return () => setDownloadLinkCallback(null);
  }, []);

  const canWrite = isAdmin || user?.apps?.filesharing?.can_write;
  const canDelete = isAdmin || user?.apps?.filesharing?.can_delete;
  const maxUploadSize = isAdmin ? 10000 : (user?.apps?.filesharing?.max_upload_size_mb || 100);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = { folder_path: currentPath, storage_area: storageArea };
      if (viewUserId && isAdmin) params.view_user_id = viewUserId;
      
      const [filesRes, foldersRes] = await Promise.all([
        api.get("/files", { params }),
        api.get("/folders", { params: { path: currentPath, storage_area: storageArea, view_user_id: viewUserId } })
      ]);
      setFiles(filesRes.data);
      setFolders(foldersRes.data.filter(f => {
        const parentPath = f.path.substring(0, f.path.lastIndexOf("/")) || "/";
        return parentPath === currentPath;
      }));
    } catch {
      toast.error("Fehler beim Laden der Dateien");
    } finally {
      setLoading(false);
    }
  }, [currentPath, storageArea, viewUserId, isAdmin]);

  const loadAllFolders = useCallback(async () => {
    try {
      const res = await api.get("/folders/all", { params: { storage_area: storageArea } });
      setAllFolders(res.data);
    } catch { /* ignore */ }
  }, [storageArea]);

  useEffect(() => {
    if (activeTab === "files") {
      loadFiles();
      loadAllFolders();
    }
  }, [loadFiles, loadAllFolders, activeTab]);

  // Drag & Drop handlers
  const handlePageDragOver = useCallback((e) => {
    e.preventDefault();
    if (activeTab === "files" && (storageArea === "personal" || canWrite)) {
      setIsDragging(true);
    }
  }, [activeTab, storageArea, canWrite]);

  const handlePageDragLeave = useCallback((e) => {
    e.preventDefault();
    if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false);
    }
  }, []);

  const handlePageDrop = useCallback(async (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (storageArea === "shared" && !canWrite) return;

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length === 0) return;

    let successCount = 0;
    for (const file of droppedFiles) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("folder_path", currentPath);
        formData.append("storage_area", storageArea);
        await api.post("/files/upload", formData, { headers: { "Content-Type": "multipart/form-data" } });
        successCount++;
      } catch (error) {
        toast.error(error.response?.data?.detail || `Fehler bei ${file.name}`);
      }
    }
    if (successCount > 0) {
      toast.success(`${successCount} Datei(en) hochgeladen`);
      loadFiles();
    }
  }, [currentPath, storageArea, canWrite, loadFiles]);

  const handleUpload = async (uploadFiles) => {
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
        await api.post("/files/upload", formData, { headers: { "Content-Type": "multipart/form-data" } });
        successCount++;
      } catch (error) {
        toast.error(error.response?.data?.detail || `Fehler bei ${file.name}`);
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
    } catch {
      toast.error("Fehler beim Herunterladen");
    }
  };

  const handleDownloadFolder = async (folder) => {
    try {
      await downloadFolderZip(folder.id, folder.name);
    } catch (error) {
      const msg = error.response?.status === 404 ? "Ordner ist leer" : "Fehler beim Herunterladen";
      toast.error(msg);
    }
  };

  const handleDelete = (file) => {
    const isOwner = file.owner_id === user?.id;
    if (!isOwner && !isAdmin && !(storageArea === "shared" && canDelete)) {
      toast.error("Keine Berechtigung zum Löschen");
      return;
    }
    setConfirmData({
      title: "Datei löschen",
      description: `Möchten Sie "${file.original_filename}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`,
      onConfirm: async () => {
        try {
          await api.delete(`/files/${file.id}`);
          toast.success("Datei gelöscht");
          loadFiles();
        } catch {
          toast.error("Fehler beim Löschen");
        }
        setConfirmOpen(false);
      }
    });
    setConfirmOpen(true);
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
    if (storageArea === "shared" && !canWrite) {
      toast.error("Keine Schreibberechtigung für gemeinsamen Bereich");
      throw new Error("No permission");
    }
    await api.post("/folders", { name, parent_path: currentPath, storage_area: storageArea });
    toast.success("Ordner erstellt");
    loadFiles();
    loadAllFolders();
  };

  const handleDeleteFolder = (folder) => {
    const isOwner = folder.owner_id === user?.id;
    if (!isOwner && !isAdmin && !(storageArea === "shared" && canDelete)) {
      toast.error("Keine Berechtigung zum Löschen");
      return;
    }
    setConfirmData({
      title: "Ordner löschen",
      description: `Möchten Sie den Ordner "${folder.name}" und alle Inhalte wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`,
      onConfirm: async () => {
        try {
          await api.delete(`/folders/${folder.id}`);
          toast.success("Ordner gelöscht");
          loadFiles();
          loadAllFolders();
        } catch {
          toast.error("Fehler beim Löschen");
        }
        setConfirmOpen(false);
      }
    });
    setConfirmOpen(true);
  };

  const handleMoveFile = (file) => {
    setMoveTarget(file);
    setMoveModalOpen(true);
  };

  const handleMoveConfirm = async (fileId, targetPath, targetArea) => {
    try {
      await api.put(`/files/${fileId}/move`, { target_folder_path: targetPath, target_storage_area: targetArea });
      toast.success("Datei verschoben");
      loadFiles();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Fehler beim Verschieben");
      throw error;
    }
  };

  const handlePreview = (file) => {
    setPreviewFile(file);
    setPreviewOpen(true);
  };

  const navigateToFolder = (path) => setCurrentPath(path);
  const navigateUp = () => {
    if (currentPath === "/") return;
    setCurrentPath(currentPath.substring(0, currentPath.lastIndexOf("/")) || "/");
  };
  const switchStorageArea = (area) => { setStorageArea(area); setCurrentPath("/"); };

  const showUploadUI = storageArea === "personal" || canWrite;

  return (
    <div 
      className="min-h-screen bg-gray-50 flex flex-col relative" 
      data-testid="dashboard-page"
      onDragOver={handlePageDragOver}
      onDragLeave={handlePageDragLeave}
      onDrop={handlePageDrop}
    >
      {/* Drag overlay */}
      {isDragging && showUploadUI && (
        <div className="fixed inset-0 z-50 bg-fuchsia-600/10 backdrop-blur-sm flex items-center justify-center pointer-events-none" data-testid="drag-overlay">
          <div className="bg-white border-2 border-dashed border-fuchsia-500 rounded-2xl p-12 text-center shadow-2xl">
            <Upload className="w-16 h-16 text-fuchsia-600 mx-auto mb-4" />
            <p className="text-xl font-semibold text-gray-900">Dateien hier ablegen</p>
            <p className="text-sm text-gray-500 mt-1">zum Hochladen in {currentPath === "/" ? "Stammverzeichnis" : currentPath}</p>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-hub-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">
              FileShare
              {viewUserId && isAdmin && <span className="ml-2 text-sm font-normal text-fuchsia-600">(Admin-Ansicht)</span>}
            </h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      {/* Storage Area Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto flex">
          <button onClick={() => switchStorageArea("personal")} className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${storageArea === "personal" ? "border-fuchsia-600 text-fuchsia-700" : "border-transparent text-gray-500 hover:text-gray-700"}`} data-testid="storage-personal">
            <Users className="w-4 h-4" /> Mein Bereich
          </button>
          <button onClick={() => switchStorageArea("shared")} className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${storageArea === "shared" ? "border-fuchsia-600 text-fuchsia-700" : "border-transparent text-gray-500 hover:text-gray-700"}`} data-testid="storage-shared">
            <Globe className="w-4 h-4" /> Gemeinsamer Bereich
          </button>
        </div>
      </div>

      {/* Sub Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto flex">
          <button onClick={() => setActiveTab("files")} className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === "files" ? "border-fuchsia-600 text-fuchsia-700" : "border-transparent text-gray-500 hover:text-gray-700"}`} data-testid="tab-files">
            <FolderOpen className="w-4 h-4" /> Dateien
          </button>
          <button onClick={() => setActiveTab("shares")} className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === "shares" ? "border-fuchsia-600 text-fuchsia-700" : "border-transparent text-gray-500 hover:text-gray-700"}`} data-testid="tab-shares">
            <Link2 className="w-4 h-4" /> Geteilte Links
          </button>
        </div>
      </div>

      {/* Toolbar */}
      {activeTab === "files" && (
        <div className="bg-white border-b border-gray-200 py-3 px-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="font-mono">{currentPath}</span>
              {storageArea === "shared" && !canWrite && <span className="ml-2 text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">Nur Lesen</span>}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={loadFiles} className="text-gray-500" data-testid="refresh-btn">
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
              <div className="hidden sm:flex border border-gray-200 rounded overflow-hidden">
                <Button variant={viewMode === "list" ? "secondary" : "ghost"} size="icon" onClick={() => setViewMode("list")} className="rounded-none h-8 w-8" data-testid="list-view-btn">
                  <List className="w-4 h-4" />
                </Button>
                <Button variant={viewMode === "grid" ? "secondary" : "ghost"} size="icon" onClick={() => setViewMode("grid")} className="rounded-none h-8 w-8" data-testid="grid-view-btn">
                  <LayoutGrid className="w-4 h-4" />
                </Button>
              </div>
              {showUploadUI && (
                <>
                  <Button variant="outline" size="sm" onClick={() => setFolderModalOpen(true)} className="hidden sm:flex text-gray-600" data-testid="create-folder-btn">
                    <FolderPlus className="w-4 h-4 mr-2" /> Ordner
                  </Button>
                  <Button onClick={() => setUploadModalOpen(true)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="upload-btn">
                    <Upload className="w-4 h-4 mr-2" /> <span className="hidden sm:inline">Hochladen</span>
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
              files={files} folders={folders} currentPath={currentPath} viewMode={viewMode} loading={loading}
              onNavigate={navigateToFolder} onNavigateUp={navigateUp}
              onDownload={handleDownload} onDelete={handleDelete}
              onShare={handleShareFile} onShareFolder={handleShareFolder} onDeleteFolder={handleDeleteFolder}
              onPreview={handlePreview} onMoveFile={handleMoveFile} onDownloadFolder={handleDownloadFolder}
              canWrite={storageArea === "personal" || canWrite}
              canDelete={storageArea === "personal" || canDelete || isAdmin}
            />
          ) : (
            <SharesPanel />
          )}
        </div>
      </main>

      {/* Modals */}
      <UploadModal open={uploadModalOpen} onClose={() => setUploadModalOpen(false)} onUpload={handleUpload} maxSizeMB={maxUploadSize} />
      <ShareModal open={shareModalOpen} onClose={() => { setShareModalOpen(false); setSelectedItem(null); }} item={selectedItem} shareType={shareType} onShareCreated={loadFiles} />
      <CreateFolderModal open={folderModalOpen} onClose={() => setFolderModalOpen(false)} onCreateFolder={handleCreateFolder} />
      <MoveFileModal open={moveModalOpen} onClose={() => { setMoveModalOpen(false); setMoveTarget(null); }} file={moveTarget} folders={allFolders} currentStorageArea={storageArea} onMove={handleMoveConfirm} />
      <FilePreview open={previewOpen} onClose={() => { setPreviewOpen(false); setPreviewFile(null); }} file={previewFile} files={files} />
      
      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title={confirmData.title}
        description={confirmData.description}
        onConfirm={confirmData.onConfirm}
        onCancel={() => setConfirmOpen(false)}
      />

      {/* Download Link Dialog (iframe fallback) */}
      <DownloadLinkDialog
        open={dlDialogOpen}
        onClose={() => setDlDialogOpen(false)}
        url={dlDialogUrl}
        filename={dlDialogFilename}
      />
    </div>
  );
}
