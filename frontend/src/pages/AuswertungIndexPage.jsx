import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ArrowLeft, BarChart3, FileText, ChevronRight, Fuel, Wrench, Heart, ClipboardList } from "lucide-react";

const subPages = [
  {
    key: "stundenberichte",
    label: "Stundenberichte",
    description: "Alle Projektberichte mit Volltextsuche – inkl. Blanko-Berichte",
    icon: ClipboardList,
    color: "fuchsia",
    path: "/verwaltung/stundenberichte",
  },
  {
    key: "dokumente",
    label: "Mitarbeiterdokumente",
    description: "Ablaufdaten, Status und Übersicht aller Mitarbeiter-Dokumente",
    icon: FileText,
    color: "fuchsia",
    path: "/verwaltung/auswertung/dokumente",
  },
  {
    key: "verbandsbuch",
    label: "Verbandsbuch",
    description: "Alle gemeldeten Unfälle und Verletzungen gem. DGUV",
    icon: Heart,
    color: "red",
    path: "/verwaltung/auswertung/verbandsbuch",
  },
  {
    key: "fuel",
    label: "Fuel",
    description: "Tankbelege, Verbrauch nach Kunde und Lager",
    icon: Fuel,
    color: "amber",
    path: "/verwaltung/fuel",
  },
  {
    key: "maschinen-auswertung",
    label: "Maschinen-Auswertung",
    description: "Störmeldungen, Ausfallstatistik pro Maschine und Zeitraum",
    icon: Wrench,
    color: "red",
    path: "/verwaltung/maschinen-auswertung",
  },
];

const colorClasses = {
  fuchsia: { bg: "bg-fuchsia-100", text: "text-fuchsia-600", hoverBorder: "hover:border-fuchsia-400", hoverIcon: "group-hover:bg-fuchsia-600" },
  blue: { bg: "bg-blue-100", text: "text-blue-600", hoverBorder: "hover:border-blue-400", hoverIcon: "group-hover:bg-blue-600" },
  green: { bg: "bg-green-100", text: "text-green-600", hoverBorder: "hover:border-green-400", hoverIcon: "group-hover:bg-green-600" },
  amber: { bg: "bg-amber-100", text: "text-amber-600", hoverBorder: "hover:border-amber-400", hoverIcon: "group-hover:bg-amber-600" },
  red: { bg: "bg-red-100", text: "text-red-600", hoverBorder: "hover:border-red-400", hoverIcon: "group-hover:bg-red-600" },
};

export default function AuswertungIndexPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  if (!isAdmin) { navigate("/hub"); return null; }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="auswertung-index-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <BarChart3 className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Auswertung</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {subPages.map(item => {
          const cc = colorClasses[item.color] || colorClasses.fuchsia;
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => navigate(item.path)}
              className={`w-full text-left bg-white border border-gray-200 ${cc.hoverBorder} rounded-xl p-5 flex items-center gap-4 hover:shadow-md transition-all group`}
              data-testid={`auswertung-${item.key}-btn`}
            >
              <div className={`w-12 h-12 rounded-xl ${cc.bg} ${cc.hoverIcon} flex items-center justify-center transition-colors`}>
                <Icon className={`w-6 h-6 ${cc.text} group-hover:text-white transition-colors`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900">{item.label}</p>
                <p className="text-sm text-gray-500 mt-0.5">{item.description}</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 flex-shrink-0" />
            </button>
          );
        })}
      </main>
    </div>
  );
}
