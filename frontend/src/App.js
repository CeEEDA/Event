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
