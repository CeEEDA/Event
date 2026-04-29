import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Logo } from "../components/Logo";
import { openExternal } from "../lib/openExternal";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Search, Download, Fuel, Filter,
  Warehouse, Truck, CheckCircle, Clock, XCircle,
  Image as ImageIcon, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_CONFIG = {
  confirmed: { label: "Bestätigt", color: "text-emerald-700", bg: "bg-emerald-50", icon: CheckCircle },
  pending: { label: "Offen", color: "text-amber-700", bg: "bg-amber-50", icon: Clock },
  rejected: { label: "Abgelehnt", color: "text-red-700", bg: "bg-red-50", icon: XCircle },
};

export default function FuelManagementPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [receipts, setReceipts] = useState([]);
  const [stats, setStats] = useState(null);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("alle");
  const [filterCategory, setFilterCategory] = useState("alle");
  const [loading, setLoading] = useState(true);
  const [bitmapReceipt, setBitmapReceipt] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [receiptsRes, statsRes] = await Promise.all([
        api.get("/fuel-receipts"),
        api.get("/fuel-receipts/stats"),
      ]);
      setReceipts(receiptsRes.data);
      setStats(statsRes.data);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const confirm = async (id) => {
    try {
      await api.post(`/fuel-receipts/${id}/confirm`);
      toast.success("Beleg bestätigt");
      loadData();
    } catch { toast.error("Fehler"); }
  };

  const filtered = receipts.filter(r => {
    if (filterStatus !== "alle" && r.status !== filterStatus) return false;
    if (filterCategory === "lager" && r.category !== "lager") return false;
    if (filterCategory === "kunde" && r.category === "lager") return false;
    if (search) {
      const s = search.toLowerCase();
      const match = (r.beleg_nr || "").toLowerCase().includes(s)
        || (r.customer_name || r.order_name || "").toLowerCase().includes(s)
        || (r.fuel_type || "").toLowerCase().includes(s)
        || (r.device_name || "").toLowerCase().includes(s);
      if (!match) return false;
    }
    return true;
  });

  const totalLiters = filtered.reduce((s, r) => s + (r.quantity_liters || 0), 0);
  const lagerLiters = receipts.filter(r => r.category === "lager").reduce((s, r) => s + (r.quantity_liters || 0), 0);
  const kundeLiters = receipts.filter(r => r.category !== "lager").reduce((s, r) => s + (r.quantity_liters || 0), 0);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="fuel-management-page">
      <header className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="h-8 w-8" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <Fuel className="w-5 h-5 text-amber-600" />
            <h1 className="text-base font-semibold text-gray-900">Tankbeleg-Verwaltung</h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 w-full space-y-6">
        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button onClick={() => setFilterCategory("alle")} className={`bg-white border rounded-lg p-4 text-left transition ${filterCategory === "alle" ? "border-amber-400 ring-1 ring-amber-200" : "border-gray-200"}`} data-testid="stat-total-fuel">
            <div className="flex items-center gap-2 mb-1">
              <Fuel className="w-4 h-4 text-amber-500" />
              <span className="text-xs text-gray-500">Gesamt</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{receipts.length}</p>
            <p className="text-xs text-gray-400">{totalLiters.toFixed(1)} Liter</p>
          </button>
          <button onClick={() => setFilterCategory("kunde")} className={`bg-white border rounded-lg p-4 text-left transition ${filterCategory === "kunde" ? "border-emerald-400 ring-1 ring-emerald-200" : "border-gray-200"}`} data-testid="stat-kunde-fuel">
            <div className="flex items-center gap-2 mb-1">
              <Truck className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-gray-500">Kunde</span>
            </div>
            <p className="text-2xl font-bold text-emerald-600">{receipts.filter(r => r.category !== "lager").length}</p>
            <p className="text-xs text-emerald-500">{kundeLiters.toFixed(1)} Liter</p>
          </button>
          <button onClick={() => setFilterCategory("lager")} className={`bg-white border rounded-lg p-4 text-left transition ${filterCategory === "lager" ? "border-violet-400 ring-1 ring-violet-200" : "border-gray-200"}`} data-testid="stat-lager-fuel">
            <div className="flex items-center gap-2 mb-1">
              <Warehouse className="w-4 h-4 text-violet-500" />
              <span className="text-xs text-gray-500">Lager / Testlauf</span>
            </div>
            <p className="text-2xl font-bold text-violet-600">{receipts.filter(r => r.category === "lager").length}</p>
            <p className="text-xs text-violet-500">{lagerLiters.toFixed(1)} Liter</p>
          </button>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-1">
              <Filter className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Nach Kraftstoff</span>
            </div>
            {stats?.by_fuel_type && Object.entries(stats.by_fuel_type).map(([type, data]) => (
              <p key={type} className="text-xs text-gray-600">
                <span className="font-medium">{type || "Unbekannt"}</span>: {data.liters?.toFixed(1)} L ({data.count}x)
              </p>
            ))}
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Suche Belegnr., Kunde, Auftrag, Kraftstoff..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-10 border-gray-300"
              data-testid="fuel-search"
            />
          </div>
        </div>

        {/* Table */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full" data-testid="fuel-table">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Beleg-Nr.</th>
                  <th className="px-4 py-3 text-left">Kategorie</th>
                  <th className="px-4 py-3 text-left">Kunde / Auftrag</th>
                  <th className="px-4 py-3 text-left hidden md:table-cell">Kraftstoff</th>
                  <th className="px-4 py-3 text-right">Liter</th>
                  <th className="px-4 py-3 text-left hidden sm:table-cell">Datum</th>
                  <th className="px-4 py-3 text-left hidden lg:table-cell">Gerät</th>
                  <th className="px-4 py-3 text-right">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">Laden...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">Keine Tankbelege gefunden</td></tr>
                ) : filtered.map(r => {
                  const st = STATUS_CONFIG[r.status] || STATUS_CONFIG.pending;
                  const Icon = st.icon;
                  const isLager = r.category === "lager";
                  return (
                    <tr key={r.id} className={`hover:bg-gray-50 ${isLager ? "bg-violet-50/30" : ""}`} data-testid={`fuel-row-${r.id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-gray-900">{r.beleg_nr || "-"}</span>
                          {r.needs_review && (
                            <span title={r.review_reason || "Manuelle Prüfung erforderlich"} className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded" data-testid={`review-flag-${r.id}`}>
                              <AlertTriangle className="w-3 h-3" /> Review
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {isLager ? (
                          <span className="inline-flex items-center gap-1 text-xs text-violet-700 bg-violet-100 px-2 py-0.5 rounded-full">
                            <Warehouse className="w-3 h-3" /> Lager
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                            <Truck className="w-3 h-3" /> Kunde
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium text-gray-900">{r.customer_name || r.order_name || "-"}</p>
                        {r.order_pk && <p className="text-xs text-gray-400">Auftrag #{r.order_pk}</p>}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-sm text-gray-600">{r.fuel_type || "-"}</td>
                      <td className="px-4 py-3 text-sm text-right font-mono font-semibold text-gray-900">{(r.quantity_liters || 0).toFixed(1)} L</td>
                      <td className="px-4 py-3 hidden sm:table-cell text-sm text-gray-500">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString("de-DE") : "-"}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-xs text-gray-400">{r.device_name || r.source || "-"}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {r.status === "pending" && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-emerald-500 hover:text-emerald-700" onClick={() => confirm(r.id)} title="Bestätigen" data-testid={`confirm-fuel-${r.id}`}>
                              <CheckCircle className="w-4 h-4" />
                            </Button>
                          )}
                          {r.source === "pi" && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-gray-400 hover:text-fuchsia-600" onClick={() => setBitmapReceipt(r)} title="Original-Druck anzeigen" data-testid={`bitmap-fuel-${r.id}`}>
                              <ImageIcon className="w-4 h-4" />
                            </Button>
                          )}
                          {r.id && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-gray-400 hover:text-amber-600" onClick={() => {
                              const token = localStorage.getItem("token");
                              const url = `${process.env.REACT_APP_BACKEND_URL}/api/fuel-receipts/${r.id}/pdf?token=${token}`;
                              openExternal(url, { title: `Tankbeleg ${r.beleg_nr || ""}` });
                            }} title="PDF" data-testid={`pdf-fuel-${r.id}`}>
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>

      {bitmapReceipt && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setBitmapReceipt(null)} data-testid="bitmap-modal">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-auto p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Original-Druck (Sening MultiFlow)</h3>
              <button onClick={() => setBitmapReceipt(null)} className="text-gray-400 hover:text-gray-700" data-testid="bitmap-close">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="text-sm text-gray-600 mb-3">
              Beleg {bitmapReceipt.beleg_nr || "-"} · {bitmapReceipt.quantity_liters?.toFixed?.(1) || "-"} L · {bitmapReceipt.date || "-"}
            </div>
            {bitmapReceipt.needs_review && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3 flex items-start gap-2 text-sm text-amber-900">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Manuelle Prüfung erforderlich:</strong> {bitmapReceipt.review_reason || "Einige Felder konnten nicht automatisch erkannt werden"}
                </div>
              </div>
            )}
            <img
              src={`${process.env.REACT_APP_BACKEND_URL}/api/fuel-receipts/${bitmapReceipt.id}/bitmap.png?token=${localStorage.getItem("token")}`}
              alt="Original-Beleg"
              className="w-full border border-gray-200 rounded-lg bg-gray-50"
              data-testid="bitmap-image"
            />
          </div>
        </div>
      )}
    </div>
  );
}
