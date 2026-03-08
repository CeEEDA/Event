import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { ArrowLeft, Zap, Check, User, Calendar, Link2, QrCode } from "lucide-react";

const api = {
  get: async (url) => {
    const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api${url}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    });
    if (!r.ok) throw { response: { data: await r.json() } };
    return { data: await r.json() };
  },
  post: async (url, body) => {
    const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api${url}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token")}` },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw { response: { data: await r.json() } };
    return { data: await r.json() };
  },
};

export default function MeterZuordnungPage() {
  const { meterId } = useParams();
  const navigate = useNavigate();
  const [meter, setMeter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [selectedSignup, setSelectedSignup] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/meters/${meterId}/info`);
      setMeter(r.data);
    } catch {
      toast.error("Zaehler nicht gefunden oder keine Berechtigung");
    } finally { setLoading(false); }
  }, [meterId]);

  useEffect(() => { load(); }, [load]);

  const handleAssign = async () => {
    if (!selectedSignup) return;
    setAssigning(true);
    try {
      const r = await api.post(`/kirmes/meters/${meterId}/assign-signup`, { signup_id: selectedSignup });
      toast.success(r.data.message);
      load();
      setSelectedSignup("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler bei Zuordnung");
    } finally { setAssigning(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-4 border-fuchsia-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!meter) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
        <QrCode className="w-16 h-16 text-gray-300 mb-4" />
        <p className="text-gray-500 text-lg">Zaehler nicht gefunden</p>
        <p className="text-gray-400 text-sm mt-1">Bitte anmelden und erneut versuchen</p>
        <Button onClick={() => navigate("/login")} className="mt-4">Anmelden</Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-700">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-base font-semibold text-gray-900">Zaehler-Zuordnung</h1>
            <p className="text-xs text-gray-500">QR-Code Zuweisung</p>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-6 space-y-4">
        {/* Meter Info Card */}
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-testid="meter-info-card">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-fuchsia-50 rounded-xl flex items-center justify-center">
              <Zap className="w-6 h-6 text-fuchsia-600" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">{meter.meter_name}</h2>
              <p className="text-xs text-gray-500">IP: {meter.meter_ip} | Geraet: {meter.device_name}</p>
            </div>
          </div>

          {/* Current Assignment */}
          {meter.current_assignment ? (
            <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-100">
              <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                <Check className="w-3.5 h-3.5" /> Aktuell zugewiesen
              </p>
              <div className="space-y-1">
                <p className="text-sm text-gray-900 flex items-center gap-2">
                  <User className="w-3.5 h-3.5 text-gray-400" />
                  {meter.current_assignment.schausteller?.firma ||
                   `${meter.current_assignment.schausteller?.vorname || ""} ${meter.current_assignment.schausteller?.name || ""}`}
                </p>
                <p className="text-sm text-gray-600 flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-gray-400" />
                  {meter.current_assignment.event?.name || "?"}
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-100 text-center">
              <p className="text-sm text-amber-700">Noch keiner Anmeldung zugewiesen</p>
            </div>
          )}
        </div>

        {/* Assignment Form */}
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-testid="assign-form">
          <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-fuchsia-500" /> Anmeldung zuweisen
          </h3>

          {(meter.available_signups || []).length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">Keine offenen Anmeldungen ohne Zaehler vorhanden</p>
          ) : (
            <>
              <select
                value={selectedSignup}
                onChange={e => setSelectedSignup(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-3 text-sm mb-3 focus:outline-none focus:border-fuchsia-500"
                data-testid="signup-select"
              >
                <option value="">-- Anmeldung waehlen --</option>
                {(meter.available_signups || []).map(s => (
                  <option key={s.id} value={s.id}>
                    {s.schausteller_name} | {s.event_name}
                  </option>
                ))}
              </select>

              <Button
                onClick={handleAssign}
                disabled={!selectedSignup || assigning}
                className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                data-testid="assign-btn"
              >
                {assigning ? "Wird zugewiesen..." : "Zaehler zuweisen"}
              </Button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
