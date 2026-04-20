import { useState, useEffect, useMemo } from "react";
import api from "../lib/api";
import { AlertTriangle, CheckCircle2, ChevronDown } from "lucide-react";

const SEVERITY_STYLES = {
  critical: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", badge: "bg-red-100 text-red-700" },
  warning: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", badge: "bg-amber-100 text-amber-700" },
  info: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", badge: "bg-blue-100 text-blue-700" },
};

function formatDate(iso) {
  if (!iso) return "–";
  try {
    return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
  } catch { return iso; }
}

function durationHuman(fromIso, toIso) {
  if (!fromIso || !toIso) return null;
  const ms = new Date(toIso) - new Date(fromIso);
  if (ms < 0) return null;
  const min = Math.floor(ms / 60000);
  if (min < 60) return `${min} Min.`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return `${h} Std. ${m} Min.`;
  const d = Math.floor(h / 24);
  return `${d} Tag(e) ${h % 24} Std.`;
}

export default function FaultDiagnosticsPanel({ deviceId, compact = false }) {
  const [data, setData] = useState({ alarms: [], total: 0, active: 0 });
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState("all"); // all | active | resolved

  useEffect(() => {
    if (!deviceId) return;
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get(`/generators/alarms-by-device/${deviceId}?limit=300`);
        if (!cancelled) setData(res.data || { alarms: [], total: 0, active: 0 });
      } catch {
        if (!cancelled) setData({ alarms: [], total: 0, active: 0 });
      }
      if (!cancelled) setLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, [deviceId]);

  // Group by message (fault type) for the summary
  const grouped = useMemo(() => {
    const map = new Map();
    for (const a of data.alarms) {
      const key = (a.message || a.alarm_type || "Unbekannt").trim();
      if (!map.has(key)) map.set(key, { message: key, count: 0, last: a.timestamp, severity: a.severity || "warning", active: 0 });
      const g = map.get(key);
      g.count += 1;
      if (!g.last || new Date(a.timestamp) > new Date(g.last)) g.last = a.timestamp;
      if (!a.resolved_at) g.active += 1;
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [data.alarms]);

  const filtered = useMemo(() => {
    if (filter === "active") return data.alarms.filter(a => !a.resolved_at);
    if (filter === "resolved") return data.alarms.filter(a => a.resolved_at);
    return data.alarms;
  }, [data.alarms, filter]);

  const visible = showAll ? filtered : filtered.slice(0, compact ? 10 : 20);

  if (loading) return null;
  if (data.total === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="fault-diagnostics-panel">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500" />
          Fehlerdiagnose ({data.total})
          {data.active > 0 && (
            <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-100 text-red-700">
              {data.active} aktiv
            </span>
          )}
        </h3>
        <div className="flex gap-1 text-[11px]">
          <button onClick={() => setFilter("all")} className={`px-2 py-1 rounded-md ${filter === "all" ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`} data-testid="fault-filter-all">Alle</button>
          <button onClick={() => setFilter("active")} className={`px-2 py-1 rounded-md ${filter === "active" ? "bg-red-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`} data-testid="fault-filter-active">Aktiv</button>
          <button onClick={() => setFilter("resolved")} className={`px-2 py-1 rounded-md ${filter === "resolved" ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`} data-testid="fault-filter-resolved">Behoben</button>
        </div>
      </div>

      {/* Summary by fault type */}
      {grouped.length > 0 && filter === "all" && (
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Häufigste Störungen</p>
          <div className="flex flex-wrap gap-1.5">
            {grouped.slice(0, 8).map((g) => {
              const style = SEVERITY_STYLES[g.severity] || SEVERITY_STYLES.warning;
              return (
                <div key={g.message} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${style.border} ${style.bg}`}>
                  <span className={`text-[11px] font-medium ${style.text} max-w-[260px] truncate`}>{g.message}</span>
                  <span className={`text-[10px] font-bold px-1.5 rounded-full ${style.badge}`}>{g.count}×</span>
                  {g.active > 0 && <span className="text-[9px] font-bold text-red-600">{g.active} aktiv</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className={`divide-y divide-gray-50 ${compact ? "max-h-[320px]" : "max-h-[480px]"} overflow-y-auto`}>
        {visible.map((a) => {
          const style = SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.warning;
          const dur = durationHuman(a.timestamp, a.resolved_at);
          return (
            <div key={a.id} className="px-4 py-2.5 hover:bg-gray-50/50" data-testid="fault-row">
              <div className="flex items-start gap-3">
                <div className={`w-7 h-7 rounded-full ${style.bg} flex items-center justify-center shrink-0 mt-0.5 border ${style.border}`}>
                  {a.resolved_at
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    : <AlertTriangle className={`w-3.5 h-3.5 ${style.text}`} />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-gray-900">{a.message || a.alarm_type || "Alarm"}</span>
                    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${style.badge}`}>{a.severity || "warning"}</span>
                    {a.resolved_at && <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">behoben</span>}
                    {!a.resolved_at && <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-red-100 text-red-700">aktiv</span>}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-gray-500 mt-0.5 flex-wrap">
                    <span>{formatDate(a.timestamp)}</span>
                    {a.resolved_at && (
                      <>
                        <span>→ behoben {formatDate(a.resolved_at)}</span>
                        {dur && <span className="text-gray-400">· Dauer {dur}</span>}
                      </>
                    )}
                    {a.acknowledged && !a.resolved_at && <span className="text-amber-600">· quittiert</span>}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length > visible.length && (
        <button onClick={() => setShowAll(true)} className="w-full px-4 py-2 text-[11px] text-fuchsia-600 hover:bg-fuchsia-50 transition-colors border-t border-gray-100 flex items-center justify-center gap-1" data-testid="fault-show-all-btn">
          <ChevronDown className="w-3 h-3" />
          Alle {filtered.length} anzeigen
        </button>
      )}
    </div>
  );
}
