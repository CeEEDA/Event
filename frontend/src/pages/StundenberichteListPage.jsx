import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Input } from "../components/ui/input";
import { ArrowLeft, ClipboardList, Search, Loader2, FileText, FileWarning, CheckCircle2, Clock } from "lucide-react";

const formatDate = (iso) => {
  if (!iso) return "—";
  // ISO datetime or YYYY-MM-DD
  const d = iso.length === 10 ? new Date(iso + "T00:00:00") : new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
};

export default function StundenberichteListPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("alle"); // alle | projekt | blanko

  useEffect(() => {
    if (!isAdmin) { navigate("/hub"); return; }
    (async () => {
      try {
        const { data } = await api.get("/project-reports");
        setReports(data || []);
      } catch {
        setReports([]);
      } finally { setLoading(false); }
    })();
  }, [isAdmin, navigate]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return reports.filter(r => {
      // Filter Projekt vs Blanko
      const isBlanko = !r.order_pk;
      if (filter === "projekt" && isBlanko) return false;
      if (filter === "blanko" && !isBlanko) return false;
      if (!q) return true;
      // Volltext: kunde, projektnummer, ort, order_name, bemerkungen, mitarbeiter, work_log
      const hay = [
        r.kunde_name,
        r.kunde_ort,
        r.projektnummer,
        r.order_name,
        r.order_pk,
        r.bemerkungen,
        r.created_by,
        ...(r.mitarbeiter || []).map(m => m.name),
        ...(r.work_log || []).map(w => w.beschreibung),
      ].filter(Boolean).join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [reports, search, filter]);

  const counts = useMemo(() => ({
    alle: reports.length,
    projekt: reports.filter(r => r.order_pk).length,
    blanko: reports.filter(r => !r.order_pk).length,
  }), [reports]);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="stundenberichte-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung/auswertung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <ClipboardList className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Stundenberichte</h1>
          <span className="ml-auto text-xs text-gray-400">{filtered.length} / {reports.length}</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-5">
        {/* Search + Filter */}
        <div className="bg-white border border-gray-200 rounded-xl p-3 mb-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <Input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Suche: Kunde, Projektnummer, Ort, Mitarbeiter, Arbeiten, Bemerkungen..."
              className="pl-9 h-10"
              data-testid="reports-search"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {[
              { key: "alle", label: "Alle", count: counts.alle },
              { key: "projekt", label: "Mit Projekt", count: counts.projekt },
              { key: "blanko", label: "Blanko", count: counts.blanko },
            ].map(t => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={`px-3 py-1.5 rounded-full border transition-colors ${
                  filter === t.key
                    ? "bg-fuchsia-600 border-fuchsia-600 text-white"
                    : "bg-white border-gray-200 text-gray-600 hover:border-fuchsia-300"
                }`}
                data-testid={`filter-${t.key}`}
              >
                {t.label} <span className="opacity-70">({t.count})</span>
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-7 h-7 animate-spin text-fuchsia-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-10 text-center text-gray-400" data-testid="reports-empty">
            <FileText className="w-10 h-10 mx-auto mb-3 text-gray-300" />
            {reports.length === 0 ? "Noch keine Projektberichte vorhanden." : "Keine Treffer für deine Suche."}
          </div>
        ) : (
          <div className="space-y-2" data-testid="reports-list">
            {filtered.map(r => {
              const isBlanko = !r.order_pk;
              const signed = !!r.unterschrift_kunde;
              const totalHours = (r.work_log || []).reduce((sum, wl) => {
                const stunden = wl.stunden || {};
                let s = 0;
                Object.values(stunden).forEach(person => {
                  Object.values(person || {}).forEach(v => { s += parseFloat(v) || 0; });
                });
                return sum + s;
              }, 0);
              const empNames = (r.mitarbeiter || []).map(m => m.name).filter(Boolean).join(", ");
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => navigate(`/project-report/${r.id}`)}
                  className={`w-full text-left bg-white border rounded-xl p-4 hover:shadow-md transition-all flex flex-col sm:flex-row gap-3 items-start ${
                    isBlanko ? "border-amber-300 border-l-4 border-l-amber-500 bg-amber-50/30" : "border-gray-200 hover:border-fuchsia-300"
                  }`}
                  data-testid={`report-row-${r.id}`}
                >
                  {/* Left badge */}
                  <div className={`shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${
                    isBlanko ? "bg-amber-100 text-amber-700" : "bg-fuchsia-100 text-fuchsia-700"
                  }`}>
                    {isBlanko ? <FileWarning className="w-6 h-6" /> : <ClipboardList className="w-6 h-6" />}
                  </div>

                  {/* Body */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-900 truncate">
                        {r.kunde_name || (isBlanko ? "(Blanko – kein Kunde eingetragen)" : "—")}
                      </span>
                      {isBlanko ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500 text-white">
                          BLANKO
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-fuchsia-100 text-fuchsia-700">
                          Projekt {r.projektnummer || r.order_pk}
                        </span>
                      )}
                      {signed && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                          <CheckCircle2 className="w-3 h-3" /> Unterschrieben
                        </span>
                      )}
                    </div>
                    {r.order_name && !isBlanko && (
                      <div className="text-sm text-gray-600 truncate">{r.order_name}</div>
                    )}
                    {empNames && (
                      <div className="text-xs text-gray-500 mt-1 truncate">
                        Mitarbeiter: {empNames}
                      </div>
                    )}
                  </div>

                  {/* Right meta */}
                  <div className="shrink-0 sm:text-right text-xs text-gray-500 space-y-0.5">
                    <div className="font-medium text-gray-700">{formatDate(r.projekt_datum || r.created_at)}</div>
                    <div className="flex items-center gap-1 sm:justify-end"><Clock className="w-3 h-3" /> {totalHours.toFixed(1)} h</div>
                    {r.created_by && <div className="text-gray-400">erstellt von {r.created_by}</div>}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
