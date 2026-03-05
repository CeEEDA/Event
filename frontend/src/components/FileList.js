import { 
  FileText, 
  FileImage, 
  FileVideo, 
  FileAudio, 
  FileArchive,
  File,
  Folder,
  Download,
  Trash2,
  Share2,
  MoreVertical,
  ChevronUp,
  Eye,
  FolderInput,
  FolderDown
} from "lucide-react";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { getDownloadUrl, getFolderDownloadUrl, downloadFile, downloadFolderZip } from "../lib/api";

const getFileIcon = (contentType) => {
  if (contentType?.startsWith("image/")) return FileImage;
  if (contentType?.startsWith("video/")) return FileVideo;
  if (contentType?.startsWith("audio/")) return FileAudio;
  if (contentType?.includes("zip") || contentType?.includes("archive") || contentType?.includes("rar")) 
    return FileArchive;
  if (contentType?.includes("pdf") || contentType?.includes("document") || contentType?.includes("text"))
    return FileText;
  return File;
};

const isPreviewable = (contentType) => {
  return contentType?.startsWith("image/") || contentType === "application/pdf";
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

export const FileList = ({
  files,
  folders,
  currentPath,
  viewMode,
  loading,
  onNavigate,
  onNavigateUp,
  onDownload,
  onDelete,
  onShare,
  onShareFolder,
  onDeleteFolder,
  onPreview,
  onMoveFile,
  onDownloadFolder,
  canWrite = true,
  canDelete = true
}) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-gray-500">Laden...</div>
      </div>
    );
  }

  const isEmpty = files.length === 0 && folders.length === 0 && currentPath === "/";

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center" data-testid="empty-state">
        <Folder className="w-16 h-16 text-gray-300 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-1">Keine Dateien</h3>
        <p className="text-sm text-gray-500">
          Laden Sie Ihre erste Datei hoch oder ziehen Sie Dateien hierher
        </p>
      </div>
    );
  }

  if (viewMode === "grid") {
    return (
      <div className="space-y-4">
        {currentPath !== "/" && (
          <button
            onClick={onNavigateUp}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-fuchsia-600 transition-colors"
            data-testid="navigate-up-btn"
          >
            <ChevronUp className="w-4 h-4" />
            Zurück
          </button>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {folders.map((folder) => (
            <div
              key={folder.id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-fuchsia-400 hover:shadow-md transition-all cursor-pointer group relative"
              onClick={() => onNavigate(folder.path)}
              data-testid={`folder-${folder.id}`}
            >
              <div className="flex flex-col items-center text-center">
                <Folder className="w-12 h-12 text-fuchsia-500 mb-2" />
                <span className="text-sm font-medium text-gray-900 truncate w-full">{folder.name}</span>
                {folder.is_shared && (
                  <span className="text-xs text-fuchsia-600 flex items-center gap-1 mt-1">
                    <Share2 className="w-3 h-3" />
                    Geteilt
                  </span>
                )}
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" size="icon" className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); downloadFolderZip(folder.id, folder.name).catch(() => {}); }}>
                    <FolderDown className="w-4 h-4 mr-2" />
                    Als ZIP herunterladen
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onShareFolder?.(folder); }}>
                    <Share2 className="w-4 h-4 mr-2" />
                    Ordner teilen
                  </DropdownMenuItem>
                  {canDelete && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDeleteFolder(folder); }} className="text-red-600">
                        <Trash2 className="w-4 h-4 mr-2" />
                        Löschen
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}

          {files.map((file) => {
            const FileIcon = getFileIcon(file.content_type);
            const canPreview = isPreviewable(file.content_type);
            return (
              <div
                key={file.id}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:border-fuchsia-400 hover:shadow-md transition-all relative group cursor-pointer"
                onClick={() => canPreview && onPreview?.(file)}
                data-testid={`file-${file.id}`}
              >
                <div className="flex flex-col items-center text-center">
                  <FileIcon className="w-12 h-12 text-gray-400 mb-2" />
                  <span className="text-sm font-medium text-gray-900 truncate w-full" title={file.original_filename}>
                    {file.original_filename}
                  </span>
                  <span className="text-xs text-gray-500 font-mono mt-1">{formatSize(file.size)}</span>
                  {file.is_shared && (
                    <span className="text-xs text-fuchsia-600 flex items-center gap-1 mt-1">
                      <Share2 className="w-3 h-3" /> Geteilt
                    </span>
                  )}
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="icon" className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {canPreview && (
                      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onPreview?.(file); }}>
                        <Eye className="w-4 h-4 mr-2" />
                        Vorschau
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); downloadFile(file.id, file.original_filename).catch(() => {}); }}>
                      <Download className="w-4 h-4 mr-2" />
                      Herunterladen
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onMoveFile?.(file); }}>
                      <FolderInput className="w-4 h-4 mr-2" />
                      Verschieben
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onShare(file); }}>
                      <Share2 className="w-4 h-4 mr-2" />
                      Teilen
                    </DropdownMenuItem>
                    {canDelete && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDelete(file); }} className="text-red-600">
                          <Trash2 className="w-4 h-4 mr-2" />
                          Löschen
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // List View
  return (
    <div className="space-y-2">
      {currentPath !== "/" && (
        <button
          onClick={onNavigateUp}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-fuchsia-600 transition-colors mb-4"
          data-testid="navigate-up-btn"
        >
          <ChevronUp className="w-4 h-4" />
          Zurück
        </button>
      )}

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full" data-testid="files-table">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-left hidden sm:table-cell">Größe</th>
              <th className="px-4 py-3 text-left hidden md:table-cell">Geändert</th>
              <th className="px-4 py-3 text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {/* Folders */}
            {folders.map((folder) => (
              <tr 
                key={folder.id} 
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => onNavigate(folder.path)}
                data-testid={`folder-row-${folder.id}`}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Folder className="w-5 h-5 text-fuchsia-500 flex-shrink-0" />
                    <div className="min-w-0">
                      <span className="font-medium text-gray-900 truncate block">{folder.name}</span>
                      {folder.is_shared && (
                        <span className="text-xs text-fuchsia-600 flex items-center gap-1">
                          <Share2 className="w-3 h-3" /> Geteilt
                        </span>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell text-gray-500">—</td>
                <td className="px-4 py-3 hidden md:table-cell text-gray-500 font-mono text-xs">
                  {formatDate(folder.created_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost" size="icon"
                      onClick={() => { downloadFolderZip(folder.id, folder.name).catch(() => {}); }}
                      className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                      title="Als ZIP herunterladen"
                      data-testid={`download-folder-${folder.id}`}
                    >
                      <FolderDown className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost" size="icon"
                      onClick={() => onShareFolder?.(folder)}
                      className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                      data-testid={`share-folder-${folder.id}`}
                    >
                      <Share2 className="w-4 h-4" />
                    </Button>
                    {canDelete && (
                      <Button
                        variant="ghost" size="icon"
                        onClick={() => onDeleteFolder(folder)}
                        className="h-8 w-8 text-gray-500 hover:text-red-500"
                        data-testid={`delete-folder-${folder.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}

            {/* Files */}
            {files.map((file) => {
              const FileIcon = getFileIcon(file.content_type);
              const canPreview = isPreviewable(file.content_type);
              return (
                <tr key={file.id} className="hover:bg-gray-50" data-testid={`file-row-${file.id}`}>
                  <td className="px-4 py-3">
                    <div 
                      className={`flex items-center gap-3 ${canPreview ? "cursor-pointer" : ""}`}
                      onClick={() => canPreview && onPreview?.(file)}
                    >
                      <FileIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <span className={`font-medium text-gray-900 truncate block ${canPreview ? "hover:text-fuchsia-600" : ""}`} title={file.original_filename}>
                          {file.original_filename}
                        </span>
                        {file.is_shared && (
                          <span className="text-xs text-fuchsia-600 flex items-center gap-1">
                            <Share2 className="w-3 h-3" /> Geteilt
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell text-gray-500 font-mono text-sm">
                    {formatSize(file.size)}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-gray-500 font-mono text-xs">
                    {formatDate(file.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {canPreview && (
                        <Button
                          variant="ghost" size="icon"
                          onClick={() => onPreview?.(file)}
                          className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                          title="Vorschau"
                          data-testid={`preview-file-${file.id}`}
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost" size="icon"
                        onClick={() => { downloadFile(file.id, file.original_filename).catch(() => {}); }}
                        className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                        title="Herunterladen"
                        data-testid={`download-file-${file.id}`}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500">
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => onMoveFile?.(file)}>
                            <FolderInput className="w-4 h-4 mr-2" />
                            Verschieben
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => onShare(file)}>
                            <Share2 className="w-4 h-4 mr-2" />
                            Teilen
                          </DropdownMenuItem>
                          {canDelete && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => onDelete(file)} className="text-red-600">
                                <Trash2 className="w-4 h-4 mr-2" />
                                Löschen
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </td>
                </tr>
              );
            })}

            {files.length === 0 && folders.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                  Dieser Ordner ist leer
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
