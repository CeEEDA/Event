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
  ChevronUp
} from "lucide-react";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

const getFileIcon = (contentType) => {
  if (contentType.startsWith("image/")) return FileImage;
  if (contentType.startsWith("video/")) return FileVideo;
  if (contentType.startsWith("audio/")) return FileAudio;
  if (contentType.includes("zip") || contentType.includes("archive") || contentType.includes("rar")) 
    return FileArchive;
  if (contentType.includes("pdf") || contentType.includes("document") || contentType.includes("text"))
    return FileText;
  return File;
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
  onDeleteFolder
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
          Laden Sie Ihre erste Datei hoch
        </p>
      </div>
    );
  }

  if (viewMode === "grid") {
    return (
      <div className="space-y-4">
        {/* Navigate Up */}
        {currentPath !== "/" && (
          <button
            onClick={onNavigateUp}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-orange-500 transition-colors"
            data-testid="navigate-up-btn"
          >
            <ChevronUp className="w-4 h-4" />
            Zurück
          </button>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {/* Folders */}
          {folders.map((folder) => (
            <div
              key={folder.id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-orange-300 hover:shadow-md transition-all cursor-pointer group relative"
              onClick={() => onNavigate(folder.path)}
              data-testid={`folder-${folder.id}`}
            >
              <div className="flex flex-col items-center text-center">
                <Folder className="w-12 h-12 text-orange-400 mb-2" />
                <span className="text-sm font-medium text-gray-900 truncate w-full">{folder.name}</span>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6"
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onDeleteFolder(folder); }}>
                    <Trash2 className="w-4 h-4 mr-2" />
                    Löschen
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}

          {/* Files */}
          {files.map((file) => {
            const FileIcon = getFileIcon(file.content_type);
            return (
              <div
                key={file.id}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:border-orange-300 hover:shadow-md transition-all relative group"
                data-testid={`file-${file.id}`}
              >
                <div className="flex flex-col items-center text-center">
                  <FileIcon className="w-12 h-12 text-gray-400 mb-2" />
                  <span className="text-sm font-medium text-gray-900 truncate w-full" title={file.original_filename}>
                    {file.original_filename}
                  </span>
                  <span className="text-xs text-gray-500 font-mono mt-1">
                    {formatSize(file.size)}
                  </span>
                  {file.is_shared && (
                    <span className="text-xs text-orange-500 flex items-center gap-1 mt-1">
                      <Share2 className="w-3 h-3" />
                      Geteilt
                    </span>
                  )}
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem onClick={() => onDownload(file)}>
                      <Download className="w-4 h-4 mr-2" />
                      Herunterladen
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onShare(file)}>
                      <Share2 className="w-4 h-4 mr-2" />
                      Teilen
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onDelete(file)} className="text-red-600">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Löschen
                    </DropdownMenuItem>
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
      {/* Navigate Up */}
      {currentPath !== "/" && (
        <button
          onClick={onNavigateUp}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-orange-500 transition-colors mb-4"
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
                    <Folder className="w-5 h-5 text-orange-400 flex-shrink-0" />
                    <span className="font-medium text-gray-900 truncate">{folder.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell text-gray-500">—</td>
                <td className="px-4 py-3 hidden md:table-cell text-gray-500 font-mono text-xs">
                  {formatDate(folder.created_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => { e.stopPropagation(); onDeleteFolder(folder); }}
                    className="h-8 w-8 text-gray-500 hover:text-red-500"
                    data-testid={`delete-folder-${folder.id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </td>
              </tr>
            ))}

            {/* Files */}
            {files.map((file) => {
              const FileIcon = getFileIcon(file.content_type);
              return (
                <tr key={file.id} className="hover:bg-gray-50" data-testid={`file-row-${file.id}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <FileIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <span className="font-medium text-gray-900 truncate block" title={file.original_filename}>
                          {file.original_filename}
                        </span>
                        {file.is_shared && (
                          <span className="text-xs text-orange-500 flex items-center gap-1">
                            <Share2 className="w-3 h-3" />
                            Geteilt
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
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDownload(file)}
                        className="h-8 w-8 text-gray-500 hover:text-orange-500"
                        data-testid={`download-file-${file.id}`}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onShare(file)}
                        className="h-8 w-8 text-gray-500 hover:text-orange-500"
                        data-testid={`share-file-${file.id}`}
                      >
                        <Share2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDelete(file)}
                        className="h-8 w-8 text-gray-500 hover:text-red-500"
                        data-testid={`delete-file-${file.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
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
