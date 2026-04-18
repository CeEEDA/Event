import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api, { getErrorMsg } from "../lib/api";
import { BACKEND_URL } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft, Wrench, Plus, Search, Clock, User, ChevronLeft, ChevronDown,
  Trash2, Pencil, AlertTriangle, CheckCircle, X, Save, Camera, FileText, FileUp, Download, Paperclip,
  ScanLine, Filter, Printer,
} from "lucide-react";
import QrScanner from "../components/QrScanner";
import EventLog from "../components/EventLog";

const TYPE_LABELS = { stromerzeuger: "Stromerzeuger", lichtmast: "Lichtmast", messkoffer: "Messkoffer", kirmeskiste: "Kirmeskiste", verteiler: "Verteiler" };

// Device types with reduced service plan (only electrical + diagnosis)
const REDUCED_PLAN_TYPES = ["messkoffer", "kirmeskiste", "verteiler"];
const isReducedPlan = (deviceType) => REDUCED_PLAN_TYPES.includes(deviceType);

// ============== Default Checklists ==============
const MECHANICAL_ITEMS = [
  "Motor auf Undichtigkeiten geprüft", "Motorölstand geprüft", "Ölwechsel",
  "Ölfilter gewechselt", "Luftfilter geprüft / ersetzt", "Kraftstofffilter geprüft / ersetzt",
  "Kühlsystem geprüft", "Keilriemen geprüft", "Abgasanlage geprüft",
  "Motorlager geprüft", "Schwingungsdämpfer geprüft", "Allgemeine Motorprüfung",
];
const ELECTRICAL_ITEMS = [
  "Kabel und Leitungen geprüft", "Kabelverschraubungen geprüft", "Alle Anschlussklemmen fest",
  "Schutzleiterverbindungen geprüft", "Generatoranschlussklemmen geprüft", "Schaltschrank sauber",
  "Sicherungen geprüft", "Leistungsschalter geprüft", "Steuerung / Bedienpanel geprüft",
  "Not-Aus Funktion geprüft", "Batterieladegerät geprüft", "Starterbatterie geprüft",
  "ATS / Netzumschaltung getestet",
];
const MEASUREMENT_FIELDS = [
  { key: "spannung_l1", label: "Spannung L1" }, { key: "spannung_l2", label: "Spannung L2" },
  { key: "spannung_l3", label: "Spannung L3" }, { key: "spannung_l1_l2", label: "Spannung L1-L2" },
  { key: "spannung_l2_l3", label: "Spannung L2-L3" }, { key: "spannung_l1_l3", label: "Spannung L1-L3" },
  { key: "frequenz", label: "Frequenz" }, { key: "batteriespannung", label: "Batteriespannung" },
  { key: "oeldruck", label: "Öldruck" }, { key: "kuehlmitteltemperatur", label: "Kühlmitteltemperatur" },
  { key: "abgastemperatur", label: "Abgastemperatur" }, { key: "drehzahl_leerlauf", label: "Drehzahl Leerlauf" },
  { key: "drehzahl_betrieb", label: "Drehzahl Betrieb" }, { key: "anlaufzeit_generator", label: "Anlaufzeit Generator" },
  { key: "netzuebernahmezeit", label: "Netzübernahmezeit" },
];
const LOAD_LEVELS = ["25 %", "50 %", "75 %", "100 %"];
const ATS_ITEMS = [
  { key: "netzausfall_simuliert", label: "Netzausfall simuliert" },
  { key: "generator_startet_auto", label: "Generator startet automatisch" },
  { key: "umschaltung_generator", label: "Umschaltung auf Generator" },
  { key: "versorgung_stabil", label: "Versorgung stabil" },
  { key: "rueckschaltung_netz", label: "Rückschaltung auf Netz" },
  { key: "nachlaufzeit_korrekt", label: "Nachlaufzeit korrekt" },
];

