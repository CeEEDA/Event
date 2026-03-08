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
  Search,
  Activity,
  Mail,
  Radio,
  Zap,
  CalendarDays,
  Settings,
  Tent,
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
  const { user: currentUser, isAdmin } = useAuth();
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
  const [allGenerators, setAllGenerators] = useState([]);
  const [allMesskoffer, setAllMesskoffer] = useState([]);
  const [schausteller, setSchausteller] = useState([]);
  const [schaustellerSearch, setSchaustellerSearch] = useState("");
  const [editingSchausteller, setEditingSchausteller] = useState(null);
  const [schaustellerModalOpen, setSchaustellerModalOpen] = useState(false);
  const [schaustellerForm, setSchaustellerForm] = useState({
    firma: "", name: "", strasse: "", plz: "", ort: "",
    steuernummer: "", email: "", telefon: "", rechnungs_email: "",
  });
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    role: "kunde",
    is_active: true,
    access_type: "permanent",
    access_start: "",
    access_end: "",
    apps: {
      filesharing: {
        enabled: false,
        max_upload_size_mb: 100,
        can_write: false,
        can_delete: false
      },
      generator_monitoring: {
        enabled: false,
        access_all: false,
        generator_ids: []
      },
      energy_monitoring: {
        enabled: false,
        access_all: false,
        device_ids: []
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
      const [usersRes, statsRes, gensRes, devicesRes] = await Promise.all([
        api.get("/users"),
        api.get("/stats"),
        api.get("/generators").catch(() => ({ data: [] })),
        api.get("/devices").catch(() => ({ data: [] })),
      ]);
      setUsers(usersRes.data);
      setStats(statsRes.data);
      setAllGenerators(gensRes.data);
      setAllMesskoffer(devicesRes.data.filter(d => d.device_type === "messkoffer"));
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

  const loadSchausteller = async () => {
    try {
      const res = await api.get("/kirmes/schausteller", { params: schaustellerSearch ? { search: schaustellerSearch } : {} });
      setSchausteller(res.data);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (userRoleFilter === "schausteller") loadSchausteller();
  }, [userRoleFilter, schaustellerSearch]);

  const openEditSchausteller = (sch) => {
    setEditingSchausteller(sch);
    setSchaustellerForm({
      firma: sch.firma || "", name: sch.name || "", strasse: sch.strasse || "",
      plz: sch.plz || "", ort: sch.ort || "", steuernummer: sch.steuernummer || "",
      email: sch.email || "", telefon: sch.telefon || "", rechnungs_email: sch.rechnungs_email || "",
    });
    setSchaustellerModalOpen(true);
  };

  const handleDeleteSchausteller = async (sch) => {
    if (!window.confirm(`"${sch.firma}" wirklich löschen? Alle zugehörigen Anmeldungen werden ebenfalls gelöscht.`)) return;
    try {
      await api.delete(`/kirmes/schausteller/${sch.id}`);
      toast.success("Schausteller gelöscht");
      loadSchausteller();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler beim Löschen");
    }
  };

  const handleSaveSchausteller = async () => {
    try {
      await api.put(`/kirmes/schausteller/${editingSchausteller.id}`, schaustellerForm);
      toast.success("Schausteller aktualisiert");
      setSchaustellerModalOpen(false);
      loadSchausteller();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler beim Speichern");
    }
  };

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
        },
        generator_monitoring: {
          enabled: false,
          access_all: false,
          generator_ids: []
        },
        energy_monitoring: {
          enabled: false,
          access_all: false,
          device_ids: [],
          access_type: "permanent",
          access_start: "",
          access_end: ""
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
      access_type: user.access_type || "permanent",
      access_start: user.access_start || "",
      access_end: user.access_end || "",
      apps: {
        filesharing: user.apps?.filesharing || {
          enabled: false,
          max_upload_size_mb: 100,
          can_write: false,
          can_delete: false
        },
        generator_monitoring: user.apps?.generator_monitoring || {
          enabled: false,
          access_all: false,
          generator_ids: []
        },
        energy_monitoring: {
          enabled: user.apps?.energy_monitoring?.enabled || false,
          access_all: user.apps?.energy_monitoring?.access_all || false,
          device_ids: user.apps?.energy_monitoring?.device_ids || []
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
          access_type: formData.access_type,
          access_start: formData.access_start || null,
          access_end: formData.access_end || null,
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

  const handleSendResetEmail = async () => {
    try {
      await api.post(`/admin/send-reset-email/${passwordTarget.id}`, {
        frontend_url: window.location.origin,
      });
      toast.success("Reset-Link per E-Mail gesendet");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Fehler beim Senden der E-Mail");
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

  const updateGeneratorMonitoringApp = (field, value) => {
    setFormData(prev => {
      const updated = {
        ...prev.apps.generator_monitoring,
        [field]: value
      };
      // When toggling access_all ON, clear individual generator_ids
      if (field === "access_all" && value === true) {
        updated.generator_ids = [];
      }
      return {
        ...prev,
        apps: {
          ...prev.apps,
          generator_monitoring: updated
        }
      };
    });
  };

  const toggleGeneratorId = (genId) => {
    setFormData(prev => {
      const current = prev.apps.generator_monitoring.generator_ids || [];
      const updated = current.includes(genId)
        ? current.filter(id => id !== genId)
        : [...current, genId];
      return {
        ...prev,
        apps: {
          ...prev.apps,
          generator_monitoring: {
            ...prev.apps.generator_monitoring,
            generator_ids: updated
          }
        }
      };
    });
  };

  const updateEnergyMonitoringApp = (field, value) => {
    setFormData(prev => {
      const updated = {
        ...prev.apps.energy_monitoring,
        [field]: value
      };
      if (field === "access_all" && value === true) {
        updated.device_ids = [];
      }
      return {
        ...prev,
        apps: {
          ...prev.apps,
          energy_monitoring: updated
        }
      };
    });
  };

  const toggleEnergyDeviceId = (deviceId) => {
    setFormData(prev => {
      const current = prev.apps.energy_monitoring.device_ids || [];
      const updated = current.includes(deviceId)
        ? current.filter(id => id !== deviceId)
        : [...current, deviceId];
      return {
        ...prev,
        apps: {
          ...prev.apps,
          energy_monitoring: {
            ...prev.apps.energy_monitoring,
            device_ids: updated
          }
        }
      };
    });
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
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/admin/settings")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="admin-settings-link"
            >
              <Settings className="w-4 h-4 mr-1" />
              Administrative Einstellungen
            </Button>
            <Logo size="small" />
          </div>
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
                  <button
                    onClick={() => { setUserRoleFilter("schausteller"); setSchaustellerSearch(""); }}
                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                      userRoleFilter === "schausteller"
                        ? "bg-fuchsia-50 text-fuchsia-700 border-b-2 border-fuchsia-600"
                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                    }`}
                    data-testid="filter-schausteller"
                  >
                    <Tent className="w-4 h-4" />
                    Schausteller
                    <span className="ml-1 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">{schausteller.length}</span>
                  </button>
                </div>
                
                <div className="flex items-center gap-2 flex-1">
                  {userRoleFilter !== "schausteller" ? (
                    <>
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
                    </>
                  ) : (
                    <div className="relative flex-1 max-w-xs">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        placeholder="Schausteller suchen..."
                        value={schaustellerSearch}
                        onChange={(e) => setSchaustellerSearch(e.target.value)}
                        className="pl-8 h-9 border-gray-300 text-sm"
                        data-testid="schausteller-search-input"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Schausteller Table */}
              {userRoleFilter === "schausteller" ? (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full" data-testid="schausteller-table">
                      <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                        <tr>
                          <th className="px-4 py-3 text-left">Firma</th>
                          <th className="px-4 py-3 text-left">Name</th>
                          <th className="px-4 py-3 text-left hidden md:table-cell">E-Mail</th>
                          <th className="px-4 py-3 text-left hidden sm:table-cell">Telefon</th>
                          <th className="px-4 py-3 text-left hidden lg:table-cell">Ort</th>
                          <th className="px-4 py-3 text-left hidden lg:table-cell">Steuernr.</th>
                          <th className="px-4 py-3 text-right">Aktionen</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {schausteller.length === 0 ? (
                          <tr>
                            <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                              {schaustellerSearch ? "Keine Schausteller gefunden" : "Noch keine Schausteller registriert"}
                            </td>
                          </tr>
                        ) : (
                          schausteller.map(sch => (
                            <tr key={sch.id} className="hover:bg-gray-50" data-testid={`sch-row-${sch.id}`}>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center">
                                    <Tent className="w-4 h-4 text-amber-600" />
                                  </div>
                                  <span className="font-medium text-gray-900">{sch.firma}</span>
                                </div>
                              </td>
                              <td className="px-4 py-3 text-gray-600">{sch.name}</td>
                              <td className="px-4 py-3 hidden md:table-cell text-gray-500 text-sm">{sch.email}</td>
                              <td className="px-4 py-3 hidden sm:table-cell text-gray-500 text-sm">{sch.telefon}</td>
                              <td className="px-4 py-3 hidden lg:table-cell text-gray-500 text-sm">{sch.plz} {sch.ort}</td>
                              <td className="px-4 py-3 hidden lg:table-cell text-gray-500 text-sm font-mono">{sch.steuernummer}</td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => openEditSchausteller(sch)}
                                    className="h-8 w-8 text-gray-500 hover:text-fuchsia-600"
                                    data-testid={`edit-sch-${sch.id}`}
                                  >
                                    <Pencil className="w-4 h-4" />
                                  </Button>
                                  {isAdmin && (
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => handleDeleteSchausteller(sch)}
                                      className="h-8 w-8 text-gray-500 hover:text-red-500"
                                      data-testid={`delete-sch-${sch.id}`}
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
              /* Users Table */
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full" data-testid="users-table">
                    <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                      <tr>
                        <th className="px-4 py-3 text-left">Name</th>
                        <th className="px-4 py-3 text-left hidden md:table-cell">E-Mail</th>
                        <th className="px-4 py-3 text-left">Rolle</th>
                        <th className="px-4 py-3 text-left hidden sm:table-cell">FileShare</th>
                        <th className="px-4 py-3 text-left hidden sm:table-cell">Monitoring</th>
                        <th className="px-4 py-3 text-left hidden lg:table-cell">Energy</th>
                        <th className="px-4 py-3 text-left hidden sm:table-cell">Status</th>
                        <th className="px-4 py-3 text-right">Aktionen</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {loading ? (
                        <tr>
                          <td colSpan={8} className="px-4 py-8 text-center text-gray-500">Laden...</td>
                        </tr>
                      ) : (() => {
                        const filtered = users.filter(u => {
                          // Role filter
                          if (userRoleFilter === "kunden" && u.role !== "kunde") return false;
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
                              <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
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
                              {user.role === "admin" || user.apps?.generator_monitoring?.enabled ? (
                                <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-green-500" />
                                  {user.role === "admin" || user.apps?.generator_monitoring?.access_all ? "Alle" : `${(user.apps?.generator_monitoring?.generator_ids || []).length} Geräte`}
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-gray-400 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-gray-300" />
                                  Nicht aktiv
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 hidden lg:table-cell">
                              {user.role === "admin" || user.apps?.energy_monitoring?.enabled ? (
                                <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-green-500" />
                                  {user.role === "admin" || user.apps?.energy_monitoring?.access_all ? "Alle" : `${(user.apps?.energy_monitoring?.device_ids || []).length} Geräte`}
                                  {user.role === "kunde" && user.apps?.energy_monitoring?.access_type === "temporary" && (
                                    <CalendarDays className="w-3 h-3 text-amber-500 ml-0.5" title="Zeitlich begrenzt" />
                                  )}
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
              )}
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

                  {/* Generator Monitoring App */}
                  <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Activity className="w-5 h-5 text-fuchsia-600" />
                        <Label className="text-gray-900 font-medium">Generator-Monitoring</Label>
                      </div>
                      <Switch
                        checked={formData.apps.generator_monitoring.enabled}
                        onCheckedChange={(checked) => updateGeneratorMonitoringApp("enabled", checked)}
                        data-testid="monitoring-enabled-toggle"
                      />
                    </div>

                    {formData.apps.generator_monitoring.enabled && (
                      <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Zugriff auf alle Generatoren</Label>
                          <Switch
                            checked={formData.apps.generator_monitoring.access_all}
                            onCheckedChange={(checked) => updateGeneratorMonitoringApp("access_all", checked)}
                            data-testid="monitoring-access-all-toggle"
                          />
                        </div>

                        {!formData.apps.generator_monitoring.access_all && (
                          <div className="space-y-2">
                            <Label className="text-gray-600 text-sm">Einzelne Generatoren auswählen</Label>
                            <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                              {allGenerators.length === 0 ? (
                                <p className="text-xs text-gray-400 p-3">Keine Generatoren vorhanden</p>
                              ) : (
                                allGenerators.map((gen) => {
                                  const isSelected = (formData.apps.generator_monitoring.generator_ids || []).includes(gen.id);
                                  return (
                                    <label
                                      key={gen.id}
                                      className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? "bg-fuchsia-50" : ""}`}
                                      data-testid={`gen-select-${gen.serial_number}`}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={isSelected}
                                        onChange={() => toggleGeneratorId(gen.id)}
                                        className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                                      />
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm text-gray-900 truncate">{gen.name}</p>
                                        <p className="text-[10px] text-gray-400 font-mono">{gen.serial_number} · {gen.location_name || "–"}</p>
                                      </div>
                                    </label>
                                  );
                                })
                              )}
                            </div>
                            <p className="text-[10px] text-gray-400">
                              {(formData.apps.generator_monitoring.generator_ids || []).length} von {allGenerators.length} ausgewählt
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Energy Monitoring App */}
                  <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Zap className="w-5 h-5 text-fuchsia-600" />
                        <Label className="text-gray-900 font-medium">Energy Monitoring</Label>
                      </div>
                      <Switch
                        checked={formData.apps.energy_monitoring.enabled}
                        onCheckedChange={(checked) => updateEnergyMonitoringApp("enabled", checked)}
                        data-testid="energy-monitoring-enabled-toggle"
                      />
                    </div>

                    {formData.apps.energy_monitoring.enabled && (
                      <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Zugriff auf alle Messkoffer</Label>
                          <Switch
                            checked={formData.apps.energy_monitoring.access_all}
                            onCheckedChange={(checked) => updateEnergyMonitoringApp("access_all", checked)}
                            data-testid="energy-access-all-toggle"
                          />
                        </div>

                        {!formData.apps.energy_monitoring.access_all && (
                          <div className="space-y-2">
                            <Label className="text-gray-600 text-sm">Einzelne Messkoffer auswählen</Label>
                            <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                              {allMesskoffer.length === 0 ? (
                                <p className="text-xs text-gray-400 p-3">Keine Messkoffer vorhanden</p>
                              ) : (
                                allMesskoffer.map((mk) => {
                                  const isSelected = (formData.apps.energy_monitoring.device_ids || []).includes(mk.id);
                                  return (
                                    <label
                                      key={mk.id}
                                      className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? "bg-fuchsia-50" : ""}`}
                                      data-testid={`energy-select-${mk.serial_number}`}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={isSelected}
                                        onChange={() => toggleEnergyDeviceId(mk.id)}
                                        className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                                      />
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm text-gray-900 truncate">{mk.user_field || mk.serial_number}</p>
                                        <p className="text-[10px] text-gray-400 font-mono">{mk.serial_number}</p>
                                      </div>
                                    </label>
                                  );
                                })
                              )}
                            </div>
                            <p className="text-[10px] text-gray-400">
                              {(formData.apps.energy_monitoring.device_ids || []).length} von {allMesskoffer.length} ausgewählt
                            </p>
                          </div>
                        )}

                        {/* Data access range for Kunden */}
                        {formData.role === "kunde" && (
                          <div className="space-y-2 pt-3 border-t border-fuchsia-200">
                            <Label className="text-gray-600 text-sm flex items-center gap-1">
                              <CalendarDays className="w-3.5 h-3.5" />
                              Verfügbare Messdaten (Zeitraum)
                            </Label>
                            <p className="text-[10px] text-gray-400">Begrenzt den Datenzugriff des Kunden auf den angegebenen Zeitraum</p>
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <Label className="text-gray-500 text-xs">Von</Label>
                                <Input
                                  type="date"
                                  value={formData.apps.energy_monitoring.data_access_start?.split("T")[0] || ""}
                                  onChange={(e) => updateEnergyMonitoringApp("data_access_start", e.target.value ? new Date(e.target.value).toISOString() : "")}
                                  className="border-gray-300 text-sm"
                                  data-testid="data-access-start-input"
                                />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-gray-500 text-xs">Bis</Label>
                                <Input
                                  type="date"
                                  value={formData.apps.energy_monitoring.data_access_end?.split("T")[0] || ""}
                                  onChange={(e) => updateEnergyMonitoringApp("data_access_end", e.target.value ? new Date(e.target.value + "T23:59:59Z").toISOString() : "")}
                                  className="border-gray-300 text-sm"
                                  data-testid="data-access-end-input"
                                />
                              </div>
                            </div>
                            <p className="text-[10px] text-gray-400">Leer lassen = keine Einschränkung</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Time-based access for Kunden - Account level */}
                  {formData.role === "kunde" && (
                    <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                      <div className="flex items-center gap-3">
                        <CalendarDays className="w-5 h-5 text-fuchsia-600" />
                        <Label className="text-gray-900 font-medium">Konto-Verfügbarkeit</Label>
                      </div>
                      <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => setFormData(prev => ({ ...prev, access_type: "permanent" }))}
                            className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                              formData.access_type === "permanent"
                                ? "bg-fuchsia-50 border-fuchsia-400 text-fuchsia-700"
                                : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                            }`}
                            data-testid="access-type-permanent"
                          >
                            Dauerhaft
                          </button>
                          <button
                            type="button"
                            onClick={() => setFormData(prev => ({ ...prev, access_type: "temporary" }))}
                            className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                              formData.access_type === "temporary"
                                ? "bg-fuchsia-50 border-fuchsia-400 text-fuchsia-700"
                                : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                            }`}
                            data-testid="access-type-temporary"
                          >
                            Fester Zeitraum
                          </button>
                        </div>

                        {formData.access_type === "temporary" && (
                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Von</Label>
                              <Input
                                type="date"
                                value={formData.access_start?.split("T")[0] || ""}
                                onChange={(e) => setFormData(prev => ({ ...prev, access_start: e.target.value ? new Date(e.target.value).toISOString() : "" }))}
                                className="border-gray-300 text-sm"
                                data-testid="access-start-input"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Bis</Label>
                              <Input
                                type="date"
                                value={formData.access_end?.split("T")[0] || ""}
                                onChange={(e) => setFormData(prev => ({ ...prev, access_end: e.target.value ? new Date(e.target.value + "T23:59:59Z").toISOString() : "" }))}
                                className="border-gray-300 text-sm"
                                data-testid="access-end-input"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
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
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleGenerateResetLink}
                    className="flex-1 border-gray-300"
                    data-testid="admin-generate-reset-link-btn"
                  >
                    <Link2 className="w-4 h-4 mr-2" />
                    Link generieren
                  </Button>
                  <Button
                    onClick={handleSendResetEmail}
                    className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                    data-testid="admin-send-reset-email-btn"
                  >
                    <Mail className="w-4 h-4 mr-2" />
                    Per E-Mail senden
                  </Button>
                </div>

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

      {/* Schausteller Edit Modal */}
      <Dialog open={schaustellerModalOpen} onOpenChange={setSchaustellerModalOpen}>
        <DialogContent className="bg-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="schausteller-modal">
          <DialogHeader>
            <DialogTitle className="text-gray-900 flex items-center gap-2">
              <Tent className="w-5 h-5 text-amber-600" />
              Schausteller bearbeiten
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-gray-700 text-sm">Firma</Label>
                <Input value={schaustellerForm.firma} onChange={e => setSchaustellerForm(f => ({ ...f, firma: e.target.value }))} className="border-gray-300" data-testid="sch-firma-input" />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-700 text-sm">Name</Label>
                <Input value={schaustellerForm.name} onChange={e => setSchaustellerForm(f => ({ ...f, name: e.target.value }))} className="border-gray-300" data-testid="sch-name-input" />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Straße</Label>
              <Input value={schaustellerForm.strasse} onChange={e => setSchaustellerForm(f => ({ ...f, strasse: e.target.value }))} className="border-gray-300" data-testid="sch-strasse-input" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="text-gray-700 text-sm">PLZ</Label>
                <Input value={schaustellerForm.plz} onChange={e => setSchaustellerForm(f => ({ ...f, plz: e.target.value }))} className="border-gray-300" data-testid="sch-plz-input" />
              </div>
              <div className="col-span-2 space-y-1">
                <Label className="text-gray-700 text-sm">Ort</Label>
                <Input value={schaustellerForm.ort} onChange={e => setSchaustellerForm(f => ({ ...f, ort: e.target.value }))} className="border-gray-300" data-testid="sch-ort-input" />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Steuernummer</Label>
              <Input value={schaustellerForm.steuernummer} onChange={e => setSchaustellerForm(f => ({ ...f, steuernummer: e.target.value }))} className="border-gray-300" data-testid="sch-steuernummer-input" />
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">E-Mail</Label>
              <Input type="email" value={schaustellerForm.email} onChange={e => setSchaustellerForm(f => ({ ...f, email: e.target.value }))} className="border-gray-300" data-testid="sch-email-input" />
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Telefon</Label>
              <Input value={schaustellerForm.telefon} onChange={e => setSchaustellerForm(f => ({ ...f, telefon: e.target.value }))} className="border-gray-300" data-testid="sch-telefon-input" />
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Rechnungs-E-Mail</Label>
              <Input type="email" value={schaustellerForm.rechnungs_email} onChange={e => setSchaustellerForm(f => ({ ...f, rechnungs_email: e.target.value }))} className="border-gray-300" data-testid="sch-rechnungs-email-input" />
              <p className="text-[10px] text-gray-400">Rechnungen werden an diese Adresse versendet</p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSchaustellerModalOpen(false)}>Abbrechen</Button>
            <Button onClick={handleSaveSchausteller} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-schausteller-btn">Speichern</Button>
          </DialogFooter>
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
