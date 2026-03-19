import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft,
  Fuel,
  Check,
  X,
  Pencil,
  Trash2,
  Download,
  Plus,
  Filter,
  Loader2,
  MapPin,
  Calendar,
  Droplets,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${API}/api` });
api.interceptors.request.use((c) => {
  const t = localStorage.getItem("token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

const FUEL_LABELS = { diesel: "Diesel", heizoel_leicht: "HEL schwefelarm", hvo: "HVO" };
const FUEL_COLORS = { diesel: "bg-amber-100 text-amber-700", heizoel_leicht: "bg-blue-100 text-blue-700", hvo: "bg-emerald-100 text-emerald-700" };
const STATUS_LABELS = { pending: "Offen", confirmed: "Bestätigt", rejected: "Abgelehnt" };
const STATUS_COLORS = { pending: "bg-amber-100 text-amber-700", confirmed: "bg-emerald-100 text-emerald-700", rejected: "bg-red-100 text-red-700" };

export default function FuelReceiptsPage() {
  const nav = useNavigate();
  const [receipts, setReceipts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "", fuel_type: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [editReceipt, setEditReceipt] = useState(null);
  const [orders, setOrders] = useState([]);
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isAdmin = user.role === "admin";

  const load = useCallback(async () => {
    try {
      const params = {};
      if (filter.status) params.status = filter.status;
      if (filter.fuel_type) params.fuel_type = filter.fuel_type;
      const [rRes, sRes] = await Promise.all([
        api.get("/fuel-receipts", { params }),
        api.get("/fuel-receipts/stats"),
      ]);
      setReceipts(rRes.data);
      setStats(sRes.data);
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api.get("/orders/epirent").then(r => setOrders(r.data?.orders || [])).catch(() => {});
  }, []);

  const handleConfirm = async (id) => {
    await api.post(`/fuel-receipts/${id}/confirm`);
    toast.success("Beleg bestätigt");
    load();
  };

  const handleReject = async (id) => {
    await api.post(`/fuel-receipts/${id}/reject`);
    toast.success("Beleg abgelehnt");
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Tankbeleg wirklich löschen?")) return;
    await api.delete(`/fuel-receipts/${id}`);
    toast.success("Beleg gelöscht");
    load();
  };

  const handlePdf = (id) => {
    const token = localStorage.getItem("token");
    window.open(`${API}/api/fuel-receipts/${id}/pdf?token=${token}`, "_blank");
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6" data-testid="fuel-receipts-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => nav("/hub")} className="p-2 rounded-lg hover:bg-gray-200" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Tankbelege</h1>
            <p className="text-sm text-gray-500">Digitale Tankbeleg-Verwaltung</p>
          </div>
        </div>
        <Button onClick={() => { setEditReceipt(null); setShowCreate(true); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="create-receipt-btn">
          <Plus className="w-4 h-4 mr-1.5" /> Neuer Beleg
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatCard label="Gesamt" value={stats.total} icon={<Fuel className="w-5 h-5" />} color="text-gray-700 bg-gray-100" />
          <StatCard label="Offen" value={stats.pending} icon={<Calendar className="w-5 h-5" />} color="text-amber-700 bg-amber-100" />
          <StatCard label="Bestätigt" value={stats.confirmed} icon={<Check className="w-5 h-5" />} color="text-emerald-700 bg-emerald-100" />
          <StatCard label="Liter gesamt" value={Object.values(stats.by_fuel_type || {}).reduce((s, v) => s + v.liters, 0).toFixed(0)} icon={<Droplets className="w-5 h-5" />} color="text-blue-700 bg-blue-100" />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))} className="text-sm border rounded-lg px-3 py-1.5" data-testid="filter-status">
          <option value="">Alle Status</option>
          <option value="pending">Offen</option>
          <option value="confirmed">Bestätigt</option>
          <option value="rejected">Abgelehnt</option>
        </select>
        <select value={filter.fuel_type} onChange={e => setFilter(f => ({ ...f, fuel_type: e.target.value }))} className="text-sm border rounded-lg px-3 py-1.5" data-testid="filter-fuel">
          <option value="">Alle Kraftstoffe</option>
          <option value="diesel">Diesel</option>
          <option value="heizoel_leicht">Heizöl Leicht</option>
          <option value="hvo">HVO</option>
        </select>
      </div>

      {/* Receipt List */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-gray-400" /></div>
      ) : receipts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Fuel className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>Keine Tankbelege vorhanden</p>
        </div>
      ) : (
        <div className="space-y-3">
          {receipts.map(r => (
            <div key={r.id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow" data-testid={`receipt-${r.id}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${FUEL_COLORS[r.fuel_type] || "bg-gray-100 text-gray-600"}`}>
                      {r.fuel_type_label || FUEL_LABELS[r.fuel_type] || r.fuel_type}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[r.status] || "bg-gray-100"}`}>
                      {STATUS_LABELS[r.status] || r.status}
                    </span>
                    {r.beleg_nr && <span className="text-xs text-gray-400 font-mono">Beleg #{r.beleg_nr}</span>}
                    <span className="text-xs text-gray-400">{r.date} {r.time}</span>
                  </div>
                  <p className="text-lg font-bold text-gray-900">{r.quantity_liters?.toFixed(1)} Liter</p>
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-500 flex-wrap">
                    {r.order_name && <span>Auftrag: {r.order_name}</span>}
                    {r.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.location}</span>}
                    {r.fahrer && <span>Fahrer: {r.fahrer}</span>}
                    {r.abgabe_start && <span>{r.abgabe_start} - {r.abgabe_ende || "?"}</span>}
                    {r.zaehler_nr && <span className="font-mono">Z-Nr: {r.zaehler_nr}</span>}
                    {isAdmin && r.gps_lat && <span className="text-gray-400">{r.gps_lat?.toFixed(4)}, {r.gps_lng?.toFixed(4)}</span>}
                    {!r.fahrer && <span>von {r.created_by}</span>}
                  </div>
                  {r.notes && <p className="text-xs text-gray-400 mt-1">{r.notes}</p>}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {r.status === "pending" && (
                    <>
                      <button onClick={() => handleConfirm(r.id)} className="p-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-600" title="Bestätigen" data-testid={`confirm-${r.id}`}>
                        <Check className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleReject(r.id)} className="p-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600" title="Ablehnen" data-testid={`reject-${r.id}`}>
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  <button onClick={() => { setEditReceipt(r); setShowCreate(true); }} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="Bearbeiten" data-testid={`edit-${r.id}`}>
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button onClick={() => handlePdf(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="PDF" data-testid={`pdf-${r.id}`}>
                    <Download className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-red-400" title="Löschen" data-testid={`delete-${r.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showCreate && (
        <ReceiptModal
          receipt={editReceipt}
          orders={orders}
          onClose={() => { setShowCreate(false); setEditReceipt(null); }}
          onSave={() => { setShowCreate(false); setEditReceipt(null); load(); }}
        />
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>{icon}</div>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

function ReceiptModal({ receipt, orders, onClose, onSave }) {
  const [form, setForm] = useState({
    order_pk: receipt?.order_pk || "",
    order_name: receipt?.order_name || "",
    fuel_type: receipt?.fuel_type || "diesel",
    quantity_liters: receipt?.quantity_liters || "",
    date: receipt?.date || new Date().toISOString().split("T")[0],
    time: receipt?.time || new Date().toTimeString().slice(0, 5),
    location: receipt?.location || "",
    abgabe_start: receipt?.abgabe_start || "",
    abgabe_ende: receipt?.abgabe_ende || "",
    fahrer: receipt?.fahrer || "",
    notes: receipt?.notes || "",
  });
  const [saving, setSaving] = useState(false);

  const handleOrderSelect = (pk) => {
    const order = orders.find(o => String(o.primary_key) === String(pk));
    setForm(f => ({ ...f, order_pk: pk, order_name: order ? `${order.order_no} - ${order.event || order.contact_name || ""}`.trim() : pk }));
  };

  const handleSave = async () => {
    if (!form.quantity_liters) { toast.error("Bitte Menge eingeben"); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        quantity_liters: parseFloat(form.quantity_liters),
      };
      if (receipt) {
        await api.put(`/fuel-receipts/${receipt.id}`, payload);
        toast.success("Beleg aktualisiert");
      } else {
        await api.post("/fuel-receipts", payload);
        toast.success("Beleg erstellt");
      }
      onSave();
    } catch (err) {
      toast.error(typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="receipt-modal">
        <h2 className="text-lg font-bold text-gray-900 mb-4">{receipt ? "Beleg bearbeiten" : "Neuer Tankbeleg"}</h2>
        <div className="space-y-3">
          <div>
            <Label className="text-sm text-gray-600">Auftrag / Projekt</Label>
            <select value={form.order_pk} onChange={e => handleOrderSelect(e.target.value)} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" data-testid="order-select">
              <option value="">-- Auftrag waehlen --</option>
              {orders.map(o => (
                <option key={o.primary_key} value={o.primary_key}>{o.order_no} - {o.event || o.contact_name || ""}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-sm text-gray-600">Kraftstoffart</Label>
            <select value={form.fuel_type} onChange={e => setForm(f => ({ ...f, fuel_type: e.target.value }))} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" data-testid="fuel-type-select">
              <option value="diesel">Diesel</option>
              <option value="heizoel_leicht">HEL schwefelarm</option>
              <option value="hvo">HVO</option>
            </select>
          </div>
          <div>
            <Label className="text-sm text-gray-600">Menge bei 15 C (Liter)</Label>
            <Input type="number" step="0.1" value={form.quantity_liters} onChange={e => setForm(f => ({ ...f, quantity_liters: e.target.value }))} placeholder="z.B. 183" className="mt-1" data-testid="quantity-input" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Datum</Label>
              <Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className="mt-1" data-testid="date-input" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Uhrzeit</Label>
              <Input type="time" value={form.time} onChange={e => setForm(f => ({ ...f, time: e.target.value }))} className="mt-1" data-testid="time-input" />
            </div>
          </div>

          {/* Druckerdaten */}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Druckerdaten</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Start</Label>
              <Input type="time" step="1" value={form.abgabe_start} onChange={e => setForm(f => ({ ...f, abgabe_start: e.target.value }))} className="mt-1 font-mono" data-testid="abgabe-start-input" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Ende</Label>
              <Input type="time" step="1" value={form.abgabe_ende} onChange={e => setForm(f => ({ ...f, abgabe_ende: e.target.value }))} className="mt-1 font-mono" data-testid="abgabe-ende-input" />
            </div>
          </div>

          {/* Manuelle Felder */}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Manuelle Eingabe</p>
          <div>
            <Label className="text-sm text-gray-600">Standort</Label>
            <Input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="z.B. Baustelle Hauptbahnhof" className="mt-1" data-testid="location-input" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Fahrer</Label>
            <Input value={form.fahrer} onChange={e => setForm(f => ({ ...f, fahrer: e.target.value }))} placeholder="z.B. Timo" className="mt-1" data-testid="fahrer-input" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Bemerkung</Label>
            <Input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" className="mt-1" data-testid="notes-input" />
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <Button onClick={handleSave} disabled={saving} className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-receipt-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
            {receipt ? "Speichern" : "Erstellen"}
          </Button>
          <Button variant="outline" onClick={onClose} className="flex-1">Abbrechen</Button>
        </div>
      </div>
    </div>
  );
}