// ============== 3-State Push Button ==============
function TriStateButton({ status, onChange, label }) {
  const states = [
    { value: "nicht_durchgefuehrt", label: "Nicht durchgeführt", cls: "bg-gray-200 text-gray-600" },
    { value: "durchgefuehrt", label: "Durchgeführt", cls: "bg-emerald-500 text-white" },
    { value: "nicht_vorhanden", label: "Nicht vorhanden", cls: "bg-amber-400 text-white" },
  ];
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-gray-100 last:border-b-0">
      <span className="text-sm text-gray-700 flex-1 min-w-0">{label}</span>
      <div className="flex gap-1 flex-shrink-0">
        {states.map(s => (
          <button
            key={s.value}
            type="button"
            onClick={() => onChange(s.value)}
            className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${status === s.value ? s.cls + " shadow-sm" : "bg-gray-100 text-gray-400 hover:bg-gray-200"}`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ============== Section Header ==============
function SectionHeader({ number, title }) {
  return (
    <div className="flex items-center gap-3 pb-2 border-b-2 border-fuchsia-200 mb-3 mt-6 first:mt-0">
      <span className="w-7 h-7 rounded-full bg-fuchsia-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">{number}</span>
      <h4 className="text-sm font-bold text-gray-900">{title}</h4>
    </div>
  );
}

function getServiceStatus(plan) {
  if (!plan || !plan.latest_entry) return { label: "Kein Service", color: "text-gray-400", bg: "bg-gray-100" };
  const lastDate = new Date(plan.latest_entry.performed_at);
  const now = new Date();
  const daysSince = Math.floor((now - lastDate) / (1000 * 60 * 60 * 24));
  const intervalDays = (plan.interval_months || 12) * 30;
  const remaining = intervalDays - daysSince;
  const currentHrs = plan.current_hours || 0;
  const lastHrs = plan.latest_entry.hours_at_service || 0;
  const intervalHrs = plan.interval_hours || 500;
  const hrsRemaining = intervalHrs - (currentHrs - lastHrs);
  const isOverdue = remaining < 0 || hrsRemaining < 0;
  const isDueSoon = remaining <= 30 || hrsRemaining <= 50;
  if (isOverdue) return { label: "Überfällig", color: "text-red-600", bg: "bg-red-50", days: remaining, hours: hrsRemaining };
  if (isDueSoon) return { label: "Bald fällig", color: "text-amber-600", bg: "bg-amber-50", days: remaining, hours: hrsRemaining };
  return { label: "OK", color: "text-emerald-600", bg: "bg-emerald-50", days: remaining, hours: hrsRemaining };
}

// ============== Entry Form ==============
function MaintenanceEntryForm({ planDetail, onSave, onCancel }) {
  const { user } = useAuth();
  const imageInputRef = useRef(null);
  const [pendingImages, setPendingImages] = useState([]);
  const [saving, setSaving] = useState(false);
  const reduced = isReducedPlan(planDetail?.device_type);

  const initChecklist = (items) => items.reduce((acc, item) => { acc[item] = "nicht_durchgefuehrt"; return acc; }, {});

  const [form, setForm] = useState({
    performed_by: user?.name || "",
    performed_at: new Date().toISOString().split("T")[0],
    hours_at_service: "",
    next_maintenance_months: "",
    next_maintenance_hours: "",
    mechanical: initChecklist(MECHANICAL_ITEMS),
    electrical: initChecklist(ELECTRICAL_ITEMS),
    measurements: MEASUREMENT_FIELDS.reduce((acc, f) => { acc[f.key] = ""; return acc; }, {}),
    load_test: LOAD_LEVELS.map(l => ({ load: l, values: "", remarks: "" })),
    ats_test: ATS_ITEMS.reduce((acc, i) => { acc[i.key] = "nicht_durchgefuehrt"; return acc; }, {}),
    ats_umschaltzeit: "",
    diagnosis: {
      fehlerspeicher_ausgelesen: "nicht_durchgefuehrt",
      keine_fehler: "nicht_durchgefuehrt",
      fehler_vorhanden: "nicht_durchgefuehrt",
      fehlercodes: "",
    },
    remarks: "",
    notes: "",
  });

  // Calculate next maintenance preview
  const calcNextMaintenanceMonths = () => {
    if (!form.next_maintenance_months) return "–";
    const val = parseInt(form.next_maintenance_months);
    const d = new Date(form.performed_at);
    d.setMonth(d.getMonth() + val);
    return d.toLocaleDateString("de-DE");
  };

  const calcNextMaintenanceHours = () => {
    if (!form.next_maintenance_hours || !form.hours_at_service) return "–";
    const hrs = parseFloat(form.hours_at_service || 0);
    const val = parseInt(form.next_maintenance_hours);
    return `bei ${hrs + val} h`;
  };

  const handleSave = async () => {
    if (!form.performed_by.trim()) { toast.error("Techniker ist erforderlich"); return; }
    if (!form.next_maintenance_months) { toast.error("Nächste Wartung in Monaten ist erforderlich"); return; }
    if (!form.next_maintenance_hours) { toast.error("Nächste Wartung in Stunden ist erforderlich"); return; }
    setSaving(true);
    try {
      await onSave({
        performed_by: form.performed_by,
        performed_at: form.performed_at,
        hours_at_service: form.hours_at_service ? parseFloat(form.hours_at_service) : null,
        next_maintenance_months: parseInt(form.next_maintenance_months),
        next_maintenance_hours: parseInt(form.next_maintenance_hours),
        checklist_data: { mechanical: form.mechanical, electrical: form.electrical },
        measurements: form.measurements,
        load_test: form.load_test,
        ats_test: { ...form.ats_test, umschaltzeit: form.ats_umschaltzeit },
        diagnosis: form.diagnosis,
        remarks: form.remarks,
        notes: form.notes,
      }, pendingImages);
    } finally { setSaving(false); }
  };

  const updateMech = (item, val) => setForm(p => ({ ...p, mechanical: { ...p.mechanical, [item]: val } }));
  const updateElec = (item, val) => setForm(p => ({ ...p, electrical: { ...p.electrical, [item]: val } }));
  const updateMeasurement = (key, val) => setForm(p => ({ ...p, measurements: { ...p.measurements, [key]: val } }));
  const updateLoadTest = (idx, field, val) => setForm(p => {
    const lt = [...p.load_test]; lt[idx] = { ...lt[idx], [field]: val }; return { ...p, load_test: lt };
  });
  const updateAts = (key, val) => setForm(p => ({ ...p, ats_test: { ...p.ats_test, [key]: val } }));
  const updateDiag = (key, val) => setForm(p => ({ ...p, diagnosis: { ...p.diagnosis, [key]: val } }));

  return (
    <div className="bg-white border border-fuchsia-200 rounded-lg p-6 mb-6" data-testid="add-entry-form">
      <h3 className="text-base font-semibold text-gray-900 mb-4">Neue Wartung anlegen</h3>

      {/* Basic Info */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div>
          <Label className="text-gray-700 text-sm">Techniker</Label>
          <Input value={form.performed_by} readOnly className="mt-1 bg-gray-50" data-testid="entry-performed-by" />
        </div>
        <div>
          <Label className="text-gray-700 text-sm">Datum</Label>
          <Input type="date" value={form.performed_at} onChange={e => setForm(p => ({ ...p, performed_at: e.target.value }))} className="mt-1" data-testid="entry-date" />
        </div>
        <div>
          <Label className="text-gray-700 text-sm">Betriebsstunden bei Wartung</Label>
          <Input type="number" value={form.hours_at_service} onChange={e => setForm(p => ({ ...p, hours_at_service: e.target.value }))} placeholder="z.B. 4500" className="mt-1" data-testid="entry-hours" />
        </div>
      </div>

      {/* Next Maintenance Calculation - Both months and hours mandatory */}
      <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-4 mb-6">
        <Label className="text-fuchsia-700 text-sm font-medium mb-2 block">Nächste Wartung *</Label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-gray-600 text-xs mb-1 block">In Monaten *</Label>
            <Input type="number" value={form.next_maintenance_months} onChange={e => setForm(p => ({ ...p, next_maintenance_months: e.target.value }))} placeholder="z.B. 12" className="border-fuchsia-300" data-testid="next-maint-months" />
            <p className="text-xs text-fuchsia-600 mt-1">Nächste Wartung: <span className="font-bold">{calcNextMaintenanceMonths()}</span></p>
          </div>
          <div>
            <Label className="text-gray-600 text-xs mb-1 block">In Betriebsstunden *</Label>
            <Input type="number" value={form.next_maintenance_hours} onChange={e => setForm(p => ({ ...p, next_maintenance_hours: e.target.value }))} placeholder="z.B. 500" className="border-fuchsia-300" data-testid="next-maint-hours" />
            <p className="text-xs text-fuchsia-600 mt-1">Nächste Wartung: <span className="font-bold">{calcNextMaintenanceHours()}</span></p>
          </div>
        </div>
      </div>

      {/* 1. Mechanische Prüfung - nur bei Stromerzeuger/Lichtmast */}
      {!reduced && (
        <>
          <SectionHeader number="1" title="Mechanische Prüfung" />
          <div className="space-y-0">
            {MECHANICAL_ITEMS.map(item => (
              <TriStateButton key={item} label={item} status={form.mechanical[item]} onChange={val => updateMech(item, val)} />
            ))}
          </div>
        </>
      )}

      {/* 2. Elektrische Prüfung */}
      <SectionHeader number={reduced ? "1" : "2"} title="Elektrische Prüfung" />
      <div className="space-y-0">
        {ELECTRICAL_ITEMS.map(item => (
          <TriStateButton key={item} label={item} status={form.electrical[item]} onChange={val => updateElec(item, val)} />
        ))}
      </div>

      {/* 3-5: Nur bei Stromerzeuger/Lichtmast */}
      {!reduced && (
        <>
          {/* 3. Generator Messwerte */}
          <SectionHeader number="3" title="Generator Messwerte" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {MEASUREMENT_FIELDS.map(f => (
              <div key={f.key}>
                <Label className="text-gray-600 text-xs">{f.label}</Label>
                <Input value={form.measurements[f.key]} onChange={e => updateMeasurement(f.key, e.target.value)} placeholder="–" className="mt-0.5 text-sm" data-testid={`meas-${f.key}`} />
              </div>
            ))}
          </div>

          {/* 4. Lasttest Generator */}
          <SectionHeader number="4" title="Lasttest Generator" />
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs text-gray-500 font-medium w-20">Last</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-500 font-medium">Lasttest</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-500 font-medium">Bemerkungen</th>
                </tr>
              </thead>
              <tbody>
                {form.load_test.map((lt, idx) => (
                  <tr key={idx} className="border-t border-gray-100">
                    <td className="px-3 py-2 font-medium text-gray-700">{lt.load}</td>
                    <td className="px-3 py-1"><Input value={lt.values} onChange={e => updateLoadTest(idx, "values", e.target.value)} placeholder="–" className="text-sm h-8" data-testid={`lt-val-${idx}`} /></td>
                    <td className="px-3 py-1"><Input value={lt.remarks} onChange={e => updateLoadTest(idx, "remarks", e.target.value)} placeholder="–" className="text-sm h-8" data-testid={`lt-rem-${idx}`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 5. ATS / Netzumschaltung Test */}
          <SectionHeader number="5" title="ATS / Netzumschaltung Test" />
          <div className="space-y-0">
            {ATS_ITEMS.map(item => (
              <TriStateButton key={item.key} label={item.label} status={form.ats_test[item.key]} onChange={val => updateAts(item.key, val)} />
            ))}
            <div className="mt-2 pt-2">
              <Label className="text-gray-600 text-xs">ATS Umschaltzeit (Sekunden)</Label>
              <Input value={form.ats_umschaltzeit} onChange={e => setForm(p => ({ ...p, ats_umschaltzeit: e.target.value }))} placeholder="–" className="mt-0.5 w-40 text-sm" data-testid="ats-umschaltzeit" />
            </div>
          </div>
        </>
      )}

      {/* 6. Diagnose */}
      <SectionHeader number={reduced ? "2" : "6"} title="Diagnose" />
      <div className="space-y-0 mb-3">
        {[
          { key: "fehlerspeicher_ausgelesen", label: "Fehlerspeicher ausgelesen" },
          { key: "keine_fehler", label: "Keine Fehler vorhanden" },
          { key: "fehler_vorhanden", label: "Fehler vorhanden" },
        ].map(item => (
          <TriStateButton key={item.key} label={item.label} status={form.diagnosis[item.key]} onChange={val => updateDiag(item.key, val)} />
        ))}
        <div className="mt-2">
          <Label className="text-gray-600 text-xs">Fehlercodes</Label>
          <textarea value={form.diagnosis.fehlercodes} onChange={e => updateDiag("fehlercodes", e.target.value)} rows={2} placeholder="Fehlercodes eingeben..." className="mt-0.5 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="diag-fehlercodes" />
        </div>
      </div>

      {/* Remarks */}
      <div className="mt-6 mb-4">
        <Label className="text-gray-700 text-sm font-medium">Bemerkungen / Besondere Vorkommnisse</Label>
        <textarea value={form.remarks} onChange={e => setForm(p => ({ ...p, remarks: e.target.value }))} rows={3} placeholder="Besonderheiten, Auffälligkeiten, Schäden..." className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="entry-remarks" />
      </div>

      {/* Anhänge (Fotos + PDFs) */}
      <div className="mb-4">
        <Label className="text-gray-700 text-sm font-medium mb-2 block">Anhänge (Fotos & Dokumente)</Label>
        <input ref={imageInputRef} type="file" accept="image/*,.pdf,application/pdf" multiple className="hidden" onChange={e => {
          const files = Array.from(e.target.files || []);
          const valid = files.filter(f => {
            if (f.size > 25 * 1024 * 1024) { toast.error(`${f.name}: Zu groß (max 25 MB)`); return false; }
            if (!f.type.startsWith("image/") && f.type !== "application/pdf") { toast.error(`${f.name}: Nur Bilder und PDFs erlaubt`); return false; }
            return true;
          });
          if (valid.length > 0) setPendingImages(prev => [...prev, ...valid]);
          e.target.value = "";
        }} />
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-4 transition-colors hover:border-fuchsia-400"
          data-testid="photo-drop-zone"
          onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-fuchsia-500", "bg-fuchsia-50"); }}
          onDragLeave={e => { e.preventDefault(); e.currentTarget.classList.remove("border-fuchsia-500", "bg-fuchsia-50"); }}
          onDrop={e => {
            e.preventDefault();
            e.currentTarget.classList.remove("border-fuchsia-500", "bg-fuchsia-50");
            const files = Array.from(e.dataTransfer.files).filter(f => {
              if (f.size > 25 * 1024 * 1024) { toast.error(`${f.name}: Zu groß (max 25 MB)`); return false; }
              return f.type.startsWith("image/") || f.type === "application/pdf";
            });
            if (files.length > 0) setPendingImages(prev => [...prev, ...files]);
          }}
        >
          <div className="flex flex-wrap gap-2">
            {pendingImages.map((file, idx) => (
              <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden border border-gray-200 group">
                {file.type === "application/pdf" ? (
                  <div className="w-full h-full bg-red-50 flex flex-col items-center justify-center">
                    <FileText className="w-6 h-6 text-red-500" />
                    <span className="text-[8px] text-red-600 font-medium mt-0.5 px-1 truncate w-full text-center">{file.name.length > 12 ? file.name.slice(0, 10) + "…" : file.name}</span>
                  </div>
                ) : (
                  <img src={URL.createObjectURL(file)} alt="" className="w-full h-full object-cover" />
                )}
                <button onClick={() => setPendingImages(p => p.filter((_, i) => i !== idx))} className="absolute top-0.5 right-0.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center"><X className="w-3 h-3" /></button>
              </div>
            ))}
            <button onClick={() => imageInputRef.current?.click()} className="w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-400 hover:border-fuchsia-400 hover:text-fuchsia-500 transition-colors" data-testid="add-photo-btn">
              <Paperclip className="w-5 h-5" /><span className="text-[10px] mt-0.5">Anhang</span>
            </button>
          </div>
          {pendingImages.length === 0 && (
            <p className="text-xs text-gray-400 text-center mt-2">Fotos oder PDFs hierher ziehen oder auf "Anhang" klicken</p>
          )}
        </div>
      </div>

      {/* Notes */}
      <div className="mb-6">
        <Label className="text-gray-700 text-sm">Notizen</Label>
        <textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} rows={2} placeholder="Weitere Hinweise..." className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="entry-notes" />
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-entry-btn">
          <Save className="w-4 h-4 mr-1" /> {saving ? "Wird gespeichert..." : "Wartung speichern"}
        </Button>
        <Button variant="outline" onClick={onCancel}>Abbrechen</Button>
      </div>
    </div>
  );
}

// ============== Entry Display ==============
function EntryCard({ entry, planId, planDetail, isAdmin, onDelete, deviceType }) {
  const [expanded, setExpanded] = useState(false);
  const reduced = isReducedPlan(deviceType);
  const cl = entry.checklist_data || {};
  const mech = cl.mechanical || {};
  const elec = cl.electrical || {};
  const meas = entry.measurements || {};
  const lt = entry.load_test || [];
  const ats = entry.ats_test || {};
  const diag = entry.diagnosis || {};
  const images = entry.images || [];

  const statusLabel = { durchgefuehrt: "Durchgeführt", nicht_durchgefuehrt: "Nicht durchgeführt", nicht_vorhanden: "Nicht vorhanden" };
  const statusCls = { durchgefuehrt: "bg-emerald-100 text-emerald-700", nicht_durchgefuehrt: "bg-gray-100 text-gray-500", nicht_vorhanden: "bg-amber-100 text-amber-700" };

  const handlePrint = (e) => {
    e.stopPropagation();
    if (!expanded) setExpanded(true);

    const deviceName = planDetail?.device_name || planDetail?.serial_number || "";
    const dateStr = new Date(entry.performed_at).toLocaleDateString("de-DE");
    const badgeCls = (v, err) => {
      if (v === "durchgefuehrt" || v === true) return err ? "badge-err" : "badge-ok";
      if (v === "nicht_vorhanden") return "badge-warn";
      return "badge-na";
    };
    const badgeTxt = (v) => v === true ? "Ja" : (statusLabel[v] || String(v || "–"));

    const sectionHtml = (title, content) => content ? `<div class="section"><h3>${title}</h3>${content}</div>` : "";

    // 1. Mechanische Prüfung
    const mechHtml = !reduced && Object.keys(mech).length > 0 ? sectionHtml("1. Mechanische Pruefung",
      `<div class="grid">${Object.entries(mech).map(([k, v]) => `<div class="row"><span class="label">${k}</span><span class="badge ${badgeCls(v)}">${badgeTxt(v)}</span></div>`).join("")}</div>`) : "";

    // 2. Elektrische Prüfung
    const elecHtml = Object.keys(elec).length > 0 ? sectionHtml("2. Elektrische Pruefung",
      `<div class="grid">${Object.entries(elec).map(([k, v]) => `<div class="row"><span class="label">${k}</span><span class="badge ${badgeCls(v)}">${badgeTxt(v)}</span></div>`).join("")}</div>`) : "";

    // 3. Generator Messwerte
    const measEntries = Object.entries(meas).filter(([, v]) => v);
    const measHtml = !reduced && measEntries.length > 0 ? sectionHtml("3. Generator Messwerte",
      `<div class="measurements">${measEntries.map(([k, v]) => {
        const lbl = MEASUREMENT_FIELDS.find(f => f.key === k)?.label || k;
        return `<div class="meas-box"><div class="lbl">${lbl}</div><div class="val">${v}</div></div>`;
      }).join("")}</div>`) : "";

    // 4. Lasttest
    const ltHtml = !reduced && lt.length > 0 && lt.some(r => r.values) ? sectionHtml("4. Lasttest Generator",
      `<table class="load-table"><thead><tr><th>Last</th><th>Lasttest</th><th>Bemerkungen</th></tr></thead><tbody>` +
      lt.map(r => `<tr><td>${r.load}</td><td>${r.values || "–"}</td><td>${r.remarks || "–"}</td></tr>`).join("") +
      `</tbody></table>`) : "";

    // 5. ATS
    const atsEntries = Object.entries(ats).filter(([k]) => k !== "umschaltzeit");
    const atsHtml = !reduced && atsEntries.length > 0 ? sectionHtml("5. ATS / Netzumschaltung",
      `<div class="grid">${atsEntries.map(([k, v]) => {
        const a = ATS_ITEMS.find(i => i.key === k);
        return `<div class="row"><span class="label">${a?.label || k}</span><span class="badge ${badgeCls(v)}">${badgeTxt(v)}</span></div>`;
      }).join("")}</div>${ats.umschaltzeit ? `<div style="margin-top:4px;">Umschaltzeit: <strong>${ats.umschaltzeit}s</strong></div>` : ""}`) : "";

    // 6. Diagnose
    const diagItems = [
      { key: "fehlerspeicher_ausgelesen", label: "Fehlerspeicher ausgelesen" },
      { key: "keine_fehler", label: "Keine Fehler vorhanden" },
      { key: "fehler_vorhanden", label: "Fehler vorhanden" },
    ].filter(i => diag[i.key]);
    const diagHtml = diagItems.length > 0 ? sectionHtml("6. Diagnose",
      `<div class="grid">${diagItems.map(i => {
        const v = diag[i.key];
        return `<div class="row"><span class="label">${i.label}</span><span class="badge ${badgeCls(v, i.key === "fehler_vorhanden")}">${badgeTxt(v)}</span></div>`;
      }).join("")}</div>${diag.fehlercodes ? `<div style="margin-top:4px;padding:4px 8px;border:1px solid #fca5a5;border-radius:4px;color:#991b1b;">${diag.fehlercodes}</div>` : ""}`) : "";

    // Bemerkungen
    const remarksHtml = entry.remarks ? `<div class="section"><h3>Bemerkungen</h3><div class="remarks">${entry.remarks}</div></div>` : "";
    const notesHtml = entry.notes ? `<div class="section"><h3>Notizen</h3><p>${entry.notes}</p></div>` : "";

    const win = window.open("", "_blank");
    if (!win) { toast.error("Popup-Blocker aktiv - bitte erlauben"); return; }
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Servicebericht ${deviceName} ${dateStr}</title>
<style>
  @page { margin: 15mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
  body { font-size: 11px; color: #1a1a1a; line-height: 1.5; }
  .header { border-bottom: 2px solid #a21caf; padding-bottom: 10px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-end; }
  .header h1 { font-size: 18px; color: #a21caf; }
  .header .meta { font-size: 10px; color: #666; text-align: right; }
  .section { margin-bottom: 12px; }
  .section h3 { font-size: 12px; font-weight: 600; color: #333; border-bottom: 1px solid #e5e5e5; padding-bottom: 3px; margin-bottom: 6px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 12px; }
  .row { display: flex; justify-content: space-between; padding: 2px 0; }
  .row .label { color: #555; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 500; }
  .badge-ok { background: #d1fae5; color: #065f46; }
  .badge-warn { background: #fef3c7; color: #92400e; }
  .badge-na { background: #f3f4f6; color: #6b7280; }
  .badge-err { background: #fee2e2; color: #991b1b; }
  .remarks { background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 6px 8px; }
  .measurements { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
  .meas-box { border: 1px solid #e5e5e5; border-radius: 4px; padding: 4px 6px; }
  .meas-box .lbl { font-size: 9px; color: #999; }
  .meas-box .val { font-weight: 600; }
  .load-table { width: 100%; border-collapse: collapse; }
  .load-table th, .load-table td { border: 1px solid #e5e5e5; padding: 3px 6px; text-align: left; }
  .load-table th { background: #f9fafb; font-size: 10px; color: #666; }
  .footer { margin-top: 20px; border-top: 1px solid #e5e5e5; padding-top: 8px; font-size: 9px; color: #999; display: flex; justify-content: space-between; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style></head><body>
<div class="header">
  <div><h1>Servicebericht</h1><div style="font-size:12px;color:#555;margin-top:2px;">${deviceName}</div></div>
  <div class="meta">
    Datum: ${dateStr}<br>
    Techniker: ${entry.performed_by || "–"}<br>
    ${entry.hours_at_service != null ? "Betriebsstunden: " + entry.hours_at_service + " h<br>" : ""}
    ${entry.next_maintenance_months ? "Naechste Wartung: " + entry.next_maintenance_months + " Mon." + (entry.next_maintenance_hours ? " / " + entry.next_maintenance_hours + " h" : "") + "<br>" : ""}
  </div>
</div>
${mechHtml}${elecHtml}${measHtml}${ltHtml}${atsHtml}${diagHtml}${remarksHtml}${notesHtml}
<div class="footer"><span>Eventenergie Deutschland</span><span>Erstellt am ${new Date().toLocaleDateString("de-DE")} ${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span></div>
</body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 400);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid={`entry-${entry.id}`}>
      {/* Clickable header to expand/collapse */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-left hover:bg-gray-50 transition-colors"
        data-testid={`entry-toggle-${entry.id}`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-fuchsia-100 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-fuchsia-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">{entry.performed_by}</p>
              <p className="text-xs text-gray-400">
                {new Date(entry.performed_at).toLocaleDateString("de-DE")}
                {entry.hours_at_service != null && ` · ${entry.hours_at_service} h`}
                {entry.next_maintenance_months && ` · Nächste: ${entry.next_maintenance_months} Mon.`}
                {entry.next_maintenance_hours && ` / ${entry.next_maintenance_hours} h`}
                {!entry.next_maintenance_months && entry.next_maintenance_mode && entry.next_maintenance_value && (
                  <> · Nächste: {entry.next_maintenance_mode === "months" ? `${entry.next_maintenance_value} Mon.` : `${entry.next_maintenance_value} h`}</>
                )}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
            <span onClick={handlePrint} className="text-gray-400 hover:text-fuchsia-600 p-1" title="Bericht drucken / PDF" data-testid={`print-entry-${entry.id}`}><Printer className="w-4 h-4" /></span>
            {isAdmin && (
              <span onClick={e => { e.stopPropagation(); onDelete(entry.id); }} className="text-gray-400 hover:text-red-500 p-1" data-testid={`delete-entry-${entry.id}`}><Trash2 className="w-4 h-4" /></span>
            )}
          </div>
        </div>
      </button>

      {/* Collapsible content showing ALL sections */}
      {expanded && (
        <div className="border-t border-gray-200 p-4 bg-gray-50 text-xs space-y-4">
          {/* 1. Mechanische Prüfung - nur bei Vollplan */}
          {!reduced && Object.keys(mech).length > 0 && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">1. Mechanische Prüfung</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {Object.entries(mech).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-2 py-0.5">
                    <span className="text-gray-600">{k}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${statusCls[v] || "bg-gray-100 text-gray-400"}`}>{statusLabel[v] || v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. Elektrische Prüfung */}
          {Object.keys(elec).length > 0 && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">2. Elektrische Prüfung</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {Object.entries(elec).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-2 py-0.5">
                    <span className="text-gray-600">{k}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${statusCls[v] || "bg-gray-100 text-gray-400"}`}>{statusLabel[v] || v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. Generator Messwerte - nur bei Vollplan */}
          {!reduced && Object.values(meas).some(v => v) && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">3. Generator Messwerte</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(meas).filter(([_, v]) => v).map(([k, v]) => {
                  const lbl = MEASUREMENT_FIELDS.find(f => f.key === k)?.label || k;
                  return (
                    <div key={k} className="bg-white rounded px-2 py-1.5 border border-gray-200">
                      <span className="text-[10px] text-gray-400 block">{lbl}</span>
                      <span className="font-medium text-gray-700">{v}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 4. Lasttest Generator - nur bei Vollplan */}
          {!reduced && lt.length > 0 && lt.some(r => r.values) && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">4. Lasttest Generator</p>
              <div className="border border-gray-200 rounded overflow-hidden bg-white">
                <div className="grid grid-cols-3 bg-gray-100 px-2 py-1">
                  <span className="text-[10px] font-medium text-gray-500">Last</span>
                  <span className="text-[10px] font-medium text-gray-500">Lasttest</span>
                  <span className="text-[10px] font-medium text-gray-500">Bemerkungen</span>
                </div>
                {lt.map((r, i) => (
                  <div key={i} className="grid grid-cols-3 px-2 py-1 border-t border-gray-100">
                    <span className="text-gray-600">{r.load}</span>
                    <span className="text-gray-700">{r.values || "–"}</span>
                    <span className="text-gray-400">{r.remarks || "–"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. ATS / Netzumschaltung - nur bei Vollplan */}
          {!reduced && Object.keys(ats).filter(k => k !== "umschaltzeit").length > 0 && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">5. ATS / Netzumschaltung</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {ATS_ITEMS.map(a => {
                  const val = ats[a.key];
                  if (!val) return null;
                  return (
                    <div key={a.key} className="flex items-center justify-between gap-2 py-0.5">
                      <span className="text-gray-600">{a.label}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${
                        val === true || val === "durchgefuehrt" ? "bg-emerald-100 text-emerald-700" :
                        val === "nicht_vorhanden" ? "bg-amber-100 text-amber-700" :
                        val === "nicht_durchgefuehrt" ? "bg-gray-100 text-gray-500" :
                        val ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-400"
                      }`}>
                        {val === true ? "Durchgeführt" : statusLabel[val] || String(val)}
                      </span>
                    </div>
                  );
                })}
              </div>
              {ats.umschaltzeit && <div className="mt-1.5 text-gray-600">Umschaltzeit: <span className="font-medium text-gray-800">{ats.umschaltzeit}s</span></div>}
            </div>
          )}

          {/* 6. Diagnose */}
          {(diag.fehlerspeicher_ausgelesen || diag.keine_fehler || diag.fehler_vorhanden) && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">6. Diagnose</p>
              <div className="space-y-1">
                {[
                  { key: "fehlerspeicher_ausgelesen", label: "Fehlerspeicher ausgelesen" },
                  { key: "keine_fehler", label: "Keine Fehler vorhanden" },
                  { key: "fehler_vorhanden", label: "Fehler vorhanden" },
                ].map(item => {
                  const val = diag[item.key];
                  if (!val) return null;
                  return (
                    <div key={item.key} className="flex items-center justify-between gap-2 py-0.5">
                      <span className={`text-gray-600 ${item.key === "fehler_vorhanden" && (val === true || val === "durchgefuehrt") ? "text-red-600 font-medium" : ""}`}>{item.label}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${
                        val === true || val === "durchgefuehrt" ? (item.key === "fehler_vorhanden" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700") :
                        val === "nicht_vorhanden" ? "bg-amber-100 text-amber-700" :
                        "bg-gray-100 text-gray-500"
                      }`}>
                        {val === true ? "Ja" : statusLabel[val] || String(val)}
                      </span>
                    </div>
                  );
                })}
              </div>
              {diag.fehlercodes && <div className="mt-1.5 bg-white p-2 rounded border border-red-200 text-red-700">{diag.fehlercodes}</div>}
            </div>
          )}

          {/* Bemerkungen & Notizen */}
          {entry.remarks && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-xs font-medium text-amber-700 mb-0.5">Bemerkungen</p>
              <p className="text-xs text-amber-800">{entry.remarks}</p>
            </div>
          )}
          {entry.notes && (
            <div>
              <p className="font-semibold text-gray-700 mb-1">Notizen</p>
              <p className="text-gray-600">{entry.notes}</p>
            </div>
          )}

          {/* Anhänge (Fotos & Dokumente) */}
          {((entry.attachments && entry.attachments.length > 0) || images.length > 0) && (
            <div>
              <p className="font-semibold text-gray-700 mb-2">Anhänge</p>
              <div className="flex flex-wrap gap-2">
                {entry.attachments && entry.attachments.length > 0 ? (
                  entry.attachments.map(att => {
                    const isPdf = att.content_type === "application/pdf";
                    return isPdf ? (
                      <a key={att.id} href={`${BACKEND_URL}/api/serviceplan/images/${att.id}`} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-red-200 bg-red-50 hover:border-red-400 transition-colors" data-testid={`att-pdf-${att.id}`}>
                        <FileText className="w-4 h-4 text-red-500 shrink-0" />
                        <span className="text-[11px] text-red-700 font-medium truncate max-w-[120px]">{att.filename}</span>
                        <Download className="w-3 h-3 text-red-400 shrink-0" />
                      </a>
                    ) : (
                      <a key={att.id} href={`${BACKEND_URL}/api/serviceplan/images/${att.id}`} target="_blank" rel="noopener noreferrer"
                        className="block w-16 h-16 rounded-lg overflow-hidden border border-gray-200 hover:border-fuchsia-400">
                        <img src={`${BACKEND_URL}/api/serviceplan/images/${att.id}`} alt="" className="w-full h-full object-cover" />
                      </a>
                    );
                  })
                ) : (
                  images.map(imgId => (
                    <a key={imgId} href={`${BACKEND_URL}/api/serviceplan/images/${imgId}`} target="_blank" rel="noopener noreferrer" className="block w-16 h-16 rounded-lg overflow-hidden border border-gray-200 hover:border-fuchsia-400">
                      <img src={`${BACKEND_URL}/api/serviceplan/images/${imgId}`} alt="" className="w-full h-full object-cover" />
                    </a>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============== Detail View ==============
function ServicePlanDetail({ plan, onBack, onUpdate }) {
  const { isAdmin } = useAuth();
  const [entries, setEntries] = useState([]);
  const [planDetail, setPlanDetail] = useState(plan);
  const [loading, setLoading] = useState(true);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [deviceParts, setDeviceParts] = useState([]);
  const [deviceDocs, setDeviceDocs] = useState([]);
  const [deviceFaults, setDeviceFaults] = useState([]);
  const [expandedFault, setExpandedFault] = useState(null);

  const loadDetail = useCallback(async () => {
    try {
      const res = await api.get(`/serviceplan/${plan.id}`);
      setPlanDetail(res.data);
      setEntries(res.data.entries || []);
      const deviceId = res.data.device_id;
      if (deviceId) {
        const [partsRes, docsRes, faultsRes] = await Promise.all([
          api.get(`/devices/${deviceId}/parts`).catch(() => ({ data: [] })),
          api.get(`/devices/${deviceId}/documents`).catch(() => ({ data: [] })),
          api.get(`/serviceplan/fault-reports?device_id=${deviceId}`).catch(() => ({ data: [] })),
        ]);
        setDeviceParts(partsRes.data);
        setDeviceDocs(docsRes.data);
        setDeviceFaults(faultsRes.data);
      }
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, [plan.id]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  const handleSaveEntry = async (data, images) => {
    try {
      const res = await api.post(`/serviceplan/${plan.id}/entries`, data);
      const entryId = res.data.id;
      if (images && images.length > 0) {
        for (const img of images) {
          const fd = new FormData(); fd.append("file", img);
          await api.post(`/serviceplan/${plan.id}/entries/${entryId}/images`, fd, { headers: { "Content-Type": "multipart/form-data" } });
        }
      }
      toast.success("Wartungseintrag gespeichert");
      setShowAddEntry(false);
      loadDetail();
      onUpdate();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const handleDeleteEntry = async (entryId) => {
    try {
      await api.delete(`/serviceplan/${plan.id}/entries/${entryId}`);
      toast.success("Eintrag gelöscht");
      loadDetail(); onUpdate();
    } catch { toast.error("Fehler"); }
  };

  const status = getServiceStatus(planDetail);
  const currentHrs = planDetail.current_hours || 0;
  const lastServiceHrs = planDetail.latest_entry?.hours_at_service || 0;
  const hrsUntilNext = (planDetail.interval_hours || 500) - (currentHrs - lastServiceHrs);

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-gray-500 hover:text-fuchsia-600 mb-4" data-testid="back-to-list">
        <ChevronLeft className="w-4 h-4" /> Zurück zur Übersicht
      </button>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6" data-testid="plan-detail-header">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            {planDetail.device_id && (
              <img
                src={`${BACKEND_URL}/api/devices/${planDetail.device_id}/image`}
                alt=""
                className="w-16 h-16 rounded-lg object-cover border border-gray-200 flex-shrink-0"
                onError={e => { e.target.style.display = "none"; }}
                data-testid="plan-device-image"
              />
            )}
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{planDetail.device_serial}</h2>
              <p className="text-sm text-gray-500">{TYPE_LABELS[planDetail.device_type] || planDetail.device_type} · {planDetail.device_model || "–"} · {planDetail.device_user_field || "–"}</p>
            </div>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>{status.label}</div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
          <div><p className="text-xs text-gray-400">Akt. Betriebsstunden</p><p className="text-sm font-bold text-gray-900">{currentHrs || "–"} h</p></div>
          <div><p className="text-xs text-gray-400">Stunden bis Wartung</p><p className={`text-sm font-bold ${hrsUntilNext <= 50 ? "text-amber-600" : hrsUntilNext <= 0 ? "text-red-600" : "text-gray-900"}`}>{planDetail.latest_entry ? `${hrsUntilNext} h` : "–"}</p></div>
          <div><p className="text-xs text-gray-400">Intervall</p><p className="text-sm font-medium text-gray-900">{planDetail.interval_hours || "–"} h / {planDetail.interval_months || "–"} Mon.</p></div>
          <div><p className="text-xs text-gray-400">Letzter Service</p><p className="text-sm font-medium text-gray-900">{planDetail.latest_entry ? new Date(planDetail.latest_entry.performed_at).toLocaleDateString("de-DE") : "–"}</p></div>
        </div>
      </div>

      {/* Ersatzteile Section */}
      {deviceParts.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4" data-testid="plan-parts-section">
          <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2"><Wrench className="w-4 h-4 text-fuchsia-500" /> Ersatzteile ({deviceParts.length})</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {deviceParts.map(part => (
              <div key={part.id} className="flex items-center gap-2 py-1.5 px-3 bg-gray-50 rounded-lg text-sm">
                <span className="font-medium text-gray-800">{part.part_type}</span>
                {part.part_number && <span className="text-gray-400 font-mono text-xs">{part.part_number}</span>}
                {part.liters != null && <span className="text-fuchsia-600 text-xs">{part.liters} L</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dateiablage Button */}
      {deviceDocs.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6" data-testid="plan-docs-section">
          <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2"><FileText className="w-4 h-4 text-fuchsia-500" /> Dateiablage ({deviceDocs.length})</h3>
          <div className="space-y-1.5">
            {deviceDocs.map(doc => (
              <button
                key={doc.id}
                onClick={async () => {
                  try {
                    const res = await api.get(`/devices/${planDetail.device_id}/documents/${doc.id}/download`, { responseType: "blob" });
                    const url = window.URL.createObjectURL(new Blob([res.data]));
                    const ct = res.headers["content-type"] || "";
                    if (ct.startsWith("image/") || ct === "application/pdf") {
                      window.open(url, "_blank");
                    } else {
                      const a = document.createElement("a");
                      a.href = url; a.download = doc.filename || "dokument"; a.click();
                    }
                    setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                  } catch { toast.error("Fehler beim Öffnen der Datei"); }
                }}
                className="w-full flex items-center gap-2 py-2 px-3 bg-gray-50 rounded-lg text-sm text-gray-700 hover:bg-fuchsia-50 hover:text-fuchsia-600 transition-colors text-left"
                data-testid={`plan-doc-${doc.id}`}
              >
                <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <span className="truncate">{doc.filename}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Ereignisprotokoll */}
      {planDetail.device_id && (
        <div className="mb-6" data-testid="serviceplan-event-log">
          <EventLog deviceId={planDetail.device_id} compact />
        </div>
      )}

      {/* Störmeldungen für dieses Gerät */}
      {deviceFaults.length > 0 && (
        <div className="mb-6" data-testid="device-fault-reports">
          <h3 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            Störmeldungen ({deviceFaults.length})
          </h3>
          <div className="space-y-2">
            {deviceFaults.map(fr => {
              const isExpanded = expandedFault === fr.id;
              const statusColors = { offen: "bg-red-100 text-red-700 border-red-200", in_arbeit: "bg-amber-100 text-amber-700 border-amber-200", erledigt: "bg-emerald-100 text-emerald-700 border-emerald-200" };
              const statusLabels = { offen: "Offen", in_arbeit: "In Arbeit", erledigt: "Erledigt" };
              return (
                <div key={fr.id} className={`bg-white border rounded-lg overflow-hidden ${fr.status === "offen" ? "border-red-300" : fr.status === "in_arbeit" ? "border-amber-300" : "border-gray-200"}`}>
                  <button onClick={() => setExpandedFault(isExpanded ? null : fr.id)} className="w-full p-3 flex items-center justify-between text-left hover:bg-gray-50 transition-all" data-testid={`fault-detail-${fr.id}`}>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${statusColors[fr.status]}`}>{statusLabels[fr.status]}</span>
                      <div>
                        <p className="text-sm text-gray-900">{fr.description.length > 60 ? fr.description.slice(0, 60) + "..." : fr.description}</p>
                        <p className="text-[10px] text-gray-400">{new Date(fr.reported_at).toLocaleDateString("de-DE")} · {fr.reported_by_name}</p>
                      </div>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 border-t border-gray-100 pt-2 space-y-2">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div><span className="text-gray-400">Gemeldet von:</span> <span className="text-gray-700 font-medium">{fr.reported_by_name}</span></div>
                        <div><span className="text-gray-400">Datum:</span> <span className="text-gray-700">{new Date(fr.reported_at).toLocaleString("de-DE")}</span></div>
                        {fr.order_name && <div><span className="text-gray-400">Auftrag:</span> <span className="text-gray-700">{fr.order_name}</span></div>}
                        {fr.lock_device && <div><span className="text-gray-400">Gerät:</span> <span className="text-red-600 font-semibold">Gesperrt</span></div>}
                      </div>
                      <div className="bg-gray-50 rounded p-2">
                        <p className="text-xs text-gray-400 mb-0.5">Fehlerbeschreibung:</p>
                        <p className="text-sm text-gray-800">{fr.description}</p>
                      </div>
                      {fr.repair_description && (
                        <div className="bg-emerald-50 rounded p-2 border border-emerald-200">
                          <p className="text-xs text-emerald-600 mb-0.5">Reparatur:</p>
                          <p className="text-sm text-emerald-800">{fr.repair_description}</p>
                          <p className="text-[10px] text-emerald-500 mt-1">Von {fr.repaired_by_name} am {new Date(fr.repaired_at).toLocaleString("de-DE")}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">Wartungshistorie</h3>
        {!showAddEntry && (
          <Button size="sm" onClick={() => setShowAddEntry(true)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="add-entry-btn">
            <Plus className="w-3.5 h-3.5 mr-1" /> Neue Wartung anlegen
          </Button>
        )}
      </div>

      {showAddEntry && <MaintenanceEntryForm planDetail={planDetail} onSave={handleSaveEntry} onCancel={() => setShowAddEntry(false)} />}

      {loading ? (
        <p className="text-gray-400 text-center py-8">Laden...</p>
      ) : entries.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
          <Clock className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Noch keine Wartungseinträge vorhanden</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map(entry => <EntryCard key={entry.id} entry={entry} planId={plan.id} planDetail={planDetail} isAdmin={isAdmin} onDelete={handleDeleteEntry} deviceType={planDetail?.device_type} />)}
        </div>
      )}
    </div>
  );
}

// ============== Main Page ==============
export default function ServiceplanPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [devices, setDevices] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState(null);
  const [showQrScanner, setShowQrScanner] = useState(false);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [activeTab, setActiveTab] = useState("wartung"); // wartung | reparatur
  const [faultReports, setFaultReports] = useState([]);
  const [showFaultModal, setShowFaultModal] = useState(false);
  const [showRepairModal, setShowRepairModal] = useState(null); // fault report to repair
  const [orders, setOrders] = useState([]);

  const loadData = useCallback(async () => {
    try {
      const [devRes, planRes, faultRes] = await Promise.all([
        api.get("/devices"),
        api.get("/serviceplan"),
        api.get("/serviceplan/fault-reports"),
      ]);
      setDevices(devRes.data.filter(d => d.status !== "ausser_betrieb"));
      setPlans(planRes.data);
      setFaultReports(faultRes.data);
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      const res = await api.get("/orders/epirent");
      const arr = Array.isArray(res.data) ? res.data : (res.data.orders || []);
      // Nur aktive Auftraege, nicht archiviert/storniert; neueste zuerst
      const active = arr.filter(o => !o.is_archived && !o.is_canceled);
      active.sort((a, b) => String(b.dispo_start || "").localeCompare(String(a.dispo_start || "")));
      setOrders(active);
    } catch { /* orders optional */ }
  }, []);

  useEffect(() => { loadData(); loadOrders(); }, [loadData, loadOrders]);

  const devicesWithPlans = devices.map(d => ({ ...d, plan: plans.find(p => p.device_id === d.id) }));
  const filtered = devicesWithPlans.filter(d => {
    // Search filter
    if (search) {
      const q = search.toLowerCase();
      const match = (d.serial_number || "").toLowerCase().includes(q) || (d.model || "").toLowerCase().includes(q) || (d.user_field || "").toLowerCase().includes(q) || (d.device_code || "").toLowerCase().includes(q);
      if (!match) return false;
    }
    // Category filter
    if (categoryFilter && d.device_type !== categoryFilter) return false;
    // Status filter
    if (statusFilter) {
      const st = d.plan ? getServiceStatus(d.plan) : null;
      if (statusFilter === "einsatzbereit") return d.plan && st && st.label === "OK";
      if (statusFilter === "bald_faellig") return d.plan && st && st.label === "Bald fällig";
      if (statusFilter === "ueberfaellig") return d.plan && st && st.label === "Überfällig";
    }
    return true;
  });

  const handleQrScan = (scannedText) => {
    setShowQrScanner(false);
    const code = scannedText.trim();
    // Find device by device_code (use devicesWithPlans to access plan info)
    const found = devicesWithPlans.find(d => (d.device_code || "").toUpperCase() === code.toUpperCase());
    if (found) {
      if (found.plan) {
        // Plan exists → open it directly
        setSelectedPlan(found.plan);
        toast.success(`${found.serial_number} - Serviceplan geöffnet`);
      } else {
        // No plan → create one and open it
        handleCreatePlanForDevice(found.id);
      }
    } else {
      toast.error(`Kein Gerät mit Code "${code}" gefunden`);
      setSearch(code);
    }
  };

  const handleCreatePlanForDevice = async (deviceId) => {
    if (creatingPlan) return;
    setCreatingPlan(true);
    try {
      const res = await api.post("/serviceplan", {
        device_id: deviceId,
        current_hours: 0,
        interval_hours: 500,
        interval_months: 12,
        tasks: [],
      });
      toast.success("Wartungsplan erstellt");
      setSelectedPlan(res.data);
      loadData();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler beim Erstellen")); }
    finally { setCreatingPlan(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="serviceplan-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn"><ArrowLeft className="w-4 h-4 mr-1" /> Zurück</Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Serviceplan</h1>
            {/* Tabs */}
            <div className="flex gap-1 ml-4 bg-gray-100 rounded-lg p-0.5">
              <button onClick={() => setActiveTab("wartung")} className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${activeTab === "wartung" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`} data-testid="tab-wartung">Wartung</button>
              <button onClick={() => setActiveTab("reparatur")} className={`px-3 py-1 rounded-md text-xs font-medium transition-all relative ${activeTab === "reparatur" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`} data-testid="tab-reparatur">
                Reparatur
                {faultReports.filter(f => f.status !== "erledigt").length > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">{faultReports.filter(f => f.status !== "erledigt").length}</span>
                )}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => { setShowFaultModal(true); }} className="bg-red-500 hover:bg-red-600 text-white text-xs" data-testid="create-fault-btn">
              <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Störmeldung
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {selectedPlan ? (
          <ServicePlanDetail plan={selectedPlan} onBack={() => { setSelectedPlan(null); loadData(); }} onUpdate={loadData} />
        ) : activeTab === "reparatur" ? (
          /* ============== REPARATUR TAB ============== */
          <div data-testid="reparatur-tab">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Störmeldungen & Reparaturen</h2>
            {faultReports.length === 0 ? (
              <div className="text-center py-16"><AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-4" /><p className="text-gray-500">Keine Störmeldungen vorhanden</p></div>
            ) : (
              <div className="space-y-3">
                {faultReports.map(fr => {
                  const statusColors = { offen: "bg-red-100 text-red-700", in_arbeit: "bg-amber-100 text-amber-700", erledigt: "bg-emerald-100 text-emerald-700" };
                  const statusLabels = { offen: "Offen", in_arbeit: "In Arbeit", erledigt: "Erledigt" };
                  return (
                    <div key={fr.id} className={`bg-white border rounded-lg p-4 ${fr.status === "offen" ? "border-red-300" : fr.status === "in_arbeit" ? "border-amber-300" : "border-gray-200"}`} data-testid={`fault-${fr.id}`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${statusColors[fr.status]}`}>{statusLabels[fr.status]}</span>
                            {fr.lock_device && <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-800 text-white">Gesperrt</span>}
                          </div>
                          <p className="text-sm font-medium text-gray-900">{fr.device_serial} <span className="text-gray-400 font-normal">({fr.device_type})</span></p>
                          {fr.order_name && <p className="text-xs text-gray-500">Auftrag: {fr.order_name}</p>}
                          <p className="text-sm text-gray-700 mt-1">{fr.description}</p>
                          <p className="text-[10px] text-gray-400 mt-1">Gemeldet von {fr.reported_by_name} am {new Date(fr.reported_at).toLocaleString("de-DE")}</p>
                          {fr.repair_description && (
                            <div className="mt-2 p-2 bg-emerald-50 rounded border border-emerald-200">
                              <p className="text-xs font-medium text-emerald-700">Reparatur:</p>
                              <p className="text-sm text-emerald-800">{fr.repair_description}</p>
                              <p className="text-[10px] text-emerald-600">Von {fr.repaired_by_name} am {new Date(fr.repaired_at).toLocaleString("de-DE")}</p>
                            </div>
                          )}
                        </div>
                        {fr.status !== "erledigt" && (
                          <Button size="sm" variant="outline" onClick={() => setShowRepairModal(fr)} className="ml-4 text-xs flex-shrink-0" data-testid={`repair-btn-${fr.id}`}>
                            <Wrench className="w-3.5 h-3.5 mr-1" /> Reparatur eintragen
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Search + QR Scanner */}
            <div className="mb-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input type="text" placeholder="Gerät suchen (Seriennummer, Modell, Bezeichnung)..." value={search} onChange={e => setSearch(e.target.value)} className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500" data-testid="service-search" />
                </div>
                <Button
                  variant="outline"
                  onClick={() => setShowQrScanner(!showQrScanner)}
                  className={`px-3 flex-shrink-0 ${showQrScanner ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-600" : "text-gray-600"}`}
                  data-testid="qr-scan-btn"
                  title="QR-Code scannen"
                >
                  <ScanLine className="w-5 h-5" />
                </Button>
              </div>

              {/* QR Scanner Inline */}
              {showQrScanner && (
                <div className="mt-3 bg-white border border-fuchsia-200 rounded-lg p-4" data-testid="qr-scanner-inline">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-gray-700">Geräte-QR scannen</p>
                    <button onClick={() => setShowQrScanner(false)} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
                  </div>
                  <div className="max-w-sm mx-auto">
                    <QrScanner
                      onScan={handleQrScan}
                      onClose={() => setShowQrScanner(false)}
                    />
                    <p className="text-xs text-gray-400 text-center mt-2">QR-Code auf dem Geräte-Etikett scannen</p>
                  </div>
                </div>
              )}
            </div>

            {/* Category Filter Tabs */}
            <div className="flex gap-2 mb-4 overflow-x-auto scrollbar-hide pb-1" data-testid="category-tabs">
              {[
                { key: null, label: "Alle", count: devicesWithPlans.length },
                { key: "stromerzeuger", label: "Stromerzeuger", count: devicesWithPlans.filter(d => d.device_type === "stromerzeuger").length },
                { key: "lichtmast", label: "Lichtmasten", count: devicesWithPlans.filter(d => d.device_type === "lichtmast").length },
                { key: "kirmeskiste", label: "Kirmeskisten", count: devicesWithPlans.filter(d => d.device_type === "kirmeskiste").length },
                { key: "verteiler", label: "Verteiler", count: devicesWithPlans.filter(d => d.device_type === "verteiler").length },
                { key: "messkoffer", label: "Messkoffer", count: devicesWithPlans.filter(d => d.device_type === "messkoffer").length },
              ].map(tab => (
                <button
                  key={tab.key || "alle"}
                  onClick={() => setCategoryFilter(categoryFilter === tab.key ? null : tab.key)}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    categoryFilter === tab.key
                      ? "bg-fuchsia-600 text-white shadow-sm"
                      : "bg-white border border-gray-200 text-gray-600 hover:border-fuchsia-300"
                  }`}
                  data-testid={`cat-${tab.key || "alle"}`}
                >
                  {tab.label} <span className="ml-1 opacity-70">({tab.count})</span>
                </button>
              ))}
            </div>

            {plans.length > 0 && (
              <div className="grid grid-cols-4 gap-3 mb-6">
                {(() => {
                  const catPlans = categoryFilter ? plans.filter(p => { const d = devices.find(dev => dev.id === p.device_id); return d && d.device_type === categoryFilter; }) : plans;
                  return (
                    <>
                    <button onClick={() => setStatusFilter(statusFilter === "einsatzbereit" ? null : "einsatzbereit")} className={`bg-white border rounded-lg p-4 text-center transition-all ${statusFilter === "einsatzbereit" ? "border-emerald-400 ring-2 ring-emerald-100" : "border-gray-200 hover:border-emerald-300"}`} data-testid="filter-einsatzbereit">
                      <p className="text-2xl font-bold text-emerald-600">{catPlans.filter(p => getServiceStatus(p).label === "OK").length}</p>
                      <p className="text-xs text-gray-500">Einsatzbereit</p>
                    </button>
                    <button onClick={() => setStatusFilter(statusFilter === "bald_faellig" ? null : "bald_faellig")} className={`bg-white border rounded-lg p-4 text-center transition-all ${statusFilter === "bald_faellig" ? "border-amber-400 ring-2 ring-amber-100" : "border-gray-200 hover:border-amber-300"}`} data-testid="filter-bald-faellig">
                      <p className="text-2xl font-bold text-amber-600">{catPlans.filter(p => getServiceStatus(p).label === "Bald fällig").length}</p>
                      <p className="text-xs text-gray-500">Bald fällig</p>
                    </button>
                    <button onClick={() => setStatusFilter(statusFilter === "ueberfaellig" ? null : "ueberfaellig")} className={`bg-white border rounded-lg p-4 text-center transition-all ${statusFilter === "ueberfaellig" ? "border-red-400 ring-2 ring-red-100" : "border-gray-200 hover:border-red-300"}`} data-testid="filter-ueberfaellig">
                      <p className="text-2xl font-bold text-red-600">{catPlans.filter(p => getServiceStatus(p).label === "Überfällig").length}</p>
                      <p className="text-xs text-gray-500">Überfällig</p>
                    </button>
                    <button onClick={() => setStatusFilter(null)} className={`bg-white border rounded-lg p-4 text-center transition-all ${statusFilter === null ? "border-fuchsia-400 ring-2 ring-fuchsia-100" : "border-gray-200 hover:border-fuchsia-300"}`} data-testid="filter-gesamt">
                      <p className="text-2xl font-bold text-gray-900">{catPlans.length}</p>
                      <p className="text-xs text-gray-500">Gesamt</p>
                    </button>
                    </>
                  );
                })()}
              </div>
            )}

            {loading ? (
              <div className="text-center py-20 text-gray-400">Laden...</div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16"><Wrench className="w-12 h-12 text-gray-300 mx-auto mb-4" /><p className="text-gray-500">{devices.length === 0 ? "Keine aktiven Geräte vorhanden" : "Keine Treffer"}</p></div>
            ) : (
              <div className="space-y-2" data-testid="device-plan-list">
                {filtered.map(d => {
                  const status = d.plan ? getServiceStatus(d.plan) : null;
                  const hasImage = d.image_gridfs_id;
                  return (
                    <button key={d.id} className="w-full flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-fuchsia-400 hover:shadow-sm transition-all text-left group" data-testid={`sp-device-${d.serial_number}`}
                      onClick={() => {
                        if (d.plan) { setSelectedPlan(d.plan); }
                        else { handleCreatePlanForDevice(d.id); }
                      }}>
                      <div className="flex items-center gap-4">
                        {hasImage ? (
                          <img src={`${BACKEND_URL}/api/devices/${d.id}/image`} alt="" className="w-10 h-10 rounded-lg object-cover flex-shrink-0 border border-gray-200" />
                        ) : (
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${d.plan ? status.bg : "bg-gray-100"}`}>
                            {d.plan ? (status.label === "Überfällig" ? <AlertTriangle className={`w-5 h-5 ${status.color}`} /> : <Wrench className={`w-5 h-5 ${status.color}`} />) : <Plus className="w-5 h-5 text-gray-400" />}
                          </div>
                        )}
                        <div>
                          <p className="text-sm font-medium text-gray-900">{d.serial_number}</p>
                          <p className="text-xs text-gray-400">{TYPE_LABELS[d.device_type] || d.device_type} · {d.model || "–"} · {d.user_field || "–"}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {d.plan ? (
                          <div className="text-right">
                            <p className={`text-xs font-medium ${status.color}`}>{status.label}</p>
                            <p className="text-[10px] text-gray-400">{d.plan.latest_entry ? `Letzter Service: ${new Date(d.plan.latest_entry.performed_at).toLocaleDateString("de-DE")}` : "Kein Eintrag"}</p>
                            <p className="text-[10px] text-gray-400">{d.plan.interval_hours}h / {d.plan.interval_months} Mon.</p>
                          </div>
                        ) : <span className="text-xs text-fuchsia-500 font-medium">Neue Wartung anlegen</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* ============== STÖRMELDUNG MODAL ============== */}
      {showFaultModal && (
        <FaultReportModal
          devices={devices}
          orders={orders}
          user={user}
          onClose={() => setShowFaultModal(false)}
          onSaved={() => { setShowFaultModal(false); loadData(); setActiveTab("reparatur"); }}
        />
      )}

      {/* ============== REPARATUR MODAL ============== */}
      {showRepairModal && (
        <RepairModal
          report={showRepairModal}
          onClose={() => setShowRepairModal(null)}
          onSaved={() => { setShowRepairModal(null); loadData(); }}
        />
      )}
    </div>
  );
}


// ============== Störmeldung Modal ==============
function FaultReportModal({ devices, orders, user, onClose, onSaved }) {
  const [deviceId, setDeviceId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [orderName, setOrderName] = useState("");
  const [description, setDescription] = useState("");
  const [lockDevice, setLockDevice] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deviceSearch, setDeviceSearch] = useState("");

  const generators = devices.filter(d => ["stromerzeuger", "lichtmast"].includes(d.device_type));
  const filteredDevices = deviceSearch
    ? generators.filter(d => (d.serial_number || "").toLowerCase().includes(deviceSearch.toLowerCase()) || (d.model || "").toLowerCase().includes(deviceSearch.toLowerCase()))
    : generators;

  const handleSave = async () => {
    if (!deviceId) { toast.error("Bitte Maschine auswählen"); return; }
    if (!description.trim()) { toast.error("Bitte Fehlerbeschreibung eingeben"); return; }
    setSaving(true);
    try {
      await api.post("/serviceplan/fault-reports", {
        device_id: deviceId,
        order_id: orderId || null,
        order_name: orderName,
        description: description.trim(),
        lock_device: lockDevice,
      });
      toast.success("Störmeldung angelegt");
      onSaved();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="fault-modal">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-5 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Störmeldung anlegen</h2>
          <button onClick={onClose}><X className="w-5 h-5 text-gray-400 hover:text-gray-600" /></button>
        </div>
        <div className="p-5 space-y-4">
          {/* Auftrag */}
          <div>
            <Label className="text-gray-700 text-sm">Auftrag / Veranstaltung</Label>
            <select value={orderId} onChange={e => {
              setOrderId(e.target.value);
              const o = orders.find(o => String(o.primary_key || o.pk || o.id) === e.target.value);
              const label = o ? `${o.order_no || o.pk || ""} · ${o.event || o.contact_name || "Auftrag"}` : "";
              setOrderName(label);
            }} className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white" data-testid="fault-order-select">
              <option value="">Kein Auftrag zugeordnet</option>
              {orders.slice(0, 200).map(o => {
                const key = o.primary_key || o.pk || o.id;
                const label = `${o.order_no || o.pk || key} · ${o.event || o.contact_name || "Auftrag"}`;
                return <option key={key} value={key}>{label}</option>;
              })}
            </select>
          </div>

          {/* Maschine */}
          <div>
            <Label className="text-gray-700 text-sm">Maschine *</Label>
            <Input placeholder="Suchen..." value={deviceSearch} onChange={e => setDeviceSearch(e.target.value)} className="mt-1 mb-1" data-testid="fault-device-search" />
            <select value={deviceId} onChange={e => setDeviceId(e.target.value)} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white" size={Math.min(filteredDevices.length + 1, 6)} data-testid="fault-device-select">
              <option value="">Maschine wählen...</option>
              {filteredDevices.map(d => (
                <option key={d.id} value={d.id}>{d.serial_number} - {d.model || d.device_type}{d.status === "gesperrt" ? " [GESPERRT]" : ""}</option>
              ))}
            </select>
          </div>

          {/* Beschreibung */}
          <div>
            <Label className="text-gray-700 text-sm">Fehlerbeschreibung *</Label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Was ist passiert? Welcher Fehler liegt vor?" className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none" data-testid="fault-description" />
          </div>

          {/* Gerät sperren */}
          <label className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg cursor-pointer" data-testid="fault-lock-toggle">
            <input type="checkbox" checked={lockDevice} onChange={e => setLockDevice(e.target.checked)} className="w-4 h-4 rounded border-red-300 text-red-600 focus:ring-red-500" />
            <div>
              <span className="text-sm font-medium text-red-700">Gerät sperren</span>
              <p className="text-[10px] text-red-500">Maschine wird als "gesperrt" markiert und ist nicht mehr einsatzbereit</p>
            </div>
          </label>
        </div>
        <div className="p-5 border-t border-gray-200 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={saving} className="bg-red-500 hover:bg-red-600 text-white" data-testid="fault-save-btn">
            {saving ? "Wird gespeichert..." : "Störmeldung anlegen"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============== Reparatur Modal ==============
function RepairModal({ report, onClose, onSaved }) {
  const [repairDesc, setRepairDesc] = useState("");
  const [newStatus, setNewStatus] = useState(report.status === "offen" ? "in_arbeit" : "erledigt");
  const [unlockDevice, setUnlockDevice] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!repairDesc.trim() && newStatus === "erledigt") { toast.error("Bitte Reparatur-Beschreibung eingeben"); return; }
    setSaving(true);
    try {
      await api.put(`/serviceplan/fault-reports/${report.id}`, {
        status: newStatus,
        repair_description: repairDesc.trim() || null,
        lock_device: unlockDevice ? false : null,
      });
      toast.success(newStatus === "erledigt" ? "Reparatur abgeschlossen" : "Status aktualisiert");
      onSaved();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="repair-modal">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
        <div className="p-5 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Reparatur eintragen</h2>
          <button onClick={onClose}><X className="w-5 h-5 text-gray-400 hover:text-gray-600" /></button>
        </div>
        <div className="p-5 space-y-4">
          {/* Störmeldung Info */}
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-sm font-medium text-gray-900">{report.device_serial}</p>
            <p className="text-xs text-gray-500">{report.description}</p>
            <p className="text-[10px] text-gray-400 mt-1">Gemeldet von {report.reported_by_name} am {new Date(report.reported_at).toLocaleString("de-DE")}</p>
          </div>

          {/* Status */}
          <div>
            <Label className="text-gray-700 text-sm">Status</Label>
            <div className="flex gap-2 mt-1">
              {[
                { value: "in_arbeit", label: "In Arbeit", cls: "border-amber-400 bg-amber-50 text-amber-700" },
                { value: "erledigt", label: "Erledigt", cls: "border-emerald-400 bg-emerald-50 text-emerald-700" },
              ].map(s => (
                <button key={s.value} onClick={() => setNewStatus(s.value)}
                  className={`flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all ${newStatus === s.value ? s.cls + " ring-2 ring-offset-1" : "border-gray-200 text-gray-500"}`}
                  data-testid={`status-${s.value}`}
                >{s.label}</button>
              ))}
            </div>
          </div>

          {/* Reparatur-Beschreibung */}
          <div>
            <Label className="text-gray-700 text-sm">Was wurde gemacht?</Label>
            <textarea value={repairDesc} onChange={e => setRepairDesc(e.target.value)} rows={3} placeholder="Reparatur beschreiben..." className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none" data-testid="repair-description" />
          </div>

          {/* Gerät entsperren */}
          {report.lock_device && (
            <label className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg cursor-pointer" data-testid="repair-unlock-toggle">
              <input type="checkbox" checked={unlockDevice} onChange={e => setUnlockDevice(e.target.checked)} className="w-4 h-4 rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500" />
              <div>
                <span className="text-sm font-medium text-emerald-700">Gerät entsperren</span>
                <p className="text-[10px] text-emerald-500">Maschine wird wieder als "aktiv" markiert</p>
              </div>
            </label>
          )}
        </div>
        <div className="p-5 border-t border-gray-200 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={saving} className="bg-emerald-500 hover:bg-emerald-600 text-white" data-testid="repair-save-btn">
            {saving ? "Wird gespeichert..." : "Speichern"}
          </Button>
        </div>
      </div>
    </div>
  );
}
