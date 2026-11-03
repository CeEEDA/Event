import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { Karte, Tab, Zeile, Dot, Btn, Fehlt } from "./MBoxUi";
import { MELDUNGEN, codeText } from "./mboxTexte";
import { PROBE, MODULE, EXTRA, ja, z2, text } from "./mboxVars";

export function MeldungenTab({ h, befehl, darf }) {
  const { v, roh } = h;
  const w = v("DB_HMI.Alarm") || [], aktiv = [];
  for (let n = 0; n < 32; n++) if (((w[n >> 4] || 0) >> (n & 15)) & 1) aktiv.push(n);
  const zeilen = [];
  for (let i = 1; i <= 30; i++) {
    const b = `DB_Fern.Protokoll[${i}].`, code = v(b + "Code");
    if (!code) continue;
    const zt = n => v(b + "Zeit." + n);
    zeilen.push({ i, code, zeit: `${z2(zt("Tag"))}.${z2(zt("Monat"))}.${zt("Jahr")} ${z2(zt("Std"))}:${z2(zt("Min"))}:${z2(zt("Sek"))}` });
  }
  return (
    <div className="space-y-4" data-testid="mbox-tab-meldungen">
      <Karte titel="Anstehende Meldungen" action={<Btn variant="haupt" disabled={!darf} onClick={() => befehl("Quittieren")} testId="mbox-btn-quittieren">Quittieren</Btn>}>
        {aktiv.length ? (
          <ul className="divide-y divide-gray-100">
            {aktiv.map(n => { const m = MELDUNGEN[n] || ["I", "Meldung " + n, ""]; return (
              <li key={n} className="py-2 flex gap-3 items-start">
                <span className={`text-xs px-2 py-0.5 rounded-md font-medium shrink-0 ${m[0] === "S" ? "bg-red-100 text-red-800" : "bg-fuchsia-100 text-fuchsia-700"}`}>{m[0] === "S" ? "Störung" : "Info"}</span>
                <div><p className="text-sm font-medium text-gray-900">{m[1]}</p>{m[2] && <p className="text-xs text-gray-500">{m[2]}</p>}</div>
              </li>); })}
          </ul>
        ) : <p className="text-xs text-gray-500">keine Meldungen<Fehlt roh={roh} name="DB_HMI.Alarm" /></p>}
      </Karte>
      <Karte titel="Ereignisprotokoll (neueste 30)">
        {zeilen.length ? (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500"><th className="py-1 pr-3">Zeit</th><th className="py-1 pr-3">Ereignis</th><th className="py-1">Code</th></tr></thead>
            <tbody>{zeilen.map(z => (
              <tr key={z.i} className="border-t border-gray-100"><td className="py-1 pr-3 whitespace-nowrap text-gray-700">{z.zeit}</td><td className="py-1 pr-3">{codeText(z.code)}</td><td className="py-1 text-xs text-gray-400">{z.code}</td></tr>
            ))}</tbody>
          </table>
        ) : <p className="text-xs text-gray-500">keine Einträge<Fehlt roh={roh} name="DB_Fern.Protokoll[1].Code" /></p>}
      </Karte>
    </div>
  );
}

export function ServiceTab({ h, befehl, darf, isAdmin, confirm }) {
  const { v, s } = h;
  const z = n => v("DB_HMI.Zaehler." + n);
  const ak = v("DB_HMI.Module.Aktiv") || [], ab = v("DB_HMI.Module.Abgelaufen") || [], rt = v("DB_HMI.Module.Rest_Tage") || [];
  const sicher = async (name, frage) => { if (await confirm(frage)) befehl(name); };
  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="mbox-tab-service">
      <Karte titel="Zähler & Wartung">
        <Tab>
          <Zeile label="Betriebsstunden">{z("Betrieb_h") ?? "–"} h {z2(z("Betrieb_min"))} min</Zeile>
          <Zeile label="Nächste Wartung bei">{z("Wartung_Bei_h") ?? "–"} h (noch {z("Wartung_Rest_h") ?? "–"} h {z2(z("Wartung_Rest_min"))} min)</Zeile>
          <Zeile label="Wartung spätestens am">{z("Wartung_Datum_Jahr") ? `${z2(z("Wartung_Datum_Tag"))}.${z2(z("Wartung_Datum_Monat"))}.${z("Wartung_Datum_Jahr")} (noch ${z("Wartung_Rest_Tage")} Tage)` : "–"}</Zeile>
          <Zeile label="Wartung">{z("Wartung_Faellig") ? <><Dot on farbe="rot" /> fällig</> : z("Wartung_Vorwarnung") ? <><Dot on farbe="gelb" /> bald fällig</> : "ok"}</Zeile>
          <Zeile label="Kundenzähler">{z("Kunde_h") ?? "–"} h {z2(z("Kunde_min"))} min ({z("Kunde_Minuten_Gesamt") ?? "–"} min gesamt)</Zeile>
        </Tab>
        {isAdmin && (
          <div className="flex flex-wrap gap-2 mt-3">
            <Btn onClick={() => sicher("Wartung_Reset", "Wartung als erledigt quittieren?")} testId="mbox-btn-wartung-reset">Wartung erledigt</Btn>
            <Btn variant="gefahr" onClick={() => sicher("Kundenzaehler_Reset", "Kundenzähler wirklich auf 0 setzen?")} testId="mbox-btn-kundenzaehler-reset">Kundenzähler zurücksetzen</Btn>
          </div>
        )}
      </Karte>
      <Karte titel="Probelauf">
        <Tab>
          <Zeile label="Läuft gerade">{ja(s("Probelauf_Aktiv"))}</Zeile>
          <Zeile label="Letztes Ergebnis">{text(PROBE, s("Probelauf_Ergebnis"))}</Zeile>
        </Tab>
        {isAdmin && <div className="mt-3"><Btn onClick={() => sicher("Probelauf_Start", "Probelauf jetzt starten? Der Generator läuft an.")} testId="mbox-btn-probelauf">Probelauf starten</Btn></div>}
      </Karte>
      <Karte titel="Zusatzmodule">
        <Tab>{MODULE.map((m, i) => (
          <Zeile key={m} label={m}>{ak[i] ? <><Dot on /> aktiv{rt[i] > 0 ? ` (noch ${rt[i]} Tage)` : ""}</> : ab[i] ? <><Dot on farbe="rot" /> abgelaufen</> : <><Dot on={false} /> nicht gebucht</>}</Zeile>
        ))}</Tab>
      </Karte>
      <Karte titel="Anlage">
        <Tab>
          <Zeile label="Wartungsmodus">{ja(s("Wartungsmodus"))}</Zeile>
          <Zeile label="Generator gesperrt">{ja(v("DB_Parameter.Generator_Gesperrt"))}</Zeile>
          <Zeile label="Netzüberwachung ein">{ja(v("DB_Parameter.Netzueberwachung_Ein"))}</Zeile>
          <Zeile label="Mast Heben / Senken gesperrt">{ja(s("Mast_Heben_Gesperrt"))} / {ja(s("Mast_Senken_Gesperrt"))}</Zeile>
          <Zeile label="Verbindung erkannt (SPS)">{ja(s("Fern_Verbunden"))}</Zeile>
          <Zeile label="Lebenszeichen SPS">{s("Lebenszeichen") ?? "–"}</Zeile>
        </Tab>
      </Karte>
    </div>
  );
}

