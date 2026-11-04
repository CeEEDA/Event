import { AlertCircle } from "lucide-react";
import { BACKEND_URL } from "../../lib/api";
import { Logo } from "../Logo";

export const PUBLIC_BASE = `${BACKEND_URL}/api/messe/public`;
export const errText = (e, fb) => e.response?.data?.detail || fb;

export function Shell({ messe, children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col" data-testid="messe-public-page">
      <header className="px-5 pt-6 pb-4">
        <div className="bg-white rounded-2xl px-4 py-3 inline-flex"><Logo size="small" /></div>
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
