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
      <DialogContent className="bg-card border-border sm:max-w-md" data-testid="share-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Link2 className="w-5 h-5 text-primary" />
            Datei teilen
          </DialogTitle>
        </DialogHeader>

        {shareLink ? (
          <div className="space-y-4">
            <div className="p-4 bg-muted/30 rounded-sm">
              <p className="text-sm text-muted-foreground mb-2">Share-Link:</p>
              <div className="flex gap-2">
                <Input
                  value={shareLink}
                  readOnly
                  className="bg-background font-mono text-sm"
                  data-testid="share-link-input"
                />
                <Button
                  onClick={handleCopy}
                  variant="outline"
                  className="flex-shrink-0"
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
              <div className="p-3 bg-secondary/10 border border-secondary/30 rounded-sm">
                <p className="text-sm text-secondary flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  Passwort: <span className="font-mono">{password}</span>
                </p>
              </div>
            )}

            <DialogFooter>
              <Button onClick={handleClose} className="w-full">
                Schließen
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            {/* File Info */}
            <div className="p-3 bg-muted/30 rounded-sm">
              <p className="text-sm font-medium truncate">{file?.original_filename}</p>
            </div>

            {/* Expiration */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                Gültig für (Tage)
              </Label>
              <Input
                type="number"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                min={1}
                max={365}
                className="bg-background"
                data-testid="expires-days-input"
              />
            </div>

            {/* Password Toggle */}
            <div className="flex items-center justify-between">
              <Label className="flex items-center gap-2">
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
                <Label>Passwort</Label>
                <Input
                  type="text"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Passwort eingeben"
                  className="bg-background"
                  data-testid="share-password-input"
                />
              </div>
            )}

            {/* Download Toggle */}
            <div className="flex items-center justify-between">
              <Label>Download erlauben</Label>
              <Switch
                checked={allowDownload}
                onCheckedChange={setAllowDownload}
                data-testid="download-toggle"
              />
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={handleClose}>
                Abbrechen
              </Button>
              <Button
                onClick={handleCreate}
                disabled={loading || (usePassword && !password)}
                className="bg-primary hover:bg-primary/90"
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
