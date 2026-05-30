import { useState, useRef } from "react";
import { X, ClipboardCheck, Plus, Trash2, MapPin } from "lucide-react";
import { Button } from "./ui/button";
import api from "../lib/api";
import { toast } from "sonner";
import VerteilerPickerDialog from "./VerteilerPickerDialog";

const BESICHTIGEN_PUNKTE = [
  ["betriebsmittel", "Auswahl der Betriebsmittel"],
  ["kennzeichnung_stromkreise", "Kennzeichnung Stromkreise"],
  ["zugaenglichkeit", "Zugänglichkeit der Betriebsmittel"],
  ["trennschaltgeraete", "Trenn- und Schaltgeräte"],
  ["kennzeichnung_n_pe", "Kennzeichnung N- und PE-Leiter"],
  ["brandabschottungen", "Brandabschottungen"],
  ["leiterverbindungen", "Leiterverbindungen"],
  ["gebaeudesystemtechnik", "Gebäudesystemtechnik"],
  ["schutz_ueberwachung", "Schutz- und Überwachungsgeräte"],
  ["hauptpotenzialausgleich", "Hauptpotenzialausgleich"],
  ["kabel_leitungen", "Kabel, Leitungen und Stromschienen"],
  ["zus_oertl_pa", "Zus. örtl. Potenzialausgleich"],
  ["schutz_direkt_beruehren", "Schutz gegen direktes Berühren"],
  ["dokumentation", "Dokumentation / Warnhinweise"],
];

const ERPROBEN_PUNKTE = [
  ["funktion_anlage", "Funktion der Anlage"],
  ["rechtsdrehfeld", "Rechtsdrehfeld Drehstromsteckdosen"],
  ["schutz_funktion", "Funktion Schutz-/Überwachungseinrichtungen"],
  ["motoren_drehrichtung", "Drehrichtung der Motoren"],
  ["gebaeudesystemtechnik", "Gebäudesystemtechnik"],
];

const PA_PUNKTE = [
  ["fundamenterder", "Fundamenterder"],
  ["pas_schiene", "PA-Schiene"],
  ["wasser_hauptltg", "Hauptwasserleitung"],
  ["hauptschutzleiter", "Hauptschutzleiter"],
  ["gas", "Gasinnenleitung"],
  ["heizung", "Heizung"],
  ["klima", "Klimaanlage"],
  ["aufzug", "Aufzugsanlage"],
  ["edv", "EDV-Anlage"],
  ["telefon", "Telefonanlage"],
  ["blitzschutz", "Blitzschutzanlage"],
  ["antenne", "Antennenanlage/BK"],
  ["gebaeude", "Gebäudekonstruktion"],
  ["wasser_zwischenzaehler", "Wasserzwischenzähler"],
];

const emptyMessung = () => ({ ziel: "", kabel: "", in_a: "", ik_a: "", zs_ohm: "", riso_ohne: "", rcd_ma: "", ta_ms: "", rpe_ohm: "" });

