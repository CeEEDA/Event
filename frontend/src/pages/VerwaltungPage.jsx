import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { ArrowLeft, ChevronRight, Receipt, FolderOpen, BarChart3, Clock, Zap, FileText, Package } from "lucide-react";

export default function VerwaltungPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const allItems = [
    {
      key: "eingangsrechnungen",
      label: "Eingangsrechnungen",
      description: "Empfangene Rechnungen tracken, überfällig/bezahlt, PDF-Vorschau",
      icon: Receipt,
      color: "amber",
      path: "/eingangsrechnungen",
      requiresBilling: true,
    },
    {
      key: "finance",
      label: "Ausgangsrechnungen",
      description: "Rechnungen verwalten, versenden und exportieren",
      icon: Receipt,
      color: "emerald",
      path: "/finance",
      requiresBilling: true,
    },
    {
      key: "documents",
      label: "Dokumentenverwaltung",
      description: "Dokumente ablegen, KI-Erkennung, Volltextsuche",
      icon: FolderOpen,
      color: "blue",
      path: "/verwaltung/dokumente",
    },
    {
      key: "auswertung",
      label: "Auswertung",
      description: "Mitarbeiter-Dokumente, Ablaufdaten und Übersicht",
      icon: BarChart3,
      color: "fuchsia",
      path: "/verwaltung/auswertung",
    },
    {
      key: "zeiterfassung",
      label: "Mitarbeiter",
      description: "Stempelzeiten aller Mitarbeiter",
      icon: Clock,
      color: "green",
      path: "/verwaltung/zeiterfassung",
    },
    {
      key: "textbausteine",
      label: "Textbausteine",
      description: "Vordefinierte Texte für das Arbeitsprotokoll im Projektbericht",
      icon: FileText,
      color: "amber",
      path: "/verwaltung/textbausteine",
    },
    {
      key: "ki-training",
      label: "KI-Training",
      description: "Dokumentenerkennung trainieren und Prompts anpassen",
      icon: Zap,
      color: "fuchsia",
      path: "/ki-training",
      adminOnly: true,
    },
    {
      key: "inventar",
      label: "Inventar",
      description: "Anlagevermoegen mit Bildern verwalten (iPad/iPhone)",
      icon: Package,
      color: "fuchsia",
      path: "/verwaltung/inventar",
    },
  ];

  const items = allItems.filter(item => {
    if (item.adminOnly) return isAdmin;
    if (item.requiredApp) return isAdmin || user?.apps?.[item.requiredApp]?.enabled;
    if (item.requiresBilling) return isAdmin || !!user?.permissions?.can_billing;
    return true;
  });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="verwaltung-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <h1 className="text-base font-semibold text-gray-900">Verwaltung</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {items.length === 0 && (
          <div className="text-center py-16" data-testid="no-permissions-message">
            <FolderOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">Keine Verwaltungsbereiche freigeschaltet.</p>
            <p className="text-sm text-gray-400 mt-1">Bitte kontaktieren Sie den Administrator.</p>
          </div>
        )}
        {items.map(item => {
          const Icon = item.icon;
          const colorClasses = {
            emerald: { bg: "bg-emerald-100", text: "text-emerald-600", hoverBorder: "hover:border-emerald-400", hoverIcon: "group-hover:bg-emerald-600" },
            fuchsia: { bg: "bg-fuchsia-100", text: "text-fuchsia-600", hoverBorder: "hover:border-fuchsia-400", hoverIcon: "group-hover:bg-fuchsia-600" },
            blue:    { bg: "bg-blue-100",    text: "text-blue-600",    hoverBorder: "hover:border-blue-400",    hoverIcon: "group-hover:bg-blue-600" },
            amber:   { bg: "bg-amber-100",   text: "text-amber-600",   hoverBorder: "hover:border-amber-400",   hoverIcon: "group-hover:bg-amber-600" },
            green:   { bg: "bg-green-100",   text: "text-green-600",   hoverBorder: "hover:border-green-400",   hoverIcon: "group-hover:bg-green-600" },
            gray:    { bg: "bg-gray-100",    text: "text-gray-600",    hoverBorder: "hover:border-gray-400",    hoverIcon: "group-hover:bg-gray-600" },
          };
          const c = colorClasses[item.color] || colorClasses.gray;
          return (
            <button key={item.key}
              onClick={() => navigate(item.path)}
              className={`w-full bg-white border border-gray-200 rounded-xl p-5 md:p-6 flex items-center gap-4 ${c.hoverBorder} hover:shadow-lg transition-all group text-left`}
              data-testid={`verwaltung-${item.key}-btn`}
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
    </div>
  );
}
