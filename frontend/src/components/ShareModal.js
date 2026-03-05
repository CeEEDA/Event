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
import { Switch } from "./ui/switch";
import { toast } from "sonner";
import api from "../lib/api";
import { Link2, Copy, Lock, Calendar, Check, Folder, FileText, Upload, Pencil } from "lucide-react";

export const ShareModal = ({ open, onClose, item, shareType = "file", onShareCreated }) => {
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [password, setPassword] = useState("");
  const [usePassword, setUsePassword] = useState(false);
  const [allowDownload, setAllowDownload] = useState(true);
  const [allowUpload, setAllowUpload] = useState(false);
  const [allowEdit, setAllowEdit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [shareLink, setShareLink] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleCreate = async () => {
    if (!item) return;
    
    setLoading(true);
    try {
      const payload = {
        share_type: shareType,
        expires_in_days: parseInt(expiresInDays),
        password: usePassword && password ? password : null,
        allow_download: allowDownload,
        allow_upload: allowUpload,
        allow_edit: allowEdit
      };
      
      if (shareType === "file") {
        payload.file_id = item.id;
      } else {
        payload.folder_id = item.id;
      }
      
      const response = await api.post("/shares", payload);
      
      const baseUrl = window.location.origin;
      setShareLink(`${baseUrl}/share/${response.data.token}`);
      toast.success("Share-Link erstellt");
      onShareCreated?.();
    } catch (error) {
      toast.error("Fehler beim Erstellen des Links");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!shareLink) return;
    
    try {
      await navigator.clipboard.writeText(shareLink);
      setCopied(true);
      toast.success("Link kopiert");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Kopieren fehlgeschlagen");
    }
  };

  const handleClose = () => {
    setShareLink(null);
    setPassword("");
    setUsePassword(false);
    setAllowUpload(false);
    setAllowEdit(false);
    setCopied(false);
    onClose();
  };

  const itemName = shareType === "file" ? item?.original_filename : item?.name;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="share-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <Link2 className="w-5 h-5 text-fuchsia-600" />
            {shareType === "file" ? "Datei teilen" : "Ordner teilen"}
          </DialogTitle>
        </DialogHeader>

        {shareLink ? (
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500 mb-2">Share-Link:</p>
              <div className="flex gap-2">
                <Input
                  value={shareLink}
                  readOnly
                  className="font-mono text-sm border-gray-300"
                  data-testid="share-link-input"
                />
                <Button
                  onClick={handleCopy}
                  variant="outline"
                  className="flex-shrink-0 border-gray-300"
                  data-testid="copy-link-btn"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
            
            {usePassword && password && (
              <div className="p-3 bg-fuchsia-50 border border-fuchsia-300 rounded-lg">
                <p className="text-sm text-fuchsia-800 flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  Passwort: <span className="font-mono">{password}</span>
                </p>
              </div>
            )}

            <div className="p-3 bg-gray-50 rounded-lg space-y-1 text-sm">
              <p className="text-gray-600">
                <span className="font-medium">Berechtigungen:</span>
              </p>
              <ul className="text-gray-500 space-y-1 ml-4">
                {allowDownload && <li>• Download erlaubt</li>}
                {allowUpload && <li>• Upload erlaubt</li>}
                {allowEdit && <li>• Bearbeiten/Löschen erlaubt</li>}
              </ul>
            </div>

            <DialogFooter>
              <Button onClick={handleClose} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                Schließen
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Item Info */}
            <div className="p-3 bg-gray-50 rounded-lg flex items-center gap-3">
              {shareType === "file" ? (
                <FileText className="w-5 h-5 text-gray-400" />
              ) : (
                <Folder className="w-5 h-5 text-fuchsia-500" />
              )}
              <span className="text-sm font-medium text-gray-900 truncate">{itemName}</span>
            </div>

            {/* Expiration */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2 text-gray-700">
                <Calendar className="w-4 h-4" />
                Gültig für (Tage)
              </Label>
              <Input
                type="number"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                min={1}
                max={365}
                className="border-gray-300"
                data-testid="expires-days-input"
              />
            </div>

            {/* Password Toggle */}
            <div className="flex items-center justify-between">
              <Label className="flex items-center gap-2 text-gray-700">
                <Lock className="w-4 h-4" />
                Passwortschutz
              </Label>
              <Switch
                checked={usePassword}
                onCheckedChange={setUsePassword}
                data-testid="password-toggle"
              />
            </div>

            {/* Password Input */}
            {usePassword && (
              <div className="space-y-2">
                <Label className="text-gray-700">Passwort</Label>
                <Input
                  type="text"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Passwort eingeben"
                  className="border-gray-300"
                  data-testid="share-password-input"
                />
              </div>
            )}

            {/* Permissions */}
            <div className="border-t border-gray-200 pt-4 space-y-3">
              <Label className="text-gray-700 font-medium">Berechtigungen für Empfänger</Label>
              
              <div className="flex items-center justify-between">
                <Label className="text-gray-600 text-sm flex items-center gap-2">
                  <Download className="w-4 h-4" />
                  Download erlauben
                </Label>
                <Switch
                  checked={allowDownload}
                  onCheckedChange={setAllowDownload}
                  data-testid="download-toggle"
                />
              </div>

              {shareType === "folder" && (
                <>
                  <div className="flex items-center justify-between">
                    <Label className="text-gray-600 text-sm flex items-center gap-2">
                      <Upload className="w-4 h-4" />
                      Upload erlauben
                    </Label>
                    <Switch
                      checked={allowUpload}
                      onCheckedChange={setAllowUpload}
                      data-testid="upload-toggle"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <Label className="text-gray-600 text-sm flex items-center gap-2">
                      <Pencil className="w-4 h-4" />
                      Bearbeiten/Löschen erlauben
                    </Label>
                    <Switch
                      checked={allowEdit}
                      onCheckedChange={setAllowEdit}
                      data-testid="edit-toggle"
                    />
                  </div>
                </>
              )}
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={handleClose} className="border-gray-300">
                Abbrechen
              </Button>
              <Button
                onClick={handleCreate}
                disabled={loading || (usePassword && !password)}
                className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                data-testid="create-share-btn"
              >
                {loading ? "Wird erstellt..." : "Link erstellen"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

// Import Download icon 
const Download = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" x2="12" y1="15" y2="3"/>
  </svg>
);
