import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { ArrowLeft, Truck, Loader2, ShieldCheck, User } from "lucide-react";

export default function AdrPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const [betanker, setBetanker] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/users/adr");
        if (!cancelled) setBetanker(res.data || []);
      } catch {
        if (!cancelled) setBetanker([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const myAdr = betanker.some(b => b.id === user?.id);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="adr-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Truck className="w-5 h-5 text-rose-600" />
          <div>
            <h1 className="text-base font-semibold text-gray-900">ADR / Tankwagen</h1>
            <p className="text-[11px] text-gray-500 -mt-0.5">Mitarbeiter mit gültigem ADR-Schein</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-5 space-y-4">
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex gap-3 items-start">
          <ShieldCheck className="w-5 h-5 text-rose-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-gray-700">
            <p className="font-medium text-rose-900">Betanker / Mitarbeiter (ADR)</p>
            <p className="text-xs text-gray-600 mt-1">
              Diese Mitarbeiter sind im Tankwagen automatisch als <strong>Betanker</strong> hinterlegt. Aktivieren oder deaktivieren der ADR-Berechtigung erfolgt durch den Administrator in der Benutzerverwaltung.
            </p>
            {myAdr && (
              <p className="text-xs text-rose-700 font-medium mt-2 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" /> Du bist als ADR-Betanker registriert.
              </p>
            )}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20"><Loader2 className="w-7 h-7 animate-spin text-rose-500" /></div>
        ) : betanker.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-10 text-center text-gray-400" data-testid="adr-empty">
            <Truck className="w-10 h-10 mx-auto mb-3 text-gray-300" />
            Aktuell sind keine Betanker registriert.
            {isAdmin && <p className="text-xs mt-2">Aktiviere ADR pro Mitarbeiter in der Benutzerverwaltung.</p>}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="adr-list">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 text-[10px] uppercase tracking-wider font-semibold text-gray-500 flex items-center justify-between">
              <span>Aktive Betanker</span>
              <span>{betanker.length}</span>
            </div>
            <div className="divide-y divide-gray-100">
              {betanker.map(b => (
                <div key={b.id} className="px-4 py-3 flex items-center gap-3" data-testid={`adr-user-${b.id}`}>
                  <div className="w-9 h-9 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0">
                    <User className="w-4 h-4 text-rose-700" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{b.name}</p>
                    <p className="text-xs text-gray-500 truncate">{b.email}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-700 uppercase tracking-wider">
                    {b.role === "admin" ? "Admin" : "Mitarbeiter"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-[11px] text-gray-400 text-center pt-2">
          Im nächsten Schritt: Bestätigung beim Betanken per Quittung/PIN durch den Betanker.
        </p>
      </main>
    </div>
  );
}
