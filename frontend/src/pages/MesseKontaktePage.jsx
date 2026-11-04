import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Phone, Mail, Download, Search, ChevronDown, ChevronUp, Trash2, Smartphone, Globe, PhoneCall } from "lucide-react";
import api, { getErrorMsg, BACKEND_URL } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Logo } from "../components/Logo";

const STATUS_LABEL = { offen: "Offen", kontaktiert: "Kontaktiert", termin: "Termin", angebot: "Angebot", erledigt: "Erledigt", kein_interesse: "Kein Interesse" };
const STATUS_CLS = { offen: "bg-amber-100 text-amber-800", kontaktiert: "bg-blue-100 text-blue-800", termin: "bg-violet-100 text-violet-800",
  angebot: "bg-fuchsia-100 text-fuchsia-800", erledigt: "bg-emerald-100 text-emerald-800", kein_interesse: "bg-gray-200 text-gray-600" };
const PRIO_CLS = { hoch: "border-l-4 border-red-500", normal: "border-l-4 border-gray-200", niedrig: "border-l-4 border-gray-100" };

function LeadRow({ lead, messeId, onChange }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState(lead.status);
  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ") || "–";

  const patch = async (body, msg) => {
    try {
      const r = await api.patch(`/messe/${messeId}/leads/${lead.id}`, body);
      onChange(r.data); if (msg) toast.success(msg);
    } catch (e) { toast.error(getErrorMsg(e, "Speichern fehlgeschlagen")); }
  };

  const anruf = async () => {
    if (!note.trim() && status === lead.status) { toast.error("Bitte Gesprächsnotiz eingeben oder Status ändern"); return; }
    await patch({ status, call_note: note }, "Anruf protokolliert");
    setNote("");
  };

  return (
    <div className={`bg-white rounded-xl border border-gray-200 ${PRIO_CLS[lead.priority] || PRIO_CLS.normal}`} data-testid={`lead-row-${lead.id}`}>
      <button type="button" onClick={() => setOpen(v => !v)} className="w-full text-left px-4 py-3 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 truncate">{lead.company || name}{lead.company && <span className="font-normal text-gray-500"> · {name}</span>}</p>
          <p className="text-xs text-gray-500 truncate">{[lead.position, lead.interest, lead.city].filter(Boolean).join(" · ") || "keine Angaben"}</p>
        </div>
        {lead.follow_up_date && <span className="hidden sm:inline text-xs text-gray-500">WV {new Date(lead.follow_up_date).toLocaleDateString("de-DE")}</span>}
        <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_CLS[lead.status]}`} data-testid={`lead-status-${lead.id}`}>{STATUS_LABEL[lead.status]}</span>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3 grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5 text-sm">
            {lead.phone && <a href={`tel:${lead.phone.replace(/\s+/g, "")}`} className="flex items-center gap-2 text-fuchsia-700 font-medium"><Phone className="w-4 h-4" /> {lead.phone}</a>}
            {lead.mobile && <a href={`tel:${lead.mobile.replace(/\s+/g, "")}`} className="flex items-center gap-2 text-fuchsia-700 font-medium"><Smartphone className="w-4 h-4" /> {lead.mobile}</a>}
            {lead.email && <a href={`mailto:${lead.email}`} className="flex items-center gap-2 text-gray-800"><Mail className="w-4 h-4 text-gray-400" /> {lead.email}</a>}
            {lead.website && <a href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-gray-800"><Globe className="w-4 h-4 text-gray-400" /> {lead.website}</a>}
            {(lead.street || lead.zip || lead.city) && <p className="text-gray-600">{[lead.street, [lead.zip, lead.city].filter(Boolean).join(" "), lead.country].filter(Boolean).join(", ")}</p>}
            {lead.products && <p><span className="text-gray-400">Produkte:</span> {lead.products}</p>}
            {lead.notes && <p className="whitespace-pre-wrap bg-gray-50 rounded-lg p-2 text-gray-700">{lead.notes}</p>}
            <p className="text-[11px] text-gray-400">Erfasst {new Date(lead.created_at).toLocaleString("de-DE")} von {lead.created_by_name} · Quelle: {lead.source}</p>
            {lead.history?.length > 0 && (
              <div className="pt-2">
                <p className="text-xs font-semibold text-gray-500 mb-1">Gesprächsverlauf</p>
                {[...lead.history].reverse().map((h, i) => (
                  <p key={i} className="text-xs text-gray-600"><span className="text-gray-400">{new Date(h.at).toLocaleString("de-DE")} · {h.by}{h.status ? ` · ${STATUS_LABEL[h.status]}` : ""}:</span> {h.text}</p>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-2">
            <label className="text-xs text-gray-500">Status</label>
            <select value={status} onChange={e => setStatus(e.target.value)} className="w-full h-10 rounded-md border border-gray-300 px-2 text-sm bg-white" data-testid={`lead-status-select-${lead.id}`}>
              {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <label className="text-xs text-gray-500">Gesprächsnotiz (Anruf)</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={3} className="w-full rounded-md border border-gray-300 p-2 text-sm" placeholder="Was wurde telefonisch besprochen?" data-testid={`lead-note-${lead.id}`} />
            <div className="flex gap-2">
              <Button onClick={anruf} className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid={`lead-call-save-${lead.id}`}><PhoneCall className="w-4 h-4 mr-1" /> Anruf protokollieren</Button>
              <Button variant="ghost" onClick={() => { if (window.confirm("Kontakt wirklich entfernen?")) patch({ deleted: true }, "Kontakt entfernt"); }} className="text-gray-500" data-testid={`lead-delete-${lead.id}`}><Trash2 className="w-4 h-4" /></Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function MesseKontaktePage() {
  const { messeId } = useParams();
  const navigate = useNavigate();
  const [messe, setMesse] = useState(null);
  const [leads, setLeads] = useState([]);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("alle");

  const load = useCallback(async () => {
    try {
      const [m, l] = await Promise.all([api.get(`/messe/${messeId}`), api.get(`/messe/${messeId}/leads`)]);
      setMesse(m.data); setLeads(l.data.leads);
    } catch (e) { toast.error(getErrorMsg(e, "Laden fehlgeschlagen")); }
  }, [messeId]);
  useEffect(() => { load(); }, [load]);

  const onChange = (lead) => setLeads(ls => lead.deleted_at ? ls.filter(x => x.id !== lead.id) : ls.map(x => x.id === lead.id ? lead : x));
  const shown = leads.filter(l => (filter === "alle" || l.status === filter) &&
    (!q || JSON.stringify(l).toLowerCase().includes(q.toLowerCase())));
  const counts = leads.reduce((a, l) => ({ ...a, [l.status]: (a[l.status] || 0) + 1 }), {});
  const token = localStorage.getItem("token");

  return (
    <div className="min-h-screen bg-gray-50" data-testid="messe-kontakte-page">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
        <button onClick={() => navigate(`/verwaltung/messe`)} className="p-2 rounded-lg hover:bg-gray-100" data-testid="kontakte-back"><ArrowLeft className="w-5 h-5" /></button>
        <div className="flex-1 min-w-0">
          <h1 className="font-bold text-gray-900 truncate">Messe Kontaktformular</h1>
          {messe && <p className="text-xs text-gray-500 truncate">{messe.name} · {leads.length} Kontakt(e) · {counts.offen || 0} offen</p>}
        </div>
        <a href={`${BACKEND_URL}/api/messe/${messeId}/leads/export.csv?token=${token}`} className="hidden sm:flex h-9 px-3 rounded-lg border border-gray-300 text-sm items-center gap-1.5 text-gray-700" data-testid="kontakte-export"><Download className="w-4 h-4" /> CSV</a>
        <Logo size="small" />
      </header>
      <main className="max-w-4xl mx-auto p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1"><Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" /><Input value={q} onChange={e => setQ(e.target.value)} placeholder="Suchen (Firma, Name, Ort, Thema …)" className="pl-9 h-10" data-testid="kontakte-search" /></div>
          <div className="flex gap-1 overflow-x-auto">
            {["alle", ...Object.keys(STATUS_LABEL)].map(s => (
              <button key={s} type="button" onClick={() => setFilter(s)} className={`h-10 px-3 rounded-lg text-xs font-medium whitespace-nowrap ${filter === s ? "bg-gray-900 text-white" : "bg-white border border-gray-200 text-gray-600"}`} data-testid={`kontakte-filter-${s}`}>
                {s === "alle" ? `Alle (${leads.length})` : `${STATUS_LABEL[s]} (${counts[s] || 0})`}
              </button>
            ))}
          </div>
        </div>
        {shown.length === 0 && <p className="text-sm text-gray-400 text-center py-10" data-testid="kontakte-empty">Noch keine Kontakte – das Messe-Team erfasst sie über „Messeprotokoll anlegen" im Hub.</p>}
        {shown.map(l => <LeadRow key={l.id} lead={l} messeId={messeId} onChange={onChange} />)}
      </main>
    </div>
  );
}
