import { useEffect, useState } from "react";
import axios from "axios";
import { AlertCircle, Lock, Timer } from "lucide-react";
import { BACKEND_URL } from "../../lib/api";
import { Logo } from "../Logo";

export const PUBLIC_BASE = `${BACKEND_URL}/api/messe/public`;
export const errText = (e, fb) => e.response?.data?.detail || fb;

// ---- Besucher-Sitzung: 5 Minuten nach dem QR-Scan, danach gesperrt ----
const key = (t) => `messe_session_${t}`;
const read = (t) => { try { return JSON.parse(localStorage.getItem(key(t)) || "null"); } catch { return null; } };
export const sessionId = (t) => read(t)?.sid || "";
export const withSession = (t, extra = {}) => ({ ...extra, headers: { ...(extra.headers || {}), "X-Messe-Session": sessionId(t) } });

export function useMesseSession(token) {
  const [state, setState] = useState({ sid: "", expires: 0, locked: false, ready: false });
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const url = new URL(window.location.href);
    const scanned = url.searchParams.has("s");
    if (scanned) { url.searchParams.delete("s"); window.history.replaceState({}, "", url.pathname + (url.search || "")); }
    const stored = read(token);
    const valid = stored && stored.expires > Date.now() + 1000;
    if (valid) { setState({ sid: stored.sid, expires: stored.expires, locked: false, ready: true }); return; }
    if (stored && !scanned) { setState({ sid: "", expires: 0, locked: true, ready: true }); return; }
    axios.post(`${PUBLIC_BASE}/${token}/session`).then(r => {
      const offset = Date.parse(r.data.server_time) - Date.now();
      const expires = Date.parse(r.data.expires_at) - offset;
      localStorage.setItem(key(token), JSON.stringify({ sid: r.data.session_id, expires }));
      setState({ sid: r.data.session_id, expires, locked: false, ready: true });
    }).catch(() => setState({ sid: "", expires: 0, locked: true, ready: true }));
  }, [token]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const restSec = state.expires ? Math.max(0, Math.floor((state.expires - now) / 1000)) : 0;
  const locked = state.ready && (state.locked || (state.expires > 0 && restSec <= 0));
  return { ...state, restSec, locked };
}

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function Shell({ messe, session, children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col" data-testid="messe-public-page">
      <header className="px-5 pt-6 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="bg-white rounded-2xl px-4 py-3 inline-flex"><Logo size="small" /></div>
          {session?.ready && !session.locked && (
            <span className={`mt-1 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${session.restSec <= 60 ? "border-amber-400 text-amber-300" : "border-gray-700 text-gray-300"}`} data-testid="messe-session-timer">
              <Timer className="w-3.5 h-3.5" /> {mmss(session.restSec)}
            </span>
          )}
        </div>
        {messe && (
          <div className="mt-4">
            <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-400 font-semibold">Messe-Demo</p>
            <h1 className="text-2xl font-bold leading-tight mt-1" data-testid="messe-public-title">{messe.name}</h1>
            {messe.location && <p className="text-sm text-gray-400">{messe.location}</p>}
            {messe.note && <p className="text-sm text-gray-300 mt-2 bg-gray-900 border border-gray-800 rounded-xl px-3 py-2" data-testid="messe-public-note">{messe.note}</p>}
          </div>
        )}
      </header>
      <main className="flex-1 bg-gray-50 text-gray-900 rounded-t-3xl px-5 pt-6 pb-10">{children}</main>
      <footer className="bg-gray-50 text-center text-[11px] text-gray-400 pb-5">Eventenergie Deutschland GmbH &amp; Co. KG · M-Box</footer>
      {session?.locked && <LockScreen minutes={messe?.session_minutes || 5} />}
    </div>
  );
}

function LockScreen({ minutes }) {
  return (
    <div className="fixed inset-0 z-50 bg-gray-950/95 text-white flex flex-col items-center justify-center px-8 text-center" data-testid="messe-session-locked">
      <div className="w-20 h-20 rounded-full bg-gray-900 border border-gray-700 flex items-center justify-center mb-6"><Lock className="w-9 h-9 text-fuchsia-400" /></div>
      <h2 className="text-2xl font-bold">Sitzung abgelaufen</h2>
      <p className="text-sm text-gray-400 mt-3 max-w-xs">Die Bedienung ist {minutes} Minuten nach dem Scannen möglich. Bitte den QR-Code am Messestand erneut scannen.</p>
    </div>
  );
}

export function Hinweis({ icon: Icon = AlertCircle, titel, text }) {
  return (
    <div className="text-center py-10" data-testid="messe-public-error">
      <Icon className="w-12 h-12 text-red-400 mx-auto mb-3" />
      <h2 className="text-lg font-semibold text-gray-900">{titel}</h2>
      <p className="text-sm text-gray-500 mt-1">{text}</p>
    </div>
  );
}
