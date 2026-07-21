import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "../components/ui/sheet";
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
  ChevronRight,
  Pin,
  Filter,
  FilePlus,
  LogOut,
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
  const { user, logout } = useAuth();
  const isFreelancer = user?.role === "freelancer";
  const handleLogout = () => { logout(); navigate("/login"); };

  // Default-Fenster: 14 Tage in der Vergangenheit bis 14 Tage in der Zukunft.
  // Der Nutzer kann den Zeitraum jederzeit anpassen.
  const defaultFrom = toISODate(new Date(Date.now() - 14 * 24 * 60 * 60 * 1000));
  const defaultTo = toISODate(new Date(Date.now() + 14 * 24 * 60 * 60 * 1000));

  // Default: aktive Jobs im 28-Tage-Fenster um Heute
  const [dateFrom, setDateFrom] = useState(defaultFrom);
  const [dateTo, setDateTo] = useState(defaultTo);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortField, setSortField] = useState("event_start");
  const [sortDir, setSortDir] = useState("asc");
  const [syncing, setSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState(null);

  // ─── Pins (VIP-Aufträge oben) ───
  const [pinnedIds, setPinnedIds] = useState(() => {
    try {
      const raw = localStorage.getItem("orders_pinned_v1");
      return new Set(raw ? JSON.parse(raw) : []);
    } catch { return new Set(); }
  });
  const persistPins = (next) => {
    try { localStorage.setItem("orders_pinned_v1", JSON.stringify(Array.from(next))); } catch {}
  };
  const togglePin = useCallback((pk) => {
    setPinnedIds(prev => {
      const next = new Set(prev);
      if (next.has(pk)) next.delete(pk); else next.add(pk);
      persistPins(next);
      return next;
    });
  }, []);

  // ─── Pull-to-Refresh State ───
  const [pullOffset, setPullOffset] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const pullStartY = useRef(null);
  const pullActive = useRef(false);
  const PULL_TRIGGER = 70;

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
      // Pins immer zuerst (unabhaengig vom Sort-Feld)
      const ap = pinnedIds.has(a.primary_key) ? 0 : 1;
      const bp = pinnedIds.has(b.primary_key) ? 0 : 1;
      if (ap !== bp) return ap - bp;
      let va = a[sortField] ?? "";
      let vb = b[sortField] ?? "";
      if (typeof va === "string") va = va.toLowerCase();
      if (typeof vb === "string") vb = vb.toLowerCase();
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      if (va > vb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });

  // Aktive Filter-Chips (Mobile)
  const activeChips = [];
  if (dateFrom || dateTo) {
    const fmt = (iso) => iso ? new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) : "…";
    activeChips.push({
      key: "dates",
      label: `${fmt(dateFrom)} – ${fmt(dateTo)}`,
      clear: () => { setDateFrom(""); setDateTo(""); },
    });
  }
  if (statusFilter !== "all") {
    const opt = STATUS_OPTIONS.find(o => o.value === statusFilter);
    activeChips.push({
      key: "status",
      label: opt?.label || statusFilter,
      clear: () => setStatusFilter("all"),
    });
  }
  if (search.trim()) {
    activeChips.push({
      key: "search",
      label: `„${search.trim().slice(0, 20)}${search.trim().length > 20 ? "…" : ""}"`,
      clear: () => setSearch(""),
    });
  }

  // Pull-to-Refresh Touch-Handler (nur wenn ScrollY == 0)
  const onPullStart = (e) => {
    if (typeof window !== "undefined" && window.scrollY > 5) return;
    pullStartY.current = e.touches[0].clientY;
    pullActive.current = false;
  };
  const onPullMove = (e) => {
    if (pullStartY.current === null) return;
    const dy = e.touches[0].clientY - pullStartY.current;
    if (dy <= 0) { setPullOffset(0); return; }
    if (window.scrollY > 5) { pullStartY.current = null; setPullOffset(0); return; }
    pullActive.current = true;
    // Dampfen: Widerstand ab 60px staerker
    const damped = dy < 60 ? dy : 60 + (dy - 60) * 0.35;
    setPullOffset(Math.min(damped, 120));
  };
  const onPullEnd = async () => {
    const shouldRefresh = pullActive.current && pullOffset >= PULL_TRIGGER;
    pullStartY.current = null;
    pullActive.current = false;
    if (shouldRefresh) {
      setPullOffset(PULL_TRIGGER);   // halte Position waehrend Refresh
      setRefreshing(true);
      try {
        await triggerSync();
      } finally {
        setRefreshing(false);
        setPullOffset(0);
      }
    } else {
      setPullOffset(0);
    }
  };

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
            {!isFreelancer && (
              <>
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
              </>
            )}
            <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-fuchsia-600" />
              {isFreelancer ? "Meine Aufträge" : "Auftragsverwaltung"}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {lastSynced && !isFreelancer && (
              <span className="text-xs text-gray-400 hidden lg:inline">
                Sync: {new Date(lastSynced).toLocaleString("de-DE", {hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit"})}
              </span>
            )}
            {!isFreelancer && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/project-report/new")}
                className="border-fuchsia-200 text-fuchsia-700 hover:bg-fuchsia-50 hover:text-fuchsia-700 hover:border-fuchsia-300 px-2 sm:px-3"
                data-testid="new-blank-report-btn"
                title="Projektbericht (leer) anlegen"
              >
                <FilePlus className="w-4 h-4 sm:mr-1" />
                <span className="hidden sm:inline">Projektbericht leer</span>
              </Button>
            )}
            {!isFreelancer && (
              <Button
                variant="outline"
                size="sm"
                onClick={triggerSync}
                disabled={syncing}
                data-testid="sync-orders-btn"
                className="px-2 sm:px-3"
                title="Aufträge aktualisieren"
              >
                <RefreshCw className={`w-4 h-4 sm:mr-1 ${syncing ? "animate-spin" : ""}`} />
                <span className="hidden sm:inline">{syncing ? "Synchronisiere..." : "Aktualisieren"}</span>
              </Button>
            )}
            {isFreelancer && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="text-gray-600 hover:text-red-600 hover:border-red-300"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-1" />
                <span className="hidden sm:inline">Abmelden</span>
              </Button>
            )}
            <div className="hidden md:block">
              <Logo size="small" />
            </div>
          </div>
        </div>
      </header>

      {/* Filters - Desktop/Tablet */}
      <div className="hidden md:block bg-white border-b border-gray-200 px-4 py-3">
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

      {/* Filters - Mobile (Sheet) */}
      <div className="md:hidden bg-white border-b border-gray-200 px-3 py-2 flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suche..."
            className="pl-8 h-9 text-sm"
            data-testid="order-search-input-mobile"
          />
        </div>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="relative px-3 h-9" data-testid="mobile-filter-btn">
              <Filter className="w-4 h-4" />
              {(dateFrom || dateTo || statusFilter !== "all") && (
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-fuchsia-500 rounded-full" />
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="rounded-t-2xl">
            <SheetHeader>
              <SheetTitle className="text-left flex items-center gap-2">
                <Filter className="w-4 h-4 text-fuchsia-500" /> Filter
              </SheetTitle>
            </SheetHeader>
            <div className="space-y-4 mt-4 pb-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">Zeitraum</label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] text-gray-500 mb-0.5">Von</label>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                      className="w-full px-2 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500"
                      data-testid="date-from-input-mobile"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-gray-500 mb-0.5">Bis</label>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => setDateTo(e.target.value)}
                      className="w-full px-2 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500"
                      data-testid="date-to-input-mobile"
                    />
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500 bg-white"
                  data-testid="status-filter-select-mobile"
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500" data-testid="order-count-mobile">
                  {loading ? "Laden..." : `${sortedOrders.length} Aufträge`}
                </span>
                {(dateFrom || dateTo || statusFilter !== "all") && (
                  <button
                    onClick={() => { setDateFrom(""); setDateTo(""); setStatusFilter("all"); }}
                    className="text-fuchsia-600 hover:text-fuchsia-700 font-medium"
                    data-testid="clear-filter-btn"
                  >
                    Filter zurücksetzen
                  </button>
                )}
              </div>
            </div>
          </SheetContent>
        </Sheet>
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
            <>
              {/* Filter-Chips ueber der Liste (Mobile) */}
              {activeChips.length > 0 && (
                <div className="md:hidden flex flex-wrap gap-1.5 mb-2" data-testid="filter-chips">
                  {activeChips.map(chip => (
                    <button
                      key={chip.key}
                      onClick={chip.clear}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-fuchsia-100 text-fuchsia-700 text-xs font-medium hover:bg-fuchsia-200"
                      data-testid={`chip-${chip.key}`}
                    >
                      {chip.label}
                      <XCircle className="w-3 h-3" />
                    </button>
                  ))}
                  {activeChips.length > 1 && (
                    <button
                      onClick={() => { setDateFrom(""); setDateTo(""); setStatusFilter("all"); setSearch(""); }}
                      className="text-[10px] text-gray-500 hover:text-gray-700 underline ml-1 self-center"
                      data-testid="chip-clear-all"
                    >
                      Alle löschen
                    </button>
                  )}
                </div>
              )}

              {/* Mobile: Card-Layout (<md) mit Pull-to-Refresh */}
              <div
                className="md:hidden relative"
                onTouchStart={onPullStart}
                onTouchMove={onPullMove}
                onTouchEnd={onPullEnd}
                onTouchCancel={onPullEnd}
                data-testid="orders-mobile-list"
              >
                {/* Pull-Indikator */}
                {(pullOffset > 0 || refreshing) && (
                  <div
                    className="absolute left-0 right-0 -top-2 flex items-center justify-center text-fuchsia-500 pointer-events-none"
                    style={{ height: Math.min(pullOffset, 70), transition: pullActive.current ? "none" : "height 200ms ease-out" }}
                    aria-live="polite"
                  >
                    <div className="flex items-center gap-2 text-xs font-medium">
                      <RefreshCw className={`w-4 h-4 ${refreshing || pullOffset >= PULL_TRIGGER ? "animate-spin" : ""}`}
                                 style={{ transform: refreshing ? "none" : `rotate(${pullOffset * 3}deg)` }} />
                      {refreshing ? "Aktualisiere…" : pullOffset >= PULL_TRIGGER ? "Loslassen zum Aktualisieren" : "Zum Aktualisieren ziehen"}
                    </div>
                  </div>
                )}
                <div
                  className="space-y-2"
                  style={{ transform: `translateY(${pullOffset}px)`, transition: pullActive.current ? "none" : "transform 200ms ease-out" }}
                >
                  {loading && orders.length === 0 ? (
                    <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-fuchsia-500 mb-2" />
                      <span className="text-sm text-gray-500">Aufträge werden geladen...</span>
                    </div>
                  ) : (
                    sortedOrders.map((order) => (
                      <SwipeableOrderCard
                        key={order.primary_key}
                        order={order}
                        pinned={pinnedIds.has(order.primary_key)}
                        onOpen={() => navigate(`/orders/${order.primary_key}`)}
                        onTogglePin={() => togglePin(order.primary_key)}
                      />
                    ))
                  )}
                </div>
              </div>

              {/* Desktop/Tablet: Table (md und höher) */}
              <div className="hidden md:block bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
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
            </>
          )}
        </div>
      </main>
    </div>
  );
}

