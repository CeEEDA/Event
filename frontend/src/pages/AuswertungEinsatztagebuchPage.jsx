import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, BookOpen, Search, Clock, AlertTriangle, CheckCircle2, Phone, Users, TrendingUp, ChevronRight, FileText } from "lucide-react";
import api from "../lib/api";
import { Input } from "../components/ui/input";

function fmtDuration(min) {
  if (min == null || !Number.isFinite(min)) return "—";
  if (min < 1) return "<1 min";
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m === 0 ? `${h}h` : `${h}h ${m}min`;
}

function StatCard({ icon: Icon, label, value, hint, color = "fuchsia" }) {
  const colorMap = {
    fuchsia: "bg-fuchsia-50 border-fuchsia-200 text-fuchsia-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-700",
    red: "bg-red-50 border-red-200 text-red-700",
  };
  return (
    <div className={`border rounded-xl p-4 ${colorMap[color] || colorMap.fuchsia}`}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide opacity-80">{label}</p>
          <p className="text-2xl font-bold mt-1 tabular-nums">{value}</p>
          {hint && <p className="text-[11px] opacity-70 mt-0.5">{hint}</p>}
        </div>
        <Icon className="w-5 h-5 opacity-60 flex-shrink-0" />
      </div>
    </div>
  );
}

export default function AuswertungEinsatztagebuchPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ summary: null, orders: [] });
  const [search, setSearch] = useState("");
  const [expandedOrderPk, setExpandedOrderPk] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/orders/diary/auswertung");
        if (!cancelled) setData(data || { summary: null, orders: [] });
      } catch (e) {
        if (!cancelled) setData({ summary: null, orders: [] });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filteredOrders = useMemo(() => {
    const q = (search || "").trim().toLowerCase();
    if (!q) return data.orders || [];
    return (data.orders || []).filter(o =>
      [o.order_no, o.contact_name, o.address, o.event, o.order_pk]
        .filter(Boolean).some(v => String(v).toLowerCase().includes(q))
    );
  }, [search, data.orders]);

  const s = data.summary || {};

  return (
    <div className="min-h-screen bg-gray-50" data-testid="auswertung-einsatztagebuch-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung/auswertung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <BookOpen className="w-5 h-5 text-slate-600" />
          <h1 className="text-lg font-semibold text-gray-900">Einsatztagebuch — Auswertung</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Gesamt-Statistik */}
        <section data-testid="overall-stats">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Gesamtübersicht</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard icon={FileText} label="Aufträge" value={loading ? "…" : (s.total_orders ?? 0)} color="fuchsia" />
            <StatCard icon={BookOpen} label="Störungen gesamt" value={loading ? "…" : (s.total_entries ?? 0)} color="indigo" />
            <StatCard icon={CheckCircle2} label="Behoben" value={loading ? "…" : (s.total_resolved ?? 0)} color="emerald" />
            <StatCard icon={AlertTriangle} label="Noch offen" value={loading ? "…" : (s.total_open ?? 0)} color="amber" />
            <StatCard icon={Clock} label="Ø Bearbeitung" value={loading ? "…" : fmtDuration(s.avg_duration_minutes)} hint="je Einsatz" color="blue" />
            <StatCard icon={TrendingUp} label="Gesamtzeit" value={loading ? "…" : fmtDuration(s.total_minutes)} hint="alle Einsätze" color="red" />
          </div>
        </section>

        {/* Suche */}
        <section>
          <div className="relative max-w-md">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suchen: Auftrag-Nr, Kunde, Adresse, Event…"
              className="pl-9"
              data-testid="auswertung-search-input"
            />
          </div>
        </section>

        {/* Aufträge mit Einsatztagebuch */}
        <section data-testid="orders-list">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
            Aufträge mit Einsatztagebuch ({filteredOrders.length})
          </h2>
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-8">Lade Daten…</p>
          ) : filteredOrders.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                {search ? "Keine Aufträge passen zum Filter." : "Bisher wurden keine Einträge im Einsatztagebuch erfasst."}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredOrders.map((o) => {
                const isOpen = expandedOrderPk === o.order_pk;
                return (
                  <div
                    key={o.order_pk}
                    className="bg-white border border-gray-200 rounded-xl overflow-hidden"
                    data-testid={`order-row-${o.order_pk}`}
                  >
                    {/* Header-Zeile */}
                    <div className="flex items-center justify-between gap-3 p-4 hover:bg-gray-50 transition-colors">
                      <button
                        onClick={() => setExpandedOrderPk(isOpen ? null : o.order_pk)}
                        className="flex-1 flex items-center gap-3 text-left min-w-0"
                        data-testid={`order-toggle-${o.order_pk}`}
                      >
                        <ChevronRight className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-gray-900">
                              Auftrag #{o.order_no || o.order_pk}
                            </span>
                            {o.contact_name && (
                              <span className="text-sm text-gray-600 truncate">· {o.contact_name}</span>
                            )}
                            {o.open > 0 && (
                              <span className="text-[10px] font-bold uppercase bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                                {o.open} offen
                              </span>
                            )}
                          </div>
                          {(o.event || o.address) && (
                            <p className="text-xs text-gray-500 truncate mt-0.5">
                              {[o.event, o.address].filter(Boolean).join(" · ")}
                            </p>
                          )}
                        </div>
                      </button>
                      <button
                        onClick={() => navigate(`/orders/${o.order_pk}`)}
                        className="text-xs text-fuchsia-600 hover:text-fuchsia-700 font-medium px-3 py-1.5 rounded hover:bg-fuchsia-50 flex-shrink-0"
                        data-testid={`order-open-${o.order_pk}`}
                      >
                        Öffnen →
                      </button>
                    </div>

                    {/* Quick-Stats */}
                    <div className="px-4 pb-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                      <div className="bg-slate-50 rounded p-2">
                        <p className="text-[10px] font-semibold text-gray-500 uppercase">Störungen</p>
                        <p className="text-base font-bold text-gray-900 tabular-nums">{o.total}</p>
                      </div>
                      <div className="bg-blue-50 rounded p-2">
                        <p className="text-[10px] font-semibold text-blue-600 uppercase">Ø Dauer</p>
                        <p className="text-base font-bold text-blue-900 tabular-nums">{fmtDuration(o.avg_duration_minutes)}</p>
                      </div>
                      <div className="bg-emerald-50 rounded p-2">
                        <p className="text-[10px] font-semibold text-emerald-600 uppercase">Gesamtzeit</p>
                        <p className="text-base font-bold text-emerald-900 tabular-nums">{fmtDuration(o.total_minutes)}</p>
                      </div>
                      <div className="bg-indigo-50 rounded p-2">
                        <p className="text-[10px] font-semibold text-indigo-600 uppercase">Anrufer (unique)</p>
                        <p className="text-base font-bold text-indigo-900 tabular-nums">{o.unique_callers}</p>
                      </div>
                    </div>

                    {/* Aufklappbare Caller-Statistik */}
                    {isOpen && (
                      <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/40" data-testid={`order-detail-${o.order_pk}`}>
                        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                          <h3 className="text-xs font-semibold text-gray-700 flex items-center gap-1.5 uppercase">
                            <Users className="w-3.5 h-3.5 text-indigo-500" />
                            Anrufer / Gäste — Häufigkeit
                          </h3>
                          {o.recurring_callers_count > 0 && (
                            <span className="text-[10px] text-fuchsia-700 bg-fuchsia-50 border border-fuchsia-200 px-2 py-0.5 rounded-full">
                              {o.recurring_callers_count} Wiederholungstäter
                            </span>
                          )}
                        </div>
                        {(!o.callers || o.callers.length === 0) ? (
                          <p className="text-xs text-gray-400 italic">Keine Anrufer-Daten erfasst.</p>
                        ) : (
                          <ul className="space-y-1">
                            {o.callers.map((c, idx) => (
                              <li
                                key={`${c.name}-${c.phone}-${idx}`}
                                className="flex items-center justify-between bg-white border border-gray-100 rounded px-3 py-1.5 text-xs"
                                data-testid={`caller-row-${o.order_pk}-${idx}`}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <Users className="w-3 h-3 text-gray-400 flex-shrink-0" />
                                  <span className="font-medium text-gray-900 truncate">
                                    {c.name || <span className="italic text-gray-400">(kein Name)</span>}
                                  </span>
                                  {c.phone && (
                                    <a href={`tel:${c.phone}`} className="text-fuchsia-600 hover:underline flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
                                      <Phone className="w-2.5 h-2.5" /> {c.phone}
                                    </a>
                                  )}
                                </div>
                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full tabular-nums ${
                                  c.count > 1 ? "bg-fuchsia-100 text-fuchsia-700" : "bg-gray-100 text-gray-700"
                                }`}>
                                  {c.count}× {c.count > 1 ? "Anrufe" : "Anruf"}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                        {o.nachtrag_count > 0 && (
                          <p className="text-[11px] text-gray-500 mt-2">
                            Davon <strong className="text-fuchsia-700">{o.nachtrag_count}</strong> als Nachtrag markiert (zusätzlich abzurechnen).
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
