import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Sidebar } from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
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
import api from "../lib/api";
import { 
  Users, 
  Plus, 
  Pencil, 
  Trash2, 
  Menu,
  Shield,
  UserCheck,
  User,
  HardDrive,
  FileText,
  Link2
} from "lucide-react";

const ROLE_LABELS = {
  admin: "Administrator",
  mitarbeiter: "Mitarbeiter",
  kunde: "Kunde"
};

const ROLE_COLORS = {
  admin: "bg-primary/20 text-primary",
  mitarbeiter: "bg-secondary/20 text-secondary",
  kunde: "bg-muted text-muted-foreground"
};

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    role: "kunde",
    max_upload_size_mb: 100,
    is_active: true
  });

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

  useEffect(() => {
    loadData();
  }, []);

  const openCreateModal = () => {
    setEditingUser(null);
    setFormData({
      name: "",
      email: "",
      password: "",
      role: "kunde",
      max_upload_size_mb: 100,
      is_active: true
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
      max_upload_size_mb: user.max_upload_size_mb,
      is_active: user.is_active
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
          max_upload_size_mb: parseInt(formData.max_upload_size_mb),
          is_active: formData.is_active
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

  const handleDelete = async (user) => {
    if (user.id === currentUser.id) {
      toast.error("Sie können sich nicht selbst löschen");
      return;
    }
    
    if (!window.confirm(`"${user.name}" wirklich löschen?`)) return;
    
    try {
      await api.delete(`/users/${user.id}`);
      toast.success("Benutzer gelöscht");
      loadData();
    } catch (error) {
      const message = error.response?.data?.detail || "Fehler beim Löschen";
      toast.error(message);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background" data-testid="admin-page">
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className={`
        fixed md:relative inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
      `}>
        <Sidebar 
          activeView="admin" 
          onViewChange={() => {}}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </Button>
            <h1 className="text-lg font-semibold">Administration</h1>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6 grid-lines">
          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-card border border-border rounded-sm p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-sm bg-primary/10 flex items-center justify-center">
                    <Users className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.users}</p>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Benutzer</p>
                  </div>
                </div>
              </div>
              <div className="bg-card border border-border rounded-sm p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-sm bg-secondary/10 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-secondary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.files}</p>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Dateien</p>
                  </div>
                </div>
              </div>
              <div className="bg-card border border-border rounded-sm p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-sm bg-green-500/10 flex items-center justify-center">
                    <Link2 className="w-5 h-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.shares}</p>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Shares</p>
                  </div>
                </div>
              </div>
              <div className="bg-card border border-border rounded-sm p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-sm bg-blue-500/10 flex items-center justify-center">
                    <HardDrive className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{formatBytes(stats.total_storage_bytes)}</p>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Speicher</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* User Management */}
          <Tabs defaultValue="users" className="space-y-4">
            <div className="flex items-center justify-between">
              <TabsList className="bg-card border border-border">
                <TabsTrigger value="users" className="data-[state=active]:bg-muted">
                  <Users className="w-4 h-4 mr-2" />
                  Benutzer
                </TabsTrigger>
              </TabsList>
              <Button
                onClick={openCreateModal}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                data-testid="create-user-btn"
              >
                <Plus className="w-4 h-4 mr-2" />
                Neuer Benutzer
              </Button>
            </div>

            <TabsContent value="users" className="mt-4">
              <div className="bg-card border border-border rounded-sm overflow-hidden">
                <table className="data-table" data-testid="users-table">
                  <thead className="bg-muted/30">
                    <tr>
                      <th className="text-left">Name</th>
                      <th className="text-left hidden md:table-cell">E-Mail</th>
                      <th className="text-left">Rolle</th>
                      <th className="text-left hidden sm:table-cell">Limit</th>
                      <th className="text-left hidden sm:table-cell">Status</th>
                      <th className="text-right">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={6} className="text-center py-8 text-muted-foreground">
                          Laden...
                        </td>
                      </tr>
                    ) : users.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center py-8 text-muted-foreground">
                          Keine Benutzer gefunden
                        </td>
                      </tr>
                    ) : (
                      users.map((user) => (
                        <tr key={user.id} data-testid={`user-row-${user.id}`}>
                          <td>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-sm bg-muted flex items-center justify-center">
                                {user.role === "admin" ? (
                                  <Shield className="w-4 h-4 text-primary" />
                                ) : user.role === "mitarbeiter" ? (
                                  <UserCheck className="w-4 h-4 text-secondary" />
                                ) : (
                                  <User className="w-4 h-4" />
                                )}
                              </div>
                              <span className="font-medium">{user.name}</span>
                            </div>
                          </td>
                          <td className="hidden md:table-cell text-muted-foreground">
                            {user.email}
                          </td>
                          <td>
                            <span className={`px-2 py-1 rounded-sm text-xs font-medium uppercase ${ROLE_COLORS[user.role]}`}>
                              {ROLE_LABELS[user.role]}
                            </span>
                          </td>
                          <td className="hidden sm:table-cell font-mono text-sm">
                            {user.max_upload_size_mb} MB
                          </td>
                          <td className="hidden sm:table-cell">
                            <span className={`w-2 h-2 rounded-full inline-block ${user.is_active ? "bg-green-500" : "bg-red-500"}`} />
                          </td>
                          <td className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => openEditModal(user)}
                                className="h-8 w-8"
                                data-testid={`edit-user-${user.id}`}
                              >
                                <Pencil className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDelete(user)}
                                className="h-8 w-8 hover:text-destructive"
                                disabled={user.id === currentUser.id}
                                data-testid={`delete-user-${user.id}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </TabsContent>
          </Tabs>
        </main>
      </div>

      {/* User Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="bg-card border-border" data-testid="user-modal">
          <DialogHeader>
            <DialogTitle>
              {editingUser ? "Benutzer bearbeiten" : "Neuer Benutzer"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Max Mustermann"
                className="bg-background"
                required
                data-testid="user-name-input"
              />
            </div>
            
            {!editingUser && (
              <>
                <div className="space-y-2">
                  <Label>E-Mail</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="name@firma.de"
                    className="bg-background"
                    required
                    data-testid="user-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Passwort</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Mindestens 6 Zeichen"
                    className="bg-background"
                    required
                    data-testid="user-password-input"
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label>Rolle</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger className="bg-background" data-testid="user-role-select">
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
                <div className="space-y-2">
                  <Label>Upload-Limit (MB)</Label>
                  <Input
                    type="number"
                    value={formData.max_upload_size_mb}
                    onChange={(e) => setFormData({ ...formData, max_upload_size_mb: e.target.value })}
                    className="bg-background"
                    min={1}
                    data-testid="user-limit-input"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-border"
                    data-testid="user-active-checkbox"
                  />
                  <Label htmlFor="is_active">Konto aktiv</Label>
                </div>
              </>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" className="bg-primary hover:bg-primary/90" data-testid="save-user-btn">
                {editingUser ? "Speichern" : "Erstellen"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
