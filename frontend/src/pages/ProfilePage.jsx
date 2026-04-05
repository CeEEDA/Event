import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, Camera, User, Phone, Mail, MapPin, Lock, Save,
  FileText, Upload, Calendar, AlertTriangle, Check, Eye, ChevronDown, ChevronUp,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL;

const DOC_TYPES = [
  { key: "personalausweis", label: "Personalausweis", icon: "🪪" },
  { key: "fuehrerschein", label: "Führerschein", icon: "🚗" },
  { key: "fahrerkarte", label: "Fahrerkarte", icon: "💳" },
  { key: "erste_hilfe", label: "Erste Hilfe", icon: "🏥" },
  { key: "sicherheitsunterweisung", label: "Sicherheitsunterweisung", icon: "⚠️" },
  { key: "staplerschein", label: "Staplerschein", icon: "🏗️" },
  { key: "hubarbeitsbuehne", label: "Hubarbeitsbühne", icon: "🔧" },
  { key: "teleskoplader", label: "Teleskoplader", icon: "🚜" },
  { key: "baumaschine", label: "Baumaschine", icon: "🚧" },
];

const DOCUMENT_LABELS = {};
DOC_TYPES.forEach(d => { DOCUMENT_LABELS[d.key] = d.label; });

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const avatarRef = useRef(null);

  const [profile, setProfile] = useState({ name: "", email: "", phone: "", street: "", zip_code: "", city: "", avatar_path: null });
  const [saving, setSaving] = useState(false);
  const [pwForm, setPwForm] = useState({ old_password: "", new_password: "", confirm: "" });
  const [showPw, setShowPw] = useState(false);

  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(null);
  const [expandedType, setExpandedType] = useState(null);
  const [expiryPrompt, setExpiryPrompt] = useState(null);
  const [manualExpiry, setManualExpiry] = useState("");

  const loadProfile = useCallback(async () => {
    try {
      const res = await api.get(`/employee/profile?token=${token}`);
      setProfile(res.data);
    } catch {}
  }, [token]);

  const loadDocuments = useCallback(async () => {
    try {
      const res = await api.get(`/employee/documents?token=${token}`);
      setDocuments(res.data);
    } catch {}
  }, [token]);

  useEffect(() => { loadProfile(); loadDocuments(); }, [loadProfile, loadDocuments]);

  const saveProfile = async () => {
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", profile.name);
      fd.append("phone", profile.phone);
      fd.append("street", profile.street);
      fd.append("zip_code", profile.zip_code);
      fd.append("city", profile.city);
      const res = await api.put(`/employee/profile?token=${token}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setProfile(res.data);
      updateUser({ name: profile.name });
      toast.success("Profil gespeichert");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    setSaving(false);
  };

  const uploadAvatar = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("avatar", file);
    fd.append("name", profile.name || "");
    fd.append("phone", profile.phone || "");
    fd.append("street", profile.street || "");
    fd.append("zip_code", profile.zip_code || "");
    fd.append("city", profile.city || "");
    try {
      const res = await api.put(`/employee/profile?token=${token}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setProfile(res.data);
      toast.success("Profilbild aktualisiert");
    } catch { toast.error("Fehler beim Hochladen"); }
  };

  const changePassword = async () => {
    if (pwForm.new_password !== pwForm.confirm) { toast.error("Passwörter stimmen nicht überein"); return; }
    try {
      await api.put(`/employee/profile/password?token=${token}`, { old_password: pwForm.old_password, new_password: pwForm.new_password });
      setPwForm({ old_password: "", new_password: "", confirm: "" });
      setShowPw(false);
      toast.success("Passwort geändert");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const uploadDocument = async (docType, file) => {
    if (!file) return;
    setUploading(docType);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("file", file);
      const res = await api.post(`/employee/documents?token=${token}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokument hochgeladen — KI prüft Ablaufdatum...");
      // Wait for AI result
      await new Promise(r => setTimeout(r, 5000));
      await loadDocuments();
      // Check if AI found a date
      const updatedDocs = await api.get(`/employee/documents?token=${token}`);
      const newDoc = updatedDocs.data.find(d => d.id === res.data.id);
      if (newDoc && !newDoc.expiry_date) {
        setExpiryPrompt(newDoc);
        setManualExpiry("");
      }
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    setUploading(null);
  };

  const updateExpiry = async (docId, date) => {
    try {
      await api.put(`/employee/documents/${docId}?token=${token}`, { expiry_date: date });
      await loadDocuments();
      toast.success("Ablaufdatum aktualisiert");
    } catch { toast.error("Fehler"); }
  };

  const getDocsForType = (type) => documents.filter(d => d.doc_type === type);
  const getActiveDoc = (type) => documents.find(d => d.doc_type === type && d.status === "active");
  const getOldDocs = (type) => documents.filter(d => d.doc_type === type && d.status === "alt");

  const isExpired = (date) => {
    if (!date) return false;
    return new Date(date) < new Date();
  };
  const isExpiringSoon = (date) => {
    if (!date) return false;
    const d = new Date(date);
    const now = new Date();
    const diff = (d - now) / (1000 * 60 * 60 * 24);
    return diff > 0 && diff <= 60;
  };

  const avatarUrl = profile.avatar_path ? `${API}/api/employee/avatar/${profile.user_id || user?.id}?token=${token}&_=${profile.avatar_path}` : null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="profile-back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-semibold text-gray-900">Mein Profil</h1>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {/* Avatar + Basic Info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row items-center gap-6">
            {/* Avatar */}
            <div className="relative">
              <div className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden">
                {avatarUrl ? (
                  <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                ) : (
                  <User className="w-10 h-10 text-gray-400" />
                )}
              </div>
              <input type="file" ref={avatarRef} accept="image/*" className="hidden" onChange={e => { if (e.target.files[0]) uploadAvatar(e.target.files[0]); e.target.value = ""; }} />
              <button
                onClick={() => avatarRef.current?.click()}
                className="absolute -bottom-1 -right-1 w-8 h-8 bg-fuchsia-600 rounded-full flex items-center justify-center text-white hover:bg-fuchsia-700 shadow-md"
                data-testid="avatar-upload-btn"
              >
                <Camera className="w-4 h-4" />
              </button>
            </div>

            {/* Name + Email */}
            <div className="flex-1 w-full space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Name</label>
                <Input value={profile.name} onChange={e => setProfile(p => ({ ...p, name: e.target.value }))} data-testid="profile-name" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">E-Mail</label>
                <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-md px-3 py-2">
                  <Mail className="w-4 h-4 text-gray-400" /> {profile.email}
                </div>
              </div>
            </div>
          </div>

          {/* Address + Phone */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5">
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1"><Phone className="w-3 h-3" />Telefon</label>
              <Input value={profile.phone} onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))} placeholder="z.B. +49 170 ..." data-testid="profile-phone" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 flex items-center gap-1"><MapPin className="w-3 h-3" />Straße</label>
              <Input value={profile.street} onChange={e => setProfile(p => ({ ...p, street: e.target.value }))} placeholder="Musterstraße 1" data-testid="profile-street" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">PLZ</label>
              <Input value={profile.zip_code} onChange={e => setProfile(p => ({ ...p, zip_code: e.target.value }))} placeholder="12345" data-testid="profile-zip" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Ort</label>
              <Input value={profile.city} onChange={e => setProfile(p => ({ ...p, city: e.target.value }))} placeholder="Musterstadt" data-testid="profile-city" />
            </div>
          </div>

          <Button onClick={saveProfile} disabled={saving} className="mt-4 bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-profile-btn">
            <Save className="w-4 h-4 mr-2" /> {saving ? "Speichern..." : "Profil speichern"}
          </Button>
        </div>

        {/* Password Change */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <button onClick={() => setShowPw(!showPw)} className="flex items-center gap-2 w-full text-left" data-testid="toggle-pw-section">
            <Lock className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-900">Passwort ändern</span>
            {showPw ? <ChevronUp className="w-4 h-4 ml-auto text-gray-400" /> : <ChevronDown className="w-4 h-4 ml-auto text-gray-400" />}
          </button>
          {showPw && (
            <div className="mt-4 space-y-3 max-w-sm">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Aktuelles Passwort</label>
                <Input type="password" value={pwForm.old_password} onChange={e => setPwForm(p => ({ ...p, old_password: e.target.value }))} data-testid="pw-old" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Neues Passwort</label>
                <Input type="password" value={pwForm.new_password} onChange={e => setPwForm(p => ({ ...p, new_password: e.target.value }))} data-testid="pw-new" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Neues Passwort bestätigen</label>
                <Input type="password" value={pwForm.confirm} onChange={e => setPwForm(p => ({ ...p, confirm: e.target.value }))} data-testid="pw-confirm" />
              </div>
              <Button onClick={changePassword} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-pw-btn">
                <Lock className="w-4 h-4 mr-2" /> Passwort ändern
              </Button>
            </div>
          )}
        </div>

        {/* Documents / Certificates */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-fuchsia-600" /> Dokumente & Zertifikate
          </h2>
          <div className="space-y-3">
            {DOC_TYPES.map(dt => {
              const active = getActiveDoc(dt.key);
              const old = getOldDocs(dt.key);
              const expired = active && isExpired(active.expiry_date);
              const expiringSoon = active && isExpiringSoon(active.expiry_date);
              const isExpanded = expandedType === dt.key;

              return (
                <div key={dt.key} className={`border rounded-lg overflow-hidden transition-colors ${expired ? "border-red-300 bg-red-50/30" : expiringSoon ? "border-amber-300 bg-amber-50/30" : "border-gray-200"}`} data-testid={`doc-card-${dt.key}`}>
                  <div className="px-4 py-3 flex items-center gap-3 cursor-pointer" onClick={() => setExpandedType(isExpanded ? null : dt.key)}>
                    <span className="text-lg">{dt.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{dt.label}</p>
                      {active ? (
                        <div className="flex items-center gap-2 mt-0.5">
                          {expired ? (
                            <span className="text-[10px] text-red-600 font-medium flex items-center gap-0.5"><AlertTriangle className="w-2.5 h-2.5" />Abgelaufen: {active.expiry_date}</span>
                          ) : expiringSoon ? (
                            <span className="text-[10px] text-amber-600 font-medium flex items-center gap-0.5"><AlertTriangle className="w-2.5 h-2.5" />Läuft bald ab: {active.expiry_date}</span>
                          ) : active.expiry_date ? (
                            <span className="text-[10px] text-green-600 font-medium flex items-center gap-0.5"><Check className="w-2.5 h-2.5" />Gültig bis: {active.expiry_date}</span>
                          ) : (
                            <span className="text-[10px] text-gray-400">Kein Ablaufdatum</span>
                          )}
                          <span className="text-[10px] text-gray-400">({active.filename})</span>
                        </div>
                      ) : (
                        <p className="text-[10px] text-gray-400">Kein Dokument hinterlegt</p>
                      )}
                    </div>
                    {active && (
                      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${expired ? "bg-red-500" : expiringSoon ? "bg-amber-400" : "bg-green-500"}`} />
                    )}
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-gray-100 pt-3 space-y-3">
                      {/* Upload / Drop Zone */}
                      <DocDropZone docType={dt.key} onUpload={uploadDocument} uploading={uploading} />

                      {/* Active document */}
                      {active && (
                        <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-gray-700">Aktuelles Dokument</p>
                            <a href={`${API}/api/employee/documents/${active.id}/file?token=${token}`} target="_blank" rel="noreferrer" className="text-xs text-fuchsia-600 hover:underline flex items-center gap-1" data-testid={`view-doc-${active.id}`}>
                              <Eye className="w-3 h-3" /> Anzeigen
                            </a>
                          </div>
                          <p className="text-[10px] text-gray-500">{active.filename} — Hochgeladen: {new Date(active.uploaded_at).toLocaleDateString("de-DE")}</p>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-3.5 h-3.5 text-gray-400" />
                            <label className="text-[10px] text-gray-500">Ablaufdatum:</label>
                            <input
                              type="date"
                              value={active.expiry_date || ""}
                              onChange={e => updateExpiry(active.id, e.target.value)}
                              className="text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-fuchsia-400"
                              data-testid={`expiry-input-${active.id}`}
                            />
                            {active.ai_expiry_date && active.ai_expiry_date !== active.expiry_date && (
                              <span className="text-[10px] text-blue-600">KI: {active.ai_expiry_date}</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Old documents */}
                      {old.length > 0 && (
                        <div>
                          <p className="text-[10px] text-gray-400 uppercase font-medium mb-1">Ältere Versionen ({old.length})</p>
                          {old.map(d => (
                            <div key={d.id} className="flex items-center gap-2 py-1 opacity-60">
                              <FileText className="w-3 h-3 text-gray-400" />
                              <span className="text-[10px] text-gray-500 flex-1 truncate">{d.filename} — {d.expiry_date || "kein Ablauf"}</span>
                              <a href={`${API}/api/employee/documents/${d.id}/file?token=${token}`} target="_blank" rel="noreferrer" className="text-[10px] text-fuchsia-600 hover:underline" data-testid={`view-old-doc-${d.id}`}>
                                Anzeigen
                              </a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Manual Expiry Date Dialog */}
      {expiryPrompt && (
        <>
          <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setExpiryPrompt(null)} />
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl shadow-2xl border border-gray-200 p-6 z-50 w-[90%] max-w-sm" data-testid="expiry-dialog">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">Ablaufdatum eingeben</h3>
            <p className="text-xs text-gray-500 mb-4">
              Die KI konnte kein Ablaufdatum für <strong>{DOCUMENT_LABELS[expiryPrompt.doc_type] || expiryPrompt.doc_type}</strong> erkennen. Bitte manuell eingeben:
            </p>
            <input
              type="date"
              value={manualExpiry}
              onChange={e => setManualExpiry(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
              autoFocus
              data-testid="manual-expiry-input"
            />
            <div className="flex gap-2">
              <Button
                onClick={async () => {
                  if (manualExpiry) {
                    await updateExpiry(expiryPrompt.id, manualExpiry);
                  }
                  setExpiryPrompt(null);
                }}
                className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                data-testid="save-expiry-btn"
              >
                Speichern
              </Button>
              <Button variant="outline" onClick={() => setExpiryPrompt(null)} className="flex-1" data-testid="skip-expiry-btn">
                Überspringen
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function DocDropZone({ docType, onUpload, uploading }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const ALLOWED = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp", "image/heic", "image/heif"];

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file && (ALLOWED.includes(file.type) || file.type.startsWith("image/"))) onUpload(docType, file);
    else toast.error("Bitte PDF oder Bild hochladen");
  };

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer ${dragOver ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 hover:border-fuchsia-300"}`}
      onClick={() => inputRef.current?.click()}
      data-testid={`drop-zone-${docType}`}
    >
      <input type="file" ref={inputRef} accept="application/pdf,image/*" className="hidden" onChange={e => { if (e.target.files[0]) onUpload(docType, e.target.files[0]); e.target.value = ""; }} />
      {uploading === docType ? (
        <p className="text-xs text-fuchsia-600 animate-pulse">Hochladen & KI-Prüfung...</p>
      ) : (
        <>
          <Upload className="w-5 h-5 text-gray-400 mx-auto mb-1" />
          <p className="text-xs text-gray-500">PDF oder Bild hierher ziehen oder klicken</p>
        </>
      )}
    </div>
  );
}
