import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Folder, ChevronRight, Home } from "lucide-react";

export const MoveFileModal = ({ open, onClose, file, folders, currentStorageArea, onMove }) => {
  const [targetPath, setTargetPath] = useState("/");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) setTargetPath("/");
  }, [open]);

  const handleMove = async () => {
    setLoading(true);
    try {
      await onMove(file.id, targetPath, currentStorageArea);
      onClose();
    } catch (error) {
      // handled in parent
    } finally {
      setLoading(false);
    }
  };

  // Get direct children of target path
  const childFolders = folders.filter(f => {
    const parent = f.path.substring(0, f.path.lastIndexOf("/")) || "/";
    return parent === targetPath;
  });

  const navigateUp = () => {
    if (targetPath === "/") return;
    setTargetPath(targetPath.substring(0, targetPath.lastIndexOf("/")) || "/");
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="move-file-modal">
        <DialogHeader>
          <DialogTitle className="text-gray-900">
            Datei verschieben
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <p className="text-sm text-gray-500 truncate">
            <span className="font-medium text-gray-700">{file?.original_filename}</span>
          </p>

          {/* Current target display */}
          <div className="flex items-center gap-2 p-2 bg-fuchsia-50 rounded-lg border border-fuchsia-200">
            <Home className="w-4 h-4 text-fuchsia-600 flex-shrink-0" />
            <span className="text-sm font-mono text-fuchsia-700 truncate">
              {targetPath === "/" ? "/ (Stammverzeichnis)" : targetPath}
            </span>
          </div>

          {/* Folder browser */}
          <div className="border border-gray-200 rounded-lg max-h-52 overflow-y-auto">
            {targetPath !== "/" && (
              <button
                onClick={navigateUp}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:bg-gray-50 border-b border-gray-100"
                data-testid="move-navigate-up"
              >
                <ChevronRight className="w-4 h-4 rotate-180" />
                Zurück
              </button>
            )}
            <button
              onClick={() => setTargetPath("/")}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 ${
                targetPath === "/" ? "bg-fuchsia-50 text-fuchsia-700 font-medium" : "text-gray-700"
              }`}
              data-testid="move-root-folder"
            >
              <Home className="w-4 h-4" />
              Stammverzeichnis
            </button>
            {childFolders.map(folder => (
              <button
                key={folder.id}
                onClick={() => setTargetPath(folder.path)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 ${
                  targetPath === folder.path ? "bg-fuchsia-50 text-fuchsia-700 font-medium" : "text-gray-700"
                }`}
                data-testid={`move-folder-${folder.id}`}
              >
                <Folder className="w-4 h-4 text-fuchsia-500" />
                <span className="truncate">{folder.name}</span>
                <ChevronRight className="w-4 h-4 ml-auto text-gray-400" />
              </button>
            ))}
            {childFolders.length === 0 && targetPath !== "/" && (
              <p className="px-3 py-2 text-xs text-gray-400">Keine Unterordner</p>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={loading} className="border-gray-300">
            Abbrechen
          </Button>
          <Button
            onClick={handleMove}
            disabled={loading || targetPath === file?.folder_path}
            className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            data-testid="move-confirm-btn"
          >
            {loading ? "Wird verschoben..." : "Hierhin verschieben"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
