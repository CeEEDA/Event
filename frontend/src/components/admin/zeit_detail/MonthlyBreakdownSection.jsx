/**
 * Monthly-Breakdown-Sektion aus AdminZeitDetailPage.jsx extrahiert.
 *
 * Pro Monat: aufklappbare Karte mit
 *  - Manuelle Stempel-Eingabe (Add-Row)
 *  - Urlaub/Krank/Ueberstundenabbau-Eintraege
 *  - Stempelliste mit Inline-Edit & Loeschen
 */
import { CalendarDays, Clock, Palmtree, ThermometerSun, ChevronDown, ChevronUp, Plus, TrendingUp, Save, Pencil, X, Trash2, MapPin } from "lucide-react";
import { Button } from "../../ui/button";

const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

export default function MonthlyBreakdownSection({
  months,
  currentMonth,
  expandedMonth,
  setExpandedMonth,
  getMonthStats,
  fmtH,
  addRow,
  updateAddRow,
  submitAddRow,
  addingRow,
  editEntryId,
  setEditEntryId,
  editDraft,
  setEditDraft,
  startEditEntry,
  saveEditEntry,
  deleteEntry,
}) {
  return (
    <div className="space-y-2">
      {months.filter(m => m.idx <= currentMonth).map(m => {
        const stats = getMonthStats(m.key);
        const isOpen = expandedMonth === m.key;

        return (
          <div key={m.key} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`month-${m.key}`}>
            <button onClick={() => setExpandedMonth(isOpen ? null : m.key)} className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
              <CalendarDays className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-sm font-semibold text-gray-900">{m.label}</span>
              <div className="flex items-center gap-2 ml-auto">
                {stats.totalMins > 0 && <span className="text-xs font-bold text-gray-700 bg-gray-100 px-2 py-0.5 rounded"><Clock className="w-3 h-3 inline mr-0.5 -mt-0.5" />{fmtH(stats.totalMins)}</span>}
                {stats.vacDays > 0 && <span className="text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded"><Palmtree className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.vacDays}T</span>}
                {stats.sickDays > 0 && <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded"><ThermometerSun className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.sickDays}T</span>}
                {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </div>
            </button>
            {isOpen && (
              <div className="border-t border-gray-100 divide-y divide-gray-50">
                {/* Manual Entry Add Row (Admin only) */}
                <div className="px-4 py-2 bg-emerald-50/40 flex items-center gap-2 text-xs flex-wrap" data-testid={`add-time-row-${m.key}`}>
                  <Plus className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                  <span className="font-semibold text-emerald-700 mr-1">Manuell erfassen:</span>
                  <input
                    type="date"
                    value={addRow[m.key]?.date || ""}
                    min={`${m.key}-01`}
                    max={`${m.key}-31`}
                    onChange={e => updateAddRow(m.key, "date", e.target.value)}
                    className="border border-emerald-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-400"
                    data-testid={`add-time-date-${m.key}`}
                  />
                  <input
                    type="time"
                    value={addRow[m.key]?.start || ""}
                    onChange={e => updateAddRow(m.key, "start", e.target.value)}
                    placeholder="Start"
                    className="border border-emerald-200 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                    data-testid={`add-time-start-${m.key}`}
                  />
                  <span className="text-gray-400">—</span>
                  <input
                    type="time"
                    value={addRow[m.key]?.end || ""}
                    onChange={e => updateAddRow(m.key, "end", e.target.value)}
                    placeholder="Ende"
                    className="border border-emerald-200 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                    data-testid={`add-time-end-${m.key}`}
                  />
                  <Button
                    onClick={() => submitAddRow(m.key)}
                    disabled={addingRow === m.key}
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white h-7 text-xs px-2.5 ml-auto"
                    data-testid={`add-time-save-${m.key}`}
                  >
                    <Save className="w-3 h-3 mr-1" /> {addingRow === m.key ? "Speichere…" : "Hinzufügen"}
                  </Button>
                </div>
                {stats.vacs.map(v => (
                  <div key={v.id} className="px-4 py-2.5 flex items-center gap-3 bg-sky-50/50">
                    <Palmtree className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                    <span className="text-xs font-semibold text-sky-700">Urlaub</span>
                    <span className="text-xs text-sky-600">{new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} — {new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</span>
                    <span className="text-xs font-bold text-sky-700 ml-auto">{v.days} Tage</span>
                  </div>
                ))}
                {stats.sicks.map(r => (
                  <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-red-50/50">
                    <ThermometerSun className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                    <span className="text-xs font-semibold text-red-600">Krank</span>
                    <span className="text-xs text-red-500">{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                    <span className="text-xs font-bold text-red-600 ml-auto">{r.days} Tage</span>
                  </div>
                ))}
                {stats.offs.map(r => (
                  <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-amber-50/50">
                    <TrendingUp className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    <span className="text-xs font-semibold text-amber-700">Überstundenabbau</span>
                    <span className="text-xs text-amber-600">{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</span>
                  </div>
                ))}
                {stats.entries.map(e => editEntryId === e.id ? (
                  <div key={e.id} className="px-4 py-2 flex items-center gap-2 text-xs bg-amber-50/60 flex-wrap" data-testid={`edit-row-${e.id}`}>
                    <Pencil className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                    <input type="date" value={editDraft.date} onChange={ev => setEditDraft(d => ({ ...d, date: ev.target.value }))} className="border border-amber-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400" />
                    <input type="time" value={editDraft.start} onChange={ev => setEditDraft(d => ({ ...d, start: ev.target.value }))} className="border border-amber-200 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-amber-400" />
                    <span className="text-gray-400">—</span>
                    <input type="time" value={editDraft.end} onChange={ev => setEditDraft(d => ({ ...d, end: ev.target.value }))} className="border border-amber-200 rounded px-2 py-1 text-xs w-24 focus:outline-none focus:ring-1 focus:ring-amber-400" />
                    <div className="ml-auto flex gap-1">
                      <Button onClick={() => saveEditEntry(e.id)} size="sm" className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs px-2" data-testid={`save-edit-${e.id}`}>
                        <Save className="w-3 h-3 mr-1" /> Speichern
                      </Button>
                      <Button onClick={() => setEditEntryId(null)} size="sm" variant="ghost" className="h-7 text-xs px-2" data-testid={`cancel-edit-${e.id}`}>
                        <X className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs group hover:bg-gray-50/70" data-testid={`time-row-${e.id}`}>
                    <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    <span className="font-medium text-gray-700 w-24 flex-shrink-0">{new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}</span>
                    <span className="text-green-600 font-medium">{formatTime(e.clock_in)}</span>
                    <span className="text-gray-300">—</span>
                    <span className={`font-medium ${e.clock_out ? "text-red-500" : "text-amber-500"}`}>{e.clock_out ? formatTime(e.clock_out) : "Aktiv"}</span>
                    {(e.manual || e.edited_by) && (
                      <span className="text-[9px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-semibold" title={e.manual ? `Manuell durch ${e.manual_by_name || "Admin"}` : `Bearbeitet durch ${e.edited_by_name || "Admin"}`}>
                        {e.manual ? "manuell" : "geändert"}
                      </span>
                    )}
                    {e.break_min > 0 && (
                      <span className="text-[9px] bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded-full font-semibold" title={`${e.break_min} Min. Pause automatisch abgezogen`}>
                        −{e.break_min}m Pause
                      </span>
                    )}
                    <span className="font-bold text-gray-900 ml-auto">{e.duration_minutes > 0 ? fmtH(e.duration_minutes) : "—"}</span>
                    {e.clock_in_lat && <a href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-fuchsia-600" onClick={ev => ev.stopPropagation()}><MapPin className="w-3 h-3" /></a>}
                    {e.clock_out_lat && <a href={`https://www.google.com/maps?q=${e.clock_out_lat},${e.clock_out_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-green-600" onClick={ev => ev.stopPropagation()}><MapPin className="w-3 h-3" /></a>}
                    <button onClick={() => startEditEntry(e)} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-amber-600 p-0.5" title="Bearbeiten" data-testid={`edit-time-${e.id}`}>
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => deleteEntry(e.id)} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 p-0.5" title="Löschen" data-testid={`delete-time-${e.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {stats.entries.length === 0 && stats.vacs.length === 0 && stats.sicks.length === 0 && stats.offs.length === 0 && (
                  <div className="px-4 py-3 text-center text-xs text-gray-400">Noch keine Stempel-Einträge — oben „Manuell erfassen" nutzen</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
