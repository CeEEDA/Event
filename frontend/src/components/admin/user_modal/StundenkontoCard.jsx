/**
 * Kleine Anzeige des Stundenkontos in der Benutzerverwaltungs-Maske.
 * Zeigt drei Werte wie in der alten Zeiterfassung:
 *   Übertrag (Stand 1. dieses Monats)  |  Monatsende (Prognose)  |  Aktuell
 *
 * Faellt das Backend aus, wird die Karte einfach nicht gerendert (`data` bleibt
 * null) — der Modal bleibt so voll benutzbar auch wenn der Saldo-Endpoint mal
 * ein 404/403 zurueckwirft.
 */
import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import api from "../../../lib/api";

export default function StundenkontoCard({ userId }) {
  const [data, setData] = useState(null);
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!userId || !token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/employee/hr-data/${userId}/saldo-summary?token=${token}`);
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [userId, token]);

  if (!data) return null;

  const fmt = (v) => (v == null ? "–" : Number(v).toFixed(2));

  return (
    <div className="border-t border-gray-200 pt-4 mt-2" data-testid="usermodal-stundenkonto">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-amber-600" />
        Stundenkonto
      </h3>
      <div className="bg-amber-50 rounded-lg px-4 py-3 grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] font-medium text-amber-600 uppercase mb-1">Übertrag</p>
          <p className="font-mono text-base font-bold text-amber-800" data-testid="usermodal-saldo-carry">
            {fmt(data.carry_over)}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium text-amber-600 uppercase mb-1">Monatsende</p>
          <p className="font-mono text-base font-bold text-amber-800" data-testid="usermodal-saldo-month-end">
            {fmt(data.month_end)}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium text-amber-600 uppercase mb-1">Aktuell</p>
          <p className="font-mono text-base font-bold text-amber-900" data-testid="usermodal-saldo-current">
            {fmt(data.current)}
          </p>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mt-1.5">Monatsende = Prognose bei planmaessiger Erfuellung des Wochenplans (Rest des Monats). Werte in Stunden.</p>
    </div>
  );
}
