import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  ArrowLeft, Phone, RefreshCw, Search, CheckCircle2, AlertCircle,
  Clock, User, X, ExternalLink, FileText,
} from "lucide-react";

const PRIORITY_STYLES = {
  urgent: { bg: "bg-red-100", text: "text-red-700", label: "🚨 Notfall" },
  high:   { bg: "bg-amber-100", text: "text-amber-700", label: "Hoch" },
  normal: { bg: "bg-gray-100", text: "text-gray-600", label: "Normal" },
  low:    { bg: "bg-slate-100", text: "text-slate-500", label: "Niedrig" },
};

function CallDetailModal({ call, onClose, onDone }) {
  if (!call) return null;
  const p = PRIORITY_STYLES[call.priority] || PRIORITY_STYLES.normal;
  const payload = call.petra_full_payload || {};
  const q = payload.qualification || {};
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-5 border-b border-gray-200 flex items-start justify-between gap-3 sticky top-0 bg-white">
          <div className="flex-1 min-w-0">
            <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full ${p.bg} ${p.text} mb-2`}>{p.label}</span>
            <h2 className="text-lg font-semibold text-gray-900">{call.title}</h2>
            <p className="text-xs text-gray-500 mt-1">
              {call.caller_name || "Unbekannt"} · {call.caller_phone || "keine Tel."} · {new Date(call.created_at).toLocaleString("de-DE")}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" data-testid="close-call-detail"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4">
          {call.customer_name && (
            <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
              <User className="w-4 h-4 text-emerald-600" />
              <span className="text-sm text-emerald-900">Kunde erkannt: <strong>{call.customer_name}</strong></span>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Zusammenfassung</p>
            <p className="text-sm text-gray-800 whitespace-pre-wrap">{call.description || q.summary || "Keine Zusammenfassung von Petra hinterlegt."}</p>
          </div>
          {q.category && (
            <div className="grid grid-cols-2 gap-3">
              <div><p className="text-[10px] uppercase text-gray-400">Kategorie</p><p className="text-sm font-medium text-gray-900">{q.category}</p></div>
              {q.urgency && <div><p className="text-[10px] uppercase text-gray-400">Dringlichkeit</p><p className="text-sm font-medium text-gray-900">{q.urgency}</p></div>}
            </div>
          )}
          {call.petra_duration_seconds != null && (
            <div>
              <p className="text-[10px] uppercase text-gray-400">Anrufdauer</p>
              <p className="text-sm text-gray-800">{Math.floor(call.petra_duration_seconds / 60)}:{String(call.petra_duration_seconds % 60).padStart(2, "0")} min</p>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {call.petra_recording_url && (
              <a href={call.petra_recording_url} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1.5 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5"
                 data-testid="call-recording-link">
                <ExternalLink className="w-3.5 h-3.5" /> Aufnahme anhören
              </a>
            )}
            {call.petra_transcript_url && (
              <a href={call.petra_transcript_url} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1.5 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5"
                 data-testid="call-transcript-link">
                <FileText className="w-3.5 h-3.5" /> Volles Transkript
              </a>
            )}
            {call.caller_phone && (
              <a href={`tel:${call.caller_phone}`}
                 className="inline-flex items-center gap-1.5 text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg px-3 py-1.5"
                 data-testid="call-callback-link">
                <Phone className="w-3.5 h-3.5" /> Zurückrufen
              </a>
            )}
          </div>
        </div>
        <div className="p-4 border-t border-gray-200 flex items-center justify-between gap-3 sticky bottom-0 bg-white">
          <p className="text-xs text-gray-500">
            Status: <span className={call.status === "done" ? "text-emerald-600 font-medium" : "text-amber-600 font-medium"}>
              {call.status === "done" ? "Erledigt" : "Offen"}
            </span>
            {call.closed_by && <span className="text-gray-400"> · durch {call.closed_by}</span>}
          </p>
          {call.status !== "done" && (
            <Button onClick={() => onDone(call.id)} size="sm" className="bg-emerald-600 hover:bg-emerald-700" data-testid="mark-call-done">
              <CheckCircle2 className="w-4 h-4 mr-1.5" /> Als erledigt markieren
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TelefonPage() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState({ total: 0, open: 0, urgent_open: 0 });
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("open"); // open | all | urgent
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const r = await api.get("/hallopetra/calls", { params: { token, limit: 200, only_open: filter === "open" } });
      setCalls(r.data.calls || []);
      setStats({ total: r.data.total || 0, open: r.data.open || 0, urgent_open: r.data.urgent_open || 0 });
    } catch (e) {
      if (e?.response?.status === 403) {
        toast.error("Kein Zugriff auf Telefon-Übersicht");
        navigate("/hub");
      } else {
        toast.error("Fehler beim Laden");
      }
    } finally { setLoading(false); }
  }, [filter, navigate]);

  useEffect(() => { load(); }, [load]);

  const markDone = async (id) => {
    try {
      const token = localStorage.getItem("token");
      await api.post(`/hallopetra/calls/${id}/mark-done`, null, { params: { token } });
      toast.success("Anruf als erledigt markiert");
      setSelected(null);
      load();
    } catch { toast.error("Fehler"); }
  };

  const filteredCalls = calls.filter(c => {
    if (filter === "urgent" && c.priority !== "urgent") return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (c.title || "").toLowerCase().includes(q) ||
      (c.caller_name || "").toLowerCase().includes(q) ||
      (c.caller_phone || "").toLowerCase().includes(q) ||
      (c.description || "").toLowerCase().includes(q) ||
      (c.customer_name || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-rose-50 via-white to-white">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-3 sm:px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="telefon-back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="w-9 h-9 rounded-lg bg-rose-100 flex items-center justify-center flex-shrink-0">
            <Phone className="w-5 h-5 text-rose-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-gray-900 truncate">Telefon</h1>
            <p className="text-[11px] text-gray-500 hidden sm:block">Anrufe von Petra – qualifizierte Anfragen mit Zusammenfassung</p>
          </div>
          <Button onClick={load} disabled={loading} size="sm" variant="outline" data-testid="telefon-refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-3 sm:px-4 py-4 space-y-4">
        {/* Statistik-Kacheln */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <button onClick={() => setFilter("open")}
            className={`rounded-xl border p-3 text-left transition-all ${filter === "open" ? "bg-rose-50 border-rose-300 ring-2 ring-rose-200" : "bg-white border-gray-200 hover:border-rose-200"}`}
            data-testid="filter-open">
            <p className="text-[10px] uppercase font-semibold text-gray-500">Offen</p>
            <p className="text-2xl font-bold text-gray-900">{stats.open}</p>
          </button>
          <button onClick={() => setFilter("urgent")}
            className={`rounded-xl border p-3 text-left transition-all ${filter === "urgent" ? "bg-red-50 border-red-300 ring-2 ring-red-200" : "bg-white border-gray-200 hover:border-red-200"}`}
            data-testid="filter-urgent">
            <p className="text-[10px] uppercase font-semibold text-gray-500">🚨 Notfälle</p>
            <p className="text-2xl font-bold text-red-700">{stats.urgent_open}</p>
          </button>
          <button onClick={() => setFilter("all")}
            className={`rounded-xl border p-3 text-left transition-all ${filter === "all" ? "bg-gray-50 border-gray-400 ring-2 ring-gray-200" : "bg-white border-gray-200 hover:border-gray-300"}`}
            data-testid="filter-all">
            <p className="text-[10px] uppercase font-semibold text-gray-500">Alle</p>
            <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
          </button>
        </div>

        {/* Suche */}
        <div className="relative">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Suche nach Name, Nummer, Anliegen..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none text-sm bg-white"
            data-testid="telefon-search"
          />
        </div>

        {/* Anrufliste */}
        {filteredCalls.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <Phone className="w-10 h-10 mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">
              {loading ? "Lädt..." : search ? "Kein Anruf passt zur Suche." : filter === "urgent" ? "Keine offenen Notfälle 👍" : filter === "open" ? "Alle Anrufe erledigt!" : "Noch keine Anrufe von Petra."}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100 overflow-hidden">
            {filteredCalls.map(c => {
              const p = PRIORITY_STYLES[c.priority] || PRIORITY_STYLES.normal;
              const isEmergency = c.is_emergency;
              return (
                <button key={c.id} onClick={() => setSelected(c)}
                  className={`w-full text-left p-3 sm:p-4 hover:bg-gray-50 transition-colors flex items-start gap-3 ${isEmergency && c.status === "open" ? "bg-red-50/30" : ""}`}
                  data-testid={`call-row-${c.id}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${isEmergency ? "bg-red-100" : c.status === "done" ? "bg-emerald-100" : "bg-rose-100"}`}>
                    {c.status === "done" ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> :
                     isEmergency ? <AlertCircle className="w-5 h-5 text-red-600" /> :
                     <Phone className="w-5 h-5 text-rose-600" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <p className={`text-sm font-semibold ${isEmergency ? "text-red-800" : "text-gray-900"} truncate`}>{c.title}</p>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${p.bg} ${p.text} flex-shrink-0`}>{p.label}</span>
                      {c.status === "done" && <span className="text-[9px] font-semibold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full flex-shrink-0">Erledigt</span>}
                    </div>
                    <p className="text-[11px] text-gray-500 mb-1">
                      {c.caller_name || "Unbekannt"} · {c.caller_phone || "keine Tel."} · <Clock className="w-3 h-3 inline -mt-0.5" /> {new Date(c.created_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                      {c.customer_name && <span className="ml-1 text-emerald-600 font-medium">· 🎯 {c.customer_name}</span>}
                    </p>
                    {c.description && <p className="text-xs text-gray-600 line-clamp-2">{c.description}</p>}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <CallDetailModal call={selected} onClose={() => setSelected(null)} onDone={markDone} />
    </div>
  );
}
