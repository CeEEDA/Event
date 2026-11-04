import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Presentation, Share2, ClipboardList, X, Maximize2 } from "lucide-react";
import { toast } from "sonner";
import api from "../../lib/api";

// Hub: waehrend einer Messe, bei der ich im Team bin -> QR-Code mit meiner Kontaktkarte zum Teilen
export function HubMesseKontakt() {
  const [messen, setMessen] = useState([]);
  const [voll, setVoll] = useState(null); // Messe, deren QR bildschirmfuellend gezeigt wird

  useEffect(() => {
    api.get("/messe/my-active").then(r => setMessen(r.data || [])).catch(() => setMessen([]));
  }, []);

  useEffect(() => {
    if (!voll) return;
    const onKey = (e) => e.key === "Escape" && setVoll(null);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [voll]);

  if (messen.length === 0) return null;

  const urlFor = (m) => `${window.location.origin}/messe/kontakt/${m.contact_token}`;

  const share = async (m) => {
    const url = urlFor(m);
    if (navigator.share) {
      try { await navigator.share({ title: `Kontakt – ${m.name}`, url }); return; } catch { /* abgebrochen */ }
    }
    navigator.clipboard?.writeText(url);
    toast.success("Kontakt-Link kopiert");
  };

  return (
    <div className="mb-5 space-y-3" data-testid="hub-messe-kontakt">
      {messen.map(m => (
        <div key={m.id} className="rounded-xl border border-fuchsia-200 bg-gradient-to-br from-fuchsia-50 to-white p-4 flex flex-col sm:flex-row items-center gap-4" data-testid={`hub-messe-kontakt-${m.id}`}>
          <button type="button" onClick={() => setVoll(m)} className="bg-white p-2 rounded-xl border border-gray-200 shadow-sm shrink-0 relative active:scale-[0.98] transition" title="QR-Code groß anzeigen" data-testid={`hub-messe-qr-${m.id}`}>
            <QRCodeSVG value={urlFor(m)} size={132} level="M" />
            <span className="absolute -bottom-2 -right-2 w-7 h-7 rounded-full bg-fuchsia-600 text-white flex items-center justify-center shadow"><Maximize2 className="w-3.5 h-3.5" /></span>
          </button>
          <div className="flex-1 min-w-0 text-center sm:text-left">
            <p className="text-xs uppercase tracking-widest text-fuchsia-600 font-semibold flex items-center justify-center sm:justify-start gap-1"><Presentation className="w-3.5 h-3.5" /> Messe läuft</p>
            <h2 className="text-base md:text-lg font-bold text-gray-900 mt-1">{m.name}</h2>
            {m.location && <p className="text-sm text-gray-500">{m.location}</p>}
            <p className="text-sm text-gray-600 mt-2">QR antippen → bildschirmfüllend zum Scannen. Besucher erhalten deine Kontaktkarte direkt aufs Handy.</p>
            <div className="flex flex-wrap gap-2 mt-3 justify-center sm:justify-start">
              <button type="button" onClick={() => setVoll(m)} className="h-9 px-3 rounded-lg bg-fuchsia-600 text-white text-sm font-semibold flex items-center gap-1.5" data-testid={`hub-messe-show-${m.id}`}><Maximize2 className="w-4 h-4" /> QR groß zeigen</button>
              <button type="button" onClick={() => share(m)} className="h-9 px-3 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 flex items-center gap-1.5" data-testid={`hub-messe-share-${m.id}`}><Share2 className="w-4 h-4" /> Kontakt teilen</button>
              <a href={`/messe-protokoll/${m.id}`} className="h-9 px-3 rounded-lg bg-gray-900 text-white text-sm font-semibold flex items-center gap-1.5" data-testid={`hub-messe-protokoll-${m.id}`}><ClipboardList className="w-4 h-4" /> Messeprotokoll anlegen</a>
            </div>
          </div>
        </div>
      ))}

      {voll && (
        <div className="fixed inset-0 z-[100] bg-white flex flex-col items-center justify-center px-6" onClick={() => setVoll(null)} data-testid="hub-messe-qr-fullscreen">
          <button type="button" onClick={() => setVoll(null)} className="absolute top-4 right-4 w-11 h-11 rounded-full bg-gray-100 flex items-center justify-center" aria-label="Schließen" data-testid="hub-messe-qr-close"><X className="w-5 h-5 text-gray-700" /></button>
          <p className="text-xs uppercase tracking-[0.25em] text-fuchsia-600 font-semibold">Kontakt scannen</p>
          <h2 className="text-2xl font-bold text-gray-900 mt-1 text-center">{voll.name}</h2>
          <div className="mt-6 w-full max-w-[min(86vw,70vh)] aspect-square bg-white p-3 rounded-2xl border border-gray-200 shadow-lg">
            <QRCodeSVG value={urlFor(voll)} level="M" style={{ width: "100%", height: "100%" }} />
          </div>
          <p className="text-sm text-gray-500 mt-6 text-center">Besucher: Kamera auf den Code richten – Kontaktkarte öffnet sich.<br />Zum Schließen irgendwo antippen.</p>
        </div>
      )}
    </div>
  );
}
