import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft, Plus, Search, Pencil, Trash2, X, Eye, Send,
  CalendarDays, MapPin, Users, ChevronRight, Copy, Check,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_LABELS = {
  entwurf: "Entwurf",
  freigegeben: "Freigegeben",
  aktiv: "Aktiv",
  abgeschlossen: "Abgeschlossen",
  abgerechnet: "Abgerechnet",
};
const STATUS_COLORS = {
  entwurf: "bg-gray-100 text-gray-600",
  freigegeben: "bg-blue-100 text-blue-700",
  aktiv: "bg-emerald-100 text-emerald-700",
  abgeschlossen: "bg-amber-100 text-amber-700",
  abgerechnet: "bg-fuchsia-100 text-fuchsia-700",
};

const CONNECTION_TYPES = ["16A", "32A", "63A", "125A", "Festanschluss"];

function PriceListModal({ open, onClose }) {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api.get("/kirmes/standard-prices")
      .then(r => setPrices(r.data))
      .catch(() => toast.error("Fehler beim Laden der Preisliste"))
      .finally(() => setLoading(false));
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { prices: prices.map(p => ({ connection_type: p.connection_type, price: p.price })) };
      await api.put("/kirmes/standard-prices", payload);
      toast.success("Preisliste gespeichert");
      onClose();
    } catch { toast.error("Fehler beim Speichern"); }
    finally { setSaving(false); }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4" data-testid="price-list-modal">
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Standard-Preisliste</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4">
          {loading ? <p className="text-gray-400 text-center py-8">Laden...</p> : (
            prices.map((p, i) => (
              <div key={p.connection_type} className="flex items-center gap-3">
                <span className="w-32 text-sm font-medium text-gray-700">{p.connection_type}</span>
                <Input
                  type="number"
                  step="0.01"
                  value={p.price}
                  onChange={e => {
                    const updated = [...prices];
                    updated[i] = { ...p, price: parseFloat(e.target.value) || 0 };
                    setPrices(updated);
                  }}
                  className="flex-1"
                  data-testid={`price-${p.connection_type}`}
                />
                <span className="text-sm text-gray-400">EUR</span>
              </div>
            ))
          )}
          <p className="text-[10px] text-gray-400">Diese Preise werden als Standard für neue Veranstaltungen übernommen. Pro Veranstaltung können die Preise angepasst werden.</p>
        </div>
        <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-prices-btn">
            {saving ? "Speichert..." : "Speichern"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function EventModal({ open, onClose, onSaved, editing }) {
  const [form, setForm] = useState({ name: "", location: "", start_date: "", end_date: "", notes: "", use_standard_prices: true });
  const [customPrices, setCustomPrices] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setForm({
        name: editing.name || "",
        location: editing.location || "",
        start_date: editing.start_date || "",
        end_date: editing.end_date || "",
        notes: editing.notes || "",
        use_standard_prices: false,
      });
      setCustomPrices(editing.prices || []);
    } else {
      setForm({ name: "", location: "", start_date: "", end_date: "", notes: "", use_standard_prices: true });
      setCustomPrices([]);
    }
  }, [open, editing]);

  const handleSave = async () => {
    if (!form.name.trim() || !form.start_date || !form.end_date) {
      toast.error("Name, Start- und Enddatum sind erforderlich");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/kirmes/events/${editing.id}`, {
          ...form,
          custom_prices: customPrices.map(p => ({ connection_type: p.connection_type, price: p.price })),
        });
        toast.success("Veranstaltung aktualisiert");
      } else {
        await api.post("/kirmes/events", {
          ...form,
          custom_prices: form.use_standard_prices ? null : customPrices.map(p => ({ connection_type: p.connection_type, price: p.price })),
        });
        toast.success("Veranstaltung angelegt");
      }
      onSaved();
      onClose();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    finally { setSaving(false); }
  };

  // Load standard prices when switching to custom
  const loadStandardPrices = async () => {
    try {
      const r = await api.get("/kirmes/standard-prices");
      setCustomPrices(r.data.map(p => ({ connection_type: p.connection_type, price: p.price })));
    } catch { /* ignore */ }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-8 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 mb-8" data-testid="event-modal">
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {editing ? "Veranstaltung bearbeiten" : "Neue Veranstaltung"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <Label className="text-gray-700 text-sm">Name *</Label>
            <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="z.B. Rheinkirmes 2026" className="mt-1" data-testid="event-name-input" />
          </div>
          <div>
            <Label className="text-gray-700 text-sm">Ort</Label>
            <Input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="z.B. Düsseldorf" className="mt-1" data-testid="event-location-input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-gray-700 text-sm">Startdatum *</Label>
              <Input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className="mt-1" data-testid="event-start-input" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Enddatum *</Label>
              <Input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className="mt-1" data-testid="event-end-input" />
            </div>
          </div>
          <div>
            <Label className="text-gray-700 text-sm">Notizen</Label>
            <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="event-notes-input" />
          </div>

          {/* Prices */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-900">Preise pro Anschluss</h3>
              {!editing && (
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input
                    type="checkbox"
                    checked={form.use_standard_prices}
                    onChange={e => {
                      const use = e.target.checked;
                      setForm(f => ({ ...f, use_standard_prices: use }));
                      if (!use) loadStandardPrices();
                    }}
                    className="rounded border-gray-300"
                  />
                  Standard-Preisliste
                </label>
              )}
            </div>
            {(editing || !form.use_standard_prices) ? (
              <div className="space-y-2">
                {(customPrices.length === 0 ? CONNECTION_TYPES.map(c => ({ connection_type: c, price: 0 })) : customPrices).map((p, i) => (
                  <div key={p.connection_type} className="flex items-center gap-3">
                    <span className="w-32 text-sm text-gray-600">{p.connection_type}</span>
                    <Input
                      type="number"
                      step="0.01"
                      value={p.price}
                      onChange={e => {
                        const updated = [...customPrices];
                        updated[i] = { ...p, price: parseFloat(e.target.value) || 0 };
                        setCustomPrices(updated);
                      }}
                      className="flex-1"
                      data-testid={`event-price-${p.connection_type}`}
                    />
                    <span className="text-xs text-gray-400">EUR</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3">Preise werden aus der Standard-Preisliste übernommen.</p>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-event-btn">
            {saving ? "Speichert..." : editing ? "Speichern" : "Anlegen"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function KirmesPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showPriceList, setShowPriceList] = useState(false);
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [copiedLink, setCopiedLink] = useState(null);

  const loadEvents = useCallback(async () => {
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : {};
      const r = await api.get("/kirmes/events", { params });
      setEvents(r.data);
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const handleRelease = async (event) => {
    if (!window.confirm(`"${event.name}" freigeben? Schausteller können sich danach anmelden.`)) return;
    try {
      await api.post(`/kirmes/events/${event.id}/release`);
      toast.success("Veranstaltung freigegeben");
      loadEvents();
    } catch { toast.error("Fehler"); }
  };

  const handleDelete = async (event) => {
    if (!window.confirm(`"${event.name}" wirklich löschen?`)) return;
    try {
      await api.delete(`/kirmes/events/${event.id}`);
      toast.success("Veranstaltung gelöscht");
      loadEvents();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const copyRegistrationLink = (eventId) => {
    const link = `${window.location.origin}/kirmes/anmeldung?event=${eventId}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(eventId);
    toast.success("Link kopiert!");
    setTimeout(() => setCopiedLink(null), 2000);
  };

  const filtered = events.filter(e => {
    if (!search) return true;
    const q = search.toLowerCase();
    return e.name.toLowerCase().includes(q) || (e.location || "").toLowerCase().includes(q);
  });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="kirmes-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Kirmes-Verwaltung</h1>
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <Button size="sm" variant="outline" onClick={() => setShowPriceList(true)} className="text-gray-600" data-testid="price-list-btn">
                Standard-Preise
              </Button>
            )}
            <Button size="sm" onClick={() => { setEditingEvent(null); setShowEventModal(true); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-event-btn">
              <Plus className="w-4 h-4 mr-1" /> Neue Veranstaltung
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Suche nach Name, Ort..." value={search} onChange={e => setSearch(e.target.value)} className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500" data-testid="kirmes-search" />
          </div>
          <div className="flex gap-1 flex-wrap">
            {["all", "entwurf", "freigegeben", "aktiv", "abgeschlossen", "abgerechnet"].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${statusFilter === s ? "bg-fuchsia-600 text-white" : "bg-white text-gray-500 hover:text-gray-700 border border-gray-200"}`} data-testid={`filter-${s}`}>
                {s === "all" ? "Alle" : STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        {/* Event List */}
        {loading ? (
          <div className="text-center py-20 text-gray-400">Laden...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20">
            <CalendarDays className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">{events.length === 0 ? "Keine Veranstaltungen angelegt" : "Keine Treffer"}</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filtered.map(event => (
              <div key={event.id} onClick={() => navigate(`/kirmes/${event.id}`)} className="bg-white border border-gray-200 rounded-xl p-5 hover:border-fuchsia-300 transition-colors cursor-pointer" data-testid={`event-${event.id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-base font-semibold text-gray-900 truncate">{event.name}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[event.status] || "bg-gray-100 text-gray-600"}`}>
                        {STATUS_LABELS[event.status] || event.status}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
                      {event.location && (
                        <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {event.location}</span>
                      )}
                      <span className="flex items-center gap-1">
                        <CalendarDays className="w-3.5 h-3.5" />
                        {new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" /> {event.signup_count || 0} Anmeldungen
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                    {event.status === "entwurf" && (
                      <Button size="sm" variant="outline" onClick={() => handleRelease(event)} className="text-blue-600 border-blue-200 hover:bg-blue-50" data-testid={`release-${event.id}`}>
                        <Send className="w-3.5 h-3.5 mr-1" /> Freigeben
                      </Button>
                    )}
                    {["freigegeben", "aktiv"].includes(event.status) && (
                      <button onClick={() => copyRegistrationLink(event.id)} className="p-2 text-gray-400 hover:text-fuchsia-600 transition-colors" title="Anmeldelink kopieren" data-testid={`copy-link-${event.id}`}>
                        {copiedLink === event.id ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                    )}
                    <button onClick={() => { setEditingEvent(event); setShowEventModal(true); }} className="p-2 text-gray-400 hover:text-fuchsia-600 transition-colors" title="Bearbeiten" data-testid={`edit-${event.id}`}>
                      <Pencil className="w-4 h-4" />
                    </button>
                    {event.status === "entwurf" && (
                      <button onClick={() => handleDelete(event)} className="p-2 text-gray-400 hover:text-red-500 transition-colors" title="Löschen" data-testid={`delete-${event.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                    <ChevronRight className="w-5 h-5 text-gray-300 ml-1" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <PriceListModal open={showPriceList} onClose={() => setShowPriceList(false)} />
      <EventModal open={showEventModal} onClose={() => setShowEventModal(false)} onSaved={loadEvents} editing={editingEvent} />
    </div>
  );
}
