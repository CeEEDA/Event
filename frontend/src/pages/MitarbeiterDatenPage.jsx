import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, ChevronRight, Clock, CalendarOff, Receipt, User as UserIcon, Heart, FileText } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";

export default function MitarbeiterDatenPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const token = localStorage.getItem("token");

  // Time-off request dialog (moved from HubPage)
  const [showTimeOff, setShowTimeOff] = useState(false);
  const [toType, setToType] = useState("");
  const [toStartDate, setToStartDate] = useState("");
  const [toEndDate, setToEndDate] = useState("");
  const [toAllDay, setToAllDay] = useState(true);
  const [toStartTime, setToStartTime] = useState("");
  const [toEndTime, setToEndTime] = useState("");
  const [toSubmitting, setToSubmitting] = useState(false);

  // Verbandsbuch (first-aid log) dialog
  const today = new Date().toISOString().slice(0, 10);
  const nowHM = new Date().toTimeString().slice(0, 5);
  const emptyVerb = {
    injured_name: user?.name || "",
    injured_address: "",
    event_date: today,
    event_time: nowHM,
    location: "",
    hergang: "",
    injury_type: "",
    first_aider: "",
    witnesses: "",
    notes: "",
  };
  const [showVerb, setShowVerb] = useState(false);
  const [verb, setVerb] = useState(emptyVerb);
  const [verbSubmitting, setVerbSubmitting] = useState(false);

  const submitVerbandsbuch = async () => {
    if (!verb.injured_name.trim()) { toast.error("Bitte Vor- und Nachname angeben"); return; }
    if (!verb.event_date || !verb.event_time) { toast.error("Bitte Datum und Uhrzeit angeben"); return; }
    if (!verb.location.trim()) { toast.error("Bitte Ort (Raum/Bereich) angeben"); return; }
    if (!verb.hergang.trim()) { toast.error("Bitte Hergang beschreiben"); return; }
    if (!verb.injury_type.trim()) { toast.error("Bitte Art/Umfang der Verletzung angeben"); return; }
    setVerbSubmitting(true);
    try {
      await api.post("/verbandsbuch", verb);
      toast.success("Verbandseintrag gespeichert");
      setShowVerb(false);
      setVerb({ ...emptyVerb, event_date: new Date().toISOString().slice(0, 10), event_time: new Date().toTimeString().slice(0, 5) });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Speichern");
    }
    setVerbSubmitting(false);
  };

  const submitTimeOff = async () => {
    if (!toType) { toast.error("Bitte Art auswählen"); return; }
    if (!toStartDate) { toast.error("Bitte Startdatum wählen"); return; }
    if (!toAllDay && (!toStartTime || !toEndTime)) { toast.error("Bitte Uhrzeiten angeben"); return; }
    setToSubmitting(true);
    try {
      await api.post(`/employee/time-off?token=${token}`, {
        type: toType,
        start_date: toStartDate,
        end_date: toEndDate || toStartDate,
        all_day: toAllDay,
        start_time: toAllDay ? null : toStartTime,
        end_time: toAllDay ? null : toEndTime,
      });
      toast.success("Antrag eingereicht");
      setShowTimeOff(false);
      setToType(""); setToStartDate(""); setToEndDate(""); setToAllDay(true); setToStartTime(""); setToEndTime("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Einreichen");
    }
    setToSubmitting(false);
  };

  const tiles = [
    {
      key: "arbeitszeit",
      label: "Arbeitszeit",
      description: "Stempelzeiten, Übersicht und Export",
      icon: Clock,
      color: "green",
      onClick: () => navigate("/arbeitszeit"),
    },
    {
      key: "time-off",
      label: "Freie Zeit",
      description: "Urlaub, Krank oder Überstundenabbau beantragen",
      icon: CalendarOff,
      color: "orange",
      onClick: () => setShowTimeOff(true),
    },
    {
      key: "abrechnung",
      label: "Abrechnung",
      description: "Lohnabrechnungen, Belege und Spesen",
      icon: Receipt,
      color: "emerald",
      onClick: () => navigate("/abrechnung"),
    },
    {
      key: "dokumente",
      label: "Dokumente",
      description: "Personalausweis, Führerschein und Zertifikate ansehen",
      icon: FileText,
      color: "fuchsia",
      onClick: () => navigate("/mitarbeiter-daten/dokumente"),
    },
    {
      key: "verbandsbuch",
      label: "Verbandseintrag melden",
      description: "Unfall, Verletzung oder Erkrankung gem. DGUV dokumentieren",
      icon: Heart,
      color: "red",
      onClick: () => setShowVerb(true),
    },
  ];

  const colorClasses = {
    green: { bg: "bg-green-100", text: "text-green-600", hoverBorder: "hover:border-green-400", hoverIcon: "group-hover:bg-green-600" },
    orange: { bg: "bg-orange-100", text: "text-orange-600", hoverBorder: "hover:border-orange-400", hoverIcon: "group-hover:bg-orange-600" },
    emerald: { bg: "bg-emerald-100", text: "text-emerald-600", hoverBorder: "hover:border-emerald-400", hoverIcon: "group-hover:bg-emerald-600" },
    red: { bg: "bg-red-100", text: "text-red-600", hoverBorder: "hover:border-red-400", hoverIcon: "group-hover:bg-red-600" },
    fuchsia: { bg: "bg-fuchsia-100", text: "text-fuchsia-600", hoverBorder: "hover:border-fuchsia-400", hoverIcon: "group-hover:bg-fuchsia-600" },
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="mitarbeiter-daten-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <UserIcon className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-base font-semibold text-gray-900">Mitarbeiter-Daten</h1>
          {user?.name && <span className="text-sm text-gray-400 ml-auto">{user.name}</span>}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {tiles.map(item => {
          const c = colorClasses[item.color];
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={item.onClick}
              className={`w-full bg-white border border-gray-200 rounded-xl p-5 md:p-6 flex items-center gap-4 ${c.hoverBorder} hover:shadow-lg transition-all group text-left`}
              data-testid={`mdaten-${item.key}-btn`}
            >
              <div className={`w-12 h-12 md:w-14 md:h-14 rounded-xl ${c.bg} flex items-center justify-center flex-shrink-0 ${c.hoverIcon} transition-colors`}>
                <Icon className={`w-6 h-6 md:w-7 md:h-7 ${c.text} group-hover:text-white transition-colors`} />
              </div>
              <div className="flex-1">
                <h2 className="text-base md:text-lg font-semibold text-gray-900 mb-0.5">{item.label}</h2>
                <p className="text-sm text-gray-500">{item.description}</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-gray-600 transition-colors" />
            </button>
          );
        })}
      </main>

      {/* Time Off Request Dialog */}
      <Dialog open={showTimeOff} onOpenChange={setShowTimeOff}>
        <DialogContent className="sm:max-w-md" data-testid="time-off-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CalendarOff className="w-5 h-5 text-orange-600" /> Arbeitsfreie Zeit beantragen
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Art</label>
              <Select value={toType} onValueChange={setToType}>
                <SelectTrigger data-testid="to-type-select">
                  <SelectValue placeholder="Bitte wählen..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="krank">Krank</SelectItem>
                  <SelectItem value="urlaub">Urlaub</SelectItem>
                  <SelectItem value="ueberstundenabbau">Überstundenabbau</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Von</label>
                <input type="date" value={toStartDate} onChange={e => setToStartDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-start-date" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Bis</label>
                <input type="date" value={toEndDate} onChange={e => setToEndDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-end-date" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-gray-700">Ganztägig</label>
              <Switch checked={toAllDay} onCheckedChange={setToAllDay} data-testid="to-all-day" />
            </div>
            {!toAllDay && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Von (Uhrzeit)</label>
                  <input type="time" value={toStartTime} onChange={e => setToStartTime(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-start-time" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Bis (Uhrzeit)</label>
                  <input type="time" value={toEndTime} onChange={e => setToEndTime(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-end-time" />
                </div>
              </div>
            )}
            <Button onClick={submitTimeOff} disabled={toSubmitting} className="w-full bg-orange-600 hover:bg-orange-700" data-testid="to-submit-btn">
              {toSubmitting ? "Wird eingereicht..." : "Absenden"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Verbandseintrag (First-aid log) Dialog */}
      <Dialog open={showVerb} onOpenChange={setShowVerb}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" data-testid="verb-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Heart className="w-5 h-5 text-red-600" /> Verbandseintrag melden
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-2">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Vorname, Name der/des Verletzten *</label>
              <Input value={verb.injured_name} onChange={e => setVerb({...verb, injured_name: e.target.value})} placeholder="Max Mustermann" data-testid="verb-name" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Anschrift (optional)</label>
              <Input value={verb.injured_address} onChange={e => setVerb({...verb, injured_address: e.target.value})} placeholder="Straße, PLZ Ort" data-testid="verb-address" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Datum *</label>
                <Input type="date" value={verb.event_date} onChange={e => setVerb({...verb, event_date: e.target.value})} data-testid="verb-date" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Uhrzeit *</label>
                <Input type="time" value={verb.event_time} onChange={e => setVerb({...verb, event_time: e.target.value})} data-testid="verb-time" />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Ort (Raum/Bereich) *</label>
              <Input value={verb.location} onChange={e => setVerb({...verb, location: e.target.value})} placeholder="z.B. Werkstatt, Lagerhalle Regal 3" data-testid="verb-location" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Hergang des Unfalls *</label>
              <Textarea rows={3} value={verb.hergang} onChange={e => setVerb({...verb, hergang: e.target.value})} placeholder="Was ist passiert? Wie kam es zur Verletzung?" data-testid="verb-hergang" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Art und Umfang der Verletzung/Erkrankung *</label>
              <Textarea rows={2} value={verb.injury_type} onChange={e => setVerb({...verb, injury_type: e.target.value})} placeholder="z.B. Schnittwunde 2 cm am linken Zeigefinger" data-testid="verb-injury" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Ersthelfer</label>
                <Input value={verb.first_aider} onChange={e => setVerb({...verb, first_aider: e.target.value})} placeholder="Name" data-testid="verb-firstaider" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Zeugen</label>
                <Input value={verb.witnesses} onChange={e => setVerb({...verb, witnesses: e.target.value})} placeholder="Name(n)" data-testid="verb-witnesses" />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Notizen (optional)</label>
              <Textarea rows={2} value={verb.notes} onChange={e => setVerb({...verb, notes: e.target.value})} placeholder="Sonstige Hinweise" data-testid="verb-notes" />
            </div>
            <Button onClick={submitVerbandsbuch} disabled={verbSubmitting} className="w-full bg-red-600 hover:bg-red-700" data-testid="verb-submit-btn">
              {verbSubmitting ? "Wird gespeichert..." : "Verbandseintrag speichern"}
            </Button>
            <p className="text-[11px] text-gray-400 pt-1">
              Gemäß DGUV Vorschrift 1 und §24 Abs. 6 SGB VII. Der Eintrag wird vom Admin im Verbandsbuch verwaltet und mind. 5 Jahre aufbewahrt.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
