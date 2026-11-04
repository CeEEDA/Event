import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Phone, Mail, Globe, Download, Building2, Presentation, Smartphone } from "lucide-react";
import { BACKEND_URL } from "../lib/api";
import { Logo } from "../components/Logo";
import { Hinweis } from "../components/messe/MessePublicShell";

const base = `${BACKEND_URL}/api/messe/kontakt`;

// Oeffentliche Kontaktkarte eines Messe-Mitarbeiters (QR aus dem Hub) - ohne Login
export default function MesseKontaktPage() {
  const { token } = useParams();
  const [c, setC] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${base}/${token}`).then(r => setC(r.data)).catch(e => setError(e?.response?.data?.detail || "Kontaktkarte nicht erreichbar"));
  }, [token]);

  const initials = (c?.name || "?").split(" ").map(s => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <header className="px-5 pt-6 pb-4">
        <div className="bg-white rounded-2xl px-4 py-3 inline-flex"><Logo size="small" /></div>
        {c && (
          <p className="mt-4 text-xs uppercase tracking-[0.2em] text-fuchsia-400 font-semibold flex items-center gap-1.5"><Presentation className="w-3.5 h-3.5" /> {c.messe.name}{c.messe.location ? ` · ${c.messe.location}` : ""}</p>
        )}
      </header>
      <main className="flex-1 bg-gray-50 text-gray-900 rounded-t-3xl px-5 pt-6 pb-10">
        {error && <Hinweis titel={error} text="Bitte den QR-Code erneut scannen oder direkt am Stand nachfragen." />}
        {!error && !c && <p className="text-center text-sm text-gray-400 py-12">Laden …</p>}
        {c && (
          <div className="max-w-md mx-auto" data-testid="messe-kontakt-card">
            <div className="bg-white rounded-3xl border border-gray-200 shadow-sm p-6 text-center">
              <div className="w-20 h-20 rounded-full bg-fuchsia-600 text-white text-2xl font-bold flex items-center justify-center mx-auto">{initials}</div>
              <h1 className="text-2xl font-bold mt-4" data-testid="messe-kontakt-name">{c.name}</h1>
              {c.position && <p className="text-sm text-gray-500">{c.position}</p>}
              <p className="text-sm text-gray-600 mt-1 flex items-center justify-center gap-1.5"><Building2 className="w-4 h-4 text-gray-400" /> {c.company}</p>
              <a href={`${base}/${token}/vcard`} className="mt-5 w-full h-14 rounded-2xl bg-fuchsia-600 text-white font-bold text-lg flex items-center justify-center gap-2 shadow-lg shadow-fuchsia-600/30 active:scale-[0.98] transition" data-testid="messe-kontakt-vcard">
                <Download className="w-5 h-5" /> Kontakt speichern
              </a>
              <p className="text-[11px] text-gray-400 mt-2">Legt die Visitenkarte in deinen Kontakten ab (vCard).</p>
            </div>
            <div className="mt-4 bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100">
              {c.mobile && (
                <a href={`tel:${c.mobile.replace(/\s+/g, "")}`} className="flex items-center gap-3 px-4 py-4" data-testid="messe-kontakt-mobile">
                  <Smartphone className="w-5 h-5 text-fuchsia-500" /><span className="flex-1 font-medium">{c.mobile}</span><span className="text-xs text-gray-400">Mobil</span>
                </a>
              )}
              {c.phone && c.phone !== c.mobile && (
                <a href={`tel:${c.phone.replace(/\s+/g, "")}`} className="flex items-center gap-3 px-4 py-4" data-testid="messe-kontakt-phone">
                  <Phone className="w-5 h-5 text-fuchsia-500" /><span className="flex-1 font-medium">{c.phone}</span><span className="text-xs text-gray-400">Telefon</span>
                </a>
              )}
              {c.email && (
                <a href={`mailto:${c.email}`} className="flex items-center gap-3 px-4 py-4" data-testid="messe-kontakt-email">
                  <Mail className="w-5 h-5 text-fuchsia-500" /><span className="flex-1 font-medium truncate">{c.email}</span><span className="text-xs text-gray-400">E-Mail</span>
                </a>
              )}
              <a href={c.web} target="_blank" rel="noreferrer" className="flex items-center gap-3 px-4 py-4" data-testid="messe-kontakt-web">
                <Globe className="w-5 h-5 text-fuchsia-500" /><span className="flex-1 font-medium truncate">{c.web.replace(/^https?:\/\//, "")}</span><span className="text-xs text-gray-400">Website</span>
              </a>
            </div>
            <p className="text-center text-[11px] text-gray-400 mt-6">{c.company}</p>
          </div>
        )}
      </main>
    </div>
  );
}