// ─── Swipeable Order Card (Mobile) ────────────────────────────────────
// Swipe LINKS: zeigt "Öffnen"-Zone rechts und navigiert bei Threshold.
// Swipe RECHTS: zeigt "Pin"-Zone links, togglet Pin-Status bei Threshold.
// Tap: Standard-Navigation. Auto-Reset bei zu kurzem Swipe.
function SwipeableOrderCard({ order, onOpen, onTogglePin, pinned }) {
  const [offset, setOffset] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const startX = useRef(null);
  const startY = useRef(null);
  const locked = useRef(false);
  const cancelClick = useRef(false);

  const REVEAL_WIDTH = 96;
  const TRIGGER_DIST = 70;

  const onTouchStart = (e) => {
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
    locked.current = false;
    cancelClick.current = false;
    setSwiping(true);
  };
  const onTouchMove = (e) => {
    if (startX.current === null) return;
    const dx = e.touches[0].clientX - startX.current;
    const dy = e.touches[0].clientY - startY.current;
    if (!locked.current) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      if (Math.abs(dy) > Math.abs(dx)) {
        startX.current = null;
        setSwiping(false);
        return;
      }
      locked.current = true;
    }
    cancelClick.current = true;
    // Beide Richtungen erlaubt, gedämpft
    const clamped = Math.max(Math.min(dx, REVEAL_WIDTH * 1.4), -REVEAL_WIDTH * 1.4);
    setOffset(clamped);
  };
  const onTouchEnd = () => {
    setSwiping(false);
    if (offset <= -TRIGGER_DIST) {
      setOffset(-REVEAL_WIDTH);
      setTimeout(() => { onOpen(); setOffset(0); }, 120);
    } else if (offset >= TRIGGER_DIST) {
      setOffset(REVEAL_WIDTH);
      setTimeout(() => { onTogglePin && onTogglePin(); setOffset(0); }, 120);
    } else {
      setOffset(0);
    }
    startX.current = null;
    startY.current = null;
    locked.current = false;
  };

  const handleClick = (e) => {
    if (cancelClick.current) {
      e.preventDefault();
      e.stopPropagation();
      cancelClick.current = false;
      return;
    }
    onOpen();
  };

  return (
    <div className="relative overflow-hidden rounded-lg" data-testid={`swipe-wrap-${order.primary_key}`}>
      {/* Pin-Zone (links, sichtbar bei Rechts-Swipe) */}
      <div
        className={`absolute inset-y-0 left-0 flex items-center justify-center text-white px-4 ${pinned ? "bg-gradient-to-r from-gray-500 to-gray-400" : "bg-gradient-to-r from-amber-500 to-amber-400"}`}
        style={{ width: REVEAL_WIDTH }}
        aria-hidden="true"
      >
        <div className="flex flex-col items-center gap-0.5">
          <Pin className={`w-5 h-5 ${pinned ? "" : "rotate-45"}`} />
          <span className="text-[10px] font-medium">{pinned ? "Lösen" : "Pinnen"}</span>
        </div>
      </div>
      {/* Öffnen-Zone (rechts, sichtbar bei Links-Swipe) */}
      <div
        className="absolute inset-y-0 right-0 flex items-center justify-center text-white bg-gradient-to-l from-fuchsia-500 to-fuchsia-400 px-4"
        style={{ width: REVEAL_WIDTH }}
        aria-hidden="true"
      >
        <div className="flex flex-col items-center gap-0.5">
          <ChevronRight className="w-5 h-5" />
          <span className="text-[10px] font-medium">Öffnen</span>
        </div>
      </div>
      {/* Vordere Karte */}
      <button
        type="button"
        onClick={handleClick}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onTouchCancel={onTouchEnd}
        className={`relative w-full text-left bg-white border p-3 hover:border-fuchsia-300 active:bg-fuchsia-50/50 ${pinned ? "border-l-4 border-l-amber-400 border-y-gray-200 border-r-gray-200" : "border-gray-200"} ${order.is_canceled ? "opacity-50" : ""} ${swiping ? "" : "transition-transform duration-150 ease-out"}`}
        style={{ transform: `translateX(${offset}px)`, touchAction: "pan-y" }}
        data-testid={`order-card-${order.primary_key}`}
      >
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="flex items-center gap-1.5 min-w-0">
            {pinned && <Pin className="w-3 h-3 text-amber-500 flex-shrink-0" data-testid="pin-badge" />}
            <span className="font-mono text-xs font-semibold text-fuchsia-700 truncate" data-testid="order-no">
              {order.order_no}
            </span>
          </div>
          <StatusBadge order={order} />
        </div>
        <div className="font-medium text-sm text-gray-900 mb-1 truncate" data-testid="order-event">
          {order.event || "—"}
        </div>
        <div className="text-xs text-gray-500 space-y-0.5">
          <div className="truncate" data-testid="order-contact">{order.contact_name || "—"}</div>
          {order.address && (
            <div className="flex items-start gap-1 truncate" data-testid="order-address">
              <MapPin className="w-3 h-3 flex-shrink-0 mt-0.5 text-gray-400" />
              <span className="truncate">{order.address}</span>
            </div>
          )}
          <div className="text-gray-400" data-testid="order-period">
            {formatDateRange(
              order.event_start || order.dispo_start,
              order.event_end || order.dispo_end
            )}
          </div>
        </div>
      </button>
    </div>
  );
}
