import { useState, useEffect, Fragment } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Logo } from "../components/Logo";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import SchaustellerEditModal from "../components/admin/SchaustellerEditModal";
import PasswordResetModal from "../components/admin/PasswordResetModal";
import UserEditModal from "../components/admin/UserEditModal";
import AdminManualExpiryDialog from "../components/admin/AdminManualExpiryDialog";
import api, { getErrorMsg } from "../lib/api";
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
  Search,
  Activity,
  Mail,
  Tent,
  ChevronDown,
  Clock,
  Globe,
  Phone,
  MapPin,
  Check,
  Camera,
} from "lucide-react";
import axios from "axios";

const ROLE_LABELS = {
  admin: "Administrator",
  mitarbeiter: "Mitarbeiter",
  freelancer: "Freelancer",
  kunde: "Kunde"
};

const ROLE_COLORS = {
  admin: "bg-fuchsia-100 text-fuchsia-800",
  mitarbeiter: "bg-blue-100 text-blue-700",
  freelancer: "bg-amber-100 text-amber-800",
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
  const [schaustellerNewPassword, setSchaustellerNewPassword] = useState("");
  // Freelancer-Auftragszuweisung
  const [freelancerOrderPks, setFreelancerOrderPks] = useState([]);
  const [freelancerAssignedOrders, setFreelancerAssignedOrders] = useState([]);
  const [freelancerSearchQ, setFreelancerSearchQ] = useState("");
  const [freelancerSearchResults, setFreelancerSearchResults] = useState([]);
  const [freelancerSearchLoading, setFreelancerSearchLoading] = useState(false);

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
      },
      finance: { enabled: false },
      dokumentenverwaltung: { enabled: false },
      modules: {
        orders: true,
        einsatzplanung: true,
        kirmes: true,
        verwaltung: true,
        power_monitoring: true,
        energy_monitoring: true,
        devices: true,
        fileshare: true,
        serviceplan: true,
        adr: false,
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

  // User activity dropdown
  const [expandedUserId, setExpandedUserId] = useState(null);
  const [userActivity, setUserActivity] = useState({});
  const [employeeProfiles, setEmployeeProfiles] = useState({});
  const [employeeDocs, setEmployeeDocs] = useState({});
  const [employeeTimeEntries, setEmployeeTimeEntries] = useState({});

  const API = process.env.REACT_APP_BACKEND_URL;
  const token = localStorage.getItem("token");

  const DOC_TYPES = [
    { key: "personalausweis", label: "Personalausweis" },
    { key: "fuehrerschein", label: "Führerschein" },
    { key: "fahrerkarte", label: "Fahrerkarte" },
    { key: "erste_hilfe", label: "Erste Hilfe" },
    { key: "sicherheitsunterweisung", label: "Sicherheitsunterweisung" },
    { key: "staplerschein", label: "Staplerschein" },
    { key: "hubarbeitsbuehne", label: "Hubarbeitsbühne" },
    { key: "teleskoplader", label: "Teleskoplader" },
    { key: "baumaschine", label: "Baumaschine" },
    { key: "adr_karte", label: "ADR-Karte" },
    { key: "kranschein", label: "Kranschein" },
  ];

  const isDocExpired = (d) => d && new Date(d) < new Date();
  const isDocExpiringSoon = (d) => {
    if (!d) return false;
    const diff = (new Date(d) - new Date()) / (1000 * 60 * 60 * 24);
    return diff > 0 && diff <= 60;
  };

  const [uploadingAdminDoc, setUploadingAdminDoc] = useState(null);
  const [adminExpiryPrompt, setAdminExpiryPrompt] = useState(null);
  const [adminManualExpiry, setAdminManualExpiry] = useState("");

  const handleAdminDocUpload = async (userId, docType, file) => {
    if (!file) return;
    setUploadingAdminDoc(`${userId}-${docType}`);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("user_id", userId);
      fd.append("file", file);
      const res = await api.post(`/employee/documents?token=${token}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokument hochgeladen — KI prüft Ablaufdatum...");
      // Wait for AI result
      await new Promise(r => setTimeout(r, 5000));
      const docsRes = await api.get(`/employee/documents?token=${token}&user_id=${userId}`);
      setEmployeeDocs(prev => ({ ...prev, [userId]: docsRes.data }));
      // Check if AI found a date
      const newDoc = docsRes.data.find(d => d.id === res.data.id);
      if (newDoc && !newDoc.expiry_date) {
        setAdminExpiryPrompt({ ...newDoc, _userId: userId });
        setAdminManualExpiry("");
      }
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler beim Hochladen"); }
    setUploadingAdminDoc(null);
  };

  const saveAdminExpiry = async () => {
    if (!adminExpiryPrompt || !adminManualExpiry) { setAdminExpiryPrompt(null); return; }
    try {
      await api.put(`/employee/documents/${adminExpiryPrompt.id}?token=${token}`, { expiry_date: adminManualExpiry });
      const uid = adminExpiryPrompt._userId;
      const docsRes = await api.get(`/employee/documents?token=${token}&user_id=${uid}`);
      setEmployeeDocs(prev => ({ ...prev, [uid]: docsRes.data }));
      toast.success("Ablaufdatum gespeichert");
    } catch { toast.error("Fehler"); }
    setAdminExpiryPrompt(null);
  };

  const toggleUserActivity = async (userId) => {
    if (expandedUserId === userId) {
      setExpandedUserId(null);
      return;
    }
    setExpandedUserId(userId);
    // Load activity
    if (!userActivity[userId]) {
      try {
        const res = await api.get(`/admin/user-activity/${userId}`);
        setUserActivity(prev => ({ ...prev, [userId]: res.data }));
      } catch {
        setUserActivity(prev => ({ ...prev, [userId]: { logins: [], password_changed_at: null } }));
      }
    }
    // Load employee profile & docs (for mitarbeiter/admin)
    if (!employeeProfiles[userId]) {
      try {
        const [profRes, docsRes] = await Promise.all([
          api.get(`/employee/profile/${userId}?token=${token}`),
          api.get(`/employee/documents?token=${token}&user_id=${userId}`),
        ]);
        setEmployeeProfiles(prev => ({ ...prev, [userId]: profRes.data }));
        setEmployeeDocs(prev => ({ ...prev, [userId]: docsRes.data }));
      } catch {
        setEmployeeProfiles(prev => ({ ...prev, [userId]: {} }));
        setEmployeeDocs(prev => ({ ...prev, [userId]: [] }));
      }
    }
    // Load time entries (current month only)
    if (!employeeTimeEntries[userId]) {
      try {
        const now = new Date();
        const y = now.getFullYear();
        const m = String(now.getMonth() + 1).padStart(2, "0");
        const from = `${y}-${m}-01`;
        const lastDay = new Date(y, now.getMonth() + 1, 0).getDate();
        const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
        const res = await api.get(`/employee/time/entries?token=${token}&user_id=${userId}&date_from=${from}&date_to=${to}`);
        setEmployeeTimeEntries(prev => ({ ...prev, [userId]: res.data || [] }));
      } catch {
        setEmployeeTimeEntries(prev => ({ ...prev, [userId]: [] }));
      }
    }
  };

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
      // Geister-Messkoffer ausblenden: nur Geraete mit last_seen (= jemals verbunden)
      setAllMesskoffer(
        devicesRes.data.filter(d => d.device_type === "messkoffer" && d.last_seen)
      );
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
    loadSchausteller();
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

  // Freelancer-Auftrags-Suche (debounced)
  useEffect(() => {
    if (!modalOpen || formData.role !== "freelancer") return;
    const handler = setTimeout(async () => {
      setFreelancerSearchLoading(true);
      try {
        const r = await api.get("/orders/freelancer-search", {
          params: { q: freelancerSearchQ, limit: 50 }
        });
        setFreelancerSearchResults(r.data || []);
      } catch {
        setFreelancerSearchResults([]);
      } finally {
        setFreelancerSearchLoading(false);
      }
    }, 300);
    return () => clearTimeout(handler);
  }, [freelancerSearchQ, modalOpen, formData.role]);

  const openEditSchausteller = (sch) => {
    setEditingSchausteller(sch);
    setSchaustellerForm({
      firma: sch.firma || "", name: sch.name || "", strasse: sch.strasse || "",
      plz: sch.plz || "", ort: sch.ort || "", steuernummer: sch.steuernummer || "",
      email: sch.email || "", telefon: sch.telefon || "", rechnungs_email: sch.rechnungs_email || "",
      kauf_auf_rechnung: sch.kauf_auf_rechnung || false,
    });
    setSchaustellerNewPassword("");
    setSchaustellerModalOpen(true);
  };

  const handleDeleteSchausteller = async (sch) => {
    if (!window.confirm(`"${sch.firma}" wirklich löschen? Alle zugehörigen Anmeldungen werden ebenfalls gelöscht.`)) return;
    try {
      await api.delete(`/kirmes/schausteller/${sch.id}`);
      toast.success("Schausteller gelöscht");
      loadSchausteller();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Löschen"));
    }
  };

  const handleSaveSchausteller = async () => {
    try {
      await api.put(`/kirmes/schausteller/${editingSchausteller.id}`, schaustellerForm);
      toast.success("Schausteller aktualisiert");
      setSchaustellerModalOpen(false);
      loadSchausteller();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Speichern"));
    }
  };

  const handleSetSchaustellerPassword = async () => {
    if (!schaustellerNewPassword || schaustellerNewPassword.length < 6) {
      toast.error("Passwort muss mindestens 6 Zeichen haben");
      return;
    }
    try {
      await api.post(`/kirmes/schausteller/${editingSchausteller.id}/set-password`, {
        password: schaustellerNewPassword,
      });
      toast.success("Passwort wurde gesetzt");
      setSchaustellerNewPassword("");
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Setzen des Passworts"));
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
    setFreelancerOrderPks([]);
    setFreelancerAssignedOrders([]);
    setFreelancerSearchQ("");
    setFreelancerSearchResults([]);
    if (user.role === "freelancer") {
      api.get(`/orders/freelancer-assignments/${user.id}`)
        .then(r => {
          setFreelancerOrderPks(r.data?.order_pks || []);
          setFreelancerAssignedOrders(r.data?.orders || []);
        })
        .catch(() => { setFreelancerOrderPks([]); setFreelancerAssignedOrders([]); });
      api.get("/orders/freelancer-search", { params: { q: "", limit: 50 } })
        .then(r => setFreelancerSearchResults(r.data || []))
        .catch(() => setFreelancerSearchResults([]));
    }
    setFormData({
      name: user.name,
      email: user.email,
      password: "",
      role: user.role,
      is_active: user.is_active,
      access_type: user.access_type || "permanent",
      access_start: user.access_start || "",
      access_end: user.access_end || "",
      permissions: user.permissions || {},
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
        },
        finance: user.apps?.finance || { enabled: false },
        dokumentenverwaltung: user.apps?.dokumentenverwaltung || { enabled: false },
        modules: {
          orders: user.apps?.modules?.orders !== false,
          einsatzplanung: user.apps?.modules?.einsatzplanung !== false,
          kirmes: user.apps?.modules?.kirmes !== false,
          verwaltung: user.apps?.modules?.verwaltung !== false,
          power_monitoring: user.apps?.modules?.power_monitoring !== false,
          energy_monitoring: user.apps?.modules?.energy_monitoring !== false,
          devices: user.apps?.modules?.devices !== false,
          fileshare: user.apps?.modules?.fileshare !== false,
          serviceplan: user.apps?.modules?.serviceplan !== false,
          adr: !!user.apps?.modules?.adr,
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
          apps: formData.apps,
          permissions: formData.permissions || {}
        });
        // Freelancer: Auftrags-Zuweisungen separat speichern
        if (formData.role === "freelancer") {
          await api.put(`/orders/freelancer-assignments/${editingUser.id}`, {
            order_pks: freelancerOrderPks
          });
        }
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
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="admin-page"
      onDragOver={e => e.preventDefault()}
      onDrop={e => e.preventDefault()}
    >
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
              onClick={() => navigate("/admin/asset-move-audit")}
              className="text-xs hidden sm:inline-flex"
              data-testid="open-asset-move-audit"
            >
              Verschoben-Audit
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
                    <span className="ml-1 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">{users.filter(u => u.role === "mitarbeiter" || u.role === "freelancer").length}</span>
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
                          <th className="px-4 py-3 text-left w-24">Kd-Nr.</th>
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
                            <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                              {schaustellerSearch ? "Keine Schausteller gefunden" : "Noch keine Schausteller registriert"}
                            </td>
                          </tr>
                        ) : (
                          schausteller.map(sch => (
                            <tr key={sch.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/admin/schausteller/${sch.id}`)} data-testid={`sch-row-${sch.id}`}>
                              <td className="px-4 py-3">
                                <span className="font-mono text-xs font-semibold text-fuchsia-600 bg-fuchsia-50 px-2 py-0.5 rounded" data-testid={`sch-knr-${sch.id}`}>{sch.kundennummer || "–"}</span>
                              </td>
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
                              <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
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
                        <th className="px-4 py-3 text-left hidden sm:table-cell">Status</th>
                        <th className="px-4 py-3 text-right">Aktionen</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {loading ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-gray-500">Laden...</td>
                        </tr>
                      ) : (() => {
                        const filtered = users.filter(u => {
                          // Role filter
                          if (userRoleFilter === "kunden" && u.role !== "kunde") return false;
                          if (userRoleFilter === "mitarbeiter" && u.role !== "mitarbeiter" && u.role !== "admin" && u.role !== "freelancer") return false;
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
                              <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                                {userSearch ? "Keine Benutzer gefunden" : "Keine Benutzer in dieser Kategorie"}
                              </td>
                            </tr>
                          );
                        }
                        return filtered.map((user) => (
                          <Fragment key={user.id}>
                          <tr className="hover:bg-gray-50 cursor-pointer" data-testid={`user-row-${user.id}`} onClick={() => toggleUserActivity(user.id)}>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                                  {user.role === "admin" ? (
                                    <Shield className="w-4 h-4 text-fuchsia-600" />
                                  ) : user.role === "mitarbeiter" ? (
                                    <UserCheck className="w-4 h-4 text-blue-500" />
                                  ) : user.role === "freelancer" ? (
                                    <UserCheck className="w-4 h-4 text-amber-600" />
                                  ) : (
                                    <User className="w-4 h-4 text-gray-500" />
                                  )}
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <span className="font-medium text-gray-900">{user.name}</span>
                                  <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${expandedUserId === user.id ? "rotate-180" : ""}`} />
                                </div>
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
                            <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
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
                          {expandedUserId === user.id && (
                            <tr data-testid={`user-activity-${user.id}`}>
                              <td colSpan={5} className="px-4 py-0">
                                <div className="py-3 pl-11 space-y-4">
                                  {/* Employee Profile Section */}
                                  {(user.role === "mitarbeiter" || user.role === "admin") && (() => {
                                    const prof = employeeProfiles[user.id];
                                    const docs = employeeDocs[user.id] || [];
                                    const avatarUrl = prof?.avatar_path ? `${API}/api/employee/avatar/${user.id}?token=${token}&_=${prof.avatar_path}` : null;
                                    if (!prof) return <span className="text-xs text-gray-400">Profildaten laden...</span>;
                                    return (
                                      <>
                                        {/* Profile Info Bar */}
                                        <div className="flex items-center gap-4 flex-wrap">
                                          <div className="relative group flex-shrink-0">
                                            <div className="w-14 h-14 rounded-full overflow-hidden bg-gray-100 border-2 border-gray-200 flex items-center justify-center">
                                              {avatarUrl ? (
                                                <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                                              ) : (
                                                <User className="w-6 h-6 text-gray-300" />
                                              )}
                                            </div>
                                            <label className="absolute inset-0 rounded-full bg-black/0 group-hover:bg-black/40 flex items-center justify-center cursor-pointer transition-colors">
                                              <input type="file" accept="image/*" className="hidden" onChange={async (ev) => {
                                                const file = ev.target.files[0];
                                                if (!file) return;
                                                const form = new FormData();
                                                form.append("file", file);
                                                try {
                                                  await axios.post(`${API}/api/employee/avatar/${user.id}/upload?token=${token}`, form, { headers: { "Content-Type": "multipart/form-data" } });
                                                  // Refresh profile cache
                                                  const profRes = await api.get(`/employee/profile/${user.id}?token=${token}`);
                                                  setEmployeeProfiles(prev => ({ ...prev, [user.id]: profRes.data }));
                                                  toast.success("Benutzerbild aktualisiert");
                                                } catch { toast.error("Upload fehlgeschlagen"); }
                                                ev.target.value = "";
                                              }} data-testid={`avatar-upload-${user.id}`} />
                                              <Camera className="w-4 h-4 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                                            </label>
                                          </div>
                                          <div className="flex flex-wrap items-center gap-3">
                                          {prof.phone && (
                                            <span className="text-xs text-gray-600 flex items-center gap-1"><Phone className="w-3 h-3 text-gray-400" />{prof.phone}</span>
                                          )}
                                          {(prof.street || prof.city) && (
                                            <span className="text-xs text-gray-600 flex items-center gap-1"><MapPin className="w-3 h-3 text-gray-400" />{[prof.street, `${prof.zip_code} ${prof.city}`].filter(Boolean).join(", ")}</span>
                                          )}
                                          {prof.email && (
                                            <span className="text-xs text-gray-600 flex items-center gap-1"><Mail className="w-3 h-3 text-gray-400" />{prof.email}</span>
                                          )}
                                          </div>
                                        </div>

                                        {/* Documents removed - now in AdminZeitDetailPage */}
                                      </>
                                    );
                                  })()}

                                  {/* Login Activity */}
                                  {(() => {
                                    const act = userActivity[user.id];
                                    if (!act) return <span className="text-xs text-gray-400">Laden...</span>;
                                    return (
                                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                          <div className="flex items-center gap-2 mb-2">
                                            <KeyRound className="w-3.5 h-3.5 text-fuchsia-500" />
                                            <span className="text-xs font-semibold text-gray-700">Passwort</span>
                                          </div>
                                          <div className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
                                            {act.password_changed_at
                                              ? <>Zuletzt geaendert: <span className="font-medium text-gray-900">{new Date(act.password_changed_at).toLocaleString("de-DE")}</span></>
                                              : <span className="text-gray-400">Noch nie geaendert (seit Erstellung: {act.created_at ? new Date(act.created_at).toLocaleDateString("de-DE") : "unbekannt"})</span>
                                            }
                                          </div>
                                        </div>
                                        <div>
                                          <div className="flex items-center gap-2 mb-2">
                                            <Clock className="w-3.5 h-3.5 text-fuchsia-500" />
                                            <span className="text-xs font-semibold text-gray-700">Letzte Logins ({act.logins?.length || 0})</span>
                                          </div>
                                          {act.logins && act.logins.length > 0 ? (
                                            <div className="bg-gray-50 rounded-lg divide-y divide-gray-100 max-h-[200px] overflow-y-auto">
                                              {act.logins.map((l, i) => (
                                                <div key={i} className="px-3 py-1.5 flex items-center justify-between">
                                                  <span className="text-xs text-gray-700 font-medium">
                                                    {new Date(l.timestamp).toLocaleString("de-DE")}
                                                  </span>
                                                  {l.ip && (
                                                    <span className="text-[10px] text-gray-400 flex items-center gap-1 font-mono">
                                                      <Globe className="w-2.5 h-2.5" />{l.ip}
                                                    </span>
                                                  )}
                                                </div>
                                              ))}
                                            </div>
                                          ) : (
                                            <div className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2">
                                              Keine Login-Eintraege vorhanden
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })()}
                                </div>
                              </td>
                            </tr>
                          )}
                          </Fragment>
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
      <UserEditModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        editingUser={editingUser}
        formData={formData}
        setFormData={setFormData}
        onSubmit={handleSubmit}
        updateFilesharingApp={updateFilesharingApp}
        updateGeneratorMonitoringApp={updateGeneratorMonitoringApp}
        updateEnergyMonitoringApp={updateEnergyMonitoringApp}
        toggleGeneratorId={toggleGeneratorId}
        toggleEnergyDeviceId={toggleEnergyDeviceId}
        allGenerators={allGenerators}
        allMesskoffer={allMesskoffer}
        freelancerOrderPks={freelancerOrderPks}
        setFreelancerOrderPks={setFreelancerOrderPks}
        freelancerAssignedOrders={freelancerAssignedOrders}
        setFreelancerAssignedOrders={setFreelancerAssignedOrders}
        freelancerSearchQ={freelancerSearchQ}
        setFreelancerSearchQ={setFreelancerSearchQ}
        freelancerSearchResults={freelancerSearchResults}
        freelancerSearchLoading={freelancerSearchLoading}
      />

      {/* Password Management Modal */}
      <PasswordResetModal
        open={passwordModalOpen}
        onOpenChange={setPasswordModalOpen}
        target={passwordTarget}
        newPassword={newPassword}
        setNewPassword={setNewPassword}
        resetLink={resetLink}
        onSetPassword={handleSetPassword}
        onGenerateResetLink={handleGenerateResetLink}
        onSendResetEmail={handleSendResetEmail}
        onCopyLink={copyToClipboard}
      />

      {/* Schausteller Edit Modal */}
      <SchaustellerEditModal
        open={schaustellerModalOpen}
        onOpenChange={setSchaustellerModalOpen}
        form={schaustellerForm}
        setForm={setSchaustellerForm}
        newPassword={schaustellerNewPassword}
        setNewPassword={setSchaustellerNewPassword}
        onSetPassword={handleSetSchaustellerPassword}
        onSave={handleSaveSchausteller}
      />

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        title={confirmData.title}
        description={confirmData.description}
        onConfirm={confirmData.onConfirm}
        onCancel={() => setConfirmOpen(false)}
      />

      {/* Admin Manual Expiry Dialog */}
      <AdminManualExpiryDialog
        open={!!adminExpiryPrompt}
        onClose={() => setAdminExpiryPrompt(null)}
        value={adminManualExpiry}
        onChange={setAdminManualExpiry}
        onSave={saveAdminExpiry}
      />
    </div>
  );
}
