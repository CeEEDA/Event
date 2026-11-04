/**
 * Audit-Log-Sektion (Aenderungs-Protokoll) aus AdminZeitDetailPage.jsx extrahiert.
 */
import { History, ChevronDown, ChevronUp } from "lucide-react";

const ACTION_LABELS = {
  time_manual_create: "Zeit manuell angelegt",
  time_edit: "Zeit korrigiert",
  time_delete: "Zeit gelöscht",
  vacation_add: "Urlaub hinzugefügt",
  vacation_delete: "Urlaub gelöscht",
  time_off_admin_create: "Abwesenheit eingetragen",
  time_off_delete: "Abwesenheit gelöscht",
  hr_data_update: "HR-Daten geändert",
  work_schedule_update: "Regelarbeitszeit geändert",
  deduction_add: "Lohnabzug hinzugefügt",
  deduction_delete: "Lohnabzug gelöscht",
  payroll_release: "Lohn freigegeben",
  time_manual_correction: "Stunden-Korrektur",
  time_off_resolve: "Antrag entschieden",
  offday_manual_adjust: "Offday-Konto",
  offday_create: "Offday eingetragen",
  offday_update: "Offday geändert",
  offday_delete: "Offday gelöscht",
  auto_balance_day: "Automatisch · Tag",
  auto_balance_recompute: "Automatisch · Konto",
};

// Automatische Buchungen des Systems deutlich von manuellen Eingriffen absetzen
const isSystemEntry = (a) => a.performed_by_role === "system" || (a.action || "").startsWith("auto_");

// Stunden-Wirkung eines Eintrags auf das Ueberstundenkonto (falls bekannt)
const hoursEffect = (a) => {
  const b = a.before?.overtime_hours, n = a.after?.overtime_hours;
  if (typeof b === "number" && typeof n === "number") return n - b;
  const d = a.after?.overtime_delta_h;
  if (typeof d === "number" && Math.abs(d) >= 0.01) return d;
  const e = a.details?.effect_min, p = a.details?.previous_effect_min;
  if (a.action === "auto_balance_day" && typeof e === "number") return (e - (typeof p === "number" ? p : 0)) / 60;
  return null;
};

export default function AuditLogSection({
  auditOpen,
  setAuditOpen,
  auditEntries,
  auditLoading,
  loadAuditLog,
}) {
  return (
    <div id="audit-section" className="bg-white rounded-xl border border-gray-200" data-testid="audit-section">
      <button
        type="button"
        onClick={() => setAuditOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-violet-50/40 transition-colors"
        data-testid="audit-toggle"
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-violet-600" />
          <span className="font-semibold text-sm text-gray-900">Änderungs­protokoll</span>
          <span className="text-xs text-gray-500">– manuelle Eingriffe und automatische Buchungen des Systems</span>
          {auditEntries.length > 0 && (
            <span className="ml-2 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-violet-100 text-violet-700 text-[10px] font-bold">
              {auditEntries.length}
            </span>
          )}
        </div>
        {auditOpen ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
      </button>
      {auditOpen && (
        <div className="border-t border-gray-100">
          {auditLoading ? (
            <div className="px-4 py-6 text-center text-xs text-gray-400">Lade…</div>
          ) : auditEntries.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-gray-400">Noch keine protokollierten Änderungen.</div>
          ) : (
            <ul className="divide-y divide-gray-50">
              {auditEntries.map(a => {
                const dt = new Date(a.created_at);
                const when = dt.toLocaleString("de-DE", {
                  day: "2-digit", month: "2-digit", year: "numeric",
                  hour: "2-digit", minute: "2-digit"
                });
                const actionLabel = ACTION_LABELS[a.action] || a.action;
                const sys = isSystemEntry(a);
                const eff = hoursEffect(a);
                return (
                  <li key={a.id} className={`px-4 py-2.5 hover:bg-gray-50 ${sys ? "bg-sky-50/40 border-l-2 border-sky-300" : ""}`} data-testid={`audit-row-${a.id}`}>
                    <div className="flex items-start gap-3">
                      <span className="text-[10px] font-mono text-gray-400 mt-0.5 whitespace-nowrap">{when}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-900 break-words">
                          <span className={`text-[10px] inline-block font-semibold uppercase px-1.5 py-0.5 rounded mr-2 ${sys ? "bg-sky-100 text-sky-800" : "bg-violet-50 text-violet-700"}`}>{actionLabel}</span>
                          {eff !== null && Math.abs(eff) >= 0.01 && (
                            <span className={`text-[10px] inline-block font-bold px-1.5 py-0.5 rounded mr-2 ${eff > 0 ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`} data-testid={`audit-effect-${a.id}`}>
                              {eff > 0 ? "+" : ""}{eff.toFixed(2)} h
                            </span>
                          )}
                          {a.summary}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-0.5">
                          durch <span className="font-medium">{a.performed_by_name}</span>
                          {a.performed_by_role && <span className="text-gray-400"> · {a.performed_by_role}</span>}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="px-4 py-2 border-t border-gray-100 flex justify-end">
            <button
              onClick={loadAuditLog}
              className="text-[11px] text-violet-600 hover:text-violet-800"
              data-testid="audit-refresh"
            >
              ↻ Aktualisieren
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
