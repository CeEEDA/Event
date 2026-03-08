import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Logo } from "../components/Logo";
import { 
  FolderOpen, 
  Users, 
  LogOut,
  ChevronRight,
  Activity,
  Settings,
  Wrench,
  Zap,
  ClipboardList,
  Tent,
} from "lucide-react";

export default function HubPage() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const hasFilesharing = isAdmin || user?.apps?.filesharing?.enabled;
  const hasMonitoring = isAdmin || user?.apps?.generator_monitoring?.enabled;
  const hasEnergyMonitoring = isAdmin || user?.apps?.energy_monitoring?.enabled;
  const isStaff = isAdmin || user?.role === "mitarbeiter";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="hub-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4 md:p-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-gray-900">{user?.name}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="text-gray-600 hover:text-red-600 hover:border-red-300"
              data-testid="logout-btn"
            >
              <LogOut className="w-4 h-4 mr-2" />
              <span className="hidden sm:inline">Abmelden</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-4 md:p-8">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-8">
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
              Willkommen, {user?.name}!
            </h1>
            <p className="text-gray-500">
              Wählen Sie einen Bereich
            </p>
          </div>

          <div className="grid gap-4 md:gap-6">
            {/* Auftragsverwaltung - ganz oben */}
            {isStaff && (
              <button
                onClick={() => navigate("/orders")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="orders-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <ClipboardList className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Auftragsverwaltung</h2>
                  <p className="text-sm text-gray-500">Aufträge anlegen, verwalten und nachverfolgen</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Kirmes-Verwaltung */}
            {isStaff && (
              <button
                onClick={() => navigate("/kirmes")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="kirmes-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Tent className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Kirmes-Verwaltung</h2>
                  <p className="text-sm text-gray-500">Veranstaltungen, Schausteller-Anmeldungen und Abrechnung</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Monitoring */}
            {hasMonitoring && (
              <button
                onClick={() => navigate("/generators")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="generator-monitoring-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Activity className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Power Monitoring</h2>
                  <p className="text-sm text-gray-500">Überwachung und Steuern von Stromerzeugern, Lichtmasten und Batteriesysteme</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Energy Monitoring */}
            {hasEnergyMonitoring && (
              <button
                onClick={() => navigate("/energy-monitoring")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="energy-monitoring-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Zap className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Energy Monitoring</h2>
                  <p className="text-sm text-gray-500">Energieverbrauch überwachen und Messdaten pro Zähler auswerten</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Geräteverwaltung - Admin + Mitarbeiter */}
            {isStaff && (
              <button
                onClick={() => navigate("/devices")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="device-management-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Settings className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Geräteverwaltung</h2>
                  <p className="text-sm text-gray-500">Endgeräte anlegen, verwalten und konfigurieren</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* FileShare - unter Geräteverwaltung */}
            {hasFilesharing && (
              <button
                onClick={() => navigate("/fileshare")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="fileshare-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <FolderOpen className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">FileShare</h2>
                  <p className="text-sm text-gray-500">Dateien hochladen, verwalten und teilen</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Serviceplan - Admin + Mitarbeiter */}
            {isStaff && (
              <button
                onClick={() => navigate("/serviceplan")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="serviceplan-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Wrench className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Serviceplan</h2>
                  <p className="text-sm text-gray-500">Wartungspläne anlegen und verwalten</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

            {/* Benutzerverwaltung - nur Admin */}
            {isAdmin && (
              <button
                onClick={() => navigate("/admin")}
                className="bg-white border border-gray-200 rounded-xl p-6 md:p-8 flex items-center gap-4 md:gap-6 hover:border-fuchsia-400 hover:shadow-lg transition-all group text-left"
                data-testid="admin-btn"
              >
                <div className="w-14 h-14 md:w-16 md:h-16 rounded-xl bg-fuchsia-100 flex items-center justify-center flex-shrink-0 group-hover:bg-fuchsia-600 transition-colors">
                  <Users className="w-7 h-7 md:w-8 md:h-8 text-fuchsia-600 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-semibold text-gray-900 mb-1">Benutzerverwaltung</h2>
                  <p className="text-sm text-gray-500">Benutzer anlegen, bearbeiten und Rechte vergeben</p>
                </div>
                <ChevronRight className="w-6 h-6 text-gray-400 group-hover:text-fuchsia-600 transition-colors" />
              </button>
            )}

          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
