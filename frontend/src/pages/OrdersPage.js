import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft,
  ClipboardList,
  Search,
  Calendar,
  Loader2,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Archive,
  MapPin,
  ChevronUp,
  ChevronDown,
  Filter,
} from "lucide-react";

const formatDate = (d) => {
  if (!d || d === "0000-00-00") return "—";
  const parts = d.split("-");
  if (parts.length !== 3) return d;
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
};

const formatDateRange = (start, end) => {
  const s = formatDate(start);
  const e = formatDate(end);
  if (s === "—" && e === "—") return "—";
  if (s === e) return s;
  return `${s} – ${e}`;
};

const toISODate = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const StatusBadge = ({ order }) => {
  if (order.is_canceled)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700" data-testid="status-canceled">
        <XCircle className="w-3 h-3" /> Storniert
      </span>
    );
  if (order.is_confirmed)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-700" data-testid="status-confirmed">
        <CheckCircle className="w-3 h-3" /> Bestätigt
      </span>
    );
  if (order.is_archived)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600" data-testid="status-archived">
        <Archive className="w-3 h-3" /> Archiviert
      </span>
    );
  if (order.status)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700" data-testid="status-custom">
        {order.status}
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-700" data-testid="status-open">
      Offen
    </span>
  );
};

const STATUS_OPTIONS = [
  { value: "all", label: "Alle Status" },
  { value: "confirmed", label: "Bestätigt" },
  { value: "open", label: "Offen" },
  { value: "canceled", label: "Storniert" },
  { value: "archived", label: "Archiviert" },
];

const getOrderStatus = (order) => {
  if (order.is_canceled) return "canceled";
  if (order.is_confirmed) return "confirmed";
  if (order.is_archived) return "archived";
  return "open";
};

