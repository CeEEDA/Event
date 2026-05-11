/**
 * EinsatzzentralePiPage — Touch-Kiosk im Portal-Look (Light Theme).
 *
 * State-Machine:
 *   user_select  -> Grid aller Mitarbeiter/Freelancer
 *   password     -> Passwort-Eingabe fuer ausgewaehlten User
 *   order_select -> Aktive Auftraege (heute -14 ... +14 Tage)
 *   workspace    -> Projekt-Header + Wetter + 4 Tiles
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import {
  Users, LogOut, ChevronLeft, Search, Calendar, MapPin, User as UserIcon,
  Loader2, AlertCircle, ArrowRight, Building2, ClipboardList, Cog, BookOpen,
  FileText, MapPinned, CloudSun, Wind, CloudRain,
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Logo } from "../components/Logo";

// ----------------------------------------------------------------------------
// KIOSK-MODE: Live-Reload (Webpack-Dev-Server) deaktivieren.
// Cloudflare-Tunnel timeouted WebSocket-Verbindung alle 10s -> Reload-Loop.
// Diese Page MUSS dauerhaft stabil bleiben da der Pi keine User-Eingabe
// erlaubt um manuell zu reloaden.
// Nur aktiv wenn Pfad mit /einsatzzentrale startet (sonst stoert es Dev-Workflow).
// ----------------------------------------------------------------------------
if (typeof window !== "undefined"
    && window.location.pathname.startsWith("/einsatzzentrale")
    && !window.__kioskReloadBlocked) {
  window.__kioskReloadBlocked = true;
  try {
    const noop = () => { console.log("[Kiosk] reload blocked"); };
    Object.defineProperty(window.location, "reload", {
      configurable: true, writable: false, value: noop,
    });
  } catch (e) { /* manche Browser blockieren das - ok */ }
  try {
    if (window.__webpack_dev_server__) {
      window.__webpack_dev_server__.reloadApp = () => { console.log("[Kiosk] WDS reload blocked"); };
    }
  } catch (e) { /* ignore */ }
  // WDS-Client wird ueber import.meta / window-Events getriggert - WS einfach killen
  try {
    const OrigWS = window.WebSocket;
    window.WebSocket = function (url, ...rest) {
      if (typeof url === "string" && (url.includes("/ws") || url.includes("sockjs") || url.includes("webpack"))) {
        console.log("[Kiosk] dev-server WS blocked:", url);
        // Dummy-Objekt zurueckgeben das nie connected ist
        return { readyState: 3, close: () => {}, send: () => {}, addEventListener: () => {}, removeEventListener: () => {} };
      }
      return new OrigWS(url, ...rest);
    };
    window.WebSocket.prototype = OrigWS.prototype;
    window.WebSocket.CONNECTING = 0;
    window.WebSocket.OPEN = 1;
    window.WebSocket.CLOSING = 2;
    window.WebSocket.CLOSED = 3;
  } catch (e) { /* ignore */ }
}

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const SS_TOKEN = "einsatzzentrale_token";
const SS_USER = "einsatzzentrale_user";
const SS_PHASE = "einsatzzentrale_phase";
const SS_ORDER = "einsatzzentrale_order";

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch { return iso; }
}

function fmtRange(start, end) {
  if (!start && !end) return "";
  if (start && end && start === end) return fmtDate(start);
  return `${fmtDate(start)} – ${fmtDate(end)}`;
}

// ---------------------------------------------------------------------------
// Wiederverwendbare Header-Komponenten
// ---------------------------------------------------------------------------
function KioskTopBar({ subtitle, right }) {
  return (
    <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 sticky top-0 z-20">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <Logo size="normal" />
          <div className="hidden sm:block border-l border-gray-200 pl-4">
            <p className="text-sm font-semibold text-gray-900">Einsatzzentrale</p>
            {subtitle && <p className="text-xs text-gray-500 truncate max-w-xs">{subtitle}</p>}
          </div>
        </div>
        {right}
      </div>
    </header>
  );
}

