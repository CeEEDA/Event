import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft,
  Wrench,
  Plus,
  Search,
} from "lucide-react";

export default function ServiceplanPage() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/devices");
        setDevices(res.data.filter(d => d.status !== "ausser_betrieb"));
      } catch { /* ignore */ }
      finally { setLoading(false); }
    };
    load();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="serviceplan-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Serviceplan</h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center py-16">
          <Wrench className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Serviceplan</h2>
          <p className="text-gray-500 mb-8">Wählen Sie ein Gerät aus, um einen Wartungsplan anzulegen</p>

          {loading ? (
            <p className="text-gray-400">Lade Geräte...</p>
          ) : devices.length === 0 ? (
            <p className="text-gray-400">Keine aktiven Geräte vorhanden. Bitte zuerst ein Gerät in der Geräteverwaltung anlegen.</p>
          ) : (
            <div className="max-w-lg mx-auto space-y-2">
              {devices.map(d => (
                <button
                  key={d.id}
                  className="w-full flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-fuchsia-400 hover:shadow-sm transition-all text-left"
                  data-testid={`sp-device-${d.serial_number}`}
                  onClick={() => toast.info("Serviceplan-Details werden im nächsten Schritt gebaut")}
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">{d.serial_number}</p>
                    <p className="text-xs text-gray-400">{d.model || d.device_type} · {d.user_field || "–"}</p>
                  </div>
                  <span className="text-xs text-gray-400">{d.next_maintenance ? `Nächste Wartung: ${new Date(d.next_maintenance).toLocaleDateString("de-DE")}` : "Kein Plan"}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