export default function OrdersPage() {
  const navigate = useNavigate();

  const today = toISODate(new Date());

  // Default: nur aktive Jobs (heute im Veranstaltungszeitraum)
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortField, setSortField] = useState("event_start");
  const [sortDir, setSortDir] = useState("asc");
  const [syncing, setSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState(null);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page_size: "500" });
      if (dateFrom) params.append("date_from", dateFrom);
      if (dateTo) params.append("date_to", dateTo);
      if (search.trim()) params.append("search", search.trim());

      const { data } = await api.get(`/orders/epirent?${params}`);
      setOrders(data.orders || []);
    } catch (err) {
      const msg = err.response?.data?.detail || "Fehler beim Laden der Auftraege";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, search]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const { data } = await api.get("/orders/sync/status");
      setLastSynced(data.last_synced);
    } catch {}
  }, []);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      const { data } = await api.post("/orders/sync/trigger");
      if (data.status === "ok") {
        toast.success(`${data.count} Auftraege synchronisiert`);
      } else if (data.status === "already_running") {
        toast.info("Synchronisierung laeuft bereits");
      } else {
        toast.error(data.message || "Sync fehlgeschlagen");
      }
      await fetchOrders();
      await fetchSyncStatus();
    } catch (err) {
      toast.error("Sync fehlgeschlagen");
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchSyncStatus();
  }, [fetchSyncStatus]);

  useEffect(() => {
    const timer = setTimeout(fetchOrders, 300);
    return () => clearTimeout(timer);
  }, [fetchOrders]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sortedOrders = [...orders]
    .filter((o) => statusFilter === "all" || getOrderStatus(o) === statusFilter)
    .sort((a, b) => {
    let va = a[sortField] ?? "";
    let vb = b[sortField] ?? "";
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDir === "asc" ? (
      <ChevronUp className="w-3 h-3 inline ml-1" />
    ) : (
      <ChevronDown className="w-3 h-3 inline ml-1" />
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="orders-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/hub")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-hub-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" /> Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-fuchsia-600" />
              Auftragsverwaltung
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {lastSynced && (
              <span className="text-xs text-gray-400 hidden sm:inline">
                Sync: {new Date(lastSynced).toLocaleString("de-DE", {hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit"})}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={triggerSync}
              disabled={syncing}
              data-testid="sync-orders-btn"
            >
              <RefreshCw className={`w-4 h-4 mr-1 ${syncing ? "animate-spin" : ""}`} />
              {syncing ? "Synchronisiere..." : "Aktualisieren"}
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-end gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <div>
              <label className="block text-xs text-gray-500 mb-1">Von</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500"
                data-testid="date-from-input"
              />
            </div>
            <span className="text-gray-400 mt-4">–</span>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Bis</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500"
                data-testid="date-to-input"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <div>
              <label className="block text-xs text-gray-500 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500 bg-white min-w-[140px]"
                data-testid="status-filter-select"
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suche: Auftrag, Event, Kunde, Lieferanschrift..."
              className="pl-9 h-9 text-sm"
              data-testid="order-search-input"
            />
          </div>

          <div className="text-sm text-gray-500 ml-auto" data-testid="order-count">
            {loading ? (
              <span className="flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" /> Laden...
              </span>
            ) : (
              `${sortedOrders.length} Aufträge`
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          {error && !loading && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-700" data-testid="orders-error">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <div>
                <p className="font-medium">Fehler beim Laden</p>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && orders.length === 0 && (
            <div className="text-center py-16" data-testid="orders-empty">
              <ClipboardList className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Keine Aufträge gefunden</h2>
              <p className="text-sm text-gray-500 max-w-md mx-auto">
                Im ausgewählten Zeitraum wurden keine Aufträge gefunden. Bitte passen Sie die Filterkriterien an.
              </p>
            </div>
          )}

          {(loading || orders.length > 0) && (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="orders-table">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th
                        className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none whitespace-nowrap"
                        onClick={() => handleSort("order_no")}
                        data-testid="sort-order-no"
                      >
                        Auftrag-Nr. <SortIcon field="order_no" />
                      </th>
                      <th
                        className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                        onClick={() => handleSort("event")}
                        data-testid="sort-event"
                      >
                        Event / Projekt <SortIcon field="event" />
                      </th>
                      <th
                        className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none whitespace-nowrap"
                        onClick={() => handleSort("event_start")}
                        data-testid="sort-event-start"
                      >
                        Veranstaltungszeitraum <SortIcon field="event_start" />
                      </th>
                      <th
                        className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                        onClick={() => handleSort("contact_name")}
                        data-testid="sort-contact"
                      >
                        Kunde <SortIcon field="contact_name" />
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">
                        Lieferanschrift
                      </th>
                      <th
                        className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none whitespace-nowrap"
                        onClick={() => handleSort("is_confirmed")}
                        data-testid="sort-status"
                      >
                        Status <SortIcon field="is_confirmed" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && orders.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center">
                          <Loader2 className="w-6 h-6 animate-spin mx-auto text-fuchsia-500 mb-2" />
                          <span className="text-gray-500">Aufträge werden geladen...</span>
                        </td>
                      </tr>
                    ) : (
                      sortedOrders.map((order) => (
                        <tr
                          key={order.primary_key}
                          className={`border-b border-gray-100 hover:bg-fuchsia-50/50 transition-colors cursor-pointer ${
                            order.is_canceled ? "opacity-50" : ""
                          }`}
                          onClick={() => navigate(`/orders/${order.primary_key}`)}
                          data-testid={`order-row-${order.primary_key}`}
                        >
                          <td className="px-4 py-3 font-mono font-medium text-fuchsia-700 whitespace-nowrap" data-testid="order-no">
                            {order.order_no}
                          </td>
                          <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate" data-testid="order-event">
                            {order.event || "—"}
                          </td>
                          <td className="px-4 py-3 text-gray-600 whitespace-nowrap" data-testid="order-period">
                            {formatDateRange(
                              order.event_start || order.dispo_start,
                              order.event_end || order.dispo_end
                            )}
                          </td>
                          <td className="px-4 py-3 text-gray-700 max-w-[200px] truncate" data-testid="order-contact">
                            {order.contact_name || "—"}
                          </td>
                          <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate" data-testid="order-address">
                            {order.address ? (
                              <span className="flex items-center gap-1">
                                <MapPin className="w-3 h-3 flex-shrink-0 text-gray-400" />
                                {order.address}
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-4 py-3" data-testid="order-status">
                            <StatusBadge order={order} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