// Dienst-Log des Node/OPC-UA-Prozesses (Admin): zeigt, warum der Dienst nicht startet / nicht verbindet
function DienstLog({ deviceId }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const preRef = useRef(null);
  const lade = useCallback(() => api.get(`/mbox/${deviceId}/log?lines=80`).then(r => setD(r.data)).catch(() => {}), [deviceId]);
  useEffect(() => { lade(); const t = setInterval(lade, 10000); return () => clearInterval(t); }, [lade]);
  useEffect(() => { if (preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight; }, [d]);
  const neustart = async () => {
    setBusy(true);
    try { await api.post(`/mbox/${deviceId}/restart`); toast.success("Dienst neu gestartet"); setTimeout(lade, 2500); }
    catch (e) { toast.error(e.response?.data?.detail || "Neustart fehlgeschlagen"); }
    finally { setBusy(false); }
  };
  const rt = d?.runtime, svc = d?.service;
  const stuerztAb = rt && !rt.running && (rt.restarts >= 2 || rt.exit_code != null);
  return (
    <Karte titel="M-Box Dienst (Node / OPC UA) auf dem Server" testId="mbox-dienst-log"
      action={<div className="flex gap-2"><Btn onClick={lade} testId="mbox-dienst-log-refresh">Aktualisieren</Btn><Btn onClick={neustart} disabled={busy} testId="mbox-dienst-restart">Dienst neu starten</Btn></div>}>
      {rt && (
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-600 mb-3" data-testid="mbox-dienst-runtime">
          <span>Status: <b className={rt.running ? "text-emerald-700" : "text-red-700"}>{rt.running ? `läuft (PID ${rt.pid})` : "gestoppt"}</b></span>
          <span>Neustarts: <b>{rt.restarts}</b></span>
          {rt.exit_code != null && <span>Exit-Code: <b className="text-red-700">{rt.exit_code}</b></span>}
          <span>Port: {rt.port}</span>
          {svc && <span>Node: <b className={svc.node_version_ok === false ? "text-red-700" : ""}>{svc.node_version || "nicht gefunden"}</b>{svc.node_version_ok === false && <> – benötigt {svc.node_required}</>}</span>}
        </div>
      )}
      {stuerztAb && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2 mb-3" data-testid="mbox-dienst-crash">
          Der Dienst beendet sich direkt nach dem Start{rt.last_error ? `: ${rt.last_error}` : ""}. Die Ursache steht in den letzten Log-Zeilen unten
          {svc?.node_version_ok === false ? ` – Node ${svc.node_version} ist zu alt, node-opcua braucht ${svc.node_required}: Node.js 22 LTS installieren (winget install OpenJS.NodeJS.LTS) und Backend-Dienst neu starten.` : "."}
        </p>
      )}
      <pre ref={preRef} className="text-[11px] leading-relaxed bg-gray-950 text-gray-100 rounded-lg p-3 max-h-80 overflow-auto whitespace-pre-wrap break-all" data-testid="mbox-dienst-log-text">
        {d ? (d.lines?.length ? d.lines.join("\n") : `Noch kein Log (${d.log_path || "–"})`) : "Lade…"}
      </pre>
    </Karte>
  );
}

export function DiagnoseTab({ h, deviceId }) {
  const { v } = h;
  return (
    <div className="space-y-6">
      <DienstLog deviceId={deviceId} />
      <Karte titel="Eingänge, Ausgänge, Rohwerte" testId="mbox-tab-diagnose">
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-x-4 gap-y-1 text-sm">
          {EXTRA.diagnose.map(n => { const x = v(n); return (
            <div key={n} className="text-gray-700">{typeof x === "number" ? <b className="mr-1">{x}</b> : <Dot on={x} />}{n.replace("DB_HMI.IO.", "")}</div>
          ); })}
        </div>
      </Karte>
    </div>
  );
}
