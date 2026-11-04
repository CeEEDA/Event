import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Plus, Presentation, ChevronRight, Radio, Music } from "lucide-react";
import api, { getErrorMsg } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { MesseDetail } from "../components/messe/MesseDetail";

export default function MessePage() {
  const navigate = useNavigate();
  const [messen, setMessen] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [neu, setNeu] = useState(false);
  const [form, setForm] = useState({ name: "", location: "", start_date: "", end_date: "" });

  const load = useCallback(async () => {
    try {
      const r = await api.get("/messe");
      setMessen(r.data);
    } catch (e) {
      toast.error(getErrorMsg(e, "Messen nicht ladbar"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const anlegen = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error("Bitte einen Namen eingeben"); return; }
    try {
      const r = await api.post("/messe", form);
      toast.success("Messe angelegt");
      setNeu(false);
      setForm({ name: "", location: "", start_date: "", end_date: "" });
      await load();
      setSelected(r.data.id);
    } catch (err) {
      toast.error(getErrorMsg(err, "Anlegen fehlgeschlagen"));
    }
  };

  if (selected) {
    return <MesseDetail messeId={selected} onBack={() => { setSelected(null); load(); }} />;
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="messe-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")} className="text-gray-600 hover:text-fuchsia-600" data-testid="messe-back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <h1 className="text-base font-semibold text-gray-900 flex items-center gap-2"><Presentation className="w-4 h-4 text-fuchsia-600" /> Messe</h1>
          <div className="flex-1" />
          <Button size="sm" onClick={() => setNeu(v => !v)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="messe-new-btn">
            <Plus className="w-4 h-4 mr-1" /> Neue Messe
          </Button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {neu && (
          <form onSubmit={anlegen} className="bg-white border border-fuchsia-200 rounded-xl p-5 space-y-3" data-testid="messe-new-form">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="text-xs text-gray-500">Name der Messe *</label>
                <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="z.B. Interschau 2026" data-testid="messe-name-input" />
              </div>
              <div className="sm:col-span-2">
                <label className="text-xs text-gray-500">Ort / Halle / Stand</label>
                <Input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="Halle 4, Stand B12" data-testid="messe-location-input" />
              </div>
              <div>
                <label className="text-xs text-gray-500">Von</label>
                <Input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} data-testid="messe-start-input" />
              </div>
              <div>
                <label className="text-xs text-gray-500">Bis</label>
                <Input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} data-testid="messe-end-input" />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" onClick={() => setNeu(false)} data-testid="messe-new-cancel">Abbrechen</Button>
              <Button type="submit" className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="messe-new-submit">Anlegen</Button>
            </div>
          </form>
        )}

        {loading && <p className="text-sm text-gray-400 py-8 text-center">Laden …</p>}
        {!loading && messen.length === 0 && !neu && (
          <div className="text-center py-16" data-testid="messe-empty">
            <Presentation className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">Noch keine Messe angelegt.</p>
            <p className="text-sm text-gray-400 mt-1">Mit „Neue Messe“ einen Messeauftritt anlegen, M-Boxen zuordnen und QR-Codes drucken.</p>
          </div>
        )}
        {messen.map(m => (
          <button key={m.id} onClick={() => setSelected(m.id)} data-testid={`messe-item-${m.id}`}
            className="w-full bg-white border border-gray-200 rounded-xl p-5 flex items-center gap-4 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${m.active ? "bg-fuchsia-100 text-fuchsia-600" : "bg-gray-100 text-gray-400"}`}>
              <Presentation className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-base font-semibold text-gray-900 truncate">{m.name}{!m.active && <span className="ml-2 text-xs font-normal text-gray-400">(deaktiviert)</span>}</h2>
              <p className="text-sm text-gray-500 truncate">{[m.location, m.start_date && m.end_date ? `${m.start_date} – ${m.end_date}` : m.start_date].filter(Boolean).join(" · ") || "ohne Ort/Datum"}</p>
              <p className="text-xs text-gray-400 mt-1 flex items-center gap-3">
                <span className="flex items-center gap-1"><Radio className="w-3 h-3" /> {m.devices?.length || 0} M-Box(en)</span>
                <span className="flex items-center gap-1"><Music className="w-3 h-3" /> {m.audio_count || 0} Durchsage(n)</span>
              </p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-gray-600" />
          </button>
        ))}
      </main>
    </div>
  );
}
