import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw, Wrench, Clock, Radio, Lightbulb, MapPin } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/button";
import api from "../lib/api";
import { useMBox } from "../components/mbox/useMBox";
import { mkHelpers } from "../components/mbox/mboxVars";
import { Hinweis, useConfirm } from "../components/mbox/MBoxUi";
import { UebersichtTab } from "../components/mbox/UebersichtTab";
import { AutomatikTab } from "../components/mbox/AutomatikTab";
import { AudioTab } from "../components/mbox/AudioTab";
import { UhrTab } from "../components/mbox/UhrTab";
import { MeldungenTab, ServiceTab, DiagnoseTab } from "../components/mbox/InfoTabs";
import { AudioPiTab } from "../components/mbox/AudioPiTab";

const TABS = [
  ["uebersicht", "Übersicht"], ["automatik", "Automatik"], ["audio", "Steckdosen & Audio"], ["uhr", "Zeitschaltuhr"],
  ["meldungen", "Meldungen & Protokoll"], ["service", "Service"], ["diagnose", "Diagnose"], ["durchsage", "Audio"],
];
// Kunden sehen nur Licht (Übersicht, eingeschränkt) und Audio-Durchsagen
const KUNDE_TABS = new Set(["uebersicht", "durchsage"]);

// GPS-Position vom Pi im Mast (gpsd, u-blox USB): nur ab mode >= 2 gueltig
function GpsAnzeige({ pi }) {
  const gps = pi?.gps;
  const st = pi?.gps_status;
  const alterMin = gps?.ts ? Math.round((Date.now() - new Date(gps.ts).getTime()) / 60000) : null;
  let text, farbe = "text-gray-400";
  if (!pi?.configured) text = "Pi nicht eingerichtet";
  else if (!pi.online && !gps) text = "Pi offline";
  else if (gps?.fix) {
    const acc = gps.epx != null && gps.epy != null ? Math.round(Math.max(gps.epx, gps.epy)) : null;
    text = `${gps.lat.toFixed(5)}, ${gps.lon.toFixed(5)} · ${gps.mode === 3 ? "3D" : "2D"}${gps.sats != null ? ` · ${gps.sats} Sat` : ""}${acc != null ? ` · ±${acc} m` : ""}${!pi.online && alterMin != null ? ` · vor ${alterMin} min` : ""}`;
    farbe = pi.online ? "text-emerald-700" : "text-gray-500";
  } else if (st && st.gpsd === false) { text = "gpsd läuft nicht"; farbe = "text-red-600"; }
  else { text = `kein GPS-Fix${st?.sats_visible != null ? ` · ${st.sats_visible} Sat sichtbar` : ""} (Suche…)`; farbe = "text-amber-600"; }
  return (
    <span className={`flex items-center gap-1 ${farbe}`} data-testid="mbox-gps">
      <MapPin className="w-3.5 h-3.5" /> GPS: <span className="font-mono" data-testid="mbox-gps-text">{text}</span>
      {gps?.fix && (
        <a href={`https://www.google.com/maps?q=${gps.lat},${gps.lon}`} target="_blank" rel="noreferrer" className="underline hover:text-fuchsia-600" data-testid="mbox-gps-map-link">Karte</a>
      )}
    </span>
  );
}

// Status-Pills im Stil der Generator-Detailseite (heller Hintergrund, Rand, Punkt)
const PILL = {
  ok: "bg-emerald-50 border-emerald-200 text-emerald-700",
  warn: "bg-amber-50 border-amber-200 text-amber-700",
  err: "bg-red-50 border-red-200 text-red-600",
  neutral: "bg-gray-50 border-gray-200 text-gray-500",
};
const DOT = { ok: "bg-emerald-500", warn: "bg-amber-400", err: "bg-red-500", neutral: "bg-gray-400" };

