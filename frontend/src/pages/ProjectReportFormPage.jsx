import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import SignatureCanvas from "react-signature-canvas";
import { ArrowLeft, Save, Plus, Trash2, Loader2, ClipboardList, Users, Wrench, Truck } from "lucide-react";

const ROLLEN = ["PL", "ME", "T", "H"];
const STUNDEN_TYPEN = ["N", "E", "NO"];
const FAHRZEUG_TYPEN = [
  { value: "PKW", label: "PKW" },
  { value: "LKW", label: "LKW" },
  { value: "LKW_LDK", label: "LKW + Ladekran" },
  { value: "PKW_ANH", label: "PKW + Anhänger" },
  { value: "Tankwagen", label: "Tankwagen" },
  { value: "Sonstig", label: "Sonstiges" },
];

const emptyEmployee = () => ({ name: "", rolle: "T" });
const emptyWorkLog = () => ({ datum: new Date().toISOString().slice(0, 10), beschreibung: "", stunden: {} });
const emptyMaterial = () => ({ pos: 0, material: "", vorbereitung: "", verarbeitet: "", bestellung: "" });
const emptyVehicle = () => ({ typ: "PKW", km: 0, stunden: 0 });

export default function ProjectReportFormPage() {
  const { reportId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isEdit = !!reportId;

  const orderPk = searchParams.get("order_pk") || "";
  const orderName = searchParams.get("order_name") || "";

  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(isEdit);

  // Form state
  const [form, setForm] = useState({
    anrede: "Firma",
    kunde_name: "",
    kunde_anschrift: "",
    kunde_plz: "",
    kunde_ort: "",
    kunde_telefon: "",
    kunde_ansprechpartner: "",
    projektnummer: orderPk,
    projekt_datum: new Date().toISOString().slice(0, 10),
    kunde_nicht_anwesend: false,
    bemerkungen: "",
    uebernachtung_zeitraum: "",
    uebernachtung_naechte: 0,
  });

  const [mitarbeiter, setMitarbeiter] = useState([{ name: user?.name || "", rolle: "T" }]);
  const [workLog, setWorkLog] = useState([emptyWorkLog()]);
  const [material, setMaterial] = useState([emptyMaterial()]);
  const [fahrzeuge, setFahrzeuge] = useState([emptyVehicle()]);

  const sigTechRef = useRef(null);
  const sigKundeRef = useRef(null);
  const [sigTechData, setSigTechData] = useState(null);
  const [sigKundeData, setSigKundeData] = useState(null);

  // Load existing report if editing
  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      try {
        const { data } = await api.get(`/project-reports/${reportId}`);
        setForm({
          anrede: data.anrede || "Firma",
          kunde_name: data.kunde_name || "",
          kunde_anschrift: data.kunde_anschrift || "",
          kunde_plz: data.kunde_plz || "",
          kunde_ort: data.kunde_ort || "",
          kunde_telefon: data.kunde_telefon || "",
          kunde_ansprechpartner: data.kunde_ansprechpartner || "",
          projektnummer: data.projektnummer || "",
          projekt_datum: data.projekt_datum || "",
          kunde_nicht_anwesend: data.kunde_nicht_anwesend || false,
          bemerkungen: data.bemerkungen || "",
          uebernachtung_zeitraum: data.uebernachtung_zeitraum || "",
          uebernachtung_naechte: data.uebernachtung_naechte || 0,
        });
        setMitarbeiter(data.mitarbeiter?.length ? data.mitarbeiter : [emptyEmployee()]);
        setWorkLog(data.work_log?.length ? data.work_log : [emptyWorkLog()]);
        setMaterial(data.material?.length ? data.material : [emptyMaterial()]);
        setFahrzeuge(data.fahrzeuge?.length ? data.fahrzeuge : [emptyVehicle()]);
        setSigTechData(data.unterschrift_techniker);
        setSigKundeData(data.unterschrift_kunde);
      } catch {
        toast.error("Projektbericht nicht gefunden");
        navigate(-1);
      } finally {
        setLoading(false);
      }
    })();
  }, [reportId, isEdit, navigate]);

  // Auto-fill customer data from order
  useEffect(() => {
    if (isEdit || !orderPk) return;
    (async () => {
      try {
        const { data } = await api.get(`/orders/epirent/${orderPk}`);
        if (data) {
          // Parse address string if structured fields are empty
          let street = data.contact_street || data.address_raw?.street || "";
          let plz = data.contact_postal_code || data.address_raw?.postal_code || "";
          let city = data.contact_city || data.address_raw?.city || "";
          
          // Fallback: parse from combined address string "Street, PLZ City"
          if (!street && !plz && data.address) {
            const parts = data.address.split(",").map(p => p.trim());
            if (parts.length >= 2) {
              street = parts[0];
              const plzCity = parts[parts.length - 1].match(/^(\d{5})\s+(.+)$/);
              if (plzCity) {
                plz = plzCity[1];
                city = plzCity[2];
              } else {
                city = parts[parts.length - 1];
              }
            } else {
              street = data.address;
            }
          }

          setForm(f => ({
            ...f,
            kunde_name: data.contact_name || "",
            kunde_anschrift: street,
            kunde_plz: plz,
            kunde_ort: city,
            kunde_telefon: data.contact_phone || "",
            kunde_ansprechpartner: data.contact_name || "",
            projektnummer: String(data.primary_key || orderPk),
          }));
        }
      } catch { /* silent */ }
    })();
  }, [orderPk, isEdit]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const techSig = sigTechRef.current && !sigTechRef.current.isEmpty()
        ? sigTechRef.current.toDataURL()
        : sigTechData;
      const kundeSig = sigKundeRef.current && !sigKundeRef.current.isEmpty()
        ? sigKundeRef.current.toDataURL()
        : sigKundeData;

      const payload = {
        ...form,
        uebernachtung_naechte: parseInt(form.uebernachtung_naechte) || 0,
        mitarbeiter,
        work_log: workLog,
        material: material.filter(m => m.material),
        fahrzeuge: fahrzeuge.filter(f => f.km > 0 || f.stunden > 0),
        unterschrift_techniker: techSig,
        unterschrift_kunde: kundeSig,
      };

      if (isEdit) {
        await api.put(`/project-reports/${reportId}`, payload);
        toast.success("Projektbericht aktualisiert");
      } else {
        await api.post("/project-reports", { ...payload, order_pk: orderPk, order_name: orderName });
        toast.success("Projektbericht erstellt");
      }
      navigate(-1);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Speichern");
    } finally { setSaving(false); }
  };

  const updateWorkLogHours = (wIdx, empIdx, typ, val) => {
    setWorkLog(wl => wl.map((w, i) => {
      if (i !== wIdx) return w;
      const stunden = { ...w.stunden };
      if (!stunden[empIdx]) stunden[empIdx] = {};
      stunden[empIdx] = { ...stunden[empIdx], [typ]: parseFloat(val) || 0 };
      return { ...w, stunden };
    }));
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-fuchsia-500" /></div>;

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-gray-500 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" /> <span className="text-sm">Zurück</span>
            </button>
            <span className="text-gray-300">|</span>
            <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-fuchsia-500" />
              {isEdit ? "Projektbericht bearbeiten" : "Neuer Projektbericht"}
            </h1>
          </div>
          <Button onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-report-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
            Speichern
          </Button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-5 space-y-5">
        {/* Section 1: Kundendaten */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-kunde">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Users className="w-4 h-4 text-fuchsia-500" /> Kundendaten
          </h2>
          <div className="grid grid-cols-4 gap-3 mb-3">
            {["Herr", "Frau", "Firma", "Projekt"].map(a => (
              <label key={a} className="flex items-center gap-1.5 text-xs cursor-pointer">
                <input type="radio" name="anrede" value={a} checked={form.anrede === a} onChange={e => setForm(f => ({ ...f, anrede: e.target.value }))} className="accent-fuchsia-600" />
                {a}
              </label>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs text-gray-500">Name / Firma</Label>
              <Input value={form.kunde_name} onChange={e => setForm(f => ({ ...f, kunde_name: e.target.value }))} className="mt-0.5" data-testid="kunde-name" />
            </div>
            <div>
              <Label className="text-xs text-gray-500">Ansprechpartner</Label>
              <Input value={form.kunde_ansprechpartner} onChange={e => setForm(f => ({ ...f, kunde_ansprechpartner: e.target.value }))} className="mt-0.5" data-testid="kunde-ansprechpartner" />
            </div>
            <div>
              <Label className="text-xs text-gray-500">Anschrift</Label>
              <Input value={form.kunde_anschrift} onChange={e => setForm(f => ({ ...f, kunde_anschrift: e.target.value }))} className="mt-0.5" data-testid="kunde-anschrift" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-xs text-gray-500">PLZ</Label>
                <Input value={form.kunde_plz} onChange={e => setForm(f => ({ ...f, kunde_plz: e.target.value }))} className="mt-0.5" data-testid="kunde-plz" />
              </div>
              <div className="col-span-2">
                <Label className="text-xs text-gray-500">Ort</Label>
                <Input value={form.kunde_ort} onChange={e => setForm(f => ({ ...f, kunde_ort: e.target.value }))} className="mt-0.5" data-testid="kunde-ort" />
              </div>
            </div>
            <div>
              <Label className="text-xs text-gray-500">Telefon</Label>
              <Input value={form.kunde_telefon} onChange={e => setForm(f => ({ ...f, kunde_telefon: e.target.value }))} className="mt-0.5" data-testid="kunde-telefon" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs text-gray-500">Projektnummer</Label>
                <Input value={form.projektnummer} onChange={e => setForm(f => ({ ...f, projektnummer: e.target.value }))} className="mt-0.5" data-testid="projektnummer" />
              </div>
              <div>
                <Label className="text-xs text-gray-500">Datum</Label>
                <Input type="date" value={form.projekt_datum} onChange={e => setForm(f => ({ ...f, projekt_datum: e.target.value }))} className="mt-0.5" data-testid="projekt-datum" />
              </div>
            </div>
          </div>
          <label className="flex items-center gap-2 mt-3 text-xs text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form.kunde_nicht_anwesend} onChange={e => setForm(f => ({ ...f, kunde_nicht_anwesend: e.target.checked }))} className="accent-fuchsia-600" data-testid="kunde-nicht-anwesend" />
            Kunde nicht anwesend
          </label>
        </div>

        {/* Section 2: Mitarbeiter */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-mitarbeiter">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Users className="w-4 h-4 text-fuchsia-500" /> Mitarbeiter
            </h2>
            <Button size="sm" variant="outline" onClick={() => setMitarbeiter(m => [...m, emptyEmployee()])} className="h-7 text-xs" data-testid="add-employee">
              <Plus className="w-3 h-3 mr-1" /> Hinzufügen
            </Button>
          </div>
          <div className="space-y-2">
            {mitarbeiter.map((emp, idx) => (
              <div key={idx} className="flex items-center gap-2" data-testid={`employee-${idx}`}>
                <span className="text-xs text-gray-400 w-5">{idx + 1}.</span>
                <Input value={emp.name} onChange={e => setMitarbeiter(m => m.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))}
                  placeholder="Name" className="flex-1 h-8 text-sm" />
                <select value={emp.rolle} onChange={e => setMitarbeiter(m => m.map((x, i) => i === idx ? { ...x, rolle: e.target.value } : x))}
                  className="h-8 border rounded px-2 text-xs">
                  {ROLLEN.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                {mitarbeiter.length > 1 && (
                  <button onClick={() => setMitarbeiter(m => m.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Arbeitsprotokoll */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-worklog">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-fuchsia-500" /> Arbeitsprotokoll
            </h2>
            <Button size="sm" variant="outline" onClick={() => setWorkLog(w => [...w, emptyWorkLog()])} className="h-7 text-xs" data-testid="add-worklog">
              <Plus className="w-3 h-3 mr-1" /> Zeile
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-[10px] text-gray-500 uppercase">
                  <th className="px-2 py-1.5 text-left w-28">Datum</th>
                  <th className="px-2 py-1.5 text-left">Arbeitsbeschreibung</th>
                  {mitarbeiter.map((emp, i) => (
                    <th key={i} className="px-1 py-1.5 text-center" colSpan={3}>
                      <span className="text-fuchsia-600">{emp.name || `MA ${i + 1}`}</span>
                    </th>
                  ))}
                  <th className="w-8"></th>
                </tr>
                <tr className="bg-gray-50 text-[9px] text-gray-400 uppercase">
                  <th></th>
                  <th></th>
                  {mitarbeiter.map((_, i) => STUNDEN_TYPEN.map(t => (
                    <th key={`${i}-${t}`} className="px-1 py-0.5 text-center">{t}</th>
                  )))}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {workLog.map((wl, wIdx) => (
                  <tr key={wIdx} className="border-t border-gray-100" data-testid={`worklog-row-${wIdx}`}>
                    <td className="px-1 py-1">
                      <Input type="date" value={wl.datum} onChange={e => setWorkLog(w => w.map((x, i) => i === wIdx ? { ...x, datum: e.target.value } : x))} className="h-7 text-xs" />
                    </td>
                    <td className="px-1 py-1">
                      <Input value={wl.beschreibung} onChange={e => setWorkLog(w => w.map((x, i) => i === wIdx ? { ...x, beschreibung: e.target.value } : x))}
                        placeholder="Arbeiten beschreiben..." className="h-7 text-xs" />
                    </td>
                    {mitarbeiter.map((_, empIdx) => STUNDEN_TYPEN.map(t => (
                      <td key={`${empIdx}-${t}`} className="px-0.5 py-1">
                        <Input type="number" step="0.5" min="0" value={wl.stunden?.[empIdx]?.[t] || ""}
                          onChange={e => updateWorkLogHours(wIdx, empIdx, t, e.target.value)}
                          className="h-7 w-12 text-xs text-center px-1" />
                      </td>
                    )))}
                    <td className="px-1 py-1">
                      {workLog.length > 1 && (
                        <button onClick={() => setWorkLog(w => w.filter((_, i) => i !== wIdx))} className="text-gray-400 hover:text-red-500">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 4: Material */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-material">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-amber-500" /> Material / Artikel
            </h2>
            <Button size="sm" variant="outline" onClick={() => setMaterial(m => [...m, emptyMaterial()])} className="h-7 text-xs" data-testid="add-material">
              <Plus className="w-3 h-3 mr-1" /> Zeile
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-[10px] text-gray-500 uppercase">
                  <th className="px-2 py-1.5 text-left w-12">Pos</th>
                  <th className="px-2 py-1.5 text-left">Material / Artikel</th>
                  <th className="px-2 py-1.5 text-left w-24">Vorber.</th>
                  <th className="px-2 py-1.5 text-left w-24">Verarb.</th>
                  <th className="px-2 py-1.5 text-left w-24">Bestell.</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {material.map((m, idx) => (
                  <tr key={idx} className="border-t border-gray-100" data-testid={`material-row-${idx}`}>
                    <td className="px-2 py-1 font-mono text-gray-400">{idx + 1}</td>
                    <td className="px-1 py-1">
                      <Input value={m.material} onChange={e => setMaterial(ml => ml.map((x, i) => i === idx ? { ...x, material: e.target.value } : x))}
                        placeholder="Bezeichnung" className="h-7 text-xs" />
                    </td>
                    <td className="px-1 py-1">
                      <Input value={m.vorbereitung} onChange={e => setMaterial(ml => ml.map((x, i) => i === idx ? { ...x, vorbereitung: e.target.value } : x))} className="h-7 text-xs" />
                    </td>
                    <td className="px-1 py-1">
                      <Input value={m.verarbeitet} onChange={e => setMaterial(ml => ml.map((x, i) => i === idx ? { ...x, verarbeitet: e.target.value } : x))} className="h-7 text-xs" />
                    </td>
                    <td className="px-1 py-1">
                      <Input value={m.bestellung} onChange={e => setMaterial(ml => ml.map((x, i) => i === idx ? { ...x, bestellung: e.target.value } : x))} className="h-7 text-xs" />
                    </td>
                    <td className="px-1 py-1">
                      {material.length > 1 && (
                        <button onClick={() => setMaterial(ml => ml.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-500">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 5: Fahrzeuge */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-fahrzeuge">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Truck className="w-4 h-4 text-blue-500" /> Fahrzeuge
            </h2>
            <Button size="sm" variant="outline" onClick={() => setFahrzeuge(f => [...f, emptyVehicle()])} className="h-7 text-xs" data-testid="add-vehicle">
              <Plus className="w-3 h-3 mr-1" /> Hinzufügen
            </Button>
          </div>
          <div className="space-y-2">
            {fahrzeuge.map((v, idx) => (
              <div key={idx} className="flex items-center gap-2" data-testid={`vehicle-${idx}`}>
                <select value={v.typ} onChange={e => setFahrzeuge(f => f.map((x, i) => i === idx ? { ...x, typ: e.target.value } : x))}
                  className="h-8 border rounded px-2 text-xs w-40">
                  {FAHRZEUG_TYPEN.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <div className="flex items-center gap-1">
                  <Label className="text-[10px] text-gray-400">KM:</Label>
                  <Input type="number" step="1" value={v.km || ""} onChange={e => setFahrzeuge(f => f.map((x, i) => i === idx ? { ...x, km: parseFloat(e.target.value) || 0 } : x))}
                    className="h-8 w-20 text-xs" />
                </div>
                <div className="flex items-center gap-1">
                  <Label className="text-[10px] text-gray-400">Std:</Label>
                  <Input type="number" step="0.5" value={v.stunden || ""} onChange={e => setFahrzeuge(f => f.map((x, i) => i === idx ? { ...x, stunden: parseFloat(e.target.value) || 0 } : x))}
                    className="h-8 w-20 text-xs" />
                </div>
                {fahrzeuge.length > 1 && (
                  <button onClick={() => setFahrzeuge(f => f.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Section 6: Bemerkungen + Übernachtung */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-bemerkungen">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Projektbesprechung / Vorkommnisse</h2>
          <textarea value={form.bemerkungen} onChange={e => setForm(f => ({ ...f, bemerkungen: e.target.value }))}
            rows={3} className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-fuchsia-500" placeholder="Anmerkungen..." data-testid="bemerkungen" />
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <Label className="text-xs text-gray-500">Übernachtung Zeitraum</Label>
              <Input value={form.uebernachtung_zeitraum} onChange={e => setForm(f => ({ ...f, uebernachtung_zeitraum: e.target.value }))} placeholder="z.B. 01.04. - 03.04." className="mt-0.5" data-testid="uebernachtung-zeitraum" />
            </div>
            <div>
              <Label className="text-xs text-gray-500">Anzahl Nächte</Label>
              <Input type="number" min="0" value={form.uebernachtung_naechte} onChange={e => setForm(f => ({ ...f, uebernachtung_naechte: e.target.value }))} className="mt-0.5" data-testid="uebernachtung-naechte" />
            </div>
          </div>
        </div>

        {/* Section 7: Unterschriften */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="section-unterschriften">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Unterschriften</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Techniker */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs text-gray-500">Techniker / Projektleiter</Label>
                <button onClick={() => { sigTechRef.current?.clear(); setSigTechData(null); }} className="text-[10px] text-gray-400 hover:text-red-500" data-testid="clear-sig-tech">Löschen</button>
              </div>
              {sigTechData && !sigTechRef.current ? (
                <img src={sigTechData} alt="Unterschrift Techniker" className="border rounded-lg bg-white w-full h-32 object-contain" />
              ) : (
                <div className="border rounded-lg bg-white touch-none">
                  <SignatureCanvas ref={sigTechRef} penColor="#1a1a2e" canvasProps={{ className: "w-full h-32", "data-testid": "sig-tech-canvas" }} />
                </div>
              )}
            </div>
            {/* Kunde */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs text-gray-500">Auftraggeber / Bauleiter / Eigentümer</Label>
                <button onClick={() => { sigKundeRef.current?.clear(); setSigKundeData(null); }} className="text-[10px] text-gray-400 hover:text-red-500" data-testid="clear-sig-kunde">Löschen</button>
              </div>
              {sigKundeData && !sigKundeRef.current ? (
                <img src={sigKundeData} alt="Unterschrift Kunde" className="border rounded-lg bg-white w-full h-32 object-contain" />
              ) : (
                <div className="border rounded-lg bg-white touch-none">
                  <SignatureCanvas ref={sigKundeRef} penColor="#1a1a2e" canvasProps={{ className: "w-full h-32", "data-testid": "sig-kunde-canvas" }} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Save Button */}
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving} size="lg" className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white px-8" data-testid="save-report-bottom">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Projektbericht speichern
          </Button>
        </div>
      </div>
    </div>
  );
}
