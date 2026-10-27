import { Karte, Zeile, Tab, Dot, Balken, Btn } from "./MBoxUi";
import { GEN, AKKU, ja, zahl, z2, text } from "./mboxVars";

export function UebersichtTab({ h, befehl, darf }) {
  const { v, s } = h;
  const lampen = v("DB_HMI.Status.Lampe") || [], ausw = v("DB_Parameter.Lampen_Auswahl") || [];
  const vs = s("Versorgung");
  const nEin = v("DB_Parameter.Netzueberwachung_Ein"), nModul = (v("DB_HMI.Module.Aktiv") || [])[2];
  const sek = ms => typeof ms === "number" ? (ms >= 60000 ? zahl(ms / 60000, ms % 60000 ? 1 : 0) + " min" : zahl(ms / 1000, 0) + " s") : "–";
  let zustand;
  if (nModul === false) zustand = <><Dot on={false} /> Modul nicht freigeschaltet</>;
  else if (!nEin) zustand = <><Dot on={false} /> aus</>;
  else if (s("Notbetrieb")) zustand = <><Dot on farbe="rot" /> Notbetrieb – Generator versorgt die Lampen</>;
  else if (vs !== 1) zustand = <><Dot on farbe="gelb" /> ein, aber nicht wirksam (nur im Netzbetrieb)</>;
  else zustand = <><Dot on /> überwacht</>;
  const fi = v("DB_HMI.Analog.Fuellstand_Intern"), fx = v("DB_HMI.Analog.Fuellstand_Extern");

  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="mbox-tab-uebersicht">
      <Karte titel="Licht">
        <div className="flex gap-2.5 mb-3">
          {[1, 2, 3, 4, 5].map(i => (
            <button key={i} type="button" disabled={!darf} title={`Lampe ${i}`} onClick={() => befehl("Lampe_Umschalten", i)}
              data-testid={`mbox-lampe-${i}`}
              className={`relative w-12 h-12 rounded-full border-2 font-semibold text-sm transition-colors disabled:opacity-50 ${lampen[i - 1] ? "bg-amber-300 border-amber-500 text-gray-900" : "bg-gray-100 border-gray-300 text-gray-600"}`}>
              {i}
              {ausw[i - 1] === false && <span className="absolute -right-0.5 -top-0.5 w-2.5 h-2.5 rounded-full bg-gray-400" />}
            </button>
          ))}
        </div>
        <Tab>
          <Zeile label="Licht zentral ein">{ja(s("Licht_Ein"))}</Zeile>
          <Zeile label="Alle an / alle aus">{ja(s("Lampen_Alle_An"))} / {ja(s("Lampen_Alle_Aus"))}</Zeile>
        </Tab>
        <div className="flex flex-wrap gap-2 mt-3">
          <Btn variant="haupt" disabled={!darf} onClick={() => befehl("Schnellstart")} testId="mbox-btn-schnellstart">Schnellstart</Btn>
          <Btn disabled={!darf} onClick={() => befehl("Schnellstop")} testId="mbox-btn-schnellstop">Schnellstop</Btn>
          <Btn disabled={!darf} onClick={() => befehl("Lampen_Ein")} testId="mbox-btn-lampen-ein">Lampen ein</Btn>
          <Btn disabled={!darf} onClick={() => befehl("Lampen_Aus")} testId="mbox-btn-lampen-aus">Lampen aus</Btn>
        </div>
        <p className="text-xs text-gray-500 mt-2">Lampe antippen = einzeln ein/aus. Schnellstart startet im Generatorbetrieb zuerst den Motor.</p>
      </Karte>

      <Karte titel="Versorgung & Generator">
        <Tab>
          <Zeile label="Versorgung">{{ 1: "Netz", 2: "Generator" }[vs] ?? "–"}</Zeile>
          <Zeile label="Netz liegt an"><Dot on={s("Netzwaechter")} /> {ja(s("Netzwaechter"))}</Zeile>
          <Zeile label="Generator">{text(GEN, s("Gen_Zustand"))}{v("DB_Parameter.Generator_Gesperrt") ? " (gesperrt)" : ""}</Zeile>
          <Zeile label="Netz- / Generatorschütz"><Dot on={s("Netzschuetz")} /> <Dot on={s("Generatorschuetz")} /></Zeile>
          <Zeile label="Batterieladung">{ja(s("Ladung_Aktiv"))}</Zeile>
          <Zeile label="Störabschaltung">{s("Abschaltung_Aktiv") ? <><Dot on farbe="rot" /> aktiv</> : "nein"}</Zeile>
          <Zeile label="Akkupack">{text(AKKU, s("Akku_Zustand"))}</Zeile>
          {s("Umschalten_Gesperrt") && <Zeile label="Hinweis">Netz/Generator nur umschaltbar, wenn Generator und Lampen aus</Zeile>}
        </Tab>
        <div className="flex flex-wrap gap-2 mt-3">
          <Btn variant={vs === 1 ? "an" : undefined} disabled={!darf} onClick={() => befehl("Netzbetrieb")} testId="mbox-btn-netzbetrieb">Netzbetrieb</Btn>
          <Btn variant={vs === 2 ? "an" : undefined} disabled={!darf} onClick={() => befehl("Generatorbetrieb")} testId="mbox-btn-generatorbetrieb">Generatorbetrieb</Btn>
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          <Btn disabled={!darf} onClick={() => befehl("Gen_Start")} testId="mbox-btn-gen-start">Generator start</Btn>
          <Btn disabled={!darf} onClick={() => befehl("Gen_Stop")} testId="mbox-btn-gen-stop">Generator stop</Btn>
        </div>
      </Karte>

      <Karte titel="Netzüberwachung" action={<Btn variant={nEin ? "an" : undefined} disabled={!darf} onClick={() => befehl("Netzueberwachung_Umschalten")} testId="mbox-btn-nub">{nEin ? "ausschalten" : "einschalten"}</Btn>}>
        <Tab>
          <Zeile label="Zustand">{zustand}</Zeile>
          <Zeile label="Netz liegt an"><Dot on={s("Netzwaechter")} /> {ja(s("Netzwaechter"))}</Zeile>
          {s("NUB_Rueckkehr_Laeuft") && <Zeile label="Netz wieder da">zurück in Wartestellung in {s("NUB_Rest_Min")}:{z2(s("NUB_Rest_Sek"))}</Zeile>}
          <Zeile label="Notbetrieb nach Netzausfall von">{sek(v("DB_Parameter.NUB_Ausfall_Verz"))}</Zeile>
          <Zeile label="Rückkehr nach Netz stabil für">{sek(v("DB_Parameter.NUB_Rueckkehr_Zeit"))}</Zeile>
        </Tab>
        <p className="text-xs text-gray-500 mt-2">Wirkt nur im Netzbetrieb: Fällt das Netz aus, startet der Generator und alle Lampen gehen an. Ist das Netz wieder stabil da, geht es nach der Rückkehrzeit zurück in Wartestellung.</p>
      </Karte>

      <Karte titel="Tank & Messwerte">
        <Tab>
          <Zeile label="Tank intern">{zahl(fi, 0)} %<Balken p={fi} warn={s("Tank_Niedrig")} err={s("Tank_Kritisch")} /></Zeile>
          {s("Tank_Extern_Angeschlossen")
            ? <Zeile label={"Tank extern" + (s("Tank_Extern_Aktiv") ? " (aktiv)" : "")}>{s("Tank_Extern_Plausibel") === false ? "unplausibel" : <>{zahl(fx, 0)} %<Balken p={fx} /></>}</Zeile>
            : <Zeile label="Tank extern">nicht angeschlossen</Zeile>}
          <Zeile label="Wind">{zahl(v("DB_HMI.Analog.Wind"))} m/s</Zeile>
          <Zeile label="Helligkeit">{zahl(v("DB_HMI.Analog.Daemmerung"), 0)} Lux</Zeile>
        </Tab>
      </Karte>
    </div>
  );
}
