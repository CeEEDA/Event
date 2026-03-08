import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, Users, MapPin, CalendarDays, Zap, Trash2, Copy, Check, Send, FileDown,
} from "lucide-react";
import jsPDF from "jspdf";
import "jspdf-autotable";

const STATUS_LABELS = {
  entwurf: "Entwurf", freigegeben: "Freigegeben", aktiv: "Aktiv",
  abgeschlossen: "Abgeschlossen", abgerechnet: "Abgerechnet",
};
const STATUS_COLORS = {
  entwurf: "bg-gray-100 text-gray-600", freigegeben: "bg-blue-100 text-blue-700",
  aktiv: "bg-emerald-100 text-emerald-700", abgeschlossen: "bg-amber-100 text-amber-700",
  abgerechnet: "bg-fuchsia-100 text-fuchsia-700",
};
const PAYMENT_LABELS = {
  ausstehend: "Ausstehend", reserviert: "Reserviert", bezahlt: "Bezahlt", erstattet: "Erstattet",
};
const PAYMENT_COLORS = {
  ausstehend: "text-amber-600", reserviert: "text-blue-600", bezahlt: "text-emerald-600", erstattet: "text-gray-500",
};

export default function KirmesEventDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedLink, setCopiedLink] = useState(false);

  const loadEvent = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/events/${id}`);
      setEvent(r.data);
    } catch { toast.error("Fehler beim Laden"); navigate("/kirmes"); }
    finally { setLoading(false); }
  }, [id, navigate]);

  useEffect(() => { loadEvent(); }, [loadEvent]);

  const handleRelease = async () => {
    if (!window.confirm(`"${event.name}" freigeben?`)) return;
    try {
      await api.post(`/kirmes/events/${id}/release`);
      toast.success("Veranstaltung freigegeben");
      loadEvent();
    } catch { toast.error("Fehler"); }
  };

  const handleDeleteSignup = async (signupId) => {
    if (!window.confirm("Anmeldung wirklich löschen?")) return;
    try {
      await api.delete(`/kirmes/signups/${signupId}`);
      toast.success("Anmeldung gelöscht");
      loadEvent();
    } catch { toast.error("Fehler"); }
  };

  const copyLink = () => {
    const link = `${window.location.origin}/kirmes/anmeldung?event=${id}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    toast.success("Anmeldelink kopiert!");
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const exportPDF = () => {
    if (!event) return;
    const doc = new jsPDF({ orientation: "landscape" });

    // Header
    doc.setFontSize(16);
    doc.text(`Montageliste: ${event.name}`, 14, 18);
    doc.setFontSize(10);
    doc.setTextColor(100);
    const info = [
      event.location && `Ort: ${event.location}`,
      `Zeitraum: ${new Date(event.start_date).toLocaleDateString("de-DE")} – ${new Date(event.end_date).toLocaleDateString("de-DE")}`,
      `Anmeldungen: ${(event.signups || []).length}`,
      `Erstellt: ${new Date().toLocaleDateString("de-DE")} ${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`,
    ].filter(Boolean);
    doc.text(info.join("  |  "), 14, 26);
    doc.setTextColor(0);

    // Table
    const signups = event.signups || [];
    const rows = signups.map((s, i) => [
      i + 1,
      s.platznummer,
      s.schausteller?.firma || "–",
      s.schausteller?.name || "–",
      s.fahrgeschaeft || "–",
      s.connection_type,
      `${(s.price || 0).toFixed(2)} EUR`,
      s.schausteller?.telefon || "–",
      s.meter_id ? "Ja" : "Nein",
    ]);

    doc.autoTable({
      startY: 32,
      head: [["#", "Platz", "Firma", "Name", "Fahrgeschäft", "Anschluss", "Preis", "Telefon", "Zähler"]],
      body: rows,
      styles: { fontSize: 9, cellPadding: 3 },
      headStyles: { fillColor: [168, 50, 168], textColor: 255 },
      alternateRowStyles: { fillColor: [248, 248, 248] },
      columnStyles: { 0: { cellWidth: 10 }, 1: { cellWidth: 18 } },
    });

    // Footer
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setTextColor(150);
      doc.text(`Eventenergie Deutschland GmbH & Co. KG – Seite ${i}/${pageCount}`, 14, doc.internal.pageSize.height - 10);
    }

    doc.save(`Montageliste_${event.name.replace(/\s+/g, "_")}.pdf`);
    toast.success("PDF heruntergeladen");
  };

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;
  if (!event) return null;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="kirmes-event-detail">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/kirmes")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900 truncate">{event.name}</h1>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[event.status]}`}>
              {STATUS_LABELS[event.status]}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {(event.signups || []).length > 0 && (
              <Button size="sm" variant="outline" onClick={exportPDF} className="text-gray-600" data-testid="export-pdf-btn">
                <FileDown className="w-3.5 h-3.5 mr-1" /> Montageliste PDF
              </Button>
            )}
            {event.status === "entwurf" && (
              <Button size="sm" variant="outline" onClick={handleRelease} className="text-blue-600 border-blue-200" data-testid="release-btn">
                <Send className="w-3.5 h-3.5 mr-1" /> Freigeben
              </Button>
            )}
            {["freigegeben", "aktiv"].includes(event.status) && (
              <Button size="sm" variant="outline" onClick={copyLink} className="text-fuchsia-600 border-fuchsia-200" data-testid="copy-link-btn">
                {copiedLink ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-500" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                {copiedLink ? "Kopiert!" : "Anmeldelink"}
              </Button>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Event Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <CalendarDays className="w-4 h-4" /> <span className="text-xs font-medium">Zeitraum</span>
            </div>
            <p className="text-sm text-gray-900 font-medium">
              {new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}
            </p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <MapPin className="w-4 h-4" /> <span className="text-xs font-medium">Ort</span>
            </div>
            <p className="text-sm text-gray-900 font-medium">{event.location || "–"}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <Users className="w-4 h-4" /> <span className="text-xs font-medium">Anmeldungen</span>
            </div>
            <p className="text-sm text-gray-900 font-medium">{event.signup_count || 0}</p>
          </div>
        </div>

        {/* Prices */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-fuchsia-500" /> Preise pro Anschluss
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {(event.prices || []).map(p => (
              <div key={p.connection_type} className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">{p.connection_type}</p>
                <p className="text-lg font-semibold text-gray-900">{p.price.toFixed(2)} <span className="text-xs text-gray-400">EUR</span></p>
              </div>
            ))}
          </div>
        </div>

        {/* Signups Table */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Anmeldungen ({(event.signups || []).length})</h2>
          </div>
          {(event.signups || []).length === 0 ? (
            <div className="px-5 py-12 text-center text-gray-400 text-sm">
              Noch keine Anmeldungen vorhanden
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="signups-table">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">Firma</th>
                    <th className="px-4 py-3 text-left">Name</th>
                    <th className="px-4 py-3 text-left">Fahrgeschäft</th>
                    <th className="px-4 py-3 text-left">Platznr.</th>
                    <th className="px-4 py-3 text-left">Anschluss</th>
                    <th className="px-4 py-3 text-right">Preis</th>
                    <th className="px-4 py-3 text-left">Zahlung</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {(event.signups || []).map(signup => (
                    <tr key={signup.id} className="border-b border-gray-100 hover:bg-gray-50" data-testid={`signup-${signup.id}`}>
                      <td className="px-4 py-3 font-medium text-gray-900">{signup.schausteller?.firma || "–"}</td>
                      <td className="px-4 py-3 text-gray-600">{signup.schausteller?.name || "–"}</td>
                      <td className="px-4 py-3 text-gray-600">{signup.fahrgeschaeft || "–"}</td>
                      <td className="px-4 py-3 font-mono text-gray-900">{signup.platznummer}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-xs bg-fuchsia-50 text-fuchsia-700 px-2 py-0.5 rounded-full">
                          <Zap className="w-3 h-3" /> {signup.connection_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{(signup.price || 0).toFixed(2)} EUR</td>
                      <td className="px-4 py-3 text-gray-600 capitalize">{signup.payment_method}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium ${PAYMENT_COLORS[signup.payment_status] || "text-gray-500"}`}>
                          {PAYMENT_LABELS[signup.payment_status] || signup.payment_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => handleDeleteSignup(signup.id)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" title="Löschen" data-testid={`delete-signup-${signup.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {event.notes && (
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-2">Notizen</h2>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{event.notes}</p>
          </div>
        )}
      </main>
    </div>
  );
}