function KioskHeaderUser({ user, subtitle, onLogout }) {
  const initials = (user.name || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
  const isFreelancer = user.role === "freelancer";
  return (
    <KioskTopBar
      subtitle={subtitle}
      right={
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2.5 pr-2">
            <div className="text-right">
              <p className="text-sm font-medium text-gray-900" data-testid="ez-header-user">{user.name}</p>
              <p className="text-[10px] uppercase tracking-wide font-semibold text-gray-500">{user.role}</p>
            </div>
            <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm ${
              isFreelancer ? "bg-amber-100 text-amber-700" : "bg-fuchsia-100 text-fuchsia-700"
            }`}>
              {initials}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onLogout}
            className="text-gray-600 hover:text-red-600 hover:border-red-300"
            data-testid="ez-logout-btn"
          >
            <LogOut className="w-4 h-4 mr-1.5" />
            <span className="hidden sm:inline">Abmelden</span>
          </Button>
        </div>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Phase 1: USER-SELECT
// ---------------------------------------------------------------------------
function UserSelect({ onPick }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${BACKEND}/api/einsatzzentrale/users`);
        if (!cancelled) setUsers(data?.users || []);
      } catch {
        if (!cancelled) setError("Server nicht erreichbar");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return users;
    return users.filter(u => (u.name || "").toLowerCase().includes(q));
  }, [users, filter]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="ez-user-select">
      <KioskTopBar subtitle="Wähle deinen Namen, um dich anzumelden" />
      <main className="flex-1 px-4 sm:px-6 py-6 max-w-6xl mx-auto w-full">
        <div className="mb-6 max-w-md">
          <div className="relative">
            <Search className="w-5 h-5 text-gray-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Name suchen…"
              className="pl-12 h-14 text-lg"
              data-testid="ez-user-filter"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-3 text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin" /> Lade Mitarbeiter…
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-center gap-3" data-testid="ez-error">
            <AlertCircle className="w-6 h-6 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        ) : visible.length === 0 ? (
          <p className="text-gray-500">Keine Mitarbeiter gefunden.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4" data-testid="ez-user-grid">
            {visible.map(u => {
              const initials = (u.name || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
              const isFreelancer = u.role === "freelancer";
              return (
                <button
                  key={u.id}
                  onClick={() => onPick(u)}
                  className="bg-white hover:bg-fuchsia-50/40 border border-gray-200 hover:border-fuchsia-400 hover:shadow-md rounded-2xl p-5 transition-all text-center group"
                  data-testid={`ez-user-${u.id}`}
                >
                  <div className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center text-2xl font-bold mb-3 transition-colors ${
                    isFreelancer
                      ? "bg-amber-100 text-amber-700 group-hover:bg-amber-200"
                      : "bg-fuchsia-100 text-fuchsia-700 group-hover:bg-fuchsia-200"
                  }`}>
                    {initials}
                  </div>
                  <p className="font-semibold text-gray-900 truncate">{u.name}</p>
                  <p className={`text-[10px] uppercase font-bold tracking-wide mt-1 ${
                    isFreelancer ? "text-amber-600" : "text-fuchsia-600"
                  }`}>
                    {u.role}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 2: PASSWORD
// ---------------------------------------------------------------------------
function PasswordPrompt({ user, onSuccess, onCancel }) {
  const [pw, setPw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const submit = useCallback(async (e) => {
    if (e) e.preventDefault();
    if (!pw) return;
    setSubmitting(true);
    setError(null);
    try {
      const { data } = await axios.post(`${BACKEND}/api/einsatzzentrale/login`, {
        user_id: user.id,
        password: pw,
      });
      onSuccess(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Login fehlgeschlagen");
      setSubmitting(false);
    }
  }, [pw, user, onSuccess]);

  const initials = (user.name || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
  const isFreelancer = user.role === "freelancer";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="ez-password">
      <KioskTopBar
        subtitle="Passwort eingeben"
        right={
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
            className="text-gray-600"
            data-testid="ez-pw-back"
          >
            <ChevronLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
        }
      />
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-10">
        <form onSubmit={submit} className="w-full max-w-md bg-white border border-gray-200 rounded-2xl shadow-sm p-8">
          <div className={`w-24 h-24 mx-auto rounded-full flex items-center justify-center text-3xl font-bold mb-4 ${
            isFreelancer ? "bg-amber-100 text-amber-700" : "bg-fuchsia-100 text-fuchsia-700"
          }`}>
            {initials}
          </div>
          <h2 className="text-2xl font-bold text-center mb-1 text-gray-900" data-testid="ez-pw-user-name">{user.name}</h2>
          <p className="text-xs text-center uppercase font-bold tracking-wide text-gray-500 mb-6">{user.role}</p>

          <label className="block mb-2 text-sm font-semibold text-gray-700">Passwort</label>
          <Input
            type="password"
            autoFocus
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="Dein Passwort"
            className="h-14 text-lg text-center tracking-widest"
            data-testid="ez-pw-input"
          />
          {error && (
            <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-center gap-2" data-testid="ez-pw-error">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
          <Button
            type="submit"
            disabled={!pw || submitting}
            className="w-full mt-5 h-14 text-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            data-testid="ez-pw-submit"
          >
            {submitting ? <Loader2 className="w-5 h-5 animate-spin" /> : "Anmelden"}
          </Button>
        </form>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 3: ORDER-SELECT
// ---------------------------------------------------------------------------
function OrderSelect({ token, user, onPick, onLogout }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("");
  const [win, setWin] = useState({ start: null, end: null });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${BACKEND}/api/einsatzzentrale/orders`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) {
          setOrders(data?.orders || []);
          setWin({ start: data?.window_start, end: data?.window_end });
        }
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || "Aufträge konnten nicht geladen werden");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return orders;
    return orders.filter(o =>
      [o.order_no, o.contact_name, o.address, o.event]
        .filter(Boolean).some(v => String(v).toLowerCase().includes(q))
    );
  }, [orders, filter]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="ez-order-select">
      <KioskHeaderUser user={user} onLogout={onLogout} subtitle="Auftrag auswählen" />
      <main className="flex-1 px-4 sm:px-6 py-6 max-w-6xl mx-auto w-full">
        <div className="flex items-center gap-3 flex-wrap mb-5">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <Search className="w-5 h-5 text-gray-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Suchen: Auftrag, Kunde, Event…"
              className="pl-12 h-12 bg-white"
              data-testid="ez-order-filter"
            />
          </div>
          {win.start && (
            <span className="text-xs text-gray-600 flex items-center gap-1.5 bg-white border border-gray-200 px-3 py-1.5 rounded-full">
              <Calendar className="w-3.5 h-3.5 text-fuchsia-500" />
              {fmtRange(win.start, win.end)}
            </span>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-3 text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin" /> Lade aktive Aufträge…
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-10 text-center">
            <ClipboardList className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500">
              {filter ? "Keine Aufträge passen zum Filter." : "Keine aktiven Aufträge im Zeitraum."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="ez-order-grid">
            {filtered.map(o => (
              <button
                key={o.primary_key}
                onClick={() => onPick(o)}
                className="bg-white hover:bg-fuchsia-50/40 border border-gray-200 hover:border-fuchsia-400 hover:shadow-md rounded-2xl p-5 text-left transition-all group"
                data-testid={`ez-order-${o.primary_key}`}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-fuchsia-600 font-bold tracking-wide">AUFTRAG #{o.order_no || o.primary_key}</p>
                    <h3 className="text-lg font-bold text-gray-900 truncate">{o.event || "—"}</h3>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-300 group-hover:text-fuchsia-500 transition-colors flex-shrink-0" />
                </div>
                <div className="space-y-1.5 text-sm text-gray-700">
                  {o.contact_name && (
                    <p className="flex items-center gap-2 truncate">
                      <Building2 className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      {o.contact_name}
                    </p>
                  )}
                  {o.address && (
                    <p className="flex items-center gap-2 truncate text-gray-500">
                      <MapPin className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      {o.address}
                    </p>
                  )}
                  <p className="flex items-center gap-2 text-gray-500">
                    <Calendar className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    {fmtRange(o.event_start, o.event_end)}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tile-Definitionen (Light Theme)
// ---------------------------------------------------------------------------
const WORKSPACE_TILES = [
  { key: "maschinen", label: "Maschinenliste", desc: "Generatoren, Verteiler, Lichtmasten",
    icon: Cog, bg: "bg-emerald-100", text: "text-emerald-600", hoverBorder: "hover:border-emerald-400" },
  { key: "diary", label: "Einsatztagebuch", desc: "Störungen & Verlauf",
    icon: BookOpen, bg: "bg-slate-100", text: "text-slate-600", hoverBorder: "hover:border-slate-400" },
  { key: "plaene", label: "Pläne", desc: "Lagepläne, Dokumente, PDFs",
    icon: FileText, bg: "bg-blue-100", text: "text-blue-600", hoverBorder: "hover:border-blue-400" },
  { key: "standorte", label: "Standortliste", desc: "Alle GPS-Positionen",
    icon: MapPinned, bg: "bg-fuchsia-100", text: "text-fuchsia-600", hoverBorder: "hover:border-fuchsia-400" },
];

// ---------------------------------------------------------------------------
// Projekt-Header (Kurzbeschreibung aus EpiRent)
// ---------------------------------------------------------------------------
function ProjectHeader({ orderPk, token, fallback }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${BACKEND}/api/einsatzzentrale/orders/${orderPk}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setData(data);
      } catch {
        if (!cancelled) setData(fallback);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderPk, token, fallback]);

  const o = data || fallback;
  return (
    <section
      className="bg-gradient-to-br from-fuchsia-50 via-white to-white border border-fuchsia-200 rounded-2xl p-6 shadow-sm"
      data-testid="ez-project-header"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold uppercase tracking-wider text-fuchsia-600 mb-1">
            Auftrag #{o.order_no || o.primary_key}
          </p>
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900" data-testid="ez-project-event">
            {o.event || "Veranstaltung"}
          </h2>
          {o.contact_name && (
            <p className="text-base text-gray-700 mt-1 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-fuchsia-500" /> {o.contact_name}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 mt-3 text-sm text-gray-600">
            {o.address && (
              <p className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5 text-gray-400" /> {o.address}</p>
            )}
            <p className="flex items-center gap-2">
              <Calendar className="w-3.5 h-3.5 text-gray-400" />
              {fmtRange(o.event_start, o.event_end)}
            </p>
            {(o.dispo_start || o.dispo_end) && (
              <p className="flex items-center gap-2 text-xs text-gray-500 sm:col-span-2">
                <span className="font-semibold">Dispo:</span>
                {fmtRange(o.dispo_start, o.dispo_end)}
              </p>
            )}
            {o.editor_name && (
              <p className="flex items-center gap-2 text-xs text-gray-500">
                <UserIcon className="w-3 h-3" /> Bearbeiter: {o.editor_name}
              </p>
            )}
          </div>
        </div>
        {loading && <Loader2 className="w-5 h-5 animate-spin text-fuchsia-500" />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Wetter-Widget (Open-Meteo, Veranstaltungszeitraum)
// ---------------------------------------------------------------------------
function WeatherWidget({ orderPk, token }) {
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data: order } = await axios.get(`${BACKEND}/api/einsatzzentrale/orders/${orderPk}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;
        const lat = order.center_lat;
        const lng = order.center_lng;
        if (lat == null || lng == null) {
          setError("Keine GPS-Koordinaten zum Auftrag hinterlegt");
          setLoading(false);
          return;
        }
        const params = new URLSearchParams({ lat, lng });
        if (order.event_start) params.set("start", order.event_start);
        if (order.event_end) params.set("end", order.event_end);
        const { data: w } = await axios.get(`${BACKEND}/api/einsatzzentrale/weather?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setWeather(w);
      } catch (err) {
        if (!cancelled) setError(err?.response?.data?.detail || "Wetter nicht verfügbar");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderPk, token]);

  return (
    <section data-testid="ez-weather">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-700 flex items-center gap-2">
          <CloudSun className="w-4 h-4 text-blue-500" /> Wetter-Prognose
        </h2>
        {weather && (
          <span className="text-[10px] text-gray-400 font-mono">
            {weather.source} · {weather.start} … {weather.end}
          </span>
        )}
      </div>
      {loading ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 flex items-center gap-3 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" /> Lade Wetterdaten…
        </div>
      ) : error ? (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center gap-3 text-amber-800 text-sm" data-testid="ez-weather-error">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error} — bitte Auftrag zuerst auf der Detail-Seite öffnen, damit GPS geocodiert wird.</span>
        </div>
      ) : !weather || !weather.days?.length ? (
        <p className="text-gray-500 text-sm">Keine Wetterdaten verfügbar.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3" data-testid="ez-weather-days">
          {weather.days.map((d) => (
            <div
              key={d.date}
              className="bg-white border border-gray-200 rounded-xl p-3 text-center hover:border-blue-300 transition-colors"
              data-testid={`ez-weather-day-${d.date}`}
            >
              <p className="text-xs font-semibold text-gray-700">
                {new Date(d.date).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}
              </p>
              <p className="text-3xl my-1" title={d.weather_label}>{d.weather_emoji}</p>
              <p className="text-[10px] text-gray-500 mb-2 truncate" title={d.weather_label}>{d.weather_label}</p>
              <p className="text-sm font-bold text-gray-900">
                <span className="text-red-500">{Math.round(d.temp_max)}°</span>
                <span className="text-gray-400 mx-1">/</span>
                <span className="text-blue-500">{Math.round(d.temp_min)}°</span>
              </p>
              {d.precipitation_mm != null && (
                <p className="text-[10px] text-blue-600 mt-1 flex items-center justify-center gap-0.5">
                  <CloudRain className="w-2.5 h-2.5" />
                  {d.precipitation_mm.toFixed(1)} mm
                  {d.precipitation_prob != null && <span className="text-gray-400"> · {d.precipitation_prob}%</span>}
                </p>
              )}
              {d.wind_gust_kmh != null && (
                <p className="text-[10px] text-gray-500 flex items-center justify-center gap-0.5">
                  <Wind className="w-2.5 h-2.5" /> Böen {Math.round(d.wind_gust_kmh)} km/h
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Workspace + Tile-Panels
// ---------------------------------------------------------------------------
function Workspace({ user, order, token, onLogout }) {
  const [activeTile, setActiveTile] = useState(null);

  if (activeTile) {
    return (
      <WorkspaceTilePanel
        tileKey={activeTile}
        order={order}
        user={user}
        token={token}
        onLogout={onLogout}
        onBack={() => setActiveTile(null)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="ez-workspace">
      <KioskHeaderUser user={user} onLogout={onLogout} subtitle={`Auftrag #${order.order_no || order.primary_key}`} />
      <main className="flex-1 px-4 sm:px-6 py-6 max-w-6xl mx-auto w-full space-y-6">
        <ProjectHeader orderPk={order.primary_key} token={token} fallback={order} />
        <WeatherWidget orderPk={order.primary_key} token={token} />
        <section data-testid="ez-tile-grid">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-700 mb-3">Bereiche</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {WORKSPACE_TILES.map(t => {
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  onClick={() => setActiveTile(t.key)}
                  className={`bg-white border border-gray-200 ${t.hoverBorder} hover:shadow-md rounded-2xl p-6 text-left transition-all group`}
                  data-testid={`ez-tile-${t.key}`}
                >
                  <div className={`w-14 h-14 rounded-2xl ${t.bg} flex items-center justify-center mb-4 group-hover:scale-105 transition-transform`}>
                    <Icon className={`w-7 h-7 ${t.text}`} />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-1">{t.label}</h3>
                  <p className="text-xs text-gray-500">{t.desc}</p>
                </button>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}

function WorkspaceTilePanel({ tileKey, order, user, onLogout, onBack }) {
  const tile = WORKSPACE_TILES.find(t => t.key === tileKey);
  const Icon = tile?.icon || ClipboardList;
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid={`ez-panel-${tileKey}`}>
      <KioskHeaderUser user={user} onLogout={onLogout} subtitle={`Auftrag #${order.order_no || order.primary_key} · ${tile?.label || ""}`} />
      <div className="max-w-6xl mx-auto w-full px-4 sm:px-6 pt-4">
        <button
          onClick={onBack}
          className="text-gray-600 hover:text-gray-900 flex items-center gap-2 text-sm"
          data-testid="ez-panel-back"
        >
          <ChevronLeft className="w-4 h-4" /> Zurück zu den Bereichen
        </button>
      </div>
      <main className="flex-1 px-4 sm:px-6 py-5 max-w-6xl mx-auto w-full">
        <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center shadow-sm">
          <div className={`w-16 h-16 rounded-2xl ${tile?.bg || "bg-gray-100"} flex items-center justify-center mx-auto mb-4`}>
            <Icon className={`w-8 h-8 ${tile?.text || "text-gray-600"}`} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{tile?.label}</h2>
          <p className="text-gray-500 max-w-md mx-auto">
            Inhalt für „{tile?.label}" wird gebaut, sobald du mir sagst was hier konkret rein soll.
          </p>
          <p className="text-xs text-gray-400 mt-4">
            (Backend-Daten verfügbar — Layout & Filter folgen nach deinen Vorgaben.)
          </p>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hauptkomponente / State-Machine
// ---------------------------------------------------------------------------
export default function EinsatzzentralePiPage() {
  const [phase, setPhase] = useState("user_select");
  const [pickedUser, setPickedUser] = useState(null);
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [order, setOrder] = useState(null);

  // Restore Session bei Page-Reload
  useEffect(() => {
    try {
      const t = sessionStorage.getItem(SS_TOKEN);
      const u = sessionStorage.getItem(SS_USER);
      const p = sessionStorage.getItem(SS_PHASE);
      const o = sessionStorage.getItem(SS_ORDER);
      if (t && u) {
        setToken(t);
        setUser(JSON.parse(u));
        if (p === "workspace" && o) {
          setOrder(JSON.parse(o));
          setPhase("workspace");
        } else {
          setPhase("order_select");
        }
      }
    } catch { /* ignore */ }
  }, []);

  const handleLogin = useCallback((data) => {
    setToken(data.token);
    setUser(data.user);
    try {
      sessionStorage.setItem(SS_TOKEN, data.token);
      sessionStorage.setItem(SS_USER, JSON.stringify(data.user));
      sessionStorage.setItem(SS_PHASE, "order_select");
      sessionStorage.removeItem(SS_ORDER);
    } catch { /* ignore */ }
    setPhase("order_select");
  }, []);

  const handlePickOrder = useCallback((o) => {
    setOrder(o);
    try {
      sessionStorage.setItem(SS_ORDER, JSON.stringify(o));
      sessionStorage.setItem(SS_PHASE, "workspace");
    } catch { /* ignore */ }
    setPhase("workspace");
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setOrder(null);
    setPickedUser(null);
    try {
      sessionStorage.removeItem(SS_TOKEN);
      sessionStorage.removeItem(SS_USER);
      sessionStorage.removeItem(SS_PHASE);
      sessionStorage.removeItem(SS_ORDER);
    } catch { /* ignore */ }
    setPhase("user_select");
  }, []);

  if (phase === "user_select") {
    return <UserSelect onPick={(u) => { setPickedUser(u); setPhase("password"); }} />;
  }
  if (phase === "password" && pickedUser) {
    return (
      <PasswordPrompt
        user={pickedUser}
        onSuccess={handleLogin}
        onCancel={() => { setPickedUser(null); setPhase("user_select"); }}
      />
    );
  }
  if (phase === "order_select" && token && user) {
    return (
      <OrderSelect
        token={token}
        user={user}
        onPick={handlePickOrder}
        onLogout={handleLogout}
      />
    );
  }
  if (phase === "workspace" && user && order) {
    return <Workspace user={user} order={order} token={token} onLogout={handleLogout} />;
  }
  return <UserSelect onPick={(u) => { setPickedUser(u); setPhase("password"); }} />;
}
