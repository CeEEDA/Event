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
  Check,
  Folder,
  FileText,
  Upload,
  Pencil
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
        <div className="animate-pulse text-gray-500">Laden...</div>
      </div>
    );
  }

  if (shares.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center" data-testid="shares-empty">
        <Link2 className="w-16 h-16 text-gray-300 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-1">Keine Share-Links</h3>
        <p className="text-sm text-gray-500">
          Teilen Sie Dateien oder Ordner über den Datei-Browser
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="shares-panel">
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Typ</th>
              <th className="px-4 py-3 text-left">Link</th>
              <th className="px-4 py-3 text-left hidden sm:table-cell">Erstellt</th>
              <th className="px-4 py-3 text-left hidden md:table-cell">Läuft ab</th>
              <th className="px-4 py-3 text-left hidden lg:table-cell">Berechtigungen</th>
              <th className="px-4 py-3 text-left hidden sm:table-cell">Status</th>
              <th className="px-4 py-3 text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {shares.map((share) => {
              const expired = isExpired(share.expires_at);
              const isFolder = share.share_type === "folder";
              return (
                <tr key={share.id} className="hover:bg-gray-50" data-testid={`share-row-${share.id}`}>
                  <td className="px-4 py-3">
                    {isFolder ? (
                      <Folder className="w-5 h-5 text-orange-400" />
                    ) : (
                      <FileText className="w-5 h-5 text-gray-400" />
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-gray-900 truncate max-w-[120px] sm:max-w-[200px]">
                        {share.token}
                      </span>
                      {share.password_protected && (
                        <Lock className="w-3 h-3 text-orange-500 flex-shrink-0" />
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell text-gray-500 text-sm">
                    {formatDate(share.created_at)}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className={`text-sm flex items-center gap-1 ${expired ? "text-red-500" : "text-gray-500"}`}>
                      <Calendar className="w-3 h-3" />
                      {formatDate(share.expires_at)}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <div className="flex items-center gap-1">
                      {share.allow_download && (
                        <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">DL</span>
                      )}
                      {share.allow_upload && (
                        <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">UP</span>
                      )}
                      {share.allow_edit && (
                        <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">Edit</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    {expired ? (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700">
                        Abgelaufen
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700">
                        Aktiv
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleCopy(share)}
                        className="h-8 w-8 text-gray-500 hover:text-orange-500"
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
                        className="h-8 w-8 text-gray-500 hover:text-orange-500"
                        disabled={expired}
                        data-testid={`open-share-${share.id}`}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(share)}
                        className="h-8 w-8 text-gray-500 hover:text-red-500"
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
