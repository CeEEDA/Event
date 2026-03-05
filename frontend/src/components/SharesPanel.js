import { useState, useEffect } from "react";
import { Button } from "./ui/button";
import { toast } from "sonner";
import api from "../lib/api";
import { 
  Link2, 
  Trash2, 
  Copy, 
  ExternalLink,
  Lock,
  Calendar,
  Eye,
  Check
} from "lucide-react";

export const SharesPanel = () => {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState(null);

  const loadShares = async () => {
    setLoading(true);
    try {
      const response = await api.get("/shares");
      setShares(response.data);
    } catch (error) {
      toast.error("Fehler beim Laden der Shares");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShares();
  }, []);

  const handleDelete = async (share) => {
    if (!window.confirm("Share-Link wirklich löschen?")) return;
    
    try {
      await api.delete(`/shares/${share.id}`);
      toast.success("Share-Link gelöscht");
      loadShares();
    } catch (error) {
      toast.error("Fehler beim Löschen");
    }
  };

  const handleCopy = async (share) => {
    const link = `${window.location.origin}/share/${share.token}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopiedId(share.id);
      toast.success("Link kopiert");
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      toast.error("Kopieren fehlgeschlagen");
    }
  };

  const formatDate = (isoString) => {
    return new Date(isoString).toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  };

  const isExpired = (expiresAt) => {
    return new Date(expiresAt) < new Date();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-muted-foreground">Laden...</div>
      </div>
    );
  }

  if (shares.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center" data-testid="shares-empty">
        <Link2 className="w-16 h-16 text-muted-foreground/30 mb-4" />
        <h3 className="text-lg font-medium mb-1">Keine Share-Links</h3>
        <p className="text-sm text-muted-foreground">
          Teilen Sie Dateien über den Datei-Browser
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="shares-panel">
      <div className="bg-card border border-border rounded-sm overflow-hidden">
        <table className="data-table">
          <thead className="bg-muted/30">
            <tr>
              <th className="text-left">Link</th>
              <th className="text-left hidden sm:table-cell">Erstellt</th>
              <th className="text-left hidden md:table-cell">Läuft ab</th>
              <th className="text-left hidden lg:table-cell">Zugriffe</th>
              <th className="text-left hidden sm:table-cell">Status</th>
              <th className="text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {shares.map((share) => {
              const expired = isExpired(share.expires_at);
              return (
                <tr key={share.id} data-testid={`share-row-${share.id}`}>
                  <td>
                    <div className="flex items-center gap-2">
                      <Link2 className="w-4 h-4 text-primary flex-shrink-0" />
                      <span className="font-mono text-sm truncate max-w-[120px] sm:max-w-[200px]">
                        {share.token}
                      </span>
                      {share.password_protected && (
                        <Lock className="w-3 h-3 text-secondary flex-shrink-0" />
                      )}
                    </div>
                  </td>
                  <td className="hidden sm:table-cell text-muted-foreground text-sm">
                    {formatDate(share.created_at)}
                  </td>
                  <td className="hidden md:table-cell">
                    <span className={`text-sm flex items-center gap-1 ${expired ? "text-destructive" : "text-muted-foreground"}`}>
                      <Calendar className="w-3 h-3" />
                      {formatDate(share.expires_at)}
                    </span>
                  </td>
                  <td className="hidden lg:table-cell">
                    <span className="text-sm flex items-center gap-1 text-muted-foreground">
                      <Eye className="w-3 h-3" />
                      {share.access_count}
                    </span>
                  </td>
                  <td className="hidden sm:table-cell">
                    {expired ? (
                      <span className="px-2 py-1 rounded-sm text-xs font-medium bg-destructive/20 text-destructive">
                        Abgelaufen
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded-sm text-xs font-medium bg-green-500/20 text-green-500">
                        Aktiv
                      </span>
                    )}
                  </td>
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleCopy(share)}
                        className="h-8 w-8"
                        disabled={expired}
                        data-testid={`copy-share-${share.id}`}
                      >
                        {copiedId === share.id ? (
                          <Check className="w-4 h-4 text-green-500" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => window.open(`/share/${share.token}`, "_blank")}
                        className="h-8 w-8"
                        disabled={expired}
                        data-testid={`open-share-${share.id}`}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(share)}
                        className="h-8 w-8 hover:text-destructive"
                        data-testid={`delete-share-${share.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
