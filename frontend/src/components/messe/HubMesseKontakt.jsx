import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Presentation, Share2, ExternalLink, ClipboardList } from "lucide-react";
import { toast } from "sonner";
import api from "../../lib/api";

// Hub: waehrend einer Messe, bei der ich im Team bin -> QR-Code mit meiner Kontaktkarte zum Teilen
export function HubMesseKontakt() {
  const [messen, setMessen] = useState([]);

  useEffect(() => {
    api.get("/messe/my-active").then(r => setMessen(r.data || [])).catch(() => setMessen([]));
  }, []);

  if (messen.length === 0) return null;

  const share = async (m, url) => {
    if (navigator.share) {
      try { await navigator.share({ title: `Kontakt – ${m.name}`, url }); return; } catch { /* abgebrochen */ }
    }
    navigator.clipboard?.writeText(url);
    toast.success("Kontakt-Link kopiert");
  };

  return (
    <div className="mb-5 space-y-3" data-testid="hub-messe-kontakt">
      {messen.map(m => {
        const url = `${window.location.origin}/messe/kontakt/${m.contact_token}`;
        return (
          <div key={m.id} className="rounded-xl border border-fuchsia-200 bg-gradient-to-br from-fuchsia-50 to-white p-4 flex flex-col sm:flex-row items-center gap-4" data-testid={`hub-messe-kontakt-${m.id}`}>
            <div className="bg-white p-2 rounded-xl border border-gray-200 shadow-sm shrink-0">
              <QRCodeSVG value={url} size={132} level="M" />
            </div>
            <div className="flex-1 min-w-0 text-center sm:text-left">
              <p className="text-xs uppercase tracking-widest text-fuchsia-600 font-semibold flex items-center justify-center sm:justify-start gap-1"><Presentation className="w-3.5 h-3.5" /> Messe läuft</p>
              <h2 className="text-base md:text-lg font-bold text-gray-900 mt-1">{m.name}</h2>
              {m.location && <p className="text-sm text-gray-500">{m.location}</p>}
              <p className="text-sm text-gray-600 mt-2">Besucher scannen den Code und erhalten deine Kontaktkarte (Name, Telefon, E-Mail) direkt aufs Handy.</p>
              <div className="flex flex-wrap gap-2 mt-3 justify-center sm:justify-start">
                <button type="button" onClick={() => share(m, url)} className="h-9 px-3 rounded-lg bg-fuchsia-600 text-white text-sm font-semibold flex items-center gap-1.5" data-testid={`hub-messe-share-${m.id}`}><Share2 className="w-4 h-4" /> Kontakt teilen</button>
                <a href={url} target="_blank" rel="noreferrer" className="h-9 px-3 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 flex items-center gap-1.5" data-testid={`hub-messe-open-${m.id}`}><ExternalLink className="w-4 h-4" /> Vorschau</a>
                <a href={`/messe-protokoll/${m.id}`} className="h-9 px-3 rounded-lg bg-gray-900 text-white text-sm font-semibold flex items-center gap-1.5" data-testid={`hub-messe-protokoll-${m.id}`}><ClipboardList className="w-4 h-4" /> Messeprotokoll anlegen</a>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
