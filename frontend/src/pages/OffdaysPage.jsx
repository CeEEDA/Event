import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import { toast } from "sonner";
import {
  ArrowLeft, CalendarCheck2, PlusCircle, MinusCircle, RefreshCw,
  Sparkles, Sun, Trees, Calendar, ChevronDown, ChevronRight, Pencil,
} from "lucide-react";

const SOURCE_ICONS = {
  clock_in: Sun,
  shift_assignment: Calendar,
  manual: Pencil,
};

const SOURCE_LABELS = {
  clock_in: "Stempelzeit",
  shift_assignment: "Einsatzplanung",
  manual: "Manuell",
};

function isVerwaltung(user) {
  if (!user) return false;
  if (user.role === "admin") return true;
  if (user.role === "mitarbeiter") {
    const m = user.apps?.modules || {};
    return m.verwaltung !== false;
  }
  return false;
}

function EntryRow({ e }) {
  const Icon = SOURCE_ICONS[e.source] || Sparkles;
  const isPlus = (e.delta || 0) > 0;
  return (
    <tr className="border-b border-gray-100 last:border-0">
      <td className="px-3 py-2 text-xs text-gray-500 font-mono">{e.ref_date || "-"}</td>
      <td className="px-3 py-2 text-sm text-gray-800">{e.user_name || "-"}</td>
      <td className="px-3 py-2">
        <span className="inline-flex items-center gap-1 text-xs text-gray-700">
          <Icon className="w-3.5 h-3.5 text-gray-400" />
          {e.source_label || SOURCE_LABELS[e.source] || e.source}
        </span>
      </td>
      <td className={`px-3 py-2 text-right font-mono font-semibold text-sm ${isPlus ? "text-emerald-600" : "text-rose-600"}`}>
        {isPlus ? "+" : ""}{e.delta}
      </td>
      <td className="px-3 py-2 text-xs text-gray-500 hidden md:table-cell">{e.note || ""}</td>
      <td className="px-3 py-2 text-xs text-gray-400 hidden lg:table-cell">{e.created_by || ""}</td>
    </tr>
  );
}

export default function OffdaysPage() {
  const navigate = useNavigate();
  const { user: _user } = useAuth();
  const token = localStorage.getItem("token");

  const [me, setMe] = useState({ balance: 0, entries: [] });
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      const r = await api.get(`/employee/offdays/me?token=${token}`);
      setMe(r.data || { balance: 0, entries: [] });
    } catch (e) {
      toast.error("Fehler beim Laden des Saldos");
    }
  }, [token]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await loadMe();
      setLoading(false);
    })();
  }, [loadMe]);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="offdays-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/mitarbeiter-daten")} className="text-gray-600 hover:text-violet-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <CalendarCheck2 className="w-5 h-5 text-violet-600" />
          <h1 className="text-base font-semibold text-gray-900">Offdays / Ausgleichstage</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Eigener Saldo Card */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 md:p-8 shadow-sm" data-testid="my-balance-card">
          <div className="flex items-start gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-fuchsia-100 flex items-center justify-center flex-shrink-0">
              <Trees className="w-8 h-8 text-violet-600" />
            </div>
            <div className="flex-1">
              <p className="text-xs uppercase tracking-wider text-gray-400 mb-1 font-medium">Dein aktueller Saldo</p>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-bold text-gray-900 font-mono" data-testid="my-balance">{me.balance}</span>
                <span className="text-lg text-gray-500">{Math.abs(me.balance) === 1 ? "Offday" : "Offdays"}</span>
              </div>
              <p className="text-sm text-gray-500 mt-2">
                Du bekommst automatisch <strong>+1 Offday</strong> für jeden Sonntag oder gesetzlichen Feiertag (RLP),
                an dem du eingestempelt warst. Verbraucht werden Offdays über die Einsatzplanung.
              </p>
            </div>
          </div>
        </section>

        {/* Eigene Historie */}
        <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <h2 className="text-sm font-semibold text-gray-700">Deine Buchungen</h2>
          </div>
          {loading ? (
            <div className="px-4 py-8 text-center text-sm text-gray-400">Wird geladen ...</div>
          ) : me.entries.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-400">Noch keine Buchungen.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50/50 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Datum</th>
                    <th className="px-3 py-2 text-left font-medium">Quelle</th>
                    <th className="px-3 py-2 text-right font-medium">Δ</th>
                    <th className="px-3 py-2 text-left font-medium hidden md:table-cell">Notiz</th>
                  </tr>
                </thead>
                <tbody data-testid="my-entries">
                  {me.entries.map(e => {
                    const Icon = SOURCE_ICONS[e.source] || Sparkles;
                    const isPlus = (e.delta || 0) > 0;
                    return (
                      <tr key={e.id} className="border-b border-gray-100 last:border-0">
                        <td className="px-3 py-2 text-xs text-gray-500 font-mono">{e.ref_date || "-"}</td>
                        <td className="px-3 py-2">
                          <span className="inline-flex items-center gap-1 text-xs text-gray-700">
                            <Icon className="w-3.5 h-3.5 text-gray-400" />
                            {e.source_label || SOURCE_LABELS[e.source] || e.source}
                          </span>
                        </td>
                        <td className={`px-3 py-2 text-right font-mono font-semibold text-sm ${isPlus ? "text-emerald-600" : "text-rose-600"}`}>
                          {isPlus ? "+" : ""}{e.delta}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500 hidden md:table-cell">{e.note || ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
