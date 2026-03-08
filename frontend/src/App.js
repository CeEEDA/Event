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
import SchaustellerAnmeldungPage from "./pages/SchaustellerAnmeldungPage";
import "./App.css";

const ProtectedRoute = ({ children, requiredRole }) => {
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
      <Route path="/kirmes/anmeldung" element={<SchaustellerAnmeldungPage />} />
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
      <Route path="/share/:token" element={<SharedFilePage />} />
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
