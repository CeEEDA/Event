import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw, Lightbulb, Wrench } from "lucide-react";
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

const TABS = [
  ["uebersicht", "Übersicht"], ["automatik", "Automatik"], ["audio", "Steckdosen & Audio"], ["uhr", "Zeitschaltuhr"],
  ["meldungen", "Meldungen & Protokoll"], ["service", "Service"], ["diagnose", "Diagnose"],
];

const Pill = ({ art, children, title, testId }) => (
  <span title={title} data-testid={testId} className={`px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${{ ok: "bg-emerald-600 text-white", warn: "bg-amber-500 text-white", err: "bg-red-600 text-white" }[art] || "bg-white/15 text-white"}`}>{children}</span>
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
  const darf = level === "admin" || level === "bedienen";
  const { s, v } = h;

  const sz = s("Stoerung_Zustand"), fe = s("Fern_Erlaubt"), fm = (v("DB_HMI.Module.Aktiv") || [])[3];
  const hinweise = [];
  if (fm === false) hinweise.push(["warn", "Das Modul Fernzugriff ist nicht freigeschaltet. Befehle werden von der SPS ignoriert."]);
  else if (fe === false) hinweise.push(["warn", "Am Panel ist „Fernbedienung erlaubt“ aus. Befehle werden von der SPS ignoriert."]);
  if (s("Wartungsmodus")) hinweise.push(["warn", "Wartungsmodus aktiv: Fernbefehle und Generator sind gesperrt."]);
  if (sz === 2) hinweise.push(["err", "Eine Störung steht an, siehe Meldungen."]);
  if (!darf && level !== "none") hinweise.push(["warn", "Du hast nur Lese-Zugriff: Status ist sichtbar, Schalten ist gesperrt."]);
  if (info?.error) hinweise.push(["err", info.error]);
  if (info && info.service_installed === false) hinweise.push(["err", "Auf dem Server fehlen die Node-Abhängigkeiten des M-Box Dienstes (npm install in backend/mbox_service)."]);

  const restart = async () => {
    if (!(await confirm("M-Box Dienst dieses Masts neu starten? Die Verbindung zur SPS wird kurz unterbrochen."))) return;
    try { await api.post(`/mbox/${id}/restart`); toast.success("Dienst neu gestartet"); setTimeout(aktualisieren, 1500); }
    catch (e) { toast.error(e.response?.data?.detail || "Neustart fehlgeschlagen"); }
  };

  const name = info?.device?.user_field || info?.device?.serial_number || "M-Box";
  const tabProps = { h, befehl, post, aktualisieren, darf, isAdmin: level === "admin", confirm };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="mbox-page">
      <header className="bg-sky-900 text-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate("/generators")} className="text-white/80 hover:text-white hover:bg-white/10" data-testid="mbox-back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <Lightbulb className="w-5 h-5 text-amber-300 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-base font-semibold truncate" data-testid="mbox-title">{name}</h1>
              <p className="text-[11px] text-white/60 truncate">M-Box Fernbedienung · {info?.device?.mbox_endpoint || "…"}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-sm">
            <Pill testId="mbox-pill-zeit">{(s("Datum_Text") || "") + " " + (s("Uhrzeit_Text") || "--:--")}</Pill>
            <Pill art={sz === 2 ? "err" : sz === 1 ? "warn" : "ok"} testId="mbox-pill-stoerung">{sz === 2 ? "Störung" : sz === 1 ? "Quittieren" : "keine Störung"}</Pill>
            <Pill art={fe && fm !== false ? "ok" : "warn"} testId="mbox-pill-fern">{fm === false ? "Modul Fernzugriff aus" : fe ? "Fernbedienung erlaubt" : "Fernbedienung gesperrt"}</Pill>
            <Pill art={verbindung.ok ? "ok" : "err"} title={verbindung.detail} testId="mbox-pill-verbindung">{verbindung.text}</Pill>
            {level === "admin" && (
              <Button variant="ghost" size="sm" onClick={restart} title="Dienst neu starten" className="text-white/80 hover:text-white hover:bg-white/10" data-testid="mbox-restart-btn"><Wrench className="w-4 h-4" /></Button>
            )}
            <Button variant="ghost" size="sm" onClick={aktualisieren} className="text-white/80 hover:text-white hover:bg-white/10" data-testid="mbox-refresh-btn"><RefreshCw className="w-4 h-4" /></Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {TABS.filter(([k]) => k !== "diagnose" || level === "admin").map(([k, l]) => (
            <button key={k} type="button" onClick={() => setSeite(k)} data-testid={`mbox-tab-btn-${k}`}
              className={`px-3.5 py-2.5 text-sm whitespace-nowrap border-b-2 transition-colors ${seite === k ? "border-sky-800 text-sky-900 font-semibold" : "border-transparent text-gray-500 hover:text-gray-800"}`}>{l}</button>
          ))}
        </div>
      </nav>

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-4 space-y-4">
        {!verbindung.ok && verbindung.detail && <Hinweis art="err" testId="mbox-hinweis-verbindung">{verbindung.detail}</Hinweis>}
        {hinweise.map(([a, t], i) => <Hinweis key={i} art={a} testId={`mbox-hinweis-${i}`}>{t}</Hinweis>)}
        {seite === "uebersicht" && <UebersichtTab {...tabProps} />}
        {seite === "automatik" && <AutomatikTab {...tabProps} />}
        {seite === "audio" && <AudioTab {...tabProps} />}
        {seite === "uhr" && <UhrTab {...tabProps} />}
        {seite === "meldungen" && <MeldungenTab {...tabProps} />}
        {seite === "service" && <ServiceTab {...tabProps} />}
        {seite === "diagnose" && level === "admin" && <DiagnoseTab {...tabProps} />}
      </main>
      {dialog}
    </div>
  );
}
