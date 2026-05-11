/**
 * EinsatzzentralePiPage
 *
 * Touch-Kiosk-Bildschirm fuer den PI in der Einsatzzentrale.
 *
 * State-Machine:
 *   user_select  -> Grid aller Mitarbeiter/Freelancer
 *   password     -> Passwort-Eingabe fuer ausgewaehlten User
 *   order_select -> Aktive Auftraege (heute -14 ... +14 Tage)
 *   workspace    -> Arbeitsmaske mit Logout-Button oben
 *
 * Logout (manuell, oben rechts) -> zurueck zur user_select.
 * Auth-Token + Auswahl wird in sessionStorage gehalten.
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import { Users, LogOut, ChevronLeft, Search, Calendar, MapPin, User as UserIcon, Loader2, AlertCircle, ArrowRight, Building2, ClipboardList } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const SS_TOKEN = "einsatzzentrale_token";
const SS_USER = "einsatzzentrale_user";

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
      } catch (e) {
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
    <div className="min-h-screen bg-slate-950 text-white flex flex-col" data-testid="ez-user-select">
      <header className="bg-slate-900/80 backdrop-blur border-b border-slate-800 px-8 py-5">
        <div className="max-w-6xl mx-auto flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-fuchsia-600/20 flex items-center justify-center">
            <Users className="w-6 h-6 text-fuchsia-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Einsatzzentrale</h1>
            <p className="text-sm text-slate-400">Wähle deinen Namen, um dich anzumelden</p>
          </div>
        </div>
      </header>
      <main className="flex-1 px-8 py-8 max-w-6xl mx-auto w-full">
        <div className="mb-6 max-w-md">
          <div className="relative">
            <Search className="w-5 h-5 text-slate-500 absolute left-4 top-1/2 -translate-y-1/2" />
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Name suchen…"
              className="pl-12 h-14 text-lg bg-slate-900 border-slate-700 text-white placeholder:text-slate-500"
              data-testid="ez-user-filter"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-3 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" /> Lade Mitarbeiter…
          </div>
        ) : error ? (
          <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-6 flex items-center gap-3" data-testid="ez-error">
            <AlertCircle className="w-6 h-6 text-red-400" />
            <p className="text-red-300">{error}</p>
          </div>
        ) : visible.length === 0 ? (
          <p className="text-slate-400">Keine Mitarbeiter gefunden.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4" data-testid="ez-user-grid">
            {visible.map(u => {
              const initials = (u.name || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
              const isFreelancer = u.role === "freelancer";
              return (
                <button
                  key={u.id}
                  onClick={() => onPick(u)}
                  className="bg-slate-900 hover:bg-slate-800 border-2 border-slate-800 hover:border-fuchsia-500 rounded-2xl p-5 transition-all text-center group"
                  data-testid={`ez-user-${u.id}`}
                >
                  <div className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center text-2xl font-bold mb-3 transition-colors ${
                    isFreelancer
                      ? "bg-amber-500/20 text-amber-300 group-hover:bg-amber-500/30"
                      : "bg-fuchsia-500/20 text-fuchsia-300 group-hover:bg-fuchsia-500/30"
                  }`}>
                    {initials}
                  </div>
                  <p className="font-semibold text-white truncate">{u.name}</p>
                  <p className={`text-[10px] uppercase font-bold tracking-wide mt-1 ${
                    isFreelancer ? "text-amber-400" : "text-fuchsia-400"
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
    <div className="min-h-screen bg-slate-950 text-white flex flex-col" data-testid="ez-password">
      <header className="bg-slate-900/80 backdrop-blur border-b border-slate-800 px-8 py-5">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <button
            onClick={onCancel}
            className="text-slate-400 hover:text-white flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-800"
            data-testid="ez-pw-back"
          >
            <ChevronLeft className="w-5 h-5" /> Zurück
          </button>
        </div>
      </header>
      <main className="flex-1 flex items-center justify-center px-8 py-10">
        <form onSubmit={submit} className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8">
          <div className={`w-24 h-24 mx-auto rounded-full flex items-center justify-center text-3xl font-bold mb-4 ${
            isFreelancer ? "bg-amber-500/20 text-amber-300" : "bg-fuchsia-500/20 text-fuchsia-300"
          }`}>
            {initials}
          </div>
          <h2 className="text-2xl font-bold text-center mb-1" data-testid="ez-pw-user-name">{user.name}</h2>
          <p className="text-xs text-center uppercase font-bold tracking-wide text-slate-400 mb-6">{user.role}</p>

          <label className="block mb-2 text-sm font-semibold text-slate-300">Passwort</label>
          <Input
            type="password"
            autoFocus
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="Dein Passwort"
            className="h-14 text-lg bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 text-center tracking-widest"
            data-testid="ez-pw-input"
          />
          {error && (
            <div className="mt-3 bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-sm text-red-300 flex items-center gap-2" data-testid="ez-pw-error">
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
  const [window, setWindow] = useState({ start: null, end: null });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${BACKEND}/api/einsatzzentrale/orders`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) {
          setOrders(data?.orders || []);
          setWindow({ start: data?.window_start, end: data?.window_end });
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
    <div className="min-h-screen bg-slate-950 text-white flex flex-col" data-testid="ez-order-select">
      <KioskHeader user={user} onLogout={onLogout} subtitle="Auftrag auswählen" />
      <main className="flex-1 px-6 py-6 max-w-6xl mx-auto w-full">
        <div className="flex items-center gap-3 flex-wrap mb-5">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <Search className="w-5 h-5 text-slate-500 absolute left-4 top-1/2 -translate-y-1/2" />
            <Input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Suchen: Auftrag, Kunde, Event…"
              className="pl-12 h-12 bg-slate-900 border-slate-700 text-white placeholder:text-slate-500"
              data-testid="ez-order-filter"
            />
          </div>
          {window.start && (
            <span className="text-xs text-slate-400 flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-full">
              <Calendar className="w-3.5 h-3.5" />
              {fmtRange(window.start, window.end)}
            </span>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-3 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" /> Lade aktive Aufträge…
          </div>
        ) : error ? (
          <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-6 flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-400" />
            <p className="text-red-300">{error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center">
            <ClipboardList className="w-12 h-12 mx-auto text-slate-600 mb-3" />
            <p className="text-slate-400">
              {filter ? "Keine Aufträge passen zum Filter." : "Keine aktiven Aufträge im Zeitraum."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="ez-order-grid">
            {filtered.map(o => (
              <button
                key={o.primary_key}
                onClick={() => onPick(o)}
                className="bg-slate-900 hover:bg-slate-800 border-2 border-slate-800 hover:border-fuchsia-500 rounded-2xl p-5 text-left transition-all group"
                data-testid={`ez-order-${o.primary_key}`}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-fuchsia-400 font-bold tracking-wide">AUFTRAG #{o.order_no || o.primary_key}</p>
                    <h3 className="text-lg font-bold text-white truncate">{o.event || "—"}</h3>
                  </div>
                  <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-fuchsia-400 transition-colors flex-shrink-0" />
                </div>
                <div className="space-y-1.5 text-sm text-slate-300">
                  {o.contact_name && (
                    <p className="flex items-center gap-2 truncate">
                      <Building2 className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                      {o.contact_name}
                    </p>
                  )}
                  {o.address && (
                    <p className="flex items-center gap-2 truncate text-slate-400">
                      <MapPin className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                      {o.address}
                    </p>
                  )}
                  <p className="flex items-center gap-2 text-slate-400">
                    <Calendar className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
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
// Phase 4: WORKSPACE (Platzhalter — Inhalt kommt vom User)
// ---------------------------------------------------------------------------
function Workspace({ user, order, onLogout }) {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col" data-testid="ez-workspace">
      <KioskHeader
        user={user}
        onLogout={onLogout}
        subtitle={`Auftrag #${order.order_no || order.primary_key} · ${order.event || ""}`}
      />
      <main className="flex-1 px-6 py-8 max-w-6xl mx-auto w-full">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
          <ClipboardList className="w-14 h-14 mx-auto text-fuchsia-400 mb-4" />
          <h2 className="text-2xl font-bold mb-2">Arbeitsmaske bereit</h2>
          <p className="text-slate-400 max-w-md mx-auto mb-6">
            Die Inhalte dieser Maske werden gleich definiert. Aktuell siehst du hier den
            ausgewählten Auftrag und den angemeldeten User.
          </p>
          <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-4 text-left max-w-lg mx-auto text-sm space-y-1">
            <p><span className="text-slate-500">User:</span> <span className="font-mono">{user.name} ({user.role})</span></p>
            <p><span className="text-slate-500">Auftrag:</span> <span className="font-mono">#{order.order_no || order.primary_key}</span></p>
            <p><span className="text-slate-500">Kunde:</span> {order.contact_name || "—"}</p>
            <p><span className="text-slate-500">Adresse:</span> {order.address || "—"}</p>
            <p><span className="text-slate-500">Event:</span> {order.event || "—"} · {fmtRange(order.event_start, order.event_end)}</p>
          </div>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Wiederverwendbarer Header mit Logout
// ---------------------------------------------------------------------------
function KioskHeader({ user, subtitle, onLogout }) {
  const initials = (user.name || "?").split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
  const isFreelancer = user.role === "freelancer";
  return (
    <header className="bg-slate-900/80 backdrop-blur border-b border-slate-800 px-6 py-4 sticky top-0 z-10">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold flex-shrink-0 ${
            isFreelancer ? "bg-amber-500/20 text-amber-300" : "bg-fuchsia-500/20 text-fuchsia-300"
          }`}>
            {initials}
          </div>
          <div className="min-w-0">
            <p className="font-semibold truncate" data-testid="ez-header-user">{user.name}</p>
            <p className="text-xs text-slate-400 truncate">{subtitle}</p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={onLogout}
          className="bg-red-900/30 border-red-700/50 text-red-300 hover:bg-red-900/50 hover:text-red-200 hover:border-red-600"
          data-testid="ez-logout-btn"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Abmelden
        </Button>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Hauptkomponente / State-Machine
// ---------------------------------------------------------------------------
export default function EinsatzzentralePiPage() {
  const [phase, setPhase] = useState("user_select"); // user_select | password | order_select | workspace
  const [pickedUser, setPickedUser] = useState(null);
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [order, setOrder] = useState(null);

  // Restore Session bei Page-Reload
  useEffect(() => {
    try {
      const t = sessionStorage.getItem(SS_TOKEN);
      const u = sessionStorage.getItem(SS_USER);
      if (t && u) {
        setToken(t);
        setUser(JSON.parse(u));
        setPhase("order_select");
      }
    } catch { /* ignore */ }
  }, []);

  const handleLogin = useCallback((data) => {
    setToken(data.token);
    setUser(data.user);
    try {
      sessionStorage.setItem(SS_TOKEN, data.token);
      sessionStorage.setItem(SS_USER, JSON.stringify(data.user));
    } catch { /* ignore */ }
    setPhase("order_select");
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setOrder(null);
    setPickedUser(null);
    try {
      sessionStorage.removeItem(SS_TOKEN);
      sessionStorage.removeItem(SS_USER);
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
        onPick={(o) => { setOrder(o); setPhase("workspace"); }}
        onLogout={handleLogout}
      />
    );
  }
  if (phase === "workspace" && user && order) {
    return <Workspace user={user} order={order} onLogout={handleLogout} />;
  }
  // Fallback
  return <UserSelect onPick={(u) => { setPickedUser(u); setPhase("password"); }} />;
}
