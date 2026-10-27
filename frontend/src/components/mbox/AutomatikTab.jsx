import { useState } from "react";
import { toast } from "sonner";
import { Karte, Zeile, Tab, Btn, Fehlt } from "./MBoxUi";
import { SONDER, EINSTELLUNGEN, ja, zahl, text } from "./mboxVars";

export function AutomatikTab({ h, befehl, post, aktualisieren, darf, isAdmin }) {
  const { v, s, roh } = h;
  const [werte, setWerte] = useState({});
  const [gps, setGps] = useState({ breite: "53.55", laenge: "9.99", fix: true });
  const ba = s("Betriebsart");

  const einstellen = async (name) => {
    const raw = (werte[name] ?? "").trim();
    if (raw === "") return toast.error("Erst einen Wert eingeben.");
    const r = await post("einstellung", { name, wert: Number(raw.replace(",", ".")) });
    if (!r.ok) return toast.error(r.fehler);
    setWerte(p => ({ ...p, [name]: "" })); toast.success("gespeichert"); setTimeout(aktualisieren, 400);
  };
  const gpsSenden = async () => {
    const r = await post("gps", undefined, { breite: gps.breite.replace(",", "."), laenge: gps.laenge.replace(",", "."), fix: gps.fix ? "1" : "0" });
    r.ok ? toast.success("GPS gesendet") : toast.error(r.fehler);
  };

  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="mbox-tab-automatik">
      <Karte titel="Automatik-Quellen" action={
        <Btn variant={ba === 2 ? "an" : undefined} disabled={!darf || ba === 3} onClick={() => befehl("Auto_Umschalten")} testId="mbox-btn-auto">
          {ba === 2 ? "Automatik deaktivieren" : ba === 3 ? "Einrichten aktiv (nur vor Ort)" : "Automatik aktivieren"}
        </Btn>}>
        <p className="text-xs text-gray-500 mb-2">Wirken nur in Betriebsart Auto. Wer zuerst „an“ bzw. „aus“ sagt, schaltet. Nach SPS-Neustart sind alle Quellen abgewählt.</p>
        <div className="flex flex-wrap gap-2 mb-3">
          <Btn variant={s("Auto_Daemmerung") ? "an" : undefined} disabled={!darf} onClick={() => befehl("Auto_Daemmerung_Umschalten")} testId="mbox-btn-quelle-daemmerung">Dämmerung</Btn>
          <Btn variant={s("Auto_Uhr") ? "an" : undefined} disabled={!darf} onClick={() => befehl("Auto_Uhr_Umschalten")} testId="mbox-btn-quelle-uhr">Zeitschaltuhr</Btn>
          <Btn variant={s("Auto_Astro") ? "an" : undefined} disabled={!darf} onClick={() => befehl("Auto_Astro_Umschalten")} testId="mbox-btn-quelle-astro">Astro</Btn>
        </div>
        <Tab>
          <Zeile label="Betriebsart">{{ 1: "Hand", 2: "Auto", 3: "Einrichten" }[ba] ?? "–"}</Zeile>
          <Zeile label="Automatik verlangt Licht">{ja(s("Auto_Licht_Soll"))}</Zeile>
          <Zeile label="Dämmerung: dunkel erkannt">{ja(s("Dunkel"))} ({zahl(v("DB_HMI.Analog.Daemmerung"), 0)} Lux)</Zeile>
          <Zeile label="Datums-Schaltzeit übersteuert">{ja(s("Datum_Uebersteuert"))}</Zeile>
          <Zeile label="Uhrzeit gültig">{ja(s("Uhr_Gueltig"))}</Zeile>
        </Tab>
      </Karte>

      <Karte titel="Astro-Uhr">
        <Tab>
          <Zeile label="Sonnenaufgang / -untergang">{s("Astro_Aufgang") || "--:--"} / {s("Astro_Untergang") || "--:--"}</Zeile>
          <Zeile label="Licht ein / aus"><b>{s("Astro_Ein") || "--:--"} / {s("Astro_Aus") || "--:--"}</b></Zeile>
          <Zeile label="Astro sagt gerade">{s("Astro_An") === undefined ? "–" : s("Astro_An") ? "an" : "aus"}</Zeile>
          <Zeile label="Sonderfall">{text(SONDER, s("Astro_Sonderfall"))}</Zeile>
          <Zeile label="GPS">{s("GPS_Aktuell") ? "aktuell" : v("DB_Astro.Position_Gueltig") ? "letzte Position" : "keine Position"}</Zeile>
          <Zeile label="Position">{zahl(v("DB_Astro.Breite"), 4)} / {zahl(v("DB_Astro.Laenge"), 4)}<Fehlt roh={roh} name="DB_Astro.Breite" /></Zeile>
        </Tab>
        {isAdmin && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <h3 className="text-xs font-semibold text-gray-700 mb-2">GPS-Test (wie Raspberry Pi senden) – nur Admin</h3>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-gray-600">Breite <input className="ml-1 w-24 px-2 py-1 border border-gray-300 rounded text-sm" value={gps.breite} onChange={e => setGps(p => ({ ...p, breite: e.target.value }))} data-testid="mbox-gps-breite" /></label>
              <label className="text-xs text-gray-600">Länge <input className="ml-1 w-24 px-2 py-1 border border-gray-300 rounded text-sm" value={gps.laenge} onChange={e => setGps(p => ({ ...p, laenge: e.target.value }))} data-testid="mbox-gps-laenge" /></label>
              <label className="text-xs text-gray-600 flex items-center gap-1"><input type="checkbox" checked={gps.fix} onChange={e => setGps(p => ({ ...p, fix: e.target.checked }))} /> Fix</label>
              <Btn onClick={gpsSenden} testId="mbox-gps-senden">Senden</Btn>
            </div>
          </div>
        )}
      </Karte>

      <Karte titel="Einstellungen" className="md:col-span-2">
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-2 items-center">
          {EINSTELLUNGEN.map(e => {
            const x = v(e.name);
            return [
              <span key={e.name + "l"} className="text-sm text-gray-700">{e.label}</span>,
              <input key={e.name + "i"} type="number" min={e.min} max={e.max} value={werte[e.name] ?? ""} disabled={!darf}
                placeholder={typeof x === "number" ? String(Math.round(x * 10) / 10) : "?"}
                onChange={ev => setWerte(p => ({ ...p, [e.name]: ev.target.value }))}
                className="w-24 px-2 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50" data-testid={`mbox-einst-${e.name}`} />,
              <Btn key={e.name + "b"} disabled={!darf} onClick={() => einstellen(e.name)} testId={`mbox-einst-setzen-${e.name}`}>Setzen</Btn>,
            ];
          })}
        </div>
        <p className="text-xs text-gray-500 mt-2">Der graue Wert im Feld ist der aktuelle Wert. Schreiben geht nur bei „Fernbedienung erlaubt“.</p>
      </Karte>
    </div>
  );
}
