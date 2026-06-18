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
  const { user } = useAuth();
  const token = localStorage.getItem("token");
  const isAdmin = isVerwaltung(user);

  const [me, setMe] = useState({ balance: 0, entries: [] });
  const [allData, setAllData] = useState({ balances: [], recent: [] });
  const [loading, setLoading] = useState(true);
  const [expandedUser, setExpandedUser] = useState(null);
  const [userDetail, setUserDetail] = useState({});  // { user_id: { balance, entries } }
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustForm, setAdjustForm] = useState({ user_id: "", user_name: "", delta: 1, note: "" });
  const [adjustSubmitting, setAdjustSubmitting] = useState(false);

  const loadMe = useCallback(async () => {
    try {
      const r = await api.get(`/employee/offdays/me?token=${token}`);
      setMe(r.data || { balance: 0, entries: [] });
    } catch (e) {
      toast.error("Fehler beim Laden des Saldos");
    }
  }, [token]);

  const loadAll = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const r = await api.get(`/employee/offdays?token=${token}`);
      setAllData(r.data || { balances: [], recent: [] });
    } catch (e) {
      // Falls 403 (z.B. Modul deaktiviert), still die eigene Ansicht anzeigen.
    }
  }, [token, isAdmin]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadMe(), loadAll()]);
      setLoading(false);
    })();
  }, [loadMe, loadAll]);

  const toggleUserDetail = async (userId) => {
    if (expandedUser === userId) {
      setExpandedUser(null);
      return;
    }
    setExpandedUser(userId);
    if (!userDetail[userId]) {
      try {
        const r = await api.get(`/employee/offdays/user/${userId}?token=${token}`);
        setUserDetail(prev => ({ ...prev, [userId]: r.data }));
      } catch {
        toast.error("Fehler beim Laden");
      }
    }
  };

  const openAdjust = (b) => {
    setAdjustForm({ user_id: b.user_id, user_name: b.user_name, delta: 1, note: "" });
    setAdjustOpen(true);
  };

  const submitAdjust = async () => {
    const d = parseInt(adjustForm.delta);
    if (!d || isNaN(d)) { toast.error("Bitte gültige Zahl eingeben (z.B. +1, -2)"); return; }
    setAdjustSubmitting(true);
    try {
      await api.post(`/employee/offdays/adjust?token=${token}`, {
        user_id: adjustForm.user_id,
        delta: d,
        note: adjustForm.note,
      });
      toast.success(`${adjustForm.user_name}: ${d > 0 ? "+" : ""}${d} Offday(s)`);
      setAdjustOpen(false);
      // Refresh
      await Promise.all([loadAll(), loadMe()]);
      // Detail für expandeden User neu laden
      if (expandedUser === adjustForm.user_id) {
        const r = await api.get(`/employee/offdays/user/${adjustForm.user_id}?token=${token}`);
        setUserDetail(prev => ({ ...prev, [adjustForm.user_id]: r.data }));
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
    setAdjustSubmitting(false);
  };

  const recompute = async () => {
    if (!window.confirm("Alle automatischen Offday-Buchungen aus Sonntag/Feiertag-Stempelzeiten neu berechnen?\n\nManuelle Korrekturen und Einsatz-Verbrauche bleiben erhalten.")) return;
    try {
      const r = await api.post(`/employee/offdays/recompute?token=${token}`);
      toast.success(`Neu berechnet: ${r.data?.granted ?? 0} Tag(e) gutgeschrieben`);
      await Promise.all([loadAll(), loadMe()]);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

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
          {isAdmin && (
            <Button size="sm" variant="ghost" onClick={recompute} className="ml-auto text-xs text-gray-500 hover:text-violet-600" data-testid="recompute-btn">
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Neu berechnen
            </Button>
          )}
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
                    <th className="px-3 py-2 text-left font-medium">User</th>
                    <th className="px-3 py-2 text-left font-medium">Quelle</th>
                    <th className="px-3 py-2 text-right font-medium">Δ</th>
                    <th className="px-3 py-2 text-left font-medium hidden md:table-cell">Notiz</th>
                    <th className="px-3 py-2 text-left font-medium hidden lg:table-cell">Erstellt von</th>
                  </tr>
                </thead>
                <tbody data-testid="my-entries">
                  {me.entries.map(e => <EntryRow key={e.id} e={e} />)}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Admin: alle User */}
        {isAdmin && (
          <section className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="admin-section">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Alle Mitarbeiter</h2>
              <span className="text-xs text-gray-400">{allData.balances.length} User</span>
            </div>
            <div className="divide-y divide-gray-100">
              {allData.balances.map(b => {
                const isExpanded = expandedUser === b.user_id;
                const detail = userDetail[b.user_id];
                return (
                  <div key={b.user_id}>
                    <div className="px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition" data-testid={`row-user-${b.user_id}`}>
                      <button onClick={() => toggleUserDetail(b.user_id)} className="text-gray-400 hover:text-violet-600 flex-shrink-0" data-testid={`toggle-${b.user_id}`}>
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{b.user_name || "-"}</p>
                        {b.last_entry && (
                          <p className="text-xs text-gray-400">Letzte Aktivität: {new Date(b.last_entry).toLocaleDateString("de-DE")}</p>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`text-2xl font-bold font-mono ${
                          b.balance > 0 ? "text-emerald-600" : b.balance < 0 ? "text-rose-600" : "text-gray-400"
                        }`} data-testid={`balance-${b.user_id}`}>
                          {b.balance}
                        </span>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-emerald-600 hover:bg-emerald-50" onClick={() => openAdjust({ ...b, delta: 1 })} data-testid={`plus-${b.user_id}`}>
                          <PlusCircle className="w-3.5 h-3.5" />
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-rose-600 hover:bg-rose-50" onClick={() => openAdjust({ ...b, delta: -1 })} data-testid={`minus-${b.user_id}`}>
                          <MinusCircle className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="bg-gray-50/50 px-4 py-3 border-t border-gray-100">
                        {!detail ? (
                          <p className="text-xs text-gray-400">Wird geladen ...</p>
                        ) : detail.entries.length === 0 ? (
                          <p className="text-xs text-gray-400">Noch keine Buchungen.</p>
                        ) : (
                          <table className="w-full text-xs">
                            <thead className="text-gray-500">
                              <tr>
                                <th className="text-left font-medium py-1">Datum</th>
                                <th className="text-left font-medium py-1">User</th>
                                <th className="text-left font-medium py-1">Quelle</th>
                                <th className="text-right font-medium py-1">Δ</th>
                                <th className="text-left font-medium py-1 hidden md:table-cell">Notiz</th>
                                <th className="text-left font-medium py-1 hidden lg:table-cell">Von</th>
                              </tr>
                            </thead>
                            <tbody data-testid={`entries-${b.user_id}`}>
                              {detail.entries.map(e => <EntryRow key={e.id} e={e} />)}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Admin: Activity Feed */}
        {isAdmin && allData.recent.length > 0 && (
          <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h2 className="text-sm font-semibold text-gray-700">Letzte Bewegungen (alle MA)</h2>
            </div>
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50/50 text-xs uppercase text-gray-500 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Datum</th>
                    <th className="px-3 py-2 text-left font-medium">User</th>
                    <th className="px-3 py-2 text-left font-medium">Quelle</th>
                    <th className="px-3 py-2 text-right font-medium">Δ</th>
                    <th className="px-3 py-2 text-left font-medium hidden md:table-cell">Notiz</th>
                    <th className="px-3 py-2 text-left font-medium hidden lg:table-cell">Von</th>
                  </tr>
                </thead>
                <tbody data-testid="recent-feed">
                  {allData.recent.map(e => <EntryRow key={e.id} e={e} />)}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {/* Adjust Dialog */}
      <Dialog open={adjustOpen} onOpenChange={setAdjustOpen}>
        <DialogContent className="sm:max-w-md" data-testid="adjust-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-600" /> Manuelle Korrektur
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-2">
            <p className="text-sm text-gray-600">User: <strong>{adjustForm.user_name}</strong></p>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Anzahl (positiv = gutschreiben, negativ = abziehen)</label>
              <Input type="number" value={adjustForm.delta} onChange={e => setAdjustForm(f => ({ ...f, delta: e.target.value }))} data-testid="adjust-delta" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Notiz / Begründung</label>
              <Textarea rows={2} value={adjustForm.note} onChange={e => setAdjustForm(f => ({ ...f, note: e.target.value }))} placeholder="z.B. Übertrag aus Excel, Rückbuchung, Bonus..." data-testid="adjust-note" />
            </div>
            <Button onClick={submitAdjust} disabled={adjustSubmitting} className="w-full bg-violet-600 hover:bg-violet-700" data-testid="adjust-submit">
              {adjustSubmitting ? "Wird gespeichert..." : "Speichern"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
