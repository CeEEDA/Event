import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Logo } from "../components/Logo";
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import api from "../lib/api";
import { 
  Users, 
  Plus, 
  Pencil, 
  Trash2, 
  ArrowLeft,
  Shield,
  UserCheck,
  User,
  HardDrive,
  FileText,
  Link2,
  FolderOpen,
  Eye,
  KeyRound,
  Copy,
  Search
} from "lucide-react";

const ROLE_LABELS = {
  admin: "Administrator",
  mitarbeiter: "Mitarbeiter",
  kunde: "Kunde"
};

const ROLE_COLORS = {
  admin: "bg-fuchsia-100 text-fuchsia-800",
  mitarbeiter: "bg-blue-100 text-blue-700",
  kunde: "bg-gray-100 text-gray-700"
};

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [activeTab, setActiveTab] = useState("users");
  const [userRoleFilter, setUserRoleFilter] = useState("kunden");
  const [userSearch, setUserSearch] = useState("");
  const [usersWithFiles, setUsersWithFiles] = useState([]);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    role: "kunde",
    is_active: true,
    apps: {
      filesharing: {
        enabled: false,
        max_upload_size_mb: 100,
        can_write: false,
        can_delete: false
      }
    }
  });

  // Password management state
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [resetLink, setResetLink] = useState(null);

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmData, setConfirmData] = useState({ title: "", description: "", onConfirm: null });

  const loadData = async () => {
    setLoading(true);
    try {
      const [usersRes, statsRes] = await Promise.all([
        api.get("/users"),
        api.get("/stats")
      ]);
      setUsers(usersRes.data);
      setStats(statsRes.data);
    } catch (error) {
      toast.error("Fehler beim Laden der Daten");
    } finally {
      setLoading(false);
    }
  };

  const loadUsersWithFiles = async () => {
    try {
      const res = await api.get("/admin/users-with-files");
      setUsersWithFiles(res.data);
    } catch (error) {
      console.error("Error loading users with files:", error);
    }
  };

  useEffect(() => {
    loadData();
    loadUsersWithFiles();
  }, []);

  const openCreateModal = () => {
    setEditingUser(null);
    setFormData({
      name: "",
      email: "",
      password: "",
      role: "kunde",
      is_active: true,
      apps: {
        filesharing: {
          enabled: false,
          max_upload_size_mb: 100,
          can_write: false,
          can_delete: false
        }
      }
    });
    setModalOpen(true);
  };

  const openEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      name: user.name,
      email: user.email,
      password: "",
      role: user.role,
      is_active: user.is_active,
      apps: user.apps || {
        filesharing: {
          enabled: false,
          max_upload_size_mb: 100,
          can_write: false,
          can_delete: false
        }
      }
    });
    setModalOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      if (editingUser) {
        await api.put(`/users/${editingUser.id}`, {
          name: formData.name,
          role: formData.role,
          is_active: formData.is_active,
          apps: formData.apps
        });
        toast.success("Benutzer aktualisiert");
      } else {
        if (!formData.password) {
          toast.error("Passwort erforderlich");
          return;
        }
        await api.post("/users", {
          name: formData.name,
          email: formData.email,
          password: formData.password,
          role: formData.role
        });
        toast.success("Benutzer erstellt");
      }
      setModalOpen(false);
      loadData();
    } catch (error) {
      const message = error.response?.data?.detail || "Fehler beim Speichern";
      toast.error(message);
    }
  };

  const handleDelete = (user) => {
    if (user.id === currentUser.id) {
      toast.error("Sie können sich nicht selbst löschen");
      return;
    }
    
    setConfirmData({
      title: "Benutzer löschen",
      description: `Möchten Sie "${user.name}" (${user.email}) wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`,
      onConfirm: async () => {
        try {
          await api.delete(`/users/${user.id}`);
          toast.success("Benutzer gelöscht");
          loadData();
        } catch (error) {
          const message = error.response?.data?.detail || "Fehler beim Löschen";
          toast.error(message);
        }
        setConfirmOpen(false);
      }
    });
    setConfirmOpen(true);
  };

  // Password management functions
  const openPasswordModal = (user) => {
    setPasswordTarget(user);
    setNewPassword("");
    setResetLink(null);
    setPasswordModalOpen(true);
  };

  const handleSetPassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error("Passwort muss mindestens 6 Zeichen haben");
      return;
    }
    try {
      await api.post("/admin/set-password", {
        user_id: passwordTarget.id,
        new_password: newPassword
      });
      toast.success("Passwort wurde gesetzt");
      setNewPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Fehler beim Setzen des Passworts");
    }
  };

  const handleGenerateResetLink = async () => {
    try {
      const res = await api.post(`/admin/generate-reset-link/${passwordTarget.id}`);
      const baseUrl = window.location.origin;
      setResetLink(`${baseUrl}/reset-password/${res.data.reset_token}`);
      toast.success("Reset-Link erstellt");
    } catch (error) {
      toast.error("Fehler beim Erstellen des Links");
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("In Zwischenablage kopiert");
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const updateFilesharingApp = (field, value) => {
    setFormData(prev => ({
      ...prev,
      apps: {
        ...prev.apps,
        filesharing: {
          ...prev.apps.filesharing,
          [field]: value
        }
      }
    }));
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="admin-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/hub")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-hub-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">Benutzerverwaltung</h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                    <Users className="w-5 h-5 text-fuchsia-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{stats.users}</p>
                    <p className="text-xs text-gray-500">Benutzer</p>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{stats.files}</p>
                    <p className="text-xs text-gray-500">Dateien</p>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                    <Link2 className="w-5 h-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{stats.shares}</p>
                    <p className="text-xs text-gray-500">Shares</p>
                  </div>
                </div>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                    <HardDrive className="w-5 h-5 text-purple-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{formatBytes(stats.total_storage_bytes)}</p>
                    <p className="text-xs text-gray-500">Speicher</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-white border border-gray-200">
              <TabsTrigger value="users" className="data-[state=active]:bg-fuchsia-50 data-[state=active]:text-fuchsia-700">
                <Users className="w-4 h-4 mr-2" />
                Benutzer
              </TabsTrigger>
              <TabsTrigger value="files" className="data-[state=active]:bg-fuchsia-50 data-[state=active]:text-fuchsia-700">
                <FolderOpen className="w-4 h-4 mr-2" />
                Dateien
              </TabsTrigger>
            </TabsList>

            {/* Users Tab */}
            <TabsContent value="users" className="mt-4 space-y-4">
              {/* Role Sub-Tabs + Search */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                <div className="flex border border-gray-200 rounded-lg overflow-hidden bg-white">
                  <button
                    onClick={() => { setUserRoleFilter("kunden"); setUserSearch(""); }}
                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                      userRoleFilter === "kunden"
                        ? "bg-fuchsia-50 text-fuchsia-700 border-b-2 border-fuchsia-600"
                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                    }`}
                    data-testid="filter-kunden"
                  >
                    <User className="w-4 h-4" />
                    Kunden
                    <span className="ml-1 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">{users.filter(u => u.role === "kunde").length}</span>
                  </button>
                  <button
                    onClick={() => { setUserRoleFilter("mitarbeiter"); setUserSearch(""); }}
                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                      userRoleFilter === "mitarbeiter"
                        ? "bg-fuchsia-50 text-fuchsia-700 border-b-2 border-fuchsia-600"
                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                    }`}
                    data-testid="filter-mitarbeiter"
                  >
                    <UserCheck className="w-4 h-4" />
                    Mitarbeiter
                    <span className="ml-1 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">{users.filter(u => u.role === "mitarbeiter").length}</span>
                  </button>
                </div>
                
                <div className="flex items-center gap-2 flex-1">
                  <div className="relative flex-1 max-w-xs">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      placeholder="Benutzer suchen..."
                      value={userSearch}
                      onChange={(e) => setUserSearch(e.target.value)}
                      className="pl-8 h-9 border-gray-300 text-sm"
                      data-testid="user-search-input"
                    />
                  </div>
                  <Button
                    onClick={openCreateModal}
                    className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white flex-shrink-0"
                    data-testid="create-user-btn"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Neuer Benutzer
                  </Button>
                </div>
              </div>

              {/* Users Table */}
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full" data-testid="users-table">
                    <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                      <tr>
                        <th className="px-4 py-3 text-left">Name</th>
                        <th className="px-4 py-3 text-left hidden md:table-cell">E-Mail</th>
                        <th className="px-4 py-3 text-left">Rolle</th>
                        <th className="px-4 py-3 text-left hidden sm:table-cell">FileShare</th>
                        <th className="px-4 py-3 text-left hidden sm:table-cell">Status</th>
                        <th className="px-4 py-3 text-right">Aktionen</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {loading ? (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-gray-500">Laden...</td>
                        </tr>
                      ) : (() => {
                        const filtered = users.filter(u => {
                          // Role filter
                          if (userRoleFilter === "kunden" && u.role !== "kunde" && u.role !== "admin") return false;
                          if (userRoleFilter === "mitarbeiter" && u.role !== "mitarbeiter" && u.role !== "admin") return false;
                          // Search filter
                          if (userSearch) {
                            const q = userSearch.toLowerCase();
                            return u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
                          }
                          return true;
                        });
                        if (filtered.length === 0) {
                          return (
                            <tr>
                              <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                                {userSearch ? "Keine Benutzer gefunden" : "Keine Benutzer in dieser Kategorie"}
                              </td>
                            </tr>
                          );
                        }
                        return filtered.map((user) => (
                          <tr key={user.id} className="hover:bg-gray-50" data-testid={`user-row-${user.id}`}>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                                  {user.role === "admin" ? (
                                    <Shield className="w-4 h-4 text-fuchsia-600" />
                                  ) : user.role === "mitarbeiter" ? (
                                    <UserCheck className="w-4 h-4 text-blue-500" />
                                  ) : (
                                    <User className="w-4 h-4 text-gray-500" />
                                  )}
                                </div>
                                <span className="font-medium text-gray-900">{user.name}</span>
                              </div>
                            </td>
                            <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                              {user.email}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${ROLE_COLORS[user.role]}`}>
                                {ROLE_LABELS[user.role]}
                              </span>
                            </td>
                            <td className="px-4 py-3 hidden sm:table-cell">
                              {user.role === "admin" || user.apps?.filesharing?.enabled ? (
                                <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-green-500" />
                                  Aktiv
                                  {user.apps?.filesharing?.can_write && " (Schreiben)"}
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-gray-400 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-gray-300" />
                                  Nicht aktiv
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 hidden sm:table-cell">
                              {user.is_active ? (
                                <span className="inline-flex items-center gap-1 text-green-600 text-sm">
                                  <span className="w-2 h-2 rounded-full bg-green-500" />
                                  Aktiv
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-red-600 text-sm">
                                  <span className="w-2 h-2 rounded-full bg-red-500" />
                                  Inaktiv
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => openPasswordModal(user)}
                                  className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                                  title="Passwort verwalten"
                                  data-testid={`password-user-${user.id}`}
                                >
                                  <KeyRound className="w-4 h-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => openEditModal(user)}
                                  className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                                  data-testid={`edit-user-${user.id}`}
                                >
                                  <Pencil className="w-4 h-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDelete(user)}
                                  className="h-8 w-8 text-gray-500 hover:text-red-500"
                                  disabled={user.id === currentUser.id}
                                  data-testid={`delete-user-${user.id}`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            </TabsContent>

            {/* Files Tab - View all users' files */}
            <TabsContent value="files" className="mt-4">
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="p-4 border-b border-gray-200">
                  <h2 className="font-semibold text-gray-900">Dateien nach Benutzer</h2>
                  <p className="text-sm text-gray-500 mt-1">Übersicht aller Benutzer und ihrer Dateien</p>
                </div>
                
                <div className="divide-y divide-gray-100">
                  {usersWithFiles.map((u) => (
                    <div key={u.id} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                          {u.role === "admin" ? (
                            <Shield className="w-5 h-5 text-fuchsia-600" />
                          ) : (
                            <User className="w-5 h-5 text-gray-500" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{u.name}</p>
                          <p className="text-sm text-gray-500">{u.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className="text-lg font-semibold text-gray-900">{u.file_count}</p>
                          <p className="text-xs text-gray-500">Dateien</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-semibold text-gray-900">{u.folder_count}</p>
                          <p className="text-xs text-gray-500">Ordner</p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/fileshare?view_user=${u.id}`)}
                          className="text-gray-600"
                        >
                          <Eye className="w-4 h-4 mr-2" />
                          Ansehen
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      {/* User Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="bg-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="user-modal">
          <DialogHeader>
            <DialogTitle className="text-gray-900">
              {editingUser ? "Benutzer bearbeiten" : "Neuer Benutzer"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-gray-700">Name</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Max Mustermann"
                className="border-gray-300"
                required
                data-testid="user-name-input"
              />
            </div>
            
            {!editingUser && (
              <>
                <div className="space-y-2">
                  <Label className="text-gray-700">E-Mail</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="name@firma.de"
                    className="border-gray-300"
                    required
                    data-testid="user-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-gray-700">Passwort</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Mindestens 6 Zeichen"
                    className="border-gray-300"
                    required
                    data-testid="user-password-input"
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label className="text-gray-700">Rolle</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger className="border-gray-300" data-testid="user-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Administrator</SelectItem>
                  <SelectItem value="mitarbeiter">Mitarbeiter</SelectItem>
                  <SelectItem value="kunde">Kunde</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {editingUser && (
              <>
                <div className="flex items-center justify-between py-2">
                  <Label className="text-gray-700">Konto aktiv</Label>
                  <Switch
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                    data-testid="user-active-toggle"
                  />
                </div>

                {/* App Permissions Section */}
                <div className="border-t border-gray-200 pt-4 mt-4">
                  <h3 className="font-semibold text-gray-900 mb-4">App-Berechtigungen</h3>
                  
                  {/* FileShare App */}
                  <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <FolderOpen className="w-5 h-5 text-fuchsia-600" />
                        <Label className="text-gray-900 font-medium">FileShare</Label>
                      </div>
                      <Switch
                        checked={formData.apps.filesharing.enabled}
                        onCheckedChange={(checked) => updateFilesharingApp("enabled", checked)}
                        data-testid="filesharing-enabled-toggle"
                      />
                    </div>

                    {formData.apps.filesharing.enabled && (
                      <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                        <div className="space-y-2">
                          <Label className="text-gray-600 text-sm">Max. Dateigröße (MB)</Label>
                          <Input
                            type="number"
                            value={formData.apps.filesharing.max_upload_size_mb}
                            onChange={(e) => updateFilesharingApp("max_upload_size_mb", parseInt(e.target.value) || 100)}
                            className="border-gray-300 w-32"
                            min={1}
                            max={10000}
                            data-testid="filesharing-max-size-input"
                          />
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Schreiben erlaubt (Gemeinsamer Bereich)</Label>
                          <Switch
                            checked={formData.apps.filesharing.can_write}
                            onCheckedChange={(checked) => updateFilesharingApp("can_write", checked)}
                            data-testid="filesharing-write-toggle"
                          />
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Löschen erlaubt (Gemeinsamer Bereich)</Label>
                          <Switch
                            checked={formData.apps.filesharing.can_delete}
                            onCheckedChange={(checked) => updateFilesharingApp("can_delete", checked)}
                            data-testid="filesharing-delete-toggle"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-user-btn">
                {editingUser ? "Speichern" : "Erstellen"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Password Management Modal */}
      <Dialog open={passwordModalOpen} onOpenChange={setPasswordModalOpen}>
        <DialogContent className="bg-white max-w-md" data-testid="password-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-gray-900">
              <KeyRound className="w-5 h-5 text-fuchsia-600" />
              Passwort verwalten
            </DialogTitle>
          </DialogHeader>

          {passwordTarget && (
            <div className="space-y-5">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-sm text-gray-500">Benutzer</p>
                <p className="font-medium text-gray-900">{passwordTarget.name} ({passwordTarget.email})</p>
              </div>

              {/* Set new password */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-700">Neues Passwort setzen</h4>
                <div className="flex gap-2">
                  <Input
                    type="text"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Neues Passwort (min. 6 Zeichen)"
                    className="border-gray-300 flex-1"
                    data-testid="admin-new-password-input"
                  />
                  <Button
                    onClick={handleSetPassword}
                    disabled={!newPassword || newPassword.length < 6}
                    className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                    data-testid="admin-set-password-btn"
                  >
                    Setzen
                  </Button>
                </div>
              </div>

              <div className="border-t border-gray-200" />

              {/* Generate reset link */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-700">Reset-Link erstellen</h4>
                <p className="text-xs text-gray-500">
                  Erstellt einen einmaligen Link, mit dem der Benutzer sein Passwort selbst zurücksetzen kann.
                </p>
                <Button
                  variant="outline"
                  onClick={handleGenerateResetLink}
                  className="w-full border-gray-300"
                  data-testid="admin-generate-reset-link-btn"
                >
                  <Link2 className="w-4 h-4 mr-2" />
                  Reset-Link generieren
                </Button>

                {resetLink && (
                  <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-3 space-y-2">
                    <p className="text-xs font-medium text-fuchsia-700">Reset-Link (24h gültig):</p>
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-fuchsia-600 break-all flex-1">{resetLink}</code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 flex-shrink-0"
                        onClick={() => copyToClipboard(resetLink)}
                        data-testid="copy-reset-link-btn"
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title={confirmData.title}
        description={confirmData.description}
        onConfirm={confirmData.onConfirm}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
