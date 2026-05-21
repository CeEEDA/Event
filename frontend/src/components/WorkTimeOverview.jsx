import { useState, useEffect, useCallback } from "react";
import api from "../lib/api";
import { Clock, TrendingUp, CalendarOff, Briefcase, AlertCircle } from "lucide-react";

/**
 * Soll/Ist-Arbeitszeit-Uebersicht.
 *
 * Props:
 *   compact: true  -> kompakte Variante (HubPage, neben Stempel-Slider)
 *           false -> ausfuehrlich (ArbeitszeitPage, mit Wochenstreifen + 7-Tage-Vorschau)
 *   refreshKey: number - aendert sich bei Stempel-Aktion, triggert Reload
 */
export function WorkTimeOverview({ compact = false, refreshKey = 0 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem("token");

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/employee/time/overview?token=${token}`);
      setData(r.data);
    } catch {
      setData(null);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load, refreshKey]);

  // Live-Refresh waehrend eingestempelt: alle 60s nachladen (damit Ist-Zeit
  // mitlaeuft wenn der Mitarbeiter eingestempelt ist).
  useEffect(() => {
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  if (loading || !data) {
    return (
      <div className="text-xs text-gray-400 py-2" data-testid="worktime-overview-loading">
        Lade Arbeitszeit-Übersicht…
      </div>
    );
  }

  const fmtH = (mins) => {
    if (mins == null) return "—";
    const abs = Math.abs(mins);
    const h = Math.floor(abs / 60);
    const m = Math.round(abs % 60);
    const sign = mins < 0 ? "-" : "";
    if (h === 0 && m === 0) return "0h";
    if (h === 0) return `${sign}${m}m`;
    if (m === 0) return `${sign}${h}h`;
    return `${sign}${h}h ${m}m`;
  };

  const diffClass = (diff) => {
    if (diff > 30) return "text-green-600";
    if (diff < -30) return "text-red-500";
    return "text-gray-500";
  };

  const today = data.today;
  const week = data.week;

  // Kompakte Variante: 2 Spalten "Heute" + "Woche" + ggf. Feiertag-Hinweis
  if (compact) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-3" data-testid="worktime-overview-compact">
        {today.is_holiday && (
          <div className="mb-2 flex items-center gap-2 text-xs bg-purple-50 border border-purple-200 rounded-lg px-2.5 py-1.5" data-testid="worktime-holiday-banner">
            <CalendarOff className="w-3.5 h-3.5 text-purple-600 flex-shrink-0" />
            <span className="text-purple-700 font-medium">Heute Feiertag:</span>
            <span className="text-purple-600">{today.holiday_name}</span>
          </div>
        )}
        {!data.has_schedule && (
          <div className="mb-2 flex items-center gap-2 text-[11px] bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
            <span className="text-amber-700">Kein Wochenplan hinterlegt - bitte beim Admin anfragen.</span>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3" data-testid="worktime-today-week">
          <div data-testid="worktime-today">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Heute</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold text-gray-900" data-testid="worktime-today-ist">{fmtH(today.ist_minutes)}</span>
              <span className="text-xs text-gray-400">/ {fmtH(today.soll_minutes)} Soll</span>
            </div>
            <p className={`text-xs font-medium mt-0.5 ${diffClass(today.diff_minutes)}`}>
              {today.diff_minutes >= 0 ? "+" : ""}{fmtH(today.diff_minutes)}
            </p>
          </div>
          <div data-testid="worktime-week">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Diese Woche</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold text-gray-900" data-testid="worktime-week-ist">{fmtH(week.ist_minutes)}</span>
              <span className="text-xs text-gray-400">/ {fmtH(week.soll_minutes)} Soll</span>
            </div>
            <p className={`text-xs font-medium mt-0.5 ${diffClass(week.diff_minutes)}`}>
              {week.diff_minutes >= 0 ? "+" : ""}{fmtH(week.diff_minutes)}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Ausfuehrliche Variante: Heute-Karte + Wochenstreifen Mo-So + 7-Tage-Vorschau
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4" data-testid="worktime-overview-full">
      {!data.has_schedule && (
        <div className="flex items-center gap-2 text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2" data-testid="worktime-no-schedule">
          <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span className="text-amber-800">Kein Wochenplan hinterlegt - Soll-Stunden können nicht berechnet werden. Bitte beim Admin anfragen.</span>
        </div>
      )}

      {/* Heute + Woche + Stundenkonto */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatBlock
          icon={<Clock className="w-4 h-4 text-sky-600" />}
          tone="sky"
          label="Heute"
          subtitle={today.weekday + (today.is_holiday ? ` · ${today.holiday_name}` : "")}
          ist={fmtH(today.ist_minutes)}
          soll={fmtH(today.soll_minutes)}
          diff={today.diff_minutes}
          fmtH={fmtH}
          testid="worktime-today-card"
        />
        <StatBlock
          icon={<Briefcase className="w-4 h-4 text-indigo-600" />}
          tone="indigo"
          label="Diese Woche"
          subtitle={`${formatShortDate(week.start)} – ${formatShortDate(week.end)}`}
          ist={fmtH(week.ist_minutes)}
          soll={fmtH(week.soll_minutes)}
          diff={week.diff_minutes}
          fmtH={fmtH}
          testid="worktime-week-card"
        />
        <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 flex items-center gap-3" data-testid="worktime-overtime-card">
          <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <p className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider">Stundenkonto</p>
            <p className="text-xl font-bold text-amber-800 leading-tight">
              {data.overtime_hours >= 0 ? "+" : ""}{Number(data.overtime_hours).toFixed(2)} <span className="text-xs font-normal text-amber-500">Std.</span>
            </p>
          </div>
        </div>
      </div>

      {/* Wochenstreifen Mo-So */}
      <div data-testid="worktime-week-strip">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Wochenübersicht</p>
        <div className="grid grid-cols-7 gap-1.5">
          {week.days.map(d => (
            <DayCell key={d.date} day={d} fmtH={fmtH} />
          ))}
        </div>
      </div>

      {/* 7-Tage-Vorschau */}
      <div data-testid="worktime-next7">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Nächste 7 Tage</p>
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {data.next_7_days.map(d => (
            <div
              key={d.date}
              className={`flex-shrink-0 min-w-[78px] rounded-lg border px-2 py-1.5 text-center ${
                d.is_holiday ? "bg-purple-50 border-purple-200" : "bg-gray-50 border-gray-200"
              }`}
              data-testid={`worktime-next7-${d.date}`}
              title={d.is_holiday ? `Feiertag: ${d.holiday_name}` : ""}
            >
              <p className="text-[10px] font-semibold text-gray-500 uppercase">{d.weekday_short}</p>
              <p className="text-xs text-gray-700">{formatShortDate(d.date)}</p>
              <p className={`text-xs font-bold mt-0.5 ${d.is_holiday ? "text-purple-700" : "text-gray-900"}`}>
                {d.is_holiday ? "FT" : fmtH(d.soll_minutes)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatBlock({ icon, tone, label, subtitle, ist, soll, diff, fmtH, testid }) {
  const toneMap = {
    sky:    { bg: "bg-sky-50",    border: "border-sky-100",    iconBg: "bg-sky-100",    text: "text-sky-700",    val: "text-sky-900" },
    indigo: { bg: "bg-indigo-50", border: "border-indigo-100", iconBg: "bg-indigo-100", text: "text-indigo-700", val: "text-indigo-900" },
  };
  const c = toneMap[tone] || toneMap.sky;
  const diffClass = diff > 30 ? "text-green-600" : diff < -30 ? "text-red-500" : "text-gray-500";
  return (
    <div className={`${c.bg} ${c.border} border rounded-lg p-3`} data-testid={testid}>
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-7 h-7 rounded-lg ${c.iconBg} flex items-center justify-center flex-shrink-0`}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className={`text-[10px] font-semibold ${c.text} uppercase tracking-wider leading-tight`}>{label}</p>
          <p className="text-[10px] text-gray-500 truncate">{subtitle}</p>
        </div>
      </div>
      <div className="flex items-baseline gap-1.5 mt-1">
        <span className={`text-xl font-bold ${c.val}`}>{ist}</span>
        <span className="text-xs text-gray-400">/ {soll} Soll</span>
      </div>
      <p className={`text-xs font-medium mt-0.5 ${diffClass}`}>
        {diff >= 0 ? "+" : ""}{fmtH(diff)}
      </p>
    </div>
  );
}

