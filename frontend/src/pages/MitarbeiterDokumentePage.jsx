import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft, FileText, Eye, AlertTriangle, CheckCircle2, Clock, Loader2, Download } from "lucide-react";
import { openExternal } from "../lib/openExternal";

const API = process.env.REACT_APP_BACKEND_URL || "";

const DOC_TYPES = [
  { key: "personalausweis", label: "Personalausweis" },
  { key: "fuehrerschein", label: "Führerschein" },
  { key: "fahrerkarte", label: "Fahrerkarte" },
  { key: "erste_hilfe", label: "Erste Hilfe" },
  { key: "sicherheitsunterweisung", label: "Sicherheitsunterweisung" },
  { key: "staplerschein", label: "Staplerschein" },
  { key: "hubarbeitsbuehne", label: "Hubarbeitsbühne" },
  { key: "teleskoplader", label: "Teleskoplader" },
  { key: "baumaschine", label: "Baumaschine" },
];

const isExpired = (d) => d && new Date(d) < new Date();
const isExpiringSoon = (d) => {
  if (!d) return false;
  const days = (new Date(d) - new Date()) / 86400000;
  return days >= 0 && days <= 30;
};

const formatDate = (d) => {
  if (!d) return "—";
  const dt = new Date(d.length === 10 ? d + "T00:00:00" : d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
};

export default function MitarbeiterDokumentePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Backend filtert automatisch auf caller.id wenn caller kein Admin ist
        // → Mitarbeiter sieht GARANTIERT nur eigene Dokumente
        const res = await api.get(`/employee/documents?token=${token}`);
        if (!cancelled) setDocs(res.data || []);
      } catch (e) {
        if (!cancelled) toast.error("Fehler beim Laden der Dokumente");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const openDocument = (docId) => {
    const url = `${API}/api/employee/documents/${docId}/file?token=${token}`;
    openExternal(url);
  };

  // Map active document by type
  const activeByType = {};
  docs.forEach(d => {
    if (d.status === "active") activeByType[d.doc_type] = d;
  });

  // Stats
  const total = DOC_TYPES.length;
  const present = DOC_TYPES.filter(dt => activeByType[dt.key]).length;
  const expiredCount = DOC_TYPES.filter(dt => activeByType[dt.key] && isExpired(activeByType[dt.key].expiry_date)).length;
  const expiringCount = DOC_TYPES.filter(dt => activeByType[dt.key] && !isExpired(activeByType[dt.key].expiry_date) && isExpiringSoon(activeByType[dt.key].expiry_date)).length;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="mitarbeiter-dokumente-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/mitarbeiter-daten")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <FileText className="w-5 h-5 text-fuchsia-600" />
          <div>
            <h1 className="text-base font-semibold text-gray-900">Meine Dokumente</h1>
            <p className="text-[11px] text-gray-500 -mt-0.5">Personalausweis, Führerschein und Zertifikate</p>
          </div>
          {user?.name && <span className="text-sm text-gray-400 ml-auto truncate max-w-[40%]">{user.name}</span>}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-5 space-y-4">
        {/* Stats Strip */}
        {!loading && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="docs-stats">
            <StatCard icon={FileText} label="Gesamt" value={`${present}/${total}`} color="gray" />
            <StatCard icon={CheckCircle2} label="Gültig" value={present - expiredCount - expiringCount} color="green" />
            <StatCard icon={Clock} label="Läuft bald ab" value={expiringCount} color="amber" />
            <StatCard icon={AlertTriangle} label="Abgelaufen" value={expiredCount} color="red" />
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-7 h-7 animate-spin text-fuchsia-500" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="docs-grid">
            {DOC_TYPES.map(dt => {
              const doc = activeByType[dt.key];
              const expired = doc && isExpired(doc.expiry_date);
              const expiring = doc && !expired && isExpiringSoon(doc.expiry_date);
              const missing = !doc;
              return (
                <div
                  key={dt.key}
                  className={`border rounded-xl p-4 flex items-center gap-3 transition-all ${
                    missing ? "border-gray-200 bg-gray-50" :
                    expired ? "border-red-300 bg-red-50" :
                    expiring ? "border-amber-300 bg-amber-50" :
                    "border-green-200 bg-green-50"
                  }`}
                  data-testid={`doc-${dt.key}`}
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    missing ? "bg-gray-200 text-gray-400" :
                    expired ? "bg-red-200 text-red-700" :
                    expiring ? "bg-amber-200 text-amber-700" :
                    "bg-green-200 text-green-700"
                  }`}>
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{dt.label}</p>
                    {doc ? (
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {expired && <span className="text-xs font-medium text-red-700">Abgelaufen</span>}
                        {expiring && <span className="text-xs font-medium text-amber-700">Läuft bald ab</span>}
                        {!expired && !expiring && <span className="text-xs font-medium text-green-700">Gültig</span>}
                        <span className="text-xs text-gray-500">
                          {doc.expiry_date ? `bis ${formatDate(doc.expiry_date)}` : "kein Ablauf"}
                        </span>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Noch nicht hinterlegt – wende dich an die Geschäftsleitung
                      </p>
                    )}
                  </div>
                  {doc && (
                    <button
                      onClick={() => openDocument(doc.id)}
                      className="flex-shrink-0 p-2 rounded-lg bg-white border border-gray-200 hover:border-fuchsia-400 hover:text-fuchsia-700 text-gray-600 transition-colors"
                      title="Dokument öffnen"
                      data-testid={`open-doc-${dt.key}`}
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Info Box */}
        <div className="bg-fuchsia-50 border border-fuchsia-100 rounded-xl p-4 flex gap-3 items-start" data-testid="docs-info">
          <Download className="w-4 h-4 text-fuchsia-600 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-gray-600 space-y-1">
            <p>Tippe auf das Augen-Symbol, um ein Dokument anzusehen oder herunterzuladen.</p>
            <p className="text-gray-500">
              Es werden ausschliesslich <strong>deine</strong> Dokumente angezeigt. Aktualisierungen werden von der Geschäftsleitung hochgeladen.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  const colors = {
    gray: { bg: "bg-white", text: "text-gray-700", border: "border-gray-200" },
    green: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
    amber: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
    red: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
  };
  const c = colors[color] || colors.gray;
  return (
    <div className={`${c.bg} ${c.border} border rounded-xl p-3 flex items-center gap-2.5`}>
      <Icon className={`w-4 h-4 ${c.text} flex-shrink-0`} />
      <div className="min-w-0">
        <p className={`text-base font-bold ${c.text} leading-tight`}>{value}</p>
        <p className="text-[10px] text-gray-500 uppercase tracking-wide truncate">{label}</p>
      </div>
    </div>
  );
}
