import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, Users, MapPin, CalendarDays, Zap, Trash2, Copy, Check, Send, FileDown,
  Receipt, Clock, Pencil, Mail, UserPlus, X, Download, SendHorizonal, FileText,
  Activity, Link2, Unlink, Gauge, Wifi, WifiOff, FolderOpen,
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Input } from "../components/ui/input";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import QrScanner from "../components/QrScanner";

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
  const [editingKwh, setEditingKwh] = useState(null);
  const [kwhForm, setKwhForm] = useState({ kwh_einbau: "", kwh_ausbau: "" });
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [expandedSignup, setExpandedSignup] = useState(null);
  const [allSchausteller, setAllSchausteller] = useState([]);
  const [selectedInvites, setSelectedInvites] = useState([]);
  const [inviting, setInviting] = useState(false);
  const [inviteSearch, setInviteSearch] = useState("");
  const [billingInProgress, setBillingInProgress] = useState(false);
  const [eventInvoices, setEventInvoices] = useState([]);
  const [emuMeters, setEmuMeters] = useState([]);
  const [meterDataMap, setMeterDataMap] = useState({});
  const [linkingMeter, setLinkingMeter] = useState(null);
  const [selectedMeterCombo, setSelectedMeterCombo] = useState("");
  const [scanningMeter, setScanningMeter] = useState(null);
  const [docCount, setDocCount] = useState(0);

  const loadEvent = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/events/${id}`);
      setEvent(r.data);
    } catch { toast.error("Fehler beim Laden"); navigate("/kirmes"); }
    finally { setLoading(false); }
  }, [id, navigate]);

  const loadInvoices = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/invoices?event_id=${id}`);
      setEventInvoices(r.data);
    } catch { /* ignore */ }
  }, [id]);

  const loadDocCount = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/events/${id}/documents`);
      setDocCount(r.data.length);
    } catch { /* ignore */ }
  }, [id]);

  useEffect(() => { loadEvent(); loadInvoices(); loadDocCount(); }, [loadEvent, loadInvoices, loadDocCount]);

  // Load available EMU meters
  useEffect(() => {
    const loadMeters = async () => {
      try {
        const r = await api.get("/kirmes/emu-meters");
        setEmuMeters(r.data);
      } catch { /* ignore */ }
    };
    loadMeters();
  }, []);

  // Load meter data when a signup is expanded and has linked meter
  const loadMeterData = useCallback(async (signupId) => {
    try {
      const r = await api.get(`/kirmes/signups/${signupId}/meter-data`);
      setMeterDataMap(prev => ({ ...prev, [signupId]: r.data }));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (expandedSignup) {
      const signup = (event?.signups || []).find(s => s.id === expandedSignup);
      if (signup?.emu_device_id && signup?.emu_meter_id) {
        loadMeterData(expandedSignup);
      }
    }
  }, [expandedSignup, event, loadMeterData]);

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
      s.schausteller?.telefon || "–",
      s.emu_meter_name || (s.meter_id ? "Ja" : "Nein"),
    ]);

    autoTable(doc, {
      startY: 32,
      head: [["#", "Platz", "Firma", "Name", "Fahrgeschäft", "Anschluss", "Telefon", "Zähler"]],
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

  const openKwhEdit = (signup) => {
    setEditingKwh(signup.id);
    setKwhForm({
      kwh_einbau: signup.kwh_einbau ?? "",
      kwh_ausbau: signup.kwh_ausbau ?? "",
    });
  };

  const saveKwh = async (signupId) => {
    try {
      const payload = {};
      if (kwhForm.kwh_einbau !== "") payload.kwh_einbau = parseFloat(kwhForm.kwh_einbau);
      if (kwhForm.kwh_ausbau !== "") payload.kwh_ausbau = parseFloat(kwhForm.kwh_ausbau);
      await api.put(`/kirmes/signups/${signupId}/kwh`, payload);
      toast.success("Zählerstände gespeichert");
      setEditingKwh(null);
      loadEvent();
    } catch { toast.error("Fehler beim Speichern"); }
  };

  const openInviteModal = async () => {
    try {
      const r = await api.get("/kirmes/schausteller");
      // Filter out already signed up
      const signedUpIds = (event?.signups || []).map(s => s.schausteller_id);
      setAllSchausteller(r.data.filter(s => !signedUpIds.includes(s.id)));
      setSelectedInvites([]);
      setInviteSearch("");
      setShowInviteModal(true);
    } catch { toast.error("Fehler beim Laden der Schausteller"); }
  };

  const toggleInvite = (schId) => {
    setSelectedInvites(prev => prev.includes(schId) ? prev.filter(id => id !== schId) : [...prev, schId]);
  };

  const sendInvitations = async () => {
    if (selectedInvites.length === 0) { toast.error("Keine Schausteller ausgewählt"); return; }
    setInviting(true);
    try {
      const r = await api.post(`/kirmes/events/${id}/invite`, { schausteller_ids: selectedInvites });
      toast.success(r.data.message);
      setShowInviteModal(false);
    } catch { toast.error("Fehler beim Versenden"); }
    finally { setInviting(false); }
  };

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;
  if (!event) return null;

  const getInvoiceForSignup = (signupId) => eventInvoices.find(inv => inv.invoice_number && (event.signups || []).find(s => s.id === signupId && s.invoice_number === inv.invoice_number));

  const handleGenerateAllInvoices = async () => {
    if (!window.confirm(`Rechnungen für alle ${(event.signups || []).length} Anmeldungen erstellen?`)) return;
    setBillingInProgress(true);
    try {
      const r = await api.post(`/kirmes/events/${event.id}/generate-invoices`);
      toast.success(`${r.data.generated} Rechnung(en) erstellt${r.data.skipped > 0 ? `, ${r.data.skipped} übersprungen` : ""}`);
      loadEvent();
      loadInvoices();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler bei der Abrechnung"));
    } finally { setBillingInProgress(false); }
  };

  const handleGenerateSingleInvoice = async (signupId) => {
    try {
      const r = await api.post(`/kirmes/signups/${signupId}/invoice`);
      toast.success(`Rechnung ${r.data.invoice_number} erstellt`);
      loadEvent();
      loadInvoices();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler"));
    }
  };

  const handleDownloadInvoice = async (invoiceId) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/kirmes/invoices/${invoiceId}/pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!response.ok) throw new Error("Fehler");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Rechnung_${invoiceId}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("PDF konnte nicht heruntergeladen werden"); }
  };

  const handleSendInvoice = async (invoiceId) => {
    try {
      const r = await api.post(`/kirmes/invoices/${invoiceId}/send`);
      toast.success(r.data.message);
      loadInvoices();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Versenden"));
    }
  };

  const handleLinkMeter = async (signupId) => {
    if (!selectedMeterCombo) return;
    const [deviceId, meterId] = selectedMeterCombo.split("|");
    try {
      await api.put(`/kirmes/signups/${signupId}/link-meter`, {
        emu_device_id: deviceId,
        emu_meter_id: meterId,
      });
      toast.success("EMU-Zähler verknüpft");
      setLinkingMeter(null);
      setSelectedMeterCombo("");
      loadEvent();
      loadMeterData(signupId);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Verknüpfen"));
    }
  };

  const handleQrScan = async (scannedText, signupId) => {
    // Extract meter ID from URL like: .../kirmes/meter-zuordnung/{meterId}
    const match = scannedText.match(/meter-zuordnung\/([a-zA-Z0-9_-]+)/);
    if (!match) {
      toast.error("Ungültiger QR-Code – kein Zähler erkannt");
      setScanningMeter(null);
      return;
    }
    const meterId = match[1];
    setScanningMeter(null);
    try {
      await api.post(`/kirmes/meters/${meterId}/assign-signup`, { signup_id: signupId });
      toast.success("Zähler per QR-Code verknüpft!");
      setLinkingMeter(null);
      loadEvent();
      loadMeterData(signupId);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Verknüpfen"));
    }
  };

  const handleUnlinkMeter = async (signupId) => {
    if (!window.confirm("Zähler-Verknüpfung wirklich entfernen?")) return;
    try {
      await api.delete(`/kirmes/signups/${signupId}/link-meter`);
      toast.success("Verknüpfung entfernt");
      setMeterDataMap(prev => { const n = { ...prev }; delete n[signupId]; return n; });
      loadEvent();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler"));
    }
  };

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
              <>
                <Button size="sm" variant="outline" onClick={exportPDF} className="text-gray-600" data-testid="export-pdf-btn">
                  <FileDown className="w-3.5 h-3.5 mr-1" /> Montageliste PDF
                </Button>
                <Button size="sm" onClick={handleGenerateAllInvoices} disabled={billingInProgress} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="billing-btn">
                  <Receipt className="w-3.5 h-3.5 mr-1" /> {billingInProgress ? "Wird erstellt..." : "Abrechnung"}
                </Button>
              </>
            )}
            {event.status === "entwurf" && (
              <Button size="sm" variant="outline" onClick={handleRelease} className="text-blue-600 border-blue-200" data-testid="release-btn">
                <Send className="w-3.5 h-3.5 mr-1" /> Freigeben
              </Button>
            )}
            {["freigegeben", "aktiv"].includes(event.status) && (
              <>
                <Button size="sm" variant="outline" onClick={openInviteModal} className="text-amber-600 border-amber-200" data-testid="invite-btn">
                  <Mail className="w-3.5 h-3.5 mr-1" /> Schausteller einladen
                </Button>
                <Button size="sm" variant="outline" onClick={copyLink} className="text-fuchsia-600 border-fuchsia-200" data-testid="copy-link-btn">
                  {copiedLink ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-500" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                  {copiedLink ? "Kopiert!" : "Anmeldelink"}
                </Button>
              </>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Event Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <CalendarDays className="w-4 h-4" /> <span className="text-xs font-medium">Veranstaltung</span>
            </div>
            <p className="text-sm text-gray-900 font-medium">
              {new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}
            </p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <Clock className="w-4 h-4" /> <span className="text-xs font-medium">Dispo-Zeitraum</span>
            </div>
            <p className="text-sm text-gray-900 font-medium">
              {event.dispo_start ? new Date(event.dispo_start).toLocaleDateString("de-DE") : "–"} – {event.dispo_end ? new Date(event.dispo_end).toLocaleDateString("de-DE") : "–"}
            </p>
            <p className="text-[10px] text-gray-400 mt-1">Aufbau bis Abbau (kWh Ausbau)</p>
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

        {/* Documents Card */}
        <div
          className="bg-white border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-fuchsia-300 hover:bg-fuchsia-50/30 transition-colors"
          onClick={() => navigate(`/kirmes/${id}/dokumente`)}
          data-testid="documents-card"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-fuchsia-50 rounded-lg flex items-center justify-center">
                <FolderOpen className="w-5 h-5 text-fuchsia-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">Dokumentenablage</p>
                <p className="text-xs text-gray-500">Lageplan, Fotos & Unterlagen</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {docCount > 0 && (
                <span className="text-xs bg-fuchsia-100 text-fuchsia-700 px-2 py-0.5 rounded-full font-medium">{docCount}</span>
              )}
              <ArrowLeft className="w-4 h-4 text-gray-400 rotate-180" />
            </div>
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
                    <th className="px-4 py-3 text-right">kWh Einbau</th>
                    <th className="px-4 py-3 text-right">kWh Ausbau</th>
                    <th className="px-4 py-3 text-right">Verbrauch</th>
                    <th className="px-4 py-3 text-right">Preis</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {(event.signups || []).map(signup => {
                    const sch = signup.schausteller;
                    const isExpanded = expandedSignup === signup.id;
                    return (
                    <React.Fragment key={signup.id}>
                    <tr
                      className={`border-b border-gray-100 cursor-pointer transition-colors ${isExpanded ? "bg-fuchsia-50" : "hover:bg-gray-50"}`}
                      onClick={() => setExpandedSignup(isExpanded ? null : signup.id)}
                      data-testid={`signup-${signup.id}`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-900">{sch?.firma || "–"}</td>
                      <td className="px-4 py-3 text-gray-600">{sch?.name || "–"}</td>
                      <td className="px-4 py-3 text-gray-600">{signup.fahrgeschaeft || "–"}</td>
                      <td className="px-4 py-3 font-mono text-gray-900">{signup.platznummer}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-xs bg-fuchsia-50 text-fuchsia-700 px-2 py-0.5 rounded-full">
                          <Zap className="w-3 h-3" /> {signup.connection_type}
                        </span>
                      </td>
                      {editingKwh === signup.id ? (
                        <>
                          <td className="px-4 py-2" onClick={e => e.stopPropagation()}>
                            <Input type="number" step="0.01" value={kwhForm.kwh_einbau} onChange={e => setKwhForm(f => ({ ...f, kwh_einbau: e.target.value }))} className="h-8 w-24 text-right text-sm" placeholder="0.00" data-testid={`kwh-einbau-input-${signup.id}`} />
                          </td>
                          <td className="px-4 py-2" onClick={e => e.stopPropagation()}>
                            <Input type="number" step="0.01" value={kwhForm.kwh_ausbau} onChange={e => setKwhForm(f => ({ ...f, kwh_ausbau: e.target.value }))} className="h-8 w-24 text-right text-sm" placeholder="0.00" data-testid={`kwh-ausbau-input-${signup.id}`} />
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="px-4 py-3 text-right font-mono text-sm text-gray-600">{signup.kwh_einbau != null ? signup.kwh_einbau.toFixed(2) : "–"}</td>
                          <td className="px-4 py-3 text-right font-mono text-sm text-gray-600">{signup.kwh_ausbau != null ? signup.kwh_ausbau.toFixed(2) : "–"}</td>
                        </>
                      )}
                      <td className="px-4 py-3 text-right font-mono text-sm font-medium text-gray-900">
                        {signup.kwh_used != null ? `${signup.kwh_used.toFixed(2)} kWh` : "–"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{(signup.price || 0).toFixed(2)} EUR</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium ${PAYMENT_COLORS[signup.payment_status] || "text-gray-500"}`}>
                          {PAYMENT_LABELS[signup.payment_status] || signup.payment_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          {editingKwh === signup.id ? (
                            <>
                              <Button size="sm" variant="outline" onClick={() => saveKwh(signup.id)} className="h-7 text-xs text-emerald-600" data-testid={`save-kwh-${signup.id}`}>
                                <Check className="w-3 h-3 mr-1" /> OK
                              </Button>
                              <button onClick={() => setEditingKwh(null)} className="p-1.5 text-gray-400 hover:text-gray-600">
                                <ArrowLeft className="w-3.5 h-3.5" />
                              </button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => openKwhEdit(signup)} className="p-1.5 text-gray-400 hover:text-fuchsia-600 transition-colors" title="Zählerstände bearbeiten" data-testid={`edit-kwh-${signup.id}`}>
                                <Pencil className="w-4 h-4" />
                              </button>
                              {signup.invoice_number ? (
                                <>
                                  <button onClick={() => {
                                    const inv = eventInvoices.find(i => i.invoice_number === signup.invoice_number);
                                    if (inv) handleDownloadInvoice(inv.id);
                                  }} className="p-1.5 text-emerald-500 hover:text-emerald-700 transition-colors" title={`PDF ${signup.invoice_number}`} data-testid={`download-inv-${signup.id}`}>
                                    <Download className="w-4 h-4" />
                                  </button>
                                  <button onClick={() => {
                                    const inv = eventInvoices.find(i => i.invoice_number === signup.invoice_number);
                                    if (inv) handleSendInvoice(inv.id);
                                  }} className="p-1.5 text-blue-400 hover:text-blue-600 transition-colors" title="Rechnung per E-Mail senden" data-testid={`send-inv-${signup.id}`}>
                                    <Send className="w-4 h-4" />
                                  </button>
                                </>
                              ) : (
                                <button onClick={() => handleGenerateSingleInvoice(signup.id)} className="p-1.5 text-amber-400 hover:text-amber-600 transition-colors" title="Rechnung erstellen" data-testid={`create-inv-${signup.id}`}>
                                  <FileText className="w-4 h-4" />
                                </button>
                              )}
                              <button onClick={() => handleDeleteSignup(signup.id)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" title="Löschen" data-testid={`delete-signup-${signup.id}`}>
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                    {/* Expanded Detail Panel */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={11} className="p-0">
                          <div className="bg-gray-50 border-y border-gray-200 p-5" data-testid={`detail-${signup.id}`}>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                              {/* Kontaktdaten */}
                              <div>
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Kontaktdaten</h4>
                                <div className="space-y-2 text-sm">
                                  <p><span className="text-gray-400 w-20 inline-block">Firma:</span> <span className="font-medium text-gray-900">{sch?.firma || "–"}</span></p>
                                  <p><span className="text-gray-400 w-20 inline-block">Name:</span> <span className="text-gray-700">{sch?.name || "–"}</span></p>
                                  <p><span className="text-gray-400 w-20 inline-block">Adresse:</span> <span className="text-gray-700">{sch?.strasse || "–"}, {sch?.plz || ""} {sch?.ort || ""}</span></p>
                                  <p><span className="text-gray-400 w-20 inline-block">Telefon:</span> <span className="text-gray-700">{sch?.telefon || "–"}</span></p>
                                  <p><span className="text-gray-400 w-20 inline-block">E-Mail:</span> <span className="text-gray-700">{sch?.email || "–"}</span></p>
                                  <p><span className="text-gray-400 w-20 inline-block">Rechnung:</span> <span className="text-gray-700">{sch?.rechnungs_email || "–"}</span></p>
                                  {sch?.steuernummer && <p><span className="text-gray-400 w-20 inline-block">Steuer-Nr:</span> <span className="text-gray-700 font-mono">{sch.steuernummer}</span></p>}
                                  {sch?.kauf_auf_rechnung && <span className="inline-block mt-1 text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">Kauf auf Rechnung</span>}
                                </div>
                              </div>

                              {/* Anmeldungsdaten */}
                              <div>
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Anmeldung</h4>
                                <div className="space-y-2 text-sm">
                                  <p><span className="text-gray-400 w-24 inline-block">Fahrgeschäft:</span> <span className="font-medium text-gray-900">{signup.fahrgeschaeft || "–"}</span></p>
                                  <p><span className="text-gray-400 w-24 inline-block">Platznummer:</span> <span className="font-mono text-gray-900">{signup.platznummer}</span></p>
                                  <p><span className="text-gray-400 w-24 inline-block">Anschluss:</span> <span className="inline-flex items-center gap-1 text-xs bg-fuchsia-50 text-fuchsia-700 px-2 py-0.5 rounded-full"><Zap className="w-3 h-3" /> {signup.connection_type}</span></p>
                                  <p><span className="text-gray-400 w-24 inline-block">Zahlung:</span> <span className="text-gray-700 capitalize">{signup.payment_method}</span></p>
                                  <p><span className="text-gray-400 w-24 inline-block">Status:</span> <span className={`text-xs font-medium ${PAYMENT_COLORS[signup.payment_status] || "text-gray-500"}`}>{PAYMENT_LABELS[signup.payment_status] || signup.payment_status}</span></p>
                                  <p><span className="text-gray-400 w-24 inline-block">Zähler-ID:</span> <span className="font-mono text-gray-700">{signup.emu_meter_name || signup.meter_id || "Nicht verknüpft"}</span></p>
                                </div>
                              </div>

                              {/* Zählerdaten / Verbrauch */}
                              <div>
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Zählerdaten</h4>
                                <div className="space-y-2 text-sm">
                                  <div className="grid grid-cols-2 gap-3">
                                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                                      <p className="text-[10px] text-gray-400 mb-1">kWh Einbau</p>
                                      <p className="text-lg font-semibold font-mono text-gray-900">{signup.kwh_einbau != null ? signup.kwh_einbau.toFixed(2) : "–"}</p>
                                    </div>
                                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                                      <p className="text-[10px] text-gray-400 mb-1">kWh Ausbau</p>
                                      <p className="text-lg font-semibold font-mono text-gray-900">{signup.kwh_ausbau != null ? signup.kwh_ausbau.toFixed(2) : "–"}</p>
                                    </div>
                                  </div>
                                  <div className="bg-white rounded-lg p-3 border border-gray-200">
                                    <p className="text-[10px] text-gray-400 mb-1">Gesamtverbrauch</p>
                                    <p className="text-xl font-bold font-mono text-fuchsia-700">{signup.kwh_used != null ? `${signup.kwh_used.toFixed(2)} kWh` : "–"}</p>
                                  </div>
                                </div>
                                {/* Invoice info */}
                                {signup.invoice_number && (() => {
                                  const inv = eventInvoices.find(i => i.invoice_number === signup.invoice_number);
                                  return inv ? (
                                    <div className="mt-3 bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                                      <div className="flex items-center justify-between">
                                        <div>
                                          <p className="text-xs font-semibold text-emerald-700">{inv.invoice_number}</p>
                                          <p className="text-[10px] text-emerald-500">{inv.invoice_date} · {inv.status}</p>
                                        </div>
                                        <p className="text-lg font-bold text-emerald-800">{inv.brutto?.toFixed(2)} EUR</p>
                                      </div>
                                      <div className="flex gap-2 mt-2">
                                        <button onClick={() => handleDownloadInvoice(inv.id)} className="text-xs text-emerald-600 hover:text-emerald-800 underline flex items-center gap-1">
                                          <Download className="w-3 h-3" /> PDF
                                        </button>
                                        <button onClick={() => handleSendInvoice(inv.id)} className="text-xs text-blue-600 hover:text-blue-800 underline flex items-center gap-1">
                                          <Send className="w-3 h-3" /> Per E-Mail senden
                                        </button>
                                      </div>
                                    </div>
                                  ) : null;
                                })()}
                                {/* EMU Zähler Live-Daten */}
                                {(() => {
                                  const hasLinked = signup.emu_device_id && signup.emu_meter_id;
                                  const md = meterDataMap[signup.id];
                                  const isLinking = linkingMeter === signup.id;

                                  if (!hasLinked && !isLinking) {
                                    return (
                                      <div className="mt-4 bg-white rounded-lg p-4 border border-dashed border-gray-300 text-center" data-testid={`emu-unlinked-${signup.id}`}>
                                        <Zap className="w-6 h-6 text-gray-300 mx-auto mb-2" />
                                        <p className="text-xs text-gray-400 mb-2">Kein EMU-Zähler verknüpft</p>
                                        <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setLinkingMeter(signup.id); setSelectedMeterCombo(""); }}
                                          className="text-xs text-fuchsia-600 border-fuchsia-200" data-testid={`link-meter-btn-${signup.id}`}>
                                          <Link2 className="w-3 h-3 mr-1" /> Zähler verknüpfen
                                        </Button>
                                      </div>
                                    );
                                  }

                                  if (isLinking) {
                                    return (
                                      <div className="mt-4 bg-white rounded-lg p-4 border border-fuchsia-200" onClick={e => e.stopPropagation()} data-testid={`emu-linking-${signup.id}`}>
                                        {scanningMeter === signup.id ? (
                                          <>
                                            <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">QR-Code scannen</h5>
                                            <QrScanner
                                              onScan={(text) => handleQrScan(text, signup.id)}
                                              onClose={() => setScanningMeter(null)}
                                            />
                                            <p className="text-[10px] text-gray-400 mt-2 text-center">QR-Code auf dem Stromverteiler scannen</p>
                                            <div className="border-t border-gray-100 mt-3 pt-3 flex items-center justify-center gap-4">
                                              <button onClick={() => setScanningMeter(null)} className="text-xs text-gray-500 hover:text-fuchsia-600 underline" data-testid={`switch-manual-${signup.id}`}>
                                                Manuell auswählen
                                              </button>
                                              <Button size="sm" variant="outline" onClick={() => { setScanningMeter(null); setLinkingMeter(null); }}
                                                className="text-xs" data-testid={`cancel-scan-${signup.id}`}>Abbrechen</Button>
                                            </div>
                                          </>
                                        ) : (
                                          <>
                                            <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">EMU-Zähler zuweisen</h5>
                                            <Button size="sm" onClick={() => setScanningMeter(signup.id)} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs mb-3" data-testid={`scan-qr-btn-${signup.id}`}>
                                              <svg className="w-3.5 h-3.5 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                                              QR-Code scannen
                                            </Button>
                                            <div className="border-t border-gray-100 pt-3">
                                              <p className="text-[10px] text-gray-400 mb-2">Oder manuell auswählen:</p>
                                              <select value={selectedMeterCombo} onChange={e => setSelectedMeterCombo(e.target.value)}
                                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:border-fuchsia-500"
                                                data-testid={`meter-select-${signup.id}`}>
                                                <option value="">-- Zähler wählen --</option>
                                                {emuMeters.map(m => (
                                                  <option key={m.id} value={`${m.device_id}|${m.id}`}>
                                                    {m.meter_name} ({m.device_name || m.device_id.slice(0,8)}) – {m.meter_ip}
                                                  </option>
                                                ))}
                                              </select>
                                              <div className="flex gap-2">
                                                <Button size="sm" onClick={() => handleLinkMeter(signup.id)} disabled={!selectedMeterCombo}
                                                  className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs" data-testid={`confirm-link-${signup.id}`}>
                                                  <Link2 className="w-3 h-3 mr-1" /> Verknüpfen
                                                </Button>
                                                <Button size="sm" variant="outline" onClick={() => { setLinkingMeter(null); setSelectedMeterCombo(""); setScanningMeter(null); }}
                                                  className="text-xs">Abbrechen</Button>
                                              </div>
                                            </div>
                                          </>
                                        )}
                                      </div>
                                    );
                                  }

                                  // Has linked meter - show data
                                  return (
                                    <div className="mt-4 space-y-3" data-testid={`emu-data-${signup.id}`}>
                                      <div className="flex items-center justify-between">
                                        <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                                          <Activity className="w-3.5 h-3.5 text-fuchsia-500" /> EMU-Zähler
                                        </h5>
                                        <div className="flex items-center gap-3">
                                          <button onClick={(e) => { e.stopPropagation(); setLinkingMeter(signup.id); setSelectedMeterCombo(""); }}
                                            className="text-[10px] text-fuchsia-500 hover:text-fuchsia-700 flex items-center gap-0.5" data-testid={`relink-meter-${signup.id}`}>
                                            <Link2 className="w-3 h-3" /> Neu verknüpfen
                                          </button>
                                          <button onClick={(e) => { e.stopPropagation(); handleUnlinkMeter(signup.id); }}
                                            className="text-[10px] text-gray-400 hover:text-red-500 flex items-center gap-0.5" data-testid={`unlink-meter-${signup.id}`}>
                                            <Unlink className="w-3 h-3" /> Trennen
                                          </button>
                                          <a href={`${process.env.REACT_APP_BACKEND_URL}/api/kirmes/meters/${signup.emu_meter_id}/qr-label?token=${localStorage.getItem("token")}`}
                                            target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                                            className="text-[10px] text-gray-400 hover:text-fuchsia-600 flex items-center gap-0.5" data-testid={`qr-label-${signup.id}`}>
                                            QR
                                          </a>
                                        </div>
                                      </div>

                                      {/* Meter name + status */}
                                      <div className="bg-white rounded-lg p-3 border border-gray-200">
                                        <div className="flex items-center justify-between mb-2">
                                          <span className="text-xs font-medium text-gray-700">{signup.emu_meter_name || "EMU-Zähler"}</span>
                                          {md?.is_online ? (
                                            <span className="flex items-center gap-1 text-[10px] text-emerald-600"><Wifi className="w-3 h-3" /> Online</span>
                                          ) : (
                                            <span className="flex items-center gap-1 text-[10px] text-gray-400"><WifiOff className="w-3 h-3" /> Offline</span>
                                          )}
                                        </div>

                                        {md?.latest ? (
                                          <div className="grid grid-cols-4 gap-2">
                                            <div className="text-center p-2 bg-gray-50 rounded">
                                              <p className="text-[10px] text-gray-400">Leistung</p>
                                              <p className="text-sm font-bold font-mono text-fuchsia-700">{(md.latest.P_sum_kW || 0).toFixed(2)}</p>
                                              <p className="text-[9px] text-gray-400">kW</p>
                                            </div>
                                            <div className="text-center p-2 bg-gray-50 rounded">
                                              <p className="text-[10px] text-gray-400">Spannung</p>
                                              <p className="text-sm font-bold font-mono text-gray-900">{(md.latest.U_L1 || 0).toFixed(0)}</p>
                                              <p className="text-[9px] text-gray-400">V (L1)</p>
                                            </div>
                                            <div className="text-center p-2 bg-gray-50 rounded">
                                              <p className="text-[10px] text-gray-400">Strom</p>
                                              <p className="text-sm font-bold font-mono text-gray-900">{(md.latest.I_sum || 0).toFixed(1)}</p>
                                              <p className="text-[9px] text-gray-400">A</p>
                                            </div>
                                            <div className="text-center p-2 bg-gray-50 rounded">
                                              <p className="text-[10px] text-gray-400">Frequenz</p>
                                              <p className="text-sm font-bold font-mono text-gray-900">{(md.latest.F_Hz || 0).toFixed(1)}</p>
                                              <p className="text-[9px] text-gray-400">Hz</p>
                                            </div>
                                          </div>
                                        ) : (
                                          <p className="text-xs text-gray-400 text-center py-2">Keine aktuellen Messdaten verfügbar</p>
                                        )}
                                      </div>

                                      {/* Power Chart */}
                                      {md?.history?.length > 1 && (
                                        <div className="bg-white rounded-lg p-3 border border-gray-200">
                                          <p className="text-[10px] text-gray-400 mb-2">Leistungsverlauf (kW)</p>
                                          <ResponsiveContainer width="100%" height={120}>
                                            <LineChart data={md.history.map(h => ({
                                              t: h.ts_utc ? new Date(h.ts_utc).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "",
                                              kW: h.P_sum_kW || 0,
                                            }))}>
                                              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                              <XAxis dataKey="t" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                                              <YAxis tick={{ fontSize: 9 }} width={35} />
                                              <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v) => [`${v.toFixed(3)} kW`, "Leistung"]} />
                                              <Line type="monotone" dataKey="kW" stroke="#a832a8" strokeWidth={1.5} dot={false} />
                                            </LineChart>
                                          </ResponsiveContainer>
                                        </div>
                                      )}

                                      {/* Last reading timestamp */}
                                      {md?.latest?.ts_utc && (
                                        <p className="text-[10px] text-gray-400 text-right">
                                          Letzte Messung: {new Date(md.latest.ts_utc).toLocaleString("de-DE")}
                                        </p>
                                      )}
                                    </div>
                                  );
                                })()}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                    );
                  })}
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

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-8 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 mb-8" data-testid="invite-modal">
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Schausteller einladen</h2>
              <button onClick={() => setShowInviteModal(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4">
              <input
                type="text" placeholder="Suche nach Firma, Name..."
                value={inviteSearch} onChange={e => setInviteSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mb-3 focus:outline-none focus:border-fuchsia-500"
                data-testid="invite-search"
              />
              <div className="max-h-64 overflow-y-auto space-y-1">
                {allSchausteller
                  .filter(s => !inviteSearch || s.firma.toLowerCase().includes(inviteSearch.toLowerCase()) || s.name.toLowerCase().includes(inviteSearch.toLowerCase()))
                  .map(sch => (
                  <label key={sch.id} className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors ${selectedInvites.includes(sch.id) ? "bg-fuchsia-50 border border-fuchsia-200" : "hover:bg-gray-50 border border-transparent"}`} data-testid={`invite-sch-${sch.id}`}>
                    <input type="checkbox" checked={selectedInvites.includes(sch.id)} onChange={() => toggleInvite(sch.id)} className="rounded border-gray-300 text-fuchsia-600" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{sch.firma || sch.name}</p>
                      <p className="text-xs text-gray-500">{sch.firma ? `${sch.name} – ` : ""}{sch.email}</p>
                    </div>
                    {sch.kauf_auf_rechnung && <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">Rechnung</span>}
                  </label>
                ))}
                {allSchausteller.length === 0 && (
                  <p className="text-center text-gray-400 py-6 text-sm">Alle Schausteller sind bereits angemeldet</p>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between p-4 border-t border-gray-200">
              <span className="text-sm text-gray-500">{selectedInvites.length} ausgewählt</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowInviteModal(false)}>Abbrechen</Button>
                <Button size="sm" onClick={sendInvitations} disabled={inviting || selectedInvites.length === 0} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="send-invites-btn">
                  <Mail className="w-3.5 h-3.5 mr-1" /> {inviting ? "Wird gesendet..." : `${selectedInvites.length} einladen`}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
