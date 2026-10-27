import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Karte, Btn, Fehlt } from "./MBoxUi";
import { TAGE, z2 } from "./mboxVars";

const PAARE = [1, 2, 3, 4, 5, 6, 7];
const leer = () => PAARE.map(() => ({ aktivEin: false, ein: "00:00", aktivAus: false, aus: "00:00" }));

// Editor wird nur aus der SPS neu gefuellt, solange nichts geaendert wurde (wie im Original)
export function UhrTab({ h, post, aktualisieren, darf, confirm }) {
  const { v, roh } = h;
  const [tag, setTag] = useState(1);
  const [paare, setPaare] = useState(leer());
  const [geaendert, setGeaendert] = useState(false);
  const [kopieren, setKopieren] = useState(PAARE.map(() => false));
  const [neu, setNeu] = useState({ datum: "", zeit: "", ein: "1" });
  const editorRef = useRef(null);

  const ausSps = (d) => PAARE.map(p => {
    const b = `DB_Schaltuhr.Woche[${d},${p}].`;
    return { aktivEin: v(b + "Aktiv_Ein") === true, ein: `${z2(v(b + "Ein_Std"))}:${z2(v(b + "Ein_Min"))}`,
      aktivAus: v(b + "Aktiv_Aus") === true, aus: `${z2(v(b + "Aus_Std"))}:${z2(v(b + "Aus_Min"))}` };
  });
  useEffect(() => {
    if (!geaendert && !(editorRef.current && editorRef.current.contains(document.activeElement))) setPaare(ausSps(tag));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [h.W, tag, geaendert]);

  const tagWaehlen = async (d) => {
    if (geaendert && d !== tag && !(await confirm(`Änderungen für ${TAGE[tag - 1]} sind noch nicht gespeichert. Verwerfen?`))) return;
    setTag(d); setGeaendert(false);
  };
  const upd = (i, patch) => { setPaare(p => p.map((x, k) => k === i ? { ...x, ...patch } : x)); setGeaendert(true); };

  const speichern = async (ziel) => {
    const out = [];
    for (let i = 0; i < 7; i++) {
      const p = paare[i];
      if ((p.aktivEin && !p.ein) || (p.aktivAus && !p.aus)) return toast.error(`Paar ${i + 1}: Uhrzeit fehlt.`);
      const [einStd, einMin] = (p.ein || "00:00").split(":").map(Number), [ausStd, ausMin] = (p.aus || "00:00").split(":").map(Number);
      out.push({ aktivEin: p.aktivEin, einStd, einMin, aktivAus: p.aktivAus, ausStd, ausMin });
    }
    if (ziel === "auswahl" && !kopieren.some(Boolean)) return toast.error("Erst die Zieltage anhaken.");
    if (ziel === "alle" && !(await confirm(`Das Programm von ${TAGE[tag - 1]} auf ALLE 7 Tage übernehmen?`))) return;
    const r = await post("uhr/woche", { tag, paare: out, ziel, kopieren });
    if (!r.ok) return toast.error(r.fehler);
    toast.success(r.meldung || "gespeichert"); setGeaendert(false); setKopieren(PAARE.map(() => false)); setTimeout(aktualisieren, 300);
  };
  const datumHinzu = async () => {
    if (!neu.datum || !neu.zeit) return toast.error("Datum und Uhrzeit eingeben.");
    const [jahr, monat, tg] = neu.datum.split("-").map(Number), [std, min] = neu.zeit.split(":").map(Number);
    const r = await post("uhr/datum", { jahr, monat, tag: tg, std, min, einschalten: neu.ein === "1" });
    if (!r.ok) return toast.error(r.fehler);
    toast.success(r.meldung || "gespeichert"); setNeu({ datum: "", zeit: "", ein: "1" }); setTimeout(aktualisieren, 300);
  };
  const datumLoeschen = async (i, t) => {
    if (!(await confirm(`Datums-Schaltzeit ${t} löschen?`))) return;
    const r = await post("uhr/datum_loeschen", { index: i });
    if (!r.ok) return toast.error(r.fehler);
    toast.success(r.meldung || "gelöscht"); setTimeout(aktualisieren, 300);
  };

  const datumsListe = [];
  for (let i = 1; i <= 20; i++) {
    const b = `DB_Schaltuhr.Datum[${i}].`;
    if (!v(b + "Belegt")) continue;
    datumsListe.push({ i, ein: v(b + "Einschalten"), text: `${z2(v(b + "Tag"))}.${z2(v(b + "Monat"))}.${v(b + "Jahr")} ${z2(v(b + "Std"))}:${z2(v(b + "Min"))}` });
  }
  const inp = "px-2 py-1 border border-gray-300 rounded text-sm disabled:opacity-40";

  return (
    <div className="space-y-4" data-testid="mbox-tab-uhr">
      <div className="grid gap-4 md:grid-cols-2">
        <Karte titel="Wochenprogramm bearbeiten">
          <div className="flex flex-wrap gap-1.5 mb-3">
            {TAGE.map((t, i) => <Btn key={t} variant={tag === i + 1 ? "haupt" : undefined} onClick={() => tagWaehlen(i + 1)} testId={`mbox-uhr-tag-${i + 1}`}>{t}</Btn>)}
          </div>
          <table className="w-full text-sm" ref={editorRef}>
            <thead><tr className="text-left text-xs text-gray-500"><th className="py-1">Paar</th><th className="py-1">Einschalten</th><th className="py-1">Ausschalten</th></tr></thead>
            <tbody>{paare.map((p, i) => (
              <tr key={i} className="border-t border-gray-100">
                <td className="py-1.5 text-gray-600">{i + 1}</td>
                <td className="py-1.5 whitespace-nowrap">
                  <input type="checkbox" disabled={!darf} checked={p.aktivEin} onChange={e => upd(i, { aktivEin: e.target.checked })} data-testid={`mbox-uhr-ae-${i + 1}`} />{" "}
                  <input type="time" className={inp} disabled={!darf || !p.aktivEin} value={p.ein} onChange={e => upd(i, { ein: e.target.value })} data-testid={`mbox-uhr-e-${i + 1}`} />
                </td>
                <td className="py-1.5 whitespace-nowrap">
                  <input type="checkbox" disabled={!darf} checked={p.aktivAus} onChange={e => upd(i, { aktivAus: e.target.checked })} data-testid={`mbox-uhr-aa-${i + 1}`} />{" "}
                  <input type="time" className={inp} disabled={!darf || !p.aktivAus} value={p.aus} onChange={e => upd(i, { aus: e.target.value })} data-testid={`mbox-uhr-a-${i + 1}`} />
                </td>
              </tr>
            ))}</tbody>
          </table>
          <div className="flex flex-wrap gap-2 mt-3">
            <Btn variant="haupt" disabled={!darf} onClick={() => speichern("tag")} testId="mbox-uhr-speichern">Speichern für {TAGE[tag - 1]}{geaendert && <span className="ml-1 text-amber-300">●</span>}</Btn>
            <Btn disabled={!darf} onClick={() => speichern("alle")} testId="mbox-uhr-alle">Auf alle Tage</Btn>
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <Btn disabled={!darf} onClick={() => speichern("auswahl")} testId="mbox-uhr-auswahl">Auf ausgewählte Tage:</Btn>
            {TAGE.map((t, i) => (
              <label key={t} className="text-xs text-gray-700 flex items-center gap-1"><input type="checkbox" disabled={!darf} checked={kopieren[i]} onChange={e => setKopieren(k => k.map((x, j) => j === i ? e.target.checked : x))} data-testid={`mbox-uhr-kopie-${i + 1}`} />{t}</label>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">Jedes Paar hat einen Ein- und einen Aus-Schaltpunkt, beide einzeln abschaltbar. Liegt „Aus“ vor „Ein“, ist der Aus-Punkt am Folgetag. Es gilt immer der zuletzt erreichte Schaltpunkt.</p>
        </Karte>

        <Karte titel="Datums-Schaltzeiten">
          {datumsListe.length ? (
            <table className="w-full text-sm"><tbody>{datumsListe.map(d => (
              <tr key={d.i} className="border-b border-gray-100 last:border-0">
                <td className="py-1.5">{d.text}</td><td className="py-1.5">{d.ein ? "Ein" : "Aus"}</td>
                <td className="py-1.5 text-right">{darf && <button type="button" onClick={() => datumLoeschen(d.i, d.text)} className="text-xs px-2 py-0.5 border border-gray-300 rounded hover:bg-gray-50" data-testid={`mbox-uhr-datum-loeschen-${d.i}`}>Löschen</button>}</td>
              </tr>))}</tbody></table>
          ) : <p className="text-xs text-gray-500">keine Einträge<Fehlt roh={roh} name="DB_Schaltuhr.Datum[1].Belegt" /></p>}
          <h3 className="text-xs font-semibold text-gray-700 mt-4 mb-2">Neue Datums-Schaltzeit</h3>
          <div className="flex flex-wrap items-center gap-2">
            <input type="date" className={inp} disabled={!darf} value={neu.datum} onChange={e => setNeu(p => ({ ...p, datum: e.target.value }))} data-testid="mbox-uhr-neu-datum" />
            <input type="time" className={inp} disabled={!darf} value={neu.zeit} onChange={e => setNeu(p => ({ ...p, zeit: e.target.value }))} data-testid="mbox-uhr-neu-zeit" />
            <select className={inp} disabled={!darf} value={neu.ein} onChange={e => setNeu(p => ({ ...p, ein: e.target.value }))} data-testid="mbox-uhr-neu-art"><option value="1">Ein</option><option value="0">Aus</option></select>
            <Btn disabled={!darf} onClick={datumHinzu} testId="mbox-uhr-neu-hinzu">Hinzufügen</Btn>
          </div>
          <p className="text-xs text-gray-500 mt-2">Eine fällige Datums-Schaltzeit übersteuert das Wochenprogramm bis zum nächsten Schaltpunkt der Woche und wird danach automatisch gelöscht. Max. 20 Einträge.</p>
        </Karte>
      </div>

      <Karte titel="Wochenübersicht">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-gray-500"><th className="py-1 pr-2">Tag</th>{PAARE.map(p => <th key={p} className="py-1 pr-2">Paar {p}</th>)}</tr></thead>
            <tbody>{TAGE.map((t, di) => { const d = di + 1; return (
              <tr key={t} onClick={() => tagWaehlen(d)} className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${d === tag ? "bg-sky-50" : ""}`} data-testid={`mbox-woche-zeile-${d}`}>
                <td className="py-1.5 pr-2 font-medium text-gray-700">{t}</td>
                {PAARE.map(p => {
                  const b = `DB_Schaltuhr.Woche[${d},${p}].`, parts = [];
                  if (v(b + "Aktiv_Ein")) parts.push("Ein " + z2(v(b + "Ein_Std")) + ":" + z2(v(b + "Ein_Min")));
                  if (v(b + "Aktiv_Aus")) parts.push("Aus " + z2(v(b + "Aus_Std")) + ":" + z2(v(b + "Aus_Min")));
                  return <td key={p} className="py-1.5 pr-2 whitespace-nowrap text-gray-800">{roh(b + "Aktiv_Ein")?.fehler ? "?" : parts.length ? parts.map(x => <div key={x}>{x}</div>) : <span className="text-gray-400">–</span>}</td>;
                })}
              </tr>); })}</tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500 mt-2">Zeile antippen, um den Tag zu bearbeiten.</p>
      </Karte>
    </div>
  );
}