export default function MessprotokollDialog({ order, onClose, onSaved, existing = null, prefillVerteiler = null }) {
  const isEdit = !!existing;
  const initialForm = existing?.data || {
    auftraggeber: order?.contact_name || order?.event || "",
    kunden_nr: order?.customer_no || "",
    anlage: order?.event || order?.contact_name || "",
    auftrags_nr: order?.order_no || "",
    auftragnehmer: "Eventenergie Deutschland GmbH & Co. KG",
    verteiler_nr: prefillVerteiler?.label || "",
    verteiler_asset_id: prefillVerteiler?.id || undefined,
    verteiler_plus_code: prefillVerteiler?.plus_code || undefined,
    verteiler_lat: prefillVerteiler?.latitude ?? undefined,
    verteiler_lng: prefillVerteiler?.longitude ?? undefined,
    normen: { din_vde_0100_600: true, din_vde_0105: false, dguv_v3: true },
    pruefart: { neuanlage: false, erweiterung: false, aenderung: false, instandsetzung: false, wiederholung: true },
    netz_volt: "400",
    netz_hz: "50",
    netzsystem: "TN-S",
    besichtigen: Object.fromEntries(BESICHTIGEN_PUNKTE.map(([k]) => [k, "iO"])),
    erproben: Object.fromEntries(ERPROBEN_PUNKTE.map(([k]) => [k, "iO"])),
    messungen: Array.from({ length: 20 }, () => emptyMessung()),
    potenzialausgleich: Object.fromEntries(PA_PUNKTE.map(([k]) => [k, false])),
    erdungswiderstand: "",
    messgeraete: [{ fabrikat: "", typ: "" }],
    ergebnis: { keine_maengel: true, maengel: false, plakette: "ja", bemerkungen: "", naechster_termin_monat: "", naechster_termin_jahr: "" },
  };

  const [tab, setTab] = useState("kopf");
  const [saving, setSaving] = useState(false);
  const [showVerteilerPicker, setShowVerteilerPicker] = useState(false);
  const dirtyRef = useRef(false);

  const [form, setForm] = useState(initialForm);

  const setField = (path, value) => {
    dirtyRef.current = true;
    setForm((f) => {
      const next = { ...f };
      const keys = path.split(".");
      let ref = next;
      for (let i = 0; i < keys.length - 1; i++) {
        ref[keys[i]] = { ...ref[keys[i]] };
        ref = ref[keys[i]];
      }
      ref[keys[keys.length - 1]] = value;
      return next;
    });
  };

  const updateMessung = (idx, key, value) => {
    dirtyRef.current = true;
    setForm((f) => {
      const arr = [...f.messungen];
      arr[idx] = { ...arr[idx], [key]: value };
      return { ...f, messungen: arr };
    });
  };

  // Beim Schließen: Falls Eingaben gemacht wurden, vorher fragen ob speichern
  const requestClose = () => {
    if (!dirtyRef.current) {
      onClose?.();
      return;
    }
    const choice = window.confirm(
      "Du hast Eingaben gemacht. Möchtest du das Messprotokoll jetzt speichern?\n\n" +
      "OK = Speichern\nAbbrechen = Verwerfen & schließen"
    );
    if (choice) {
      save();
    } else {
      onClose?.();
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const orderPk = order.primary_key || order.id || order.order_pk;
      if (isEdit) {
        const res = await api.put(`/orders/messprotokoll/${orderPk}/${existing.id}`, form);
        toast.success(`Messprotokoll ${res.data.protokoll_nr} aktualisiert`);
      } else {
        const res = await api.post(`/orders/messprotokoll/${orderPk}`, form);
        toast.success(`Messprotokoll ${res.data.protokoll_nr} erstellt`);
      }
      onSaved?.();
      onClose?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  const TABS = [
    { key: "kopf", label: "Kopfdaten" },
    { key: "besichtigen", label: "Besichtigen" },
    { key: "erproben", label: "Erproben" },
    { key: "messen", label: "Messen (20 Kreise)" },
    { key: "pa", label: "Potenzialausgleich" },
    { key: "geraete", label: "Messgeräte" },
    { key: "ergebnis", label: "Ergebnis" },
  ];

  const ioRow = (obj, key, label, onChange) => (
    <div key={key} className="flex items-center justify-between py-1.5 border-b border-gray-100">
      <span className="text-sm text-gray-700">{label}</span>
      <div className="flex gap-1" data-testid={`mp-io-${key}`}>
        {["iO", "niO", "na"].map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => onChange(key, v)}
            className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
              obj[key] === v
                ? v === "iO" ? "bg-emerald-500 text-white border-emerald-500"
                  : v === "niO" ? "bg-red-500 text-white border-red-500"
                  : "bg-gray-400 text-white border-gray-400"
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
            }`}
          >
            {v === "iO" ? "i.O." : v === "niO" ? "n.i.O." : "n/a"}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" data-testid="messprotokoll-dialog">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl max-h-[95vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-violet-600" />
            <h2 className="text-base font-bold text-gray-900">{isEdit ? "Messprotokoll bearbeiten" : "Neues Messprotokoll"}</h2>
            <span className="text-xs text-gray-400">{isEdit ? `Nr. ${existing.protokoll_nr || ""}` : `Auftrag ${order?.order_no || ""}`}</span>
          </div>
          <button onClick={requestClose} className="p-1.5 hover:bg-gray-100 rounded-md" data-testid="mp-close">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-5 pt-3 border-b border-gray-200 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-2 text-xs font-medium rounded-t-md transition-colors whitespace-nowrap ${
                tab === t.key ? "bg-violet-50 text-violet-700 border-b-2 border-violet-600" : "text-gray-500 hover:text-gray-700"
              }`}
              data-testid={`mp-tab-${t.key}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {tab === "kopf" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <L label="Auftraggeber"><I value={form.auftraggeber} onChange={(v) => setField("auftraggeber", v)} /></L>
              <L label="Auftragnehmer"><I value={form.auftragnehmer} onChange={(v) => setField("auftragnehmer", v)} /></L>
              <L label="Kunden-Nr."><I value={form.kunden_nr} onChange={(v) => setField("kunden_nr", v)} /></L>
              <L label="Auftrags-Nr."><I value={form.auftrags_nr} onChange={(v) => setField("auftrags_nr", v)} /></L>
              <L label="Anlage / Objekt" cols={2}><I value={form.anlage} onChange={(v) => setField("anlage", v)} /></L>
              <L label="Netz (V)"><I value={form.netz_volt} onChange={(v) => setField("netz_volt", v)} /></L>
              <L label="Frequenz (Hz)"><I value={form.netz_hz} onChange={(v) => setField("netz_hz", v)} /></L>
              <L label="Netzsystem" cols={2}>
                <div className="flex gap-2 flex-wrap">
                  {["TN-C", "TN-S", "TN-C-S", "TT", "IT"].map((v) => (
                    <button key={v} type="button" onClick={() => setField("netzsystem", v)}
                      className={`px-3 py-1.5 rounded-md text-sm border ${form.netzsystem === v ? "bg-violet-600 text-white border-violet-600" : "bg-white text-gray-700 border-gray-200"}`}>
                      {v}
                    </button>
                  ))}
                </div>
              </L>
              <L label="Prüfung nach" cols={2}>
                <div className="flex gap-4 flex-wrap">
                  {[["din_vde_0100_600", "DIN VDE 0100-600"], ["din_vde_0105", "DIN VDE 0105"], ["dguv_v3", "DGUV V3"]].map(([k, lbl]) => (
                    <label key={k} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                      <input type="checkbox" checked={!!form.normen[k]} onChange={(e) => setField(`normen.${k}`, e.target.checked)} className="w-4 h-4" />
                      {lbl}
                    </label>
                  ))}
                </div>
              </L>
              <L label="Prüfart" cols={2}>
                <div className="flex gap-4 flex-wrap">
                  {[["neuanlage", "Neuanlage"], ["erweiterung", "Erweiterung"], ["aenderung", "Änderung"], ["instandsetzung", "Instandsetzung"], ["wiederholung", "Wiederholung"]].map(([k, lbl]) => (
                    <label key={k} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                      <input type="checkbox" checked={!!form.pruefart[k]} onChange={(e) => setField(`pruefart.${k}`, e.target.checked)} className="w-4 h-4" />
                      {lbl}
                    </label>
                  ))}
                </div>
              </L>
              <L label="Stromkreisverteiler-Nr." cols={2}>
                <div className="flex items-center gap-2">
                  <I value={form.verteiler_nr} onChange={(v) => setField("verteiler_nr", v)} />
                  <button
                    type="button"
                    onClick={() => setShowVerteilerPicker(true)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100 transition-colors text-xs font-medium whitespace-nowrap"
                    title="Verteiler aus der Karte des Auftrags auswählen"
                    data-testid="link-verteiler-btn"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    Auf Karte
                  </button>
                </div>
                {form.verteiler_asset_id && form.verteiler_plus_code && (
                  <p className="text-[10px] text-orange-600 mt-1">
                    🔗 Verknüpft mit Asset · Plus Code: {form.verteiler_plus_code}
                  </p>
                )}
              </L>
            </div>
          )}

          {tab === "besichtigen" && (
            <div>{BESICHTIGEN_PUNKTE.map(([k, lbl]) => ioRow(form.besichtigen, k, lbl, (key, val) => setField(`besichtigen.${key}`, val)))}</div>
          )}

          {tab === "erproben" && (
            <div>{ERPROBEN_PUNKTE.map(([k, lbl]) => ioRow(form.erproben, k, lbl, (key, val) => setField(`erproben.${key}`, val)))}</div>
          )}

          {tab === "messen" && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 sticky top-0">
                  <tr className="text-left text-gray-600">
                    <th className="px-1 py-2 w-8">Nr</th>
                    <th className="px-1 py-2">Zielbezeichnung</th>
                    <th className="px-1 py-2 w-24">Kabel</th>
                    <th className="px-1 py-2 w-16">I_n (A)</th>
                    <th className="px-1 py-2 w-16">I_k (A)</th>
                    <th className="px-1 py-2 w-16">Z_S (Ω)</th>
                    <th className="px-1 py-2 w-16">R_iso (MΩ)</th>
                    <th className="px-1 py-2 w-16">RCD I_n</th>
                    <th className="px-1 py-2 w-16">t_a (ms)</th>
                    <th className="px-1 py-2 w-16">R_PE (Ω)</th>
                  </tr>
                </thead>
                <tbody>
                  {form.messungen.map((m, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="px-1 py-1 text-center text-gray-500 font-mono">{i + 1}</td>
                      {["ziel", "kabel", "in_a", "ik_a", "zs_ohm", "riso_ohne", "rcd_ma", "ta_ms", "rpe_ohm"].map((k) => (
                        <td key={k} className="px-0.5 py-0.5">
                          <input
                            value={m[k] || ""}
                            onChange={(e) => updateMessung(i, k, e.target.value)}
                            className="w-full px-1.5 py-1 text-xs border border-transparent hover:border-gray-200 focus:border-violet-400 focus:ring-1 focus:ring-violet-200 rounded-md outline-none"
                            data-testid={`mp-mess-${i}-${k}`}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === "pa" && (
            <div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
                {PA_PUNKTE.map(([k, lbl]) => (
                  <label key={k} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer px-3 py-2 border border-gray-200 rounded-md hover:bg-gray-50">
                    <input type="checkbox" checked={!!form.potenzialausgleich[k]} onChange={(e) => setField(`potenzialausgleich.${k}`, e.target.checked)} className="w-4 h-4" />
                    {lbl}
                  </label>
                ))}
              </div>
              <L label="Erdungswiderstand R_E (Ω)"><I value={form.erdungswiderstand} onChange={(v) => setField("erdungswiderstand", v)} /></L>
            </div>
          )}

          {tab === "geraete" && (
            <div className="space-y-4">
              {form.messgeraete.map((g, i) => {
                const presets = [
                  { label: "Fluke 1664 FC", fabrikat: "Fluke", typ: "1664 FC" },
                  { label: "Gossen Profitest Mxtra", fabrikat: "Gossen Metrawatt", typ: "Profitest Mxtra" },
                ];
                const selectedIdx = presets.findIndex(p => p.fabrikat === g.fabrikat && p.typ === g.typ);
                const onPresetChange = (val) => {
                  const arr = [...form.messgeraete];
                  if (val === "") {
                    arr[i] = { ...arr[i], fabrikat: "", typ: "" };
                  } else {
                    const p = presets[Number(val)];
                    arr[i] = { ...arr[i], fabrikat: p.fabrikat, typ: p.typ };
                  }
                  setField("messgeraete", arr);
                };
                return (
                  <div key={i} className="border border-gray-200 rounded-lg p-4">
                    <h4 className="text-sm font-semibold mb-3">Messgerät {i + 1}</h4>
                    <L label="Gerät auswählen" cols={2}>
                      <select
                        value={selectedIdx >= 0 ? String(selectedIdx) : ""}
                        onChange={(e) => onPresetChange(e.target.value)}
                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:border-violet-400 focus:ring-1 focus:ring-violet-200 outline-none bg-white"
                        data-testid={`mp-geraet-${i}-preset`}
                      >
                        <option value="">— Bitte wählen —</option>
                        {presets.map((p, pi) => (
                          <option key={pi} value={String(pi)}>{p.label}</option>
                        ))}
                      </select>
                    </L>
                    <div className="grid grid-cols-2 gap-4 mt-3">
                      <L label="Fabrikat">
                        <I value={g.fabrikat} onChange={(v) => { const arr = [...form.messgeraete]; arr[i] = { ...arr[i], fabrikat: v }; setField("messgeraete", arr); }} />
                      </L>
                      <L label="Typ">
                        <I value={g.typ} onChange={(v) => { const arr = [...form.messgeraete]; arr[i] = { ...arr[i], typ: v }; setField("messgeraete", arr); }} />
                      </L>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {tab === "ergebnis" && (
            <div className="space-y-4">
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="maengel" checked={form.ergebnis.keine_maengel} onChange={() => { setField("ergebnis.keine_maengel", true); setField("ergebnis.maengel", false); }} />
                  <span className="text-emerald-700 font-medium">keine Mängel festgestellt</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="maengel" checked={form.ergebnis.maengel} onChange={() => { setField("ergebnis.keine_maengel", false); setField("ergebnis.maengel", true); }} />
                  <span className="text-red-700 font-medium">Mängel festgestellt</span>
                </label>
              </div>
              <div className="flex gap-4 items-center">
                <span className="text-sm text-gray-700">Prüfplakette erteilt:</span>
                {["ja", "nein"].map((v) => (
                  <label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <input type="radio" name="plakette" checked={form.ergebnis.plakette === v} onChange={() => setField("ergebnis.plakette", v)} />
                    {v}
                  </label>
                ))}
              </div>
              <L label="Mängel / Bemerkungen">
                <textarea value={form.ergebnis.bemerkungen} onChange={(e) => setField("ergebnis.bemerkungen", e.target.value)}
                  rows={5} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:border-violet-400 focus:ring-1 focus:ring-violet-200 outline-none"
                  data-testid="mp-bemerkungen" />
              </L>
              <div className="grid grid-cols-2 gap-4">
                <L label="Nächster Prüftermin – Monat"><I value={form.ergebnis.naechster_termin_monat} onChange={(v) => setField("ergebnis.naechster_termin_monat", v)} placeholder="MM" /></L>
                <L label="Nächster Prüftermin – Jahr"><I value={form.ergebnis.naechster_termin_jahr} onChange={(v) => setField("ergebnis.naechster_termin_jahr", v)} placeholder="JJJJ" /></L>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 bg-gray-50">
          <span className="text-xs text-gray-500">Protokoll-Nr. wird automatisch vergeben · Prüfer wird aus Benutzeranmeldung übernommen</span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={requestClose} data-testid="mp-cancel">Abbrechen</Button>
            <Button onClick={save} disabled={saving} className="bg-violet-600 hover:bg-violet-700 text-white" data-testid="mp-save">
              {saving ? "Speichere…" : (isEdit ? "PDF aktualisieren & speichern" : "PDF erstellen & speichern")}
            </Button>
          </div>
        </div>
      </div>
      {showVerteilerPicker && (
        <VerteilerPickerDialog
          orderPk={order?.primary_key || order?.id || order?.order_pk}
          currentId={form.verteiler_asset_id}
          onClose={() => setShowVerteilerPicker(false)}
          onSelect={(v) => {
            setForm(f => ({
              ...f,
              verteiler_nr: v.label,
              verteiler_asset_id: v.id,
              verteiler_plus_code: v.plus_code,
              verteiler_lat: v.latitude,
              verteiler_lng: v.longitude,
            }));
            dirtyRef.current = true;
            toast.success(`Verteiler "${v.label}" verknüpft`);
          }}
        />
      )}
    </div>
  );
}

function L({ label, children, cols = 1 }) {
  return (
    <div className={cols === 2 ? "md:col-span-2" : ""}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}

function I({ value, onChange, placeholder }) {
  return (
    <input
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:border-violet-400 focus:ring-1 focus:ring-violet-200 outline-none"
    />
  );
}
