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
import { Link2, Copy, Lock, Calendar, Check } from "lucide-react";

export const ShareModal = ({ open, onClose, file, onShareCreated }) => {
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [password, setPassword] = useState("");
  const [usePassword, setUsePassword] = useState(false);
  const [allowDownload, setAllowDownload] = useState(true);
  const [loading, setLoading] = useState(false);
  const [shareLink, setShareLink] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleCreate = async () => {
    if (!file) return;
    
    setLoading(true);
    try {
      const response = await api.post("/shares", {
        file_id: file.id,
        expires_in_days: parseInt(expiresInDays),
        password: usePassword && password ? password : null,
        allow_download: allowDownload
      });
      
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
    setCopied(false);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="share-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <Link2 className="w-5 h-5 text-orange-500" />
            Datei teilen
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
              <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <p className="text-sm text-orange-700 flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  Passwort: <span className="font-mono">{password}</span>
                </p>
              </div>
            )}

            <DialogFooter>
              <Button onClick={handleClose} className="w-full bg-orange-500 hover:bg-orange-600 text-white">
                Schließen
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            {/* File Info */}
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-900 truncate">{file?.original_filename}</p>
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

            {/* Download Toggle */}
            <div className="flex items-center justify-between">
              <Label className="text-gray-700">Download erlauben</Label>
              <Switch
                checked={allowDownload}
                onCheckedChange={setAllowDownload}
                data-testid="download-toggle"
              />
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={handleClose} className="border-gray-300">
                Abbrechen
              </Button>
              <Button
                onClick={handleCreate}
                disabled={loading || (usePassword && !password)}
                className="bg-orange-500 hover:bg-orange-600 text-white"
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
