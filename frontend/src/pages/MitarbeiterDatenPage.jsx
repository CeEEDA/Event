import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, ChevronRight, Clock, CalendarOff, Receipt, User as UserIcon } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Switch } from "../components/ui/switch";

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
  ];

  const colorClasses = {
    green: { bg: "bg-green-100", text: "text-green-600", hoverBorder: "hover:border-green-400", hoverIcon: "group-hover:bg-green-600" },
    orange: { bg: "bg-orange-100", text: "text-orange-600", hoverBorder: "hover:border-orange-400", hoverIcon: "group-hover:bg-orange-600" },
    emerald: { bg: "bg-emerald-100", text: "text-emerald-600", hoverBorder: "hover:border-emerald-400", hoverIcon: "group-hover:bg-emerald-600" },
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
    </div>
  );
}
