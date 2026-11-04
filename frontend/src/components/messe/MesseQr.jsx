import { QRCodeSVG } from "qrcode.react";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "sonner";
import { Copy, ExternalLink, Printer, QrCode } from "lucide-react";
import { Button } from "../ui/button";
import { Karte } from "../mbox/MBoxUi";

const publicUrl = (messe, deviceId) => `${window.location.origin}/messe/${messe.public_token}${deviceId ? `/${deviceId}` : ""}`;

export function MesseQr({ messe }) {
  const devices = messe.devices || [];

  const copy = async (url) => {
    try { await navigator.clipboard.writeText(url); toast.success("Link kopiert"); } catch { toast.error("Kopieren nicht möglich"); }
  };

  const print = () => {
    const karte = (key, titel, untertitel, url, text) => (
      <div className="card" key={key}>
        <h1>{titel}</h1>
        <h2>{untertitel}</h2>
        <QRCodeSVG value={url} size={264} level="M" includeMargin={false} />
        <p>{text}<br />Kein Login nötig.</p>
      </div>
    );
    const html = renderToStaticMarkup(
      <html>
        <head>
          <title>QR-Codes {messe.name}</title>
          <style>{`body{font-family:Arial,sans-serif;margin:0;padding:16mm;color:#111}
            .card{page-break-inside:avoid;border:2px solid #111;border-radius:16px;padding:14mm;margin-bottom:12mm;text-align:center}
            h1{font-size:26pt;margin:0 0 4mm} h2{font-size:18pt;margin:0 0 8mm;color:#444} p{font-size:12pt;margin:6mm 0 0;color:#666} svg{width:70mm;height:70mm}`}</style>
        </head>
        <body>
          {karte("messe", messe.name, messe.location || "Messe-Demo", publicUrl(messe), "QR-Code scannen – alle Lichtmasten der Messe sehen, Lampen schalten und Testdurchsage abspielen.")}
          {devices.map(d => karte(d.id, d.name, `${messe.name}${messe.location ? ` · ${messe.location}` : ""}`, publicUrl(messe, d.id), "QR-Code scannen – Lampen schalten und Testdurchsage abspielen."))}
        </body>
      </html>
    );
    const w = window.open("", "_blank");
    if (!w) { toast.error("Popup blockiert – bitte erlauben"); return; }
    w.document.write("<!doctype html>" + html);
    w.document.close();
    setTimeout(() => { w.focus(); w.print(); }, 300);
  };

  const QrKarte = ({ url, titel, sub, testKey, hervor }) => (
    <div className={`rounded-xl p-3 flex gap-3 items-center border ${hervor ? "border-fuchsia-300 bg-fuchsia-50" : "border-gray-200"}`} data-testid={`messe-qr-${testKey}`}>
      <div className="bg-white p-1 rounded-lg border border-gray-100 shrink-0">
        <QRCodeSVG value={url} size={96} level="M" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate flex items-center gap-1"><QrCode className="w-3.5 h-3.5 text-fuchsia-500" /> {titel}</p>
        {sub && <p className="text-xs text-gray-500">{sub}</p>}
        <p className="text-[11px] text-gray-400 break-all line-clamp-2">{url}</p>
        <div className="flex gap-1 mt-2">
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => copy(url)} data-testid={`messe-qr-copy-${testKey}`}><Copy className="w-3.5 h-3.5 mr-1" /> Link</Button>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => window.open(url, "_blank")} data-testid={`messe-qr-open-${testKey}`}><ExternalLink className="w-3.5 h-3.5 mr-1" /> Öffnen</Button>
        </div>
      </div>
    </div>
  );

  return (
    <Karte titel="QR-Codes" testId="messe-qr"
      action={<Button size="sm" variant="outline" onClick={print} data-testid="messe-qr-print-btn"><Printer className="w-4 h-4 mr-1" /> Alle drucken</Button>}>
      <div className="grid gap-3">
        <QrKarte url={publicUrl(messe)} titel={`Messe: ${messe.name}`} sub="Zeigt alle verknüpften Lichtmasten und Durchsagen" testKey="messe" hervor />
        {devices.map(d => <QrKarte key={d.id} url={publicUrl(messe, d.id)} titel={d.name} sub="Direkt dieser Lichtmast" testKey={d.serial_number} />)}
      </div>
      {devices.length === 0 && <p className="text-xs text-gray-400 mt-3">Noch keine M-Box ausgewählt – der Messe-Code zeigt dann eine leere Mastliste.</p>}
    </Karte>
  );
}
