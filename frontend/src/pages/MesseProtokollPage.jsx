import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, QrCode, Camera, Keyboard, Save, Loader2, Building2, User, Phone, Mail, MapPin, MessageSquare, Sparkles, X } from "lucide-react";
import api, { getErrorMsg } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Logo } from "../components/Logo";
import QrScanner from "../components/QrScanner";

const EMPTY = { company: "", first_name: "", last_name: "", position: "", phone: "", mobile: "", email: "", website: "",
  street: "", zip: "", city: "", country: "", interest: "", products: "", notes: "", follow_up_date: "", priority: "normal", source: "manuell" };

const PRIO = [["hoch", "Hoch – schnell melden"], ["normal", "Normal"], ["niedrig", "Niedrig"]];

function Feld({ label, k, form, set, type = "text", placeholder, testId }) {
  return (
    <div>
      <label className="text-xs text-gray-500">{label}</label>
      <Input type={type} value={form[k] || ""} onChange={e => set({ ...form, [k]: e.target.value })} placeholder={placeholder} className="h-10" data-testid={testId || `lead-${k}`} />
    </div>
  );
}

function Gruppe({ icon: Icon, titel, children }) {
  return (
    <section className="bg-white rounded-2xl border border-gray-200 p-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3"><Icon className="w-4 h-4 text-fuchsia-500" /> {titel}</h2>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </section>
  );
}

