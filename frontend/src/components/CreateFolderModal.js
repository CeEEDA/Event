import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Folder } from "lucide-react";

export const CreateFolderModal = ({ open, onClose, onCreateFolder }) => {
  const [folderName, setFolderName] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!folderName.trim()) return;
    
    setLoading(true);
    try {
      await onCreateFolder(folderName.trim());
      setFolderName("");
      onClose();
    } catch (error) {
      // Error handled in parent
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setFolderName("");
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="create-folder-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <Folder className="w-5 h-5 text-fuchsia-600" />
            Neuen Ordner erstellen
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-gray-700">Ordnername</Label>
            <Input
              type="text"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="Mein Ordner"
              className="border-gray-300"
              autoFocus
              data-testid="folder-name-input"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleClose}
              disabled={loading}
              className="border-gray-300"
            >
              Abbrechen
            </Button>
            <Button
              type="submit"
              disabled={loading || !folderName.trim()}
              className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
              data-testid="create-folder-submit-btn"
            >
              {loading ? "Wird erstellt..." : "Erstellen"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
