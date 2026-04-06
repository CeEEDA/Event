import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import HubPage from "./pages/HubPage";
import DashboardPage from "./pages/DashboardPage";
import AdminPage from "./pages/AdminPage";
import SharedFilePage from "./pages/SharedFilePage";
import GeneratorDashboardPage from "./pages/GeneratorDashboardPage";
import GeneratorDetailPage from "./pages/GeneratorDetailPage";
import DeviceManagementPage from "./pages/DeviceManagementPage";
import ServiceplanPage from "./pages/ServiceplanPage";
import MqttConfigPage from "./pages/MqttConfigPage";
import EnergyMonitoringPage from "./pages/EnergyMonitoringPage";
import EnergyMonitoringDetailPage from "./pages/EnergyMonitoringDetailPage";
import AdminSettingsPage from "./pages/AdminSettingsPage";
import OrdersPage from "./pages/OrdersPage";
import OrderDetailPage from "./pages/OrderDetailPage";
import KirmesPage from "./pages/KirmesPage";
import KirmesEventDetailPage from "./pages/KirmesEventDetailPage";
import KirmesEventDocumentsPage from "./pages/KirmesEventDocumentsPage";
import KirmesZaehlerPage from "./pages/KirmesZaehlerPage";
import PaymentDashboardPage from "./pages/PaymentDashboardPage";
import SchaustellerAnmeldungPage from "./pages/SchaustellerAnmeldungPage";
import SchaustellerDetailPage from "./pages/SchaustellerDetailPage";
import MeterZuordnungPage from "./pages/MeterZuordnungPage";
import MeterDiagnosticsPage from "./pages/MeterDiagnosticsPage";
import ProjectReportFormPage from "./pages/ProjectReportFormPage";
import OrderDocumentsPage from "./pages/OrderDocumentsPage";
import FinancePage from "./pages/FinancePage";
import VerwaltungPage from "./pages/VerwaltungPage";
import DocumentManagementPage from "./pages/DocumentManagementPage";
import ChatPage from "./pages/ChatPage";
import ProfilePage from "./pages/ProfilePage";
import EmployeeAdminPage from "./pages/EmployeeAdminPage";
import AuswertungPage from "./pages/AuswertungPage";
import AuswertungIndexPage from "./pages/AuswertungIndexPage";
import ArbeitszeitPage from "./pages/ArbeitszeitPage";
import AdminZeiterfassungPage from "./pages/AdminZeiterfassungPage";
import AdminZeitDetailPage from "./pages/AdminZeitDetailPage";
import MitarbeiterNotizenPage from "./pages/MitarbeiterNotizenPage";
import AbrechnungPage from "./pages/AbrechnungPage";
import EinsatzplanungPage from "./pages/EinsatzplanungPage";
import "./App.css";

const ProtectedRoute = ({ children, requiredRole, requiredApp }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-white">
        <div className="animate-pulse text-fuchsia-600">Laden...</div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  if (requiredRole && user.role !== requiredRole && user.role !== "admin") {
    return <Navigate to="/hub" replace />;
  }

  if (requiredApp && user.role !== "admin") {
    const appPerm = user.apps?.[requiredApp];
    if (!appPerm?.enabled) {
      return <Navigate to="/hub" replace />;
    }
  }
  
  return children;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-white">
        <div className="animate-pulse text-fuchsia-600">Laden...</div>
      </div>
    );
  }
  
  if (user) {
    return <Navigate to="/hub" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/register" 
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/forgot-password" 
        element={
          <PublicRoute>
            <ForgotPasswordPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/reset-password/:token" 
        element={
          <PublicRoute>
            <ResetPasswordPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/hub" 
        element={
          <ProtectedRoute>
            <HubPage />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/fileshare" 
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/admin" 
        element={
          <ProtectedRoute requiredRole="admin">
            <AdminPage />
          </ProtectedRoute>
        } 
      />
      <Route
        path="/admin/settings"
        element={
          <ProtectedRoute requiredRole="admin">
            <AdminSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders"
        element={
          <ProtectedRoute>
            <OrdersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders/:pk"
        element={
          <ProtectedRoute>
            <OrderDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders/:pk/dokumente"
        element={
          <ProtectedRoute>
            <OrderDocumentsPage />
          </ProtectedRoute>
        }
      />
      <Route path="/kirmes/anmeldung" element={<SchaustellerAnmeldungPage />} />
      <Route
        path="/verwaltung"
        element={
          <ProtectedRoute>
            <VerwaltungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/dokumente"
        element={
          <ProtectedRoute requiredApp="dokumentenverwaltung">
            <DocumentManagementPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/finance"
        element={
          <ProtectedRoute requiredApp="finance">
            <FinancePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/mitarbeiter"
        element={
          <ProtectedRoute>
            <EmployeeAdminPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes/meter-zuordnung/:meterId"
        element={
          <ProtectedRoute>
            <MeterZuordnungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes"
        element={
          <ProtectedRoute>
            <KirmesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes/:id"
        element={
          <ProtectedRoute>
            <KirmesEventDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes/:id/dokumente"
        element={
          <ProtectedRoute>
            <KirmesEventDocumentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes/:eventId/zaehler/:signupId"
        element={
          <ProtectedRoute>
            <KirmesZaehlerPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kirmes/zahlungen"
        element={
          <ProtectedRoute>
            <PaymentDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/schausteller/:id"
        element={
          <ProtectedRoute>
            <SchaustellerDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/generators"
        element={
          <ProtectedRoute>
            <GeneratorDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/generators/:id"
        element={
          <ProtectedRoute>
            <GeneratorDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/devices"
        element={
          <ProtectedRoute>
            <DeviceManagementPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/devices/:deviceId/meters/:meterId"
        element={
          <ProtectedRoute>
            <MeterDiagnosticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/serviceplan"
        element={
          <ProtectedRoute>
            <ServiceplanPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mqtt-config"
        element={
          <ProtectedRoute requiredRole="admin">
            <MqttConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/energy-monitoring"
        element={
          <ProtectedRoute>
            <EnergyMonitoringPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/energy-monitoring/:id"
        element={
          <ProtectedRoute>
            <EnergyMonitoringDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/auswertung"
        element={
          <ProtectedRoute requiredRole="admin">
            <AuswertungIndexPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/auswertung/dokumente"
        element={
          <ProtectedRoute requiredRole="admin">
            <AuswertungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/zeiterfassung"
        element={
          <ProtectedRoute requiredRole="admin">
            <AdminZeiterfassungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/zeiterfassung/:userId/notizen"
        element={
          <ProtectedRoute requiredRole="admin">
            <MitarbeiterNotizenPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/verwaltung/zeiterfassung/:userId"
        element={
          <ProtectedRoute requiredRole="admin">
            <AdminZeitDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/arbeitszeit"
        element={
          <ProtectedRoute>
            <ArbeitszeitPage />
          </ProtectedRoute>
        }
      />
      <Route path="/share/:token" element={<SharedFilePage />} />
      <Route
        path="/abrechnung"
        element={
          <ProtectedRoute>
            <AbrechnungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/einsatzplanung"
        element={
          <ProtectedRoute>
            <EinsatzplanungPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/project-report/new"
        element={
          <ProtectedRoute>
            <ProjectReportFormPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/project-report/:reportId"
        element={
          <ProtectedRoute>
            <ProjectReportFormPage />
          </ProtectedRoute>
        }
      />
      {/* Redirect old dashboard route */}
      <Route path="/dashboard" element={<Navigate to="/hub" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster 
          position="top-right"
          toastOptions={{
            className: "bg-white border-gray-200 text-gray-900",
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