function DayCell({ day, fmtH }) {
  const isHoliday = day.is_holiday;
  const isFutureToday = false; // could highlight today, see below
  const reached = day.soll_minutes > 0 && day.ist_minutes >= day.soll_minutes;
  const bg = isHoliday
    ? "bg-purple-50 border-purple-200"
    : reached
    ? "bg-green-50 border-green-200"
    : day.ist_minutes > 0
    ? "bg-sky-50 border-sky-200"
    : "bg-gray-50 border-gray-200";
  return (
    <div
      className={`${bg} border rounded-lg px-1.5 py-2 text-center`}
      data-testid={`worktime-day-${day.date}`}
      title={isHoliday ? `Feiertag: ${day.holiday_name}` : ""}
    >
      <p className="text-[10px] font-semibold text-gray-500 uppercase">{day.weekday_short}</p>
      <p className="text-[10px] text-gray-400 mb-1">{formatDayOnly(day.date)}</p>
      {isHoliday ? (
        <>
          <p className="text-[10px] font-bold text-purple-700 truncate">FT</p>
          <p className="text-[9px] text-purple-600 leading-tight truncate">{day.holiday_name}</p>
        </>
      ) : (
        <>
          <p className="text-xs font-bold text-gray-900">{fmtH(day.ist_minutes)}</p>
          <p className="text-[10px] text-gray-400">/ {fmtH(day.soll_minutes)}</p>
        </>
      )}
      {/* eslint-disable-next-line no-unused-vars */}
      {isFutureToday && null}
    </div>
  );
}

function formatShortDate(iso) {
  try {
    const d = new Date(iso + "T00:00");
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  } catch {
    return iso;
  }
}

function formatDayOnly(iso) {
  try {
    return new Date(iso + "T00:00").toLocaleDateString("de-DE", { day: "2-digit" });
  } catch {
    return iso.slice(-2);
  }
}
