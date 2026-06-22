/**
 * Regelarbeitszeit + Stundenlohn + Zuschlaege aus AdminZeitDetailPage.jsx extrahiert.
 */
import { Briefcase, Save } from "lucide-react";
import { Button } from "../../ui/button";

const WEEKDAYS = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"];
const WEEKDAY_LABELS = { montag: "Montag", dienstag: "Dienstag", mittwoch: "Mittwoch", donnerstag: "Donnerstag", freitag: "Freitag", samstag: "Samstag" };

export default function WeeklyScheduleSection({
  weeklyTotalMin,
  schedule,
  calcDayHours,
  updateDay,
  hourlyWage,
  setHourlyWage,
  surcharges,
  setSurcharges,
  saveSchedule,
  savingSchedule,
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="work-schedule-section">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-indigo-600" />
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Regelarbeitszeit</p>
        </div>
        <div className="text-xs text-gray-500">Woche: <span className="font-bold text-indigo-700">{Math.floor(weeklyTotalMin / 60)}h {weeklyTotalMin % 60 > 0 ? `${weeklyTotalMin % 60}m` : ""}</span></div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-gray-400 uppercase tracking-wider">
              <th className="text-left pb-2 pr-2 font-semibold w-28">Tag</th>
              <th className="text-left pb-2 px-2 font-semibold">Sollstunden</th>
              <th className="text-left pb-2 px-2 font-semibold">Pause (Min.)</th>
              <th className="text-right pb-2 pl-2 font-semibold">Summe</th>
            </tr>
          </thead>
          <tbody>
            {WEEKDAYS.map(day => {
              const d = schedule[day] || {};
              const mins = calcDayHours(day);
              const h = mins !== null ? Math.floor(mins / 60) : null;
              const m = mins !== null ? mins % 60 : null;
              const sollDisplay = (d.soll_hours != null && d.soll_hours !== "")
                ? d.soll_hours
                : (d.start && d.end
                    ? (((parseInt(d.end.split(":")[0]) * 60 + parseInt(d.end.split(":")[1]))
                        - (parseInt(d.start.split(":")[0]) * 60 + parseInt(d.start.split(":")[1]))
                        - (parseInt(d.break_min) || 0)) / 60).toFixed(2).replace(/\.?0+$/, "")
                    : "");
              return (
                <tr key={day} className="border-t border-gray-50">
                  <td className="py-1.5 pr-2 font-medium text-gray-700">{WEEKDAY_LABELS[day]}</td>
                  <td className="py-1.5 px-2">
                    <input
                      type="number" min="0" max="24" step="0.25"
                      value={sollDisplay}
                      onChange={e => updateDay(day, "soll_hours", e.target.value)}
                      placeholder="0"
                      className="border border-gray-200 rounded px-2 py-1 text-sm w-24 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      data-testid={`schedule-${day}-soll-hours`}
                    />
                    <span className="text-[10px] text-gray-400 ml-1">h</span>
                  </td>
                  <td className="py-1.5 px-2">
                    <input type="number" min="0" step="5" value={d.break_min || ""} onChange={e => updateDay(day, "break_min", e.target.value)}
                      placeholder="0" className="border border-gray-200 rounded px-2 py-1 text-sm w-20 focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid={`schedule-${day}-break`} />
                  </td>
                  <td className="py-1.5 pl-2 text-right">
                    {mins !== null ? (
                      <span className="font-bold text-indigo-700">{h}h{m > 0 ? ` ${m}m` : ""}</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Hourly wage & surcharges */}
      <div className="mt-4 pt-3 border-t border-gray-100 space-y-3">
        <div className="grid grid-cols-2 gap-3 max-w-md">
          <div>
            <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Stundenlohn (EUR)</label>
            <input type="number" step="0.01" min="0" value={hourlyWage} onChange={e => setHourlyWage(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="hourly-wage" placeholder="0.00" />
          </div>
          <div>
            <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Nachtzuschlag %</label>
            <input type="number" min="0" value={surcharges.night} onChange={e => setSurcharges(p => ({ ...p, night: parseFloat(e.target.value) || 0 }))}
              className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="surcharge-night" />
          </div>
        </div>
        <p className="text-[10px] text-gray-400">Nacht: 20:00–06:00 Uhr. Sonn-/Feiertagsarbeit wird über das Offday-System (Ersatzruhetag) ausgeglichen, nicht über Zuschläge.</p>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-100">
        <Button onClick={saveSchedule} disabled={savingSchedule} size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-schedule-btn">
          <Save className="w-3.5 h-3.5 mr-1.5" /> {savingSchedule ? "Speichern..." : "Speichern"}
        </Button>
      </div>
    </div>
  );
}