const Pill = ({ art = "neutral", children, title, testId, pulse }) => (
  <span title={title} data-testid={testId} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap ${PILL[art]}`}>
    <span className={`w-2 h-2 rounded-full ${DOT[art]} ${pulse ? "animate-pulse" : ""}`} />
    {children}
  </span>
);

export default function MBoxPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [seite, setSeite] = useState("uebersicht");
  const { W, verbindung, info, aktualisieren, post, befehl } = useMBox(id, seite);
  const h = useMemo(() => ({ ...mkHelpers(W), W }), [W]);
  const { confirm, dialog } = useConfirm();
  const level = info?.level || (isAdmin ? "admin" : "lesen");
  const kunde = level === "kunde";
  const darf = level === "admin" || level === "bedienen" || kunde;
  const { s, v } = h;

  const sz = s("Stoerung_Zustand"), fe = s("Fern_Erlaubt"), fm = (v("DB_HMI.Module.Aktiv") || [])[3];
  const hinweise = [];
  if (fm === false) hinweise.push(["warn", "Das Modul Fernzugriff ist nicht freigeschaltet. Befehle werden von der SPS ignoriert."]);
  else if (fe === false) hinweise.push(["warn", "Am Panel ist „Fernbedienung erlaubt“ aus. Befehle werden von der SPS ignoriert."]);
  if (s("Wartungsmodus")) hinweise.push(["warn", "Wartungsmodus aktiv: Fernbefehle und Generator sind gesperrt."]);
  if (sz === 2) hinweise.push(["err", "Eine Störung steht an, siehe Meldungen."]);
  if (!darf && level !== "none") hinweise.push(["warn", "Du hast nur Lese-Zugriff: Status ist sichtbar, Schalten ist gesperrt."]);
  if (kunde) hinweise.push(["info", "Sie können an diesem Lichtmast die Beleuchtung schalten und Durchsagen abspielen. Generator, Netz und Einstellungen betreut Eventenergie."]);
  if (info?.error) hinweise.push(["err", info.error]);
  if (info && info.service_installed === false) hinweise.push(["err", "Auf dem Server fehlen die Node-Abhängigkeiten des M-Box Dienstes (npm install in backend/mbox_service)."]);

  const restart = async () => {
    if (!(await confirm("M-Box Dienst dieses Masts neu starten? Die Verbindung zur SPS wird kurz unterbrochen."))) return;
    try { await api.post(`/mbox/${id}/restart`); toast.success("Dienst neu gestartet"); setTimeout(aktualisieren, 1500); }
    catch (e) { toast.error(e.response?.data?.detail || "Neustart fehlgeschlagen"); }
  };

  const name = info?.device?.user_field || info?.device?.serial_number || "M-Box";
  const tabProps = { h, befehl, post, aktualisieren, darf, isAdmin: level === "admin", confirm, kunde };
  const sichtbareTabs = TABS.filter(([k]) => (k !== "diagnose" || level === "admin") && (!kunde || KUNDE_TABS.has(k)));
  const spsZeit = (s("Datum_Text") || s("Uhrzeit_Text")) ? `${s("Datum_Text") || ""} ${s("Uhrzeit_Text") || ""}`.trim() : null;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="mbox-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate(kunde ? "/hub" : "/generators")} className="text-gray-600 hover:text-fuchsia-600 shrink-0" data-testid="mbox-back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-gray-900 tracking-tight truncate" data-testid="mbox-title">{name}</h1>
              <p className="text-xs text-gray-400 truncate">M-Box Lichtmast{info?.device?.serial_number && info.device.serial_number !== name ? ` · ${info.device.serial_number}` : ""}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Pill art={verbindung.ok ? "ok" : "err"} pulse={verbindung.ok} title={verbindung.detail} testId="mbox-pill-verbindung">{verbindung.ok ? "Online" : "Offline"}</Pill>
            {level === "admin" && (
              <Button variant="ghost" size="sm" onClick={restart} title="M-Box Dienst neu starten" className="text-gray-500 hover:text-fuchsia-600" data-testid="mbox-restart-btn"><Wrench className="w-4 h-4" /></Button>
            )}
            <Button variant="ghost" size="sm" onClick={aktualisieren} className="text-gray-500 hover:text-fuchsia-600" data-testid="mbox-refresh-btn"><RefreshCw className="w-4 h-4" /></Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      {!verbindung.ok && verbindung.detail && (
        <div className="bg-red-600 text-white px-4 py-2.5" data-testid="mbox-hinweis-verbindung">
          <div className="max-w-7xl mx-auto text-sm font-medium">{verbindung.text} – {verbindung.detail}</div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Info-Leiste + Zustands-Pills */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1"><Lightbulb className="w-3.5 h-3.5" /> M-Box Fernbedienung</span>
            <span className="flex items-center gap-1 font-mono"><Radio className="w-3.5 h-3.5" /> {info?.device?.mbox_endpoint || "…"}</span>
            <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> SPS-Zeit: <span data-testid="mbox-pill-zeit">{spsZeit || "–"}</span></span>
            <GpsAnzeige pi={info?.device?.pi} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill art={sz === 2 ? "err" : sz === 1 ? "warn" : "ok"} testId="mbox-pill-stoerung">{sz === 2 ? "Störung" : sz === 1 ? "Quittieren" : "keine Störung"}</Pill>
            <Pill art={fe && fm !== false ? "ok" : "warn"} testId="mbox-pill-fern">{fm === false ? "Modul Fernzugriff aus" : fe ? "Fernbedienung erlaubt" : "Fernbedienung gesperrt"}</Pill>
          </div>
        </div>

        {/* Reiter */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <nav className="flex gap-1 px-2 overflow-x-auto border-b border-gray-100" data-testid="mbox-tabs">
            {sichtbareTabs.map(([k, l]) => (
              <button key={k} type="button" onClick={() => setSeite(k)} data-testid={`mbox-tab-btn-${k}`}
                className={`px-3.5 py-3 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors ${seite === k ? "border-fuchsia-600 text-fuchsia-700 font-semibold" : "border-transparent text-gray-500 hover:text-gray-900"}`}>{l}</button>
            ))}
          </nav>
          <div className="p-4 sm:p-5 space-y-4 bg-gray-50/60">
            {hinweise.map(([a, t], i) => <Hinweis key={i} art={a} testId={`mbox-hinweis-${i}`}>{t}</Hinweis>)}
            {seite === "uebersicht" && <UebersichtTab {...tabProps} />}
            {seite === "automatik" && <AutomatikTab {...tabProps} />}
            {seite === "audio" && <AudioTab {...tabProps} />}
            {seite === "uhr" && <UhrTab {...tabProps} />}
            {seite === "meldungen" && <MeldungenTab {...tabProps} />}
            {seite === "service" && <ServiceTab {...tabProps} />}
            {seite === "diagnose" && level === "admin" && <DiagnoseTab {...tabProps} />}
            {seite === "durchsage" && <AudioPiTab deviceId={id} darf={darf} isAdmin={level === "admin"} kunde={kunde} />}
          </div>
        </div>
      </main>
      {dialog}
    </div>
  );
}
