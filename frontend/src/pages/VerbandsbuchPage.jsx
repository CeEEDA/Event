import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { BACKEND_URL } from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Heart, Trash2, Calendar, MapPin, User as UserIcon, Eye, Pencil, FileDown, Mail } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
const API = BACKEND_URL;

export default function VerbandsbuchPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);

  // Email share dialog
  const [showMail, setShowMail] = useState(false);
  const [mailTo, setMailTo] = useState("");
  const [mailMsg, setMailMsg] = useState("");
  const [mailSending, setMailSending] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") { navigate("/hub"); return; }
    loadEntries();
  }, [user, navigate]);

  const loadEntries = async () => {
    setLoading(true);
    try {
      const r = await api.get("/verbandsbuch");
      setEntries(r.data.entries || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Laden");
    }
    setLoading(false);
  };

  const handleDelete = async (entry) => {
    if (!window.confirm(`Eintrag Nr. ${entry.lfd_nr} wirklich löschen? (Soft-Delete)`)) return;
    try {
      await api.delete(`/verbandsbuch/${entry.id}`);
      toast.success("Eintrag gelöscht");
      setSelected(null);
      loadEntries();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Löschen");
    }
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const payload = {
        injured_name: selected.injured_name,
        injured_address: selected.injured_address || "",
        event_date: selected.event_date,
        event_time: selected.event_time,
        location: selected.location,
        hergang: selected.hergang,
        injury_type: selected.injury_type,
        witnesses: selected.witnesses || "",
        first_aider: selected.first_aider || "",
        notes: selected.notes || "",
      };
      const r = await api.patch(`/verbandsbuch/${selected.id}`, payload);
      setSelected(r.data);
      setEditMode(false);
      toast.success("Gespeichert");
      loadEntries();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Speichern");
    }
    setSaving(false);
  };

  const formatDate = (d) => {
    if (!d) return "-";
    try { return new Date(d + "T00:00:00").toLocaleDateString("de-DE"); } catch { return d; }
  };

  const handleDownloadPdf = async (entry) => {
    try {
      const token = localStorage.getItem("token");
      const resp = await fetch(`${API}/verbandsbuch/${entry.id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Verbandsbuch_Nr${String(entry.lfd_nr).padStart(4, "0")}_${entry.event_date}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("PDF heruntergeladen");
    } catch (e) {
      toast.error("PDF-Download fehlgeschlagen");
    }
  };

  const handleSendMail = async () => {
    if (!selected) return;
    if (!mailTo.trim() || !/.+@.+\..+/.test(mailTo)) {
      toast.error("Bitte gültige E-Mail-Adresse eingeben");
      return;
    }
    setMailSending(true);
    try {
      await api.post(`/verbandsbuch/${selected.id}/email`, { to_email: mailTo.trim(), message: mailMsg });
      toast.success(`E-Mail an ${mailTo} versendet`);
      setShowMail(false);
      setMailTo("");
      setMailMsg("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "E-Mail-Versand fehlgeschlagen");
    }
    setMailSending(false);
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="verbandsbuch-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung/auswertung")} className="text-gray-600 hover:text-red-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <Heart className="w-5 h-5 text-red-600" />
          <h1 className="text-base font-semibold text-gray-900">Verbandsbuch</h1>
          <span className="text-sm text-gray-400 ml-auto">{entries.length} Eintr{entries.length === 1 ? "ag" : "äge"}</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {loading ? (
          <div className="text-center py-16 text-gray-400">Lade...</div>
        ) : entries.length === 0 ? (
          <div className="text-center py-16" data-testid="no-entries">
            <Heart className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">Noch keine Einträge im Verbandsbuch.</p>
            <p className="text-sm text-gray-400 mt-1">Mitarbeiter können Einträge über "Mitarbeiter-Daten → Verbandseintrag melden" hinzufügen.</p>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-green-50 border-b border-gray-200 text-gray-700">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold w-16">Lfd.&nbsp;Nr.</th>
                    <th className="px-3 py-2 text-left font-semibold">Verletzte/r</th>
                    <th className="px-3 py-2 text-left font-semibold">Datum / Uhrzeit</th>
                    <th className="px-3 py-2 text-left font-semibold">Ort</th>
                    <th className="px-3 py-2 text-left font-semibold">Hergang</th>
                    <th className="px-3 py-2 text-left font-semibold">Art / Umfang</th>
                    <th className="px-3 py-2 text-left font-semibold">Meldung durch</th>
                    <th className="px-3 py-2 text-right font-semibold w-24">Aktion</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(e => (
                    <tr key={e.id} className="border-t border-gray-100 hover:bg-gray-50" data-testid={`verb-row-${e.lfd_nr}`}>
                      <td className="px-3 py-2 font-semibold text-gray-900">{e.lfd_nr}</td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-gray-900">{e.injured_name}</div>
                        {e.injured_address && <div className="text-xs text-gray-500">{e.injured_address}</div>}
                      </td>
                      <td className="px-3 py-2 text-gray-700">
                        <div>{formatDate(e.event_date)}</div>
                        <div className="text-xs text-gray-500">{e.event_time}</div>
                      </td>
                      <td className="px-3 py-2 text-gray-700">{e.location}</td>
                      <td className="px-3 py-2 text-gray-700 max-w-xs truncate" title={e.hergang}>{e.hergang}</td>
                      <td className="px-3 py-2 text-gray-700 max-w-xs truncate" title={e.injury_type}>{e.injury_type}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">{e.reporter_name}</td>
                      <td className="px-3 py-2 text-right">
                        <button onClick={() => { setSelected(e); setEditMode(false); }} className="text-gray-500 hover:text-fuchsia-600 p-1" title="Details" data-testid={`verb-view-${e.lfd_nr}`}>
                          <Eye className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleDownloadPdf(e)} className="text-gray-500 hover:text-emerald-600 p-1 ml-1" title="PDF herunterladen" data-testid={`verb-pdf-${e.lfd_nr}`}>
                          <FileDown className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleDelete(e)} className="text-gray-500 hover:text-red-600 p-1 ml-1" title="Löschen" data-testid={`verb-del-${e.lfd_nr}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      <Dialog open={!!selected} onOpenChange={(v) => { if (!v) { setSelected(null); setEditMode(false); } }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="verb-detail-dialog">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Heart className="w-5 h-5 text-red-600" />
                  Verbandsbuch – Lfd. Nr. {selected.lfd_nr}
                </DialogTitle>
              </DialogHeader>

              <div className="space-y-3 pt-2">
                <FieldRow label="Vorname, Name" icon={UserIcon}>
                  {editMode ? (
                    <Input value={selected.injured_name} onChange={e => setSelected({...selected, injured_name: e.target.value})} data-testid="edit-name" />
                  ) : <span>{selected.injured_name}</span>}
                </FieldRow>
                <FieldRow label="Anschrift">
                  {editMode ? (
                    <Input value={selected.injured_address || ""} onChange={e => setSelected({...selected, injured_address: e.target.value})} data-testid="edit-address" />
                  ) : <span className="text-gray-700">{selected.injured_address || "—"}</span>}
                </FieldRow>
                <div className="grid grid-cols-2 gap-3">
                  <FieldRow label="Datum" icon={Calendar}>
                    {editMode ? (
                      <Input type="date" value={selected.event_date} onChange={e => setSelected({...selected, event_date: e.target.value})} data-testid="edit-date" />
                    ) : <span>{formatDate(selected.event_date)}</span>}
                  </FieldRow>
                  <FieldRow label="Uhrzeit">
                    {editMode ? (
                      <Input type="time" value={selected.event_time} onChange={e => setSelected({...selected, event_time: e.target.value})} data-testid="edit-time" />
                    ) : <span>{selected.event_time}</span>}
                  </FieldRow>
                </div>
                <FieldRow label="Ort (Raum/Bereich)" icon={MapPin}>
                  {editMode ? (
                    <Input value={selected.location} onChange={e => setSelected({...selected, location: e.target.value})} data-testid="edit-location" />
                  ) : <span>{selected.location}</span>}
                </FieldRow>
                <FieldRow label="Hergang">
                  {editMode ? (
                    <Textarea rows={3} value={selected.hergang} onChange={e => setSelected({...selected, hergang: e.target.value})} data-testid="edit-hergang" />
                  ) : <span className="whitespace-pre-wrap text-gray-700">{selected.hergang}</span>}
                </FieldRow>
                <FieldRow label="Art und Umfang der Verletzung/Erkrankung">
                  {editMode ? (
                    <Textarea rows={2} value={selected.injury_type} onChange={e => setSelected({...selected, injury_type: e.target.value})} data-testid="edit-injury" />
                  ) : <span className="whitespace-pre-wrap text-gray-700">{selected.injury_type}</span>}
                </FieldRow>
                <FieldRow label="Ersthelfer">
                  {editMode ? (
                    <Input value={selected.first_aider || ""} onChange={e => setSelected({...selected, first_aider: e.target.value})} data-testid="edit-firstaider" />
                  ) : <span className="text-gray-700">{selected.first_aider || "—"}</span>}
                </FieldRow>
                <FieldRow label="Zeugen">
                  {editMode ? (
                    <Input value={selected.witnesses || ""} onChange={e => setSelected({...selected, witnesses: e.target.value})} data-testid="edit-witnesses" />
                  ) : <span className="text-gray-700">{selected.witnesses || "—"}</span>}
                </FieldRow>
                <FieldRow label="Notizen">
                  {editMode ? (
                    <Textarea rows={2} value={selected.notes || ""} onChange={e => setSelected({...selected, notes: e.target.value})} data-testid="edit-notes" />
                  ) : <span className="whitespace-pre-wrap text-gray-700">{selected.notes || "—"}</span>}
                </FieldRow>
                <div className="pt-2 text-xs text-gray-400 border-t border-gray-100">
                  Gemeldet durch: <b>{selected.reporter_name}</b> · {new Date(selected.created_at).toLocaleString("de-DE")}
                </div>
              </div>

              <DialogFooter className="gap-2 flex-wrap">
                {editMode ? (
                  <>
                    <Button variant="outline" onClick={() => setEditMode(false)} data-testid="cancel-edit">Abbrechen</Button>
                    <Button onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700" data-testid="save-edit">
                      {saving ? "Speichere..." : "Speichern"}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button variant="outline" onClick={() => handleDownloadPdf(selected)} data-testid="detail-pdf">
                      <FileDown className="w-4 h-4 mr-1" /> PDF
                    </Button>
                    <Button variant="outline" onClick={() => { setMailTo(""); setMailMsg(""); setShowMail(true); }} data-testid="detail-mail">
                      <Mail className="w-4 h-4 mr-1" /> Per E-Mail
                    </Button>
                    <Button onClick={() => setEditMode(true)} className="bg-fuchsia-600 hover:bg-fuchsia-700" data-testid="enable-edit">
                      <Pencil className="w-4 h-4 mr-1" /> Bearbeiten
                    </Button>
                  </>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Email share dialog */}
      <Dialog open={showMail} onOpenChange={setShowMail}>
        <DialogContent className="sm:max-w-md" data-testid="verb-mail-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-fuchsia-600" /> Verbandsbuch-Eintrag per E-Mail teilen
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-2">
            {selected && (
              <div className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-md px-3 py-2">
                Eintrag <b>Lfd. Nr. {selected.lfd_nr}</b> · {selected.injured_name} · {formatDate(selected.event_date)}
              </div>
            )}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Empfänger E-Mail *</label>
              <Input type="email" value={mailTo} onChange={e => setMailTo(e.target.value)} placeholder="z.B. bg@bgetem.de" data-testid="mail-to" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Nachricht (optional)</label>
              <Textarea rows={3} value={mailMsg} onChange={e => setMailMsg(e.target.value)} placeholder="Persönliche Nachricht an den Empfänger..." data-testid="mail-msg" />
            </div>
            <Button onClick={handleSendMail} disabled={mailSending} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700" data-testid="mail-send-btn">
              {mailSending ? "Wird gesendet..." : "PDF versenden"}
            </Button>
            <p className="text-[11px] text-gray-400">Der PDF-Anhang wird über das konfigurierte SMTP-Postfach versendet. Der Versand wird im Eintrag protokolliert.</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const FieldRow = ({ label, icon: Icon, children }) => (
  <div>
    <label className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {label}
    </label>
    <div className="text-sm">{children}</div>
  </div>
);
