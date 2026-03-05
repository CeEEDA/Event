import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";
import { 
  Zap, 
  FolderOpen, 
  Link2, 
  Settings, 
  Users, 
  LogOut,
  X,
  ChevronRight
} from "lucide-react";

export const Sidebar = ({ activeView, onViewChange, onClose }) => {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isAdminPage = location.pathname === "/admin";

  const navItems = [
    {
      id: "files",
      label: "Dateien",
      icon: FolderOpen,
      onClick: () => {
        if (isAdminPage) {
          navigate("/dashboard");
        } else {
          onViewChange("files");
        }
      },
      active: !isAdminPage && activeView === "files"
    },
    {
      id: "shares",
      label: "Geteilte Links",
      icon: Link2,
      onClick: () => {
        if (isAdminPage) {
          navigate("/dashboard");
          setTimeout(() => onViewChange("shares"), 100);
        } else {
          onViewChange("shares");
        }
      },
      active: !isAdminPage && activeView === "shares"
    }
  ];

  if (isAdmin) {
    navItems.push({
      id: "admin",
      label: "Administration",
      icon: Users,
      onClick: () => navigate("/admin"),
      active: isAdminPage
    });
  }

  return (
    <div className="h-full flex flex-col bg-card/80 backdrop-blur-xl border-r border-border" data-testid="sidebar">
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-primary flex items-center justify-center">
            <Zap className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="font-bold tracking-tight">FileShare</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onClose}
        >
          <X className="w-5 h-5" />
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={item.onClick}
            className={`
              w-full flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm font-medium
              transition-colors duration-150
              ${item.active 
                ? "bg-primary/10 text-primary border-l-2 border-primary" 
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              }
            `}
            data-testid={`nav-${item.id}`}
          >
            <item.icon className="w-5 h-5" />
            <span className="flex-1 text-left">{item.label}</span>
            {item.active && <ChevronRight className="w-4 h-4" />}
          </button>
        ))}
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3 px-3 py-2 mb-3">
          <div className="w-8 h-8 rounded-sm bg-muted flex items-center justify-center text-sm font-medium">
            {user?.name?.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.name}</p>
            <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
          </div>
        </div>
        
        <Button
          variant="ghost"
          onClick={handleLogout}
          className="w-full justify-start text-muted-foreground hover:text-destructive"
          data-testid="logout-btn"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Abmelden
        </Button>
      </div>
    </div>
  );
};