export default function MesseProtokollPage() {
  const { messeId } = useParams();
  const navigate = useNavigate();
  const [messe, setMesse] = useState(null);
  const [denied, setDenied] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [scan, setScan] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [count, setCount] = useState(0);
  const cam = useRef(null);

  useEffect(() => {
    api.get("/messe/my-active").then(r => {
      const m = r.data.find(x => x.id === messeId);
      if (!m) setDenied("Du bist dieser Messe nicht als Team zugeteilt oder die Messe läuft heute nicht.");
      else setMesse(m);
    }).catch(e => setDenied(getErrorMsg(e, "Messe nicht gefunden")));
    api.get(`/messe/${messeId}/leads`).then(r => setCount(r.data.leads.filter(l => l.created_by_name).length)).catch(() => {});
  }, [messeId]);

  const merge = (fields, source) => setForm(f => ({ ...f, ...Object.fromEntries(Object.entries(fields).filter(([, v]) => v)), source }));

  const onQr = async (text) => {
    setScan(false);
    try {
      const r = await api.post(`/messe/${messeId}/leads/parse-qr`, { text });
      merge(r.data.fields, "qr");
      toast.success("Kontakt aus QR-Code übernommen – bitte prüfen und ergänzen");
    } catch (e) { toast.error(getErrorMsg(e, "QR-Code konnte nicht gelesen werden")); }
  };

  const onCard = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.post(`/messe/${messeId}/leads/scan-card`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 90000 });
      merge(r.data.fields, "visitenkarte");
      toast.success("Visitenkarte gelesen – bitte prüfen und ergänzen");
    } catch (e) { toast.error(getErrorMsg(e, "Visitenkarte konnte nicht gelesen werden")); }
    finally { setBusy(false); if (cam.current) cam.current.value = ""; }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.post(`/messe/${messeId}/leads`, form);
      toast.success("Messeprotokoll gespeichert");
      setForm(EMPTY); setCount(c => c + 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) { toast.error(getErrorMsg(e, "Speichern fehlgeschlagen")); }
    finally { setSaving(false); }
  };

  const leer = Object.entries(form).every(([k, v]) => ["priority", "source"].includes(k) || !v);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="messe-protokoll-page">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
        <button onClick={() => navigate("/hub")} className="p-2 rounded-lg hover:bg-gray-100" data-testid="protokoll-back"><ArrowLeft className="w-5 h-5" /></button>
        <div className="flex-1 min-w-0">
          <h1 className="font-bold text-gray-900 truncate">Messeprotokoll</h1>
          {messe && <p className="text-xs text-gray-500 truncate">{messe.name}{messe.location ? ` · ${messe.location}` : ""} · {count} Kontakt(e) erfasst</p>}
        </div>
        <Logo size="small" />
      </header>

      <main className="max-w-3xl mx-auto p-4 space-y-4">
        {denied && <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-4 text-sm" data-testid="protokoll-denied">{denied}</div>}
        {messe && (
          <>
            <div className="grid grid-cols-3 gap-2">
              <button type="button" onClick={() => setScan(true)} className="h-20 rounded-2xl bg-gray-900 text-white flex flex-col items-center justify-center gap-1 text-xs font-semibold active:scale-[0.98]" data-testid="protokoll-scan-qr"><QrCode className="w-6 h-6" /> Kontakt-QR scannen</button>
              <button type="button" onClick={() => cam.current?.click()} disabled={busy} className="h-20 rounded-2xl bg-fuchsia-600 text-white flex flex-col items-center justify-center gap-1 text-xs font-semibold active:scale-[0.98] disabled:opacity-60" data-testid="protokoll-scan-card">
                {busy ? <Loader2 className="w-6 h-6 animate-spin" /> : <Camera className="w-6 h-6" />} {busy ? "wird gelesen …" : "Visitenkarte fotografieren"}
              </button>
              <button type="button" onClick={() => document.getElementById("lead-company")?.focus()} className="h-20 rounded-2xl bg-white border border-gray-300 text-gray-800 flex flex-col items-center justify-center gap-1 text-xs font-semibold active:scale-[0.98]" data-testid="protokoll-manual"><Keyboard className="w-6 h-6" /> Manuell eingeben</button>
              <input ref={cam} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => onCard(e.target.files?.[0])} data-testid="protokoll-card-input" />
            </div>
            {form.source !== "manuell" && <p className="text-xs text-fuchsia-700 flex items-center gap-1"><Sparkles className="w-3 h-3" /> Felder aus {form.source === "qr" ? "QR-Code" : "Visitenkarte"} übernommen – alles prüfbar und änderbar.</p>}

            <Gruppe icon={Building2} titel="Firma">
              <div className="sm:col-span-2"><label className="text-xs text-gray-500">Firma</label><Input id="lead-company" value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} className="h-10" data-testid="lead-company" /></div>
              <Feld label="Website" k="website" form={form} set={setForm} placeholder="www…" />
              <Feld label="Land" k="country" form={form} set={setForm} />
            </Gruppe>
            <Gruppe icon={User} titel="Ansprechpartner">
              <Feld label="Vorname" k="first_name" form={form} set={setForm} />
              <Feld label="Nachname" k="last_name" form={form} set={setForm} />
              <div className="sm:col-span-2"><Feld label="Position / Funktion" k="position" form={form} set={setForm} /></div>
            </Gruppe>
            <Gruppe icon={Phone} titel="Kontakt">
              <Feld label="Telefon" k="phone" form={form} set={setForm} type="tel" />
              <Feld label="Mobil" k="mobile" form={form} set={setForm} type="tel" />
              <div className="sm:col-span-2"><Feld label="E-Mail" k="email" form={form} set={setForm} type="email" /></div>
            </Gruppe>
            <Gruppe icon={MapPin} titel="Adresse">
              <div className="sm:col-span-2"><Feld label="Straße" k="street" form={form} set={setForm} /></div>
              <Feld label="PLZ" k="zip" form={form} set={setForm} />
              <Feld label="Ort" k="city" form={form} set={setForm} />
            </Gruppe>
            <Gruppe icon={MessageSquare} titel="Gespräch">
              <div className="sm:col-span-2"><Feld label="Interesse / Thema" k="interest" form={form} set={setForm} placeholder="z.B. Stromversorgung Kirmes, M-Box Lichtmast" /></div>
              <div className="sm:col-span-2"><Feld label="Produkte / Mengen" k="products" form={form} set={setForm} placeholder="z.B. 2× Lichtmast, 1× 100 kVA" /></div>
              <div className="sm:col-span-2">
                <label className="text-xs text-gray-500">Notizen</label>
                <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={4} className="w-full rounded-md border border-gray-300 p-2 text-sm" placeholder="Was wurde besprochen, was wünscht der Kunde?" data-testid="lead-notes" />
              </div>
              <Feld label="Wiedervorlage / Anruf am" k="follow_up_date" form={form} set={setForm} type="date" />
              <div>
                <label className="text-xs text-gray-500">Priorität</label>
                <select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })} className="w-full h-10 rounded-md border border-gray-300 px-2 text-sm bg-white" data-testid="lead-priority">
                  {PRIO.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
            </Gruppe>

            <div className="flex gap-2 sticky bottom-3">
              <Button variant="outline" onClick={() => setForm(EMPTY)} disabled={leer} className="h-12 bg-white" data-testid="lead-reset"><X className="w-4 h-4 mr-1" /> Verwerfen</Button>
              <Button onClick={save} disabled={saving || leer} className="flex-1 h-12 bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold shadow-lg" data-testid="lead-save">
                {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />} Protokoll speichern
              </Button>
            </div>
            <p className="text-[11px] text-gray-400 text-center">Keine Pflichtfelder. Alles landet unter Verwaltung → Messe → {messe.name} → Messe Kontaktformular.</p>
          </>
        )}
      </main>

      {scan && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" data-testid="protokoll-qr-overlay">
          <div className="bg-white rounded-2xl p-4 w-full max-w-md">
            <div className="flex items-center justify-between mb-2"><h3 className="font-semibold">Kontakt-QR des Besuchers scannen</h3><button onClick={() => setScan(false)} className="p-1" data-testid="protokoll-qr-close"><X className="w-5 h-5" /></button></div>
            <QrScanner onScan={onQr} onError={() => {}} onClose={() => setScan(false)} />
            <p className="text-xs text-gray-500 mt-2">Funktioniert mit vCard-/MeCard-QR-Codes (z.B. aus Kontakte-Apps oder Visitenkarten).</p>
          </div>
        </div>
      )}
    </div>
  );
}
