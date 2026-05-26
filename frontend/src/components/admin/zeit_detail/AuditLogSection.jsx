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
          <span className="text-xs text-gray-500">– manuelle Eingriffe an Zeit / Urlaub / Stammdaten</span>
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
                return (
                  <li key={a.id} className="px-4 py-2.5 hover:bg-gray-50" data-testid={`audit-row-${a.id}`}>
                    <div className="flex items-start gap-3">
                      <span className="text-[10px] font-mono text-gray-400 mt-0.5 whitespace-nowrap">{when}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-900 truncate">
                          <span className="text-[10px] inline-block bg-violet-50 text-violet-700 font-semibold uppercase px-1.5 py-0.5 rounded mr-2">{actionLabel}</span>
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
