import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, User, Search, Phone, Mail, MapPin, FileText,
  AlertTriangle, Check, ChevronDown, ChevronUp, Eye, Shield, Calendar,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const DOC_TYPES = [
  { key: "personalausweis", label: "Personalausweis", icon: "id" },
  { key: "fuehrerschein", label: "Führerschein", icon: "car" },
  { key: "fahrerkarte", label: "Fahrerkarte", icon: "card" },
  { key: "erste_hilfe", label: "Erste Hilfe", icon: "first-aid" },
  { key: "sicherheitsunterweisung", label: "Sicherheitsunterweisung", icon: "safety" },
  { key: "staplerschein", label: "Staplerschein", icon: "forklift" },
  { key: "hubarbeitsbuehne", label: "Hubarbeitsbühne", icon: "lift" },
  { key: "teleskoplader", label: "Teleskoplader", icon: "tele" },
  { key: "baumaschine", label: "Baumaschine", icon: "machine" },
  { key: "adr_karte", label: "ADR-Karte", icon: "adr" },
  { key: "kranschein", label: "Kranschein", icon: "crane" },
];

export default function EmployeeAdminPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [employees, setEmployees] = useState([]);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [employeeDocs, setEmployeeDocs] = useState({});
  const [employeeProfiles, setEmployeeProfiles] = useState({});

  const loadEmployees = useCallback(async () => {
    try {
      const res = await api.get(`/employee/all?token=${token}`);
      setEmployees(res.data);
    } catch (err) { toast.error("Fehler beim Laden"); }
  }, [token]);

  useEffect(() => { loadEmployees(); }, [loadEmployees]);

  const loadEmployeeDetail = async (uid) => {
    if (employeeDocs[uid]) return;
    try {
      const [profileRes, docsRes] = await Promise.all([
        api.get(`/employee/profile/${uid}?token=${token}`),
        api.get(`/employee/documents?token=${token}&user_id=${uid}`),
      ]);
      setEmployeeProfiles(prev => ({ ...prev, [uid]: profileRes.data }));
      setEmployeeDocs(prev => ({ ...prev, [uid]: docsRes.data }));
    } catch {}
  };

  const toggleExpand = (uid) => {
    if (expandedId === uid) {
      setExpandedId(null);
    } else {
      setExpandedId(uid);
      loadEmployeeDetail(uid);
    }
  };

  const filtered = employees.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.email.toLowerCase().includes(search.toLowerCase())
  );

  if (!isAdmin) {
    navigate("/hub");
    return null;
  }

  const getAvatarUrl = (e) => e.avatar_path ? `${API}/api/employee/avatar/${e.user_id}?token=${token}&_=${e.avatar_path}` : null;

  const isExpired = (d) => d && new Date(d) < new Date();
  const isExpiringSoon = (d) => {
    if (!d) return false;
    const diff = (new Date(d) - new Date()) / (1000 * 60 * 60 * 24);
    return diff > 0 && diff <= 60;
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="employee-admin-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Shield className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Mitarbeiterverwaltung</h1>
          <span className="text-xs text-gray-400 ml-auto">{employees.length} Mitarbeiter</span>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-4">
        {/* Search */}
        <div className="relative mb-4">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Mitarbeiter suchen..."
            className="pl-10"
            data-testid="employee-search"
          />
        </div>

        {/* Employee List */}
        <div className="space-y-2">
          {filtered.map(e => {
            const isOpen = expandedId === e.user_id;
            const avatar = getAvatarUrl(e);
            const profile = employeeProfiles[e.user_id];
            const docs = employeeDocs[e.user_id] || [];

            return (
              <div key={e.user_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`employee-card-${e.user_id}`}>
                {/* Summary Row */}
                <button onClick={() => toggleExpand(e.user_id)} className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                    {avatar ? <img src={avatar} alt="" className="w-full h-full object-cover" /> : <User className="w-5 h-5 text-gray-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 truncate">{e.name}</p>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${e.role === "admin" ? "bg-fuchsia-100 text-fuchsia-700" : "bg-gray-100 text-gray-600"}`}>{e.role}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-[11px] text-gray-500">
                      <span>{e.email}</span>
                      {e.city && <span className="flex items-center gap-0.5"><MapPin className="w-2.5 h-2.5" />{e.city}</span>}
                    </div>
                  </div>
                  {/* Doc status badges */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {e.expired_count > 0 && (
                      <span className="flex items-center gap-0.5 text-[10px] text-red-600 bg-red-50 px-1.5 py-0.5 rounded-full font-medium" data-testid={`expired-badge-${e.user_id}`}>
                        <AlertTriangle className="w-2.5 h-2.5" />{e.expired_count} abgelaufen
                      </span>
                    )}
                    {e.expiring_soon_count > 0 && (
                      <span className="flex items-center gap-0.5 text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full font-medium">
                        <AlertTriangle className="w-2.5 h-2.5" />{e.expiring_soon_count} bald
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">{e.doc_count}/9</span>
                    {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </div>
                </button>

                {/* Expanded Detail */}
                {isOpen && (
                  <div className="border-t border-gray-100 px-4 py-4">
                    {/* Profile Info */}
                    {profile && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-xs">
                        <div className="flex items-center gap-1.5 text-gray-600">
                          <Phone className="w-3 h-3 text-gray-400" />
                          {profile.phone || <span className="text-gray-300">—</span>}
                        </div>
                        <div className="flex items-center gap-1.5 text-gray-600">
                          <Mail className="w-3 h-3 text-gray-400" />
                          {profile.email}
                        </div>
                        <div className="flex items-center gap-1.5 text-gray-600 col-span-2">
                          <MapPin className="w-3 h-3 text-gray-400" />
                          {profile.street || profile.zip_code || profile.city
                            ? `${profile.street}, ${profile.zip_code} ${profile.city}`.replace(/^, /, "").replace(/, $/, "")
                            : <span className="text-gray-300">Keine Adresse</span>}
                        </div>
                      </div>
                    )}

                    {/* Documents Grid */}
                    <p className="text-[10px] text-gray-400 uppercase font-medium mb-2">Dokumente & Zertifikate</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {DOC_TYPES.map(dt => {
                        const activeDoc = docs.find(d => d.doc_type === dt.key && d.status === "active");
                        const expired = activeDoc && isExpired(activeDoc.expiry_date);
                        const expiring = activeDoc && isExpiringSoon(activeDoc.expiry_date);

                        return (
                          <div
                            key={dt.key}
                            className={`border rounded-lg px-3 py-2 flex items-center gap-2 ${
                              !activeDoc ? "border-gray-200 bg-gray-50 opacity-50" :
                              expired ? "border-red-300 bg-red-50" :
                              expiring ? "border-amber-300 bg-amber-50" :
                              "border-green-200 bg-green-50"
                            }`}
                            data-testid={`admin-doc-${e.user_id}-${dt.key}`}
                          >
                            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              !activeDoc ? "bg-gray-300" : expired ? "bg-red-500" : expiring ? "bg-amber-400" : "bg-green-500"
                            }`} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-800 truncate">{dt.label}</p>
                              {activeDoc ? (
                                <p className={`text-[10px] ${expired ? "text-red-600" : expiring ? "text-amber-600" : "text-green-600"}`}>
                                  {activeDoc.expiry_date || "Kein Ablauf"}
                                </p>
                              ) : (
                                <p className="text-[10px] text-gray-400">Fehlt</p>
                              )}
                            </div>
                            {activeDoc && (
                              <a
                                href={`${API}/api/employee/documents/${activeDoc.id}/file?token=${token}`}
                                target="_blank" rel="noreferrer"
                                className="text-fuchsia-600 hover:text-fuchsia-700 flex-shrink-0"
                                title="Anzeigen"
                                data-testid={`view-doc-${activeDoc.id}`}
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </a>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
