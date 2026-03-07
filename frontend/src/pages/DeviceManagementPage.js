import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft,
  Plus,
  Search,
  Pencil,
  Trash2,
  FileText,
  Upload,
  X,
  Zap,
  Lightbulb,
  Settings,
  Power,
  PowerOff,
  Camera,
  Wrench,
  Printer,
  QrCode,
  Download,
  Server,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Pi Setup Section for Messkoffer - generates all-in-one installer
function PiSetupSection({ deviceId, deviceName }) {
  const [loading, setLoading] = useState(false);
  const [wgetCommand, setWgetCommand] = useState(null);

  const handleGenerateSetup = async () => {
    if (!window.confirm("Ein neuer Geräteschlüssel wird generiert und in das Setup-Skript eingebettet.\n\nFalls bereits ein Schlüssel existiert, wird er ersetzt.\n\nFortfahren?")) return;
    setLoading(true);
    try {
      const res = await api.post(`/energy-monitoring/devices/${deviceId}/setup-script`);
      const url = res.data.download_url;
      setWgetCommand(`wget "${url}" -O setup.sh && sudo bash setup.sh`);
      toast.success("Setup-Skript generiert!");
    } catch {
      toast.error("Fehler beim Generieren des Setup-Skripts");
    } finally {
      setLoading(false);
    }
  };

  const copyCommand = () => {
    navigator.clipboard.writeText(wgetCommand);
    toast.success("Befehl kopiert!");
  };

  return (
    <div className="border-t border-gray-100 pt-4">
      <div className="flex items-center gap-2 mb-1">
        <Server className="w-4 h-4 text-fuchsia-600" />
        <h3 className="text-sm font-medium text-gray-900">Pi Setup</h3>
      </div>
      <p className="text-[10px] text-gray-400 mb-3">
        Generiert ein Installations-Skript mit Shelly-Logger, GPS-Anbindung, lokaler Datenbank und Portal-Sync.
      </p>

      {wgetCommand && (
        <div className="mb-3 bg-emerald-50 border border-emerald-200 rounded-lg p-3" data-testid="setup-instructions">
          <p className="text-xs text-emerald-800 font-medium mb-2">Diesen Befehl auf dem Pi einfügen:</p>
          <div className="flex items-start gap-2">
            <code className="flex-1 bg-white border border-emerald-300 px-3 py-2 rounded text-[11px] font-mono select-all break-all leading-relaxed">{wgetCommand}</code>
            <button onClick={copyCommand} className="shrink-0 px-2 py-2 bg-white border border-emerald-300 rounded hover:bg-emerald-100 transition-colors" data-testid="copy-wget-btn" title="Kopieren">
              <Download className="w-4 h-4 text-emerald-600" />
            </button>
          </div>
          <p className="text-[10px] text-emerald-600 mt-2">Link ist 1 Stunde gültig. Danach neu generieren.</p>
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={handleGenerateSetup}
        disabled={loading}
        className="text-gray-600 hover:text-fuchsia-600"
        data-testid="download-setup-script-btn"
      >
        <Download className="w-3.5 h-3.5 mr-1.5" />
        {loading ? "Wird generiert..." : "Setup generieren"}
      </Button>
      <p className="text-[10px] text-gray-400 mt-2">Enthält: Shelly-Logger + GPS + Lokale DB + Schlüssel + Systemd-Dienst</p>
    </div>
  );
}

const CONTROLLER_OPTIONS = ["DSE 8610 MKII", "DSE 8610", "DSE 7310", "DSE L401"];
const CONTROLLER_TOPIC_INFO = {
  "DSE 8610 MKII": { filename: "dse8610_module_topics.csv", label: "DSE 8610 Module Topics" },
  "DSE 8610": { filename: "dse8610_module_topics.csv", label: "DSE 8610 Module Topics" },
  "DSE 7310": { filename: "dse8610_module_topics.csv", label: "DSE 7310 Module Topics" },
  "DSE L401": { filename: "dsel401_module_topics.csv", label: "DSE L401 Module Topics" },
};

function DseGatewaySetupSection({ controller, serialNumber, formData, update }) {
  const topicInfo = CONTROLLER_TOPIC_INFO[controller];
  const brokerUrl = "broker.hivemq.com";
  const brokerPort = "1883";
  const topicPrefix = `/${serialNumber || "SERIENNUMMER"}/`;

  const handleDownloadModuleTopics = () => {
    if (!controller || !topicInfo) return;
    window.open(`${BACKEND_URL}/api/download-controller-topics/${encodeURIComponent(controller)}`, "_blank");
  };

  const handleDownloadGatewayTopics = () => {
    window.open(`${BACKEND_URL}/api/download-dse890-gateway-topics`, "_blank");
  };

  return (
    <div className="border-t border-gray-100 pt-4" data-testid="dse-gateway-section">
      <div className="flex items-center gap-2 mb-1">
        <Server className="w-4 h-4 text-fuchsia-600" />
        <h3 className="text-sm font-medium text-gray-900">DSE890 Gateway Konfiguration</h3>
      </div>
      <p className="text-[10px] text-gray-400 mb-3">
        Einstellungen und Topic-Dateien für das DSE890 WebNet Gateway.
      </p>

      {/* MQTT Configuration Info */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-3" data-testid="dse-mqtt-info">
        <p className="text-xs text-gray-700 font-medium mb-2">MQTT-Einstellungen im DSE890:</p>
        <div className="space-y-1.5 text-xs font-mono">
          <div className="flex justify-between bg-white px-2 py-1.5 rounded border border-gray-100">
            <span className="text-gray-400">Broker</span>
            <span className="text-gray-900 select-all">{brokerUrl}</span>
          </div>
          <div className="flex justify-between bg-white px-2 py-1.5 rounded border border-gray-100">
            <span className="text-gray-400">Port</span>
            <span className="text-gray-900 select-all">{brokerPort}</span>
          </div>
          <div className="flex justify-between bg-white px-2 py-1.5 rounded border border-gray-100">
            <span className="text-gray-400">Topic-Prefix</span>
            <span className="text-gray-900 select-all">{topicPrefix}</span>
          </div>
        </div>
      </div>

      {/* MQTT Username & Password */}
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <Label className="text-gray-700 text-sm">MQTT Benutzer</Label>
          <Input
            value={formData.mqtt_username || ""}
            onChange={e => update("mqtt_username", e.target.value)}
            placeholder="Gateway-Benutzer"
            className="mt-1"
            data-testid="mqtt-username-input"
          />
        </div>
        <div>
          <Label className="text-gray-700 text-sm">MQTT Passwort</Label>
          <Input
            type="password"
            value={formData.mqtt_password || ""}
            onChange={e => update("mqtt_password", e.target.value)}
            placeholder="Gateway-Passwort"
            className="mt-1"
            data-testid="mqtt-password-input"
          />
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mb-3">Benutzer/Passwort werden nach dem Umzug auf den eigenen Broker aktiv.</p>

      {/* Standort (manuell) */}
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <Label className="text-gray-700 text-sm">Breitengrad (Lat)</Label>
          <Input
            type="number"
            step="any"
            value={formData.latitude || ""}
            onChange={e => update("latitude", e.target.value ? parseFloat(e.target.value) : "")}
            placeholder="z.B. 50.9375"
            className="mt-1 font-mono"
            data-testid="latitude-input"
          />
        </div>
        <div>
          <Label className="text-gray-700 text-sm">Längengrad (Lng)</Label>
          <Input
            type="number"
            step="any"
            value={formData.longitude || ""}
            onChange={e => update("longitude", e.target.value ? parseFloat(e.target.value) : "")}
            placeholder="z.B. 6.9603"
            className="mt-1 font-mono"
            data-testid="longitude-input"
          />
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mb-3">Manueller Standort als Fallback. Wird automatisch überschrieben wenn GPS-Daten vom Gateway empfangen werden.</p>

      {/* Topic File Downloads */}
      <div className="flex flex-wrap gap-2">
        {controller && topicInfo ? (
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadModuleTopics}
            className="text-gray-600 hover:text-fuchsia-600"
            data-testid="download-module-topics-btn"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            {topicInfo.label}
          </Button>
        ) : (
          <p className="text-[10px] text-gray-400">Bitte eine Steuerung auswählen, um die Topic-Datei herunterzuladen.</p>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={handleDownloadGatewayTopics}
          className="text-gray-600 hover:text-fuchsia-600"
          data-testid="download-gateway-topics-btn"
        >
          <Download className="w-3.5 h-3.5 mr-1.5" />
          DSE890 Gateway Topics
        </Button>
      </div>
    </div>
  );
}

const DEVICE_TYPES = [
  { value: "stromerzeuger", label: "Stromerzeuger", icon: Zap },
  { value: "lichtmast", label: "Lichtmast", icon: Lightbulb },
  { value: "messkoffer", label: "Messkoffer", icon: Settings },
  { value: "kirmeskiste", label: "Kirmeskiste", icon: Settings },
];

const TYPE_LABELS = Object.fromEntries(DEVICE_TYPES.map(t => [t.value, t.label]));

const EMPTY_FORM = {
  device_type: "stromerzeuger",
  serial_number: "",
  user_field: "",
  model: "",
  engine_manufacturer: "",
  engine_type: "",
  engine_number: "",
  generator_manufacturer: "",
  generator_type: "",
  generator_number: "",
  year_of_manufacture: "",
  power_output: "",
  controller: "",
  acquired_date: "",
  portal_link: "",
  notes: "",
  pi_hostname: "",
  pi_ip: "",
  pi_port: "",
  pi_username: "",
  pi_password: "",
  pi_notes: "",
  mqtt_username: "",
  mqtt_password: "",
  latitude: "",
  longitude: "",
};

function DeviceModal({ open, onClose, formData, setFormData, onSave, editing, isAdmin, allDevices }) {
  const fileInputRef = useRef(null);
  const imageInputRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [copySearch, setCopySearch] = useState("");
  const [showCopyDropdown, setShowCopyDropdown] = useState(false);
  const [deviceImageUrl, setDeviceImageUrl] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [pendingImage, setPendingImage] = useState(null);
  const [parts, setParts] = useState([]);
  const [showAddPart, setShowAddPart] = useState(false);
  const [newPart, setNewPart] = useState({ part_type: "", part_number: "", liters: "", notes: "" });
  const [controllerCustomMode, setControllerCustomMode] = useState(false);

  const isGenerator = formData.device_type === "stromerzeuger" || formData.device_type === "lichtmast";

  const PART_TYPES = [
    "Kraftstoffvorfilter", "Kraftstofffilter", "Ölfilter", "Keilriemen",
    "Umlenkrollen", "Wasserpumpe", "Luftfilter", "Motoröl",
  ];

  const loadDocuments = useCallback(async () => {
    if (!editing) return;
    try {
      const res = await api.get(`/devices/${editing.id}/documents`);
      setDocuments(res.data);
    } catch { setDocuments([]); }
  }, [editing]);

  const loadParts = useCallback(async () => {
    if (!editing) return;
    try {
      const res = await api.get(`/devices/${editing.id}/parts`);
      setParts(res.data);
    } catch { setParts([]); }
  }, [editing]);

  useEffect(() => {
    if (open && editing) {
      loadDocuments();
      loadParts();
      if (editing.image_gridfs_id) {
        setDeviceImageUrl(`${BACKEND_URL}/api/devices/${editing.id}/image`);
      } else {
        setDeviceImageUrl(null);
      }
      const KNOWN = ["DSE 8610 MKII", "DSE 8610", "DSE 7310", "DSE L401"];
      setControllerCustomMode(!!editing.controller && !KNOWN.includes(editing.controller));
    } else {
      setDocuments([]);
      setParts([]);
      setDeviceImageUrl(null);
      setShowAddPart(false);
      setNewPart({ part_type: "", part_number: "", liters: "", notes: "" });
      setPendingImage(null);
      setControllerCustomMode(false);
    }
  }, [open, editing, loadDocuments, loadParts]);

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (editing) {
      // Existing device: upload immediately
      setUploadingImage(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        await api.post(`/devices/${editing.id}/image`, fd, { headers: { "Content-Type": "multipart/form-data" } });
        toast.success("Gerätebild hochgeladen");
        setDeviceImageUrl(`${BACKEND_URL}/api/devices/${editing.id}/image?t=${Date.now()}`);
      } catch { toast.error("Bild-Upload fehlgeschlagen"); }
      finally { setUploadingImage(false); if (imageInputRef.current) imageInputRef.current.value = ""; }
    } else {
      // New device: store file for upload after creation
      setPendingImage(file);
      setDeviceImageUrl(URL.createObjectURL(file));
      if (imageInputRef.current) imageInputRef.current.value = "";
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !editing) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/devices/${editing.id}/documents`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokument hochgeladen");
      loadDocuments();
    } catch { toast.error("Upload fehlgeschlagen"); }
    finally { setUploading(false); if (fileInputRef.current) fileInputRef.current.value = ""; }
  };

  const handleDeleteDoc = async (docId) => {
    if (!editing) return;
    try {
      await api.delete(`/devices/${editing.id}/documents/${docId}`);
      toast.success("Dokument gelöscht");
      loadDocuments();
    } catch { toast.error("Fehler"); }
  };

  const handleAddPart = async () => {
    if (!editing || !newPart.part_type) { toast.error("Bitte Typ auswählen"); return; }
    try {
      await api.post(`/devices/${editing.id}/parts`, {
        part_type: newPart.part_type,
        part_number: newPart.part_number,
        liters: newPart.liters ? parseFloat(newPart.liters) : null,
        notes: newPart.notes,
      });
      toast.success("Ersatzteil hinzugefügt");
      setNewPart({ part_type: "", part_number: "", liters: "", notes: "" });
      setShowAddPart(false);
      loadParts();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const handleDeletePart = async (partId) => {
    try {
      await api.delete(`/devices/parts/${partId}`);
      toast.success("Ersatzteil gelöscht");
      loadParts();
    } catch { toast.error("Fehler"); }
  };

  const update = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));

  const handleCopyFromDevice = (device) => {
    setFormData({
      device_type: device.device_type || "stromerzeuger",
      serial_number: "",
      user_field: device.user_field || "",
      model: device.model || "",
      engine_manufacturer: device.engine_manufacturer || "",
      engine_type: device.engine_type || "",
      engine_number: "",
      generator_manufacturer: device.generator_manufacturer || "",
      generator_type: device.generator_type || "",
      generator_number: "",
      year_of_manufacture: device.year_of_manufacture ?? "",
      power_output: device.power_output || "",
      controller: device.controller || "",
      acquired_date: "",
      portal_link: device.portal_link || "",
      notes: "",
      copy_image_from: device.image_gridfs_id ? device.id : null,
      copy_docs_from: device.id,
    });
    setCopySearch("");
    setShowCopyDropdown(false);
    toast.success("Daten übernommen – Dokumente können nach dem Speichern übernommen werden");
  };

  const copyFilteredDevices = (allDevices || []).filter(d => {
    if (!copySearch) return true;
    const q = copySearch.toLowerCase();
    return (d.serial_number || "").toLowerCase().includes(q) ||
      (d.model || "").toLowerCase().includes(q) ||
      (d.user_field || "").toLowerCase().includes(q);
  });

  if (!open) return null;

  const currentType = DEVICE_TYPES.find(t => t.value === formData.device_type);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-8 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 mb-8" data-testid="device-modal">
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {editing ? "Gerät bearbeiten" : "Neues Gerät anlegen"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto" data-testid="device-form">
          {/* Copy from existing device - only in create mode */}
          {!editing && isAdmin && allDevices && allDevices.length > 0 && (
            <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-4" data-testid="copy-from-section">
              <Label className="text-fuchsia-700 text-sm font-medium mb-2 block">Von bestehendem Gerät kopieren</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fuchsia-400" />
                <input
                  type="text"
                  placeholder="Gerät suchen (Seriennummer, Modell...)"
                  value={copySearch}
                  onChange={e => { setCopySearch(e.target.value); setShowCopyDropdown(true); }}
                  onFocus={() => setShowCopyDropdown(true)}
                  className="w-full pl-9 pr-3 py-2 border border-fuchsia-300 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                  data-testid="copy-search-input"
                />
                {showCopyDropdown && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                    {copyFilteredDevices.length === 0 ? (
                      <p className="text-xs text-gray-400 p-3">Keine Geräte gefunden</p>
                    ) : (
                      copyFilteredDevices.slice(0, 10).map(d => (
                        <button
                          key={d.id}
                          onClick={() => handleCopyFromDevice(d)}
                          className="w-full text-left px-3 py-2 hover:bg-fuchsia-50 transition-colors border-b border-gray-50 last:border-b-0"
                          data-testid={`copy-option-${d.serial_number}`}
                        >
                          <p className="text-sm font-medium text-gray-900">{d.serial_number}</p>
                          <p className="text-[10px] text-gray-400">{TYPE_LABELS[d.device_type] || d.device_type} · {d.model || "–"} · {d.user_field || "–"}</p>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
              {showCopyDropdown && (
                <button onClick={() => setShowCopyDropdown(false)} className="text-xs text-fuchsia-500 mt-1 hover:underline">Schließen</button>
              )}
            </div>
          )}
          {/* Device Image - available for both new and existing devices */}
          <div className="flex items-center gap-4 bg-gray-50 rounded-lg p-4" data-testid="device-image-section">
            <input ref={imageInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleImageUpload} />
            {deviceImageUrl ? (
              <img src={deviceImageUrl} alt="Gerät" className="w-20 h-20 rounded-lg object-cover border border-gray-200" data-testid="device-image-preview" />
            ) : (
              <div className="w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center text-gray-400">
                <Camera className="w-6 h-6" />
              </div>
            )}
            <div>
              <p className="text-sm font-medium text-gray-700">Gerätebild</p>
              <p className="text-xs text-gray-400 mb-2">Bild zur visuellen Identifikation</p>
              <Button size="sm" variant="outline" onClick={() => imageInputRef.current?.click()} disabled={uploadingImage} data-testid="upload-device-image-btn">
                <Camera className="w-3.5 h-3.5 mr-1" /> {uploadingImage ? "Wird hochgeladen..." : deviceImageUrl ? "Bild ändern" : "Bild hinzufügen"}
              </Button>
            </div>
          </div>

          {/* QR Code Section */}
          {editing && editing.device_code && (
            <div className="border border-gray-200 rounded-lg p-4" data-testid="qr-code-section">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="bg-white p-2 rounded-lg border border-gray-200" id="qr-print-area">
                    <QRCodeSVG value={editing.device_code} size={80} level="M" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">Geräte-Code</h3>
                    <p className="text-lg font-mono font-bold text-fuchsia-600 tracking-wider mt-0.5">{editing.device_code}</p>
                    <p className="text-[10px] text-gray-400 mt-1">Einmaliger Code zur Geräteidentifikation</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    const printWin = window.open("", "_blank", "width=400,height=500");
                    printWin.document.write(`
                      <html><head><title>QR Code - ${editing.serial_number}</title>
                      <style>body{font-family:sans-serif;text-align:center;padding:40px}
                      .code{font-size:28px;font-weight:bold;letter-spacing:4px;margin:16px 0;font-family:monospace}
                      .serial{font-size:14px;color:#666;margin-top:8px}
                      svg{margin:20px auto}
                      </style></head><body>
                      <h2>Geräte-Code</h2>
                      <div class="code">${editing.device_code}</div>
                      ${document.getElementById("qr-print-area")?.innerHTML || ""}
                      <div class="serial">${editing.serial_number}</div>
                      <div class="serial">${editing.model || ""}</div>
                      <script>setTimeout(()=>{window.print();window.close()},500)<\/script>
                      </body></html>`);
                    printWin.document.close();
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors"
                  data-testid="print-qr-btn"
                >
                  <Printer className="w-3.5 h-3.5" /> Drucken
                </button>
              </div>
            </div>
          )}

          {/* Ersatzteile (Parts) - at the top of the form */}
          {editing && (
            <div className="border border-gray-200 rounded-lg p-4" data-testid="parts-section">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Ersatzteile ({parts.length})</h3>
                  <p className="text-[10px] text-gray-400">Filter, Öle, Riemen und weitere Teile</p>
                </div>
                <button
                  onClick={() => setShowAddPart(!showAddPart)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors"
                  data-testid="add-part-btn"
                >
                  <Plus className="w-3.5 h-3.5" /> Ersatzteil
                </button>
              </div>

              {showAddPart && (
                <div className="bg-white border border-gray-200 rounded-lg p-3 mb-3" data-testid="add-part-form">
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <div>
                      <Label className="text-gray-600 text-xs">Typ *</Label>
                      <select
                        value={PART_TYPES.includes(newPart.part_type) ? newPart.part_type : (newPart.part_type ? "__custom" : "")}
                        onChange={e => {
                          if (e.target.value === "__custom") {
                            setNewPart(p => ({ ...p, part_type: "" }));
                          } else {
                            setNewPart(p => ({ ...p, part_type: e.target.value }));
                          }
                        }}
                        className="w-full mt-0.5 px-2 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                        data-testid="part-type-select"
                      >
                        <option value="">Typ wählen...</option>
                        {PART_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                        <option value="__custom">Sonderteil (Freitext)...</option>
                      </select>
                      {!PART_TYPES.includes(newPart.part_type) && newPart.part_type !== "" && (
                        <Input
                          value={newPart.part_type}
                          onChange={e => setNewPart(p => ({ ...p, part_type: e.target.value }))}
                          placeholder="Sonderteil-Bezeichnung..."
                          className="mt-1 text-sm"
                          data-testid="part-custom-type"
                          autoFocus
                        />
                      )}
                    </div>
                    <div>
                      <Label className="text-gray-600 text-xs">Teilenummer</Label>
                      <Input
                        value={newPart.part_number}
                        onChange={e => setNewPart(p => ({ ...p, part_number: e.target.value }))}
                        placeholder="z.B. 265272"
                        className="mt-0.5 text-sm"
                        data-testid="part-number-input"
                      />
                    </div>
                  </div>
                  {(newPart.part_type === "Motoröl" || newPart.liters) && (
                    <div className="mb-2">
                      <Label className="text-gray-600 text-xs">Literzahl</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={newPart.liters}
                        onChange={e => setNewPart(p => ({ ...p, liters: e.target.value }))}
                        placeholder="z.B. 12.5"
                        className="mt-0.5 text-sm w-40"
                        data-testid="part-liters-input"
                      />
                    </div>
                  )}
                  <div className="mb-2">
                    <Label className="text-gray-600 text-xs">Notiz</Label>
                    <Input
                      value={newPart.notes}
                      onChange={e => setNewPart(p => ({ ...p, notes: e.target.value }))}
                      placeholder="Zusatzinfo..."
                      className="mt-0.5 text-sm"
                      data-testid="part-notes-input"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleAddPart} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs" data-testid="save-part-btn">Hinzufügen</Button>
                    <Button size="sm" variant="outline" onClick={() => setShowAddPart(false)} className="text-xs">Abbrechen</Button>
                  </div>
                </div>
              )}

              {parts.length === 0 ? (
                <p className="text-xs text-gray-400 py-3 text-center bg-gray-50 rounded-lg">Keine Ersatzteile hinterlegt</p>
              ) : (
                <div className="space-y-1.5">
                  {parts.map(part => (
                    <div key={part.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg" data-testid={`part-${part.id}`}>
                      <div className="flex items-center gap-2 min-w-0">
                        <Wrench className="w-4 h-4 text-fuchsia-400 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm text-gray-900 truncate">
                            {part.part_type}
                            {part.part_number && <span className="text-gray-400 ml-1.5 font-mono text-xs">{part.part_number}</span>}
                          </p>
                          <p className="text-[10px] text-gray-400">
                            {part.liters != null && `${part.liters} L`}
                            {part.liters != null && part.notes && " · "}
                            {part.notes}
                          </p>
                        </div>
                      </div>
                      <button onClick={() => handleDeletePart(part.id)} className="text-gray-400 hover:text-red-500 flex-shrink-0 ml-2" data-testid={`delete-part-${part.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Device Type - selectable only on create OR for admin editing */}
          {!editing ? (
            <div>
              <Label className="text-gray-700 text-sm mb-1.5 block">Gerätetyp</Label>
              <div className="grid grid-cols-4 gap-2">
                {DEVICE_TYPES.map(t => (
                  <button
                    key={t.value}
                    onClick={() => update("device_type", t.value)}
                    className={`p-3 rounded-lg border text-center text-xs font-medium transition-colors ${
                      formData.device_type === t.value
                        ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700"
                        : "border-gray-200 text-gray-500 hover:border-gray-300"
                    }`}
                    data-testid={`type-${t.value}`}
                  >
                    <t.icon className="w-5 h-5 mx-auto mb-1" />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <Label className="text-gray-700 text-sm mb-1.5 block">Gerätetyp</Label>
              {isAdmin ? (
                <div className="grid grid-cols-4 gap-2">
                  {DEVICE_TYPES.map(t => (
                    <button
                      key={t.value}
                      onClick={() => update("device_type", t.value)}
                      className={`p-3 rounded-lg border text-center text-xs font-medium transition-colors ${
                        formData.device_type === t.value
                          ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700"
                          : "border-gray-200 text-gray-500 hover:border-gray-300"
                      }`}
                      data-testid={`type-${t.value}`}
                    >
                      <t.icon className="w-5 h-5 mx-auto mb-1" />
                      {t.label}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                  {currentType && <currentType.icon className="w-5 h-5 text-fuchsia-500" />}
                  <span className="text-sm font-medium text-gray-700">{currentType?.label || formData.device_type}</span>
                </div>
              )}
            </div>
          )}

          {/* Common Fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-gray-700 text-sm">{formData.device_type === "messkoffer" ? "Gerätenummer" : "Seriennummer"} *</Label>
              <Input value={formData.serial_number} onChange={e => update("serial_number", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="serial-input" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Benutzerfeld</Label>
              <Input value={formData.user_field} onChange={e => update("user_field", e.target.value)} placeholder="Freitext (suchbar)" className="mt-1" data-testid="user-field-input" />
            </div>
          </div>

          {/* Stromerzeuger/Lichtmast fields */}
          {isGenerator && (
            <>
              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Gerätedaten</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Modell</Label>
                    <Input value={formData.model} onChange={e => update("model", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="model-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Baujahr</Label>
                    <Input type="number" value={formData.year_of_manufacture} onChange={e => update("year_of_manufacture", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="year-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Leistung</Label>
                    <Input value={formData.power_output} onChange={e => update("power_output", e.target.value)} placeholder="z.B. 400 kVA" className="mt-1" disabled={!isAdmin && !!editing} data-testid="power-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Steuerung</Label>
                    {(() => {
                      const CONTROLLER_OPTIONS = ["DSE 8610 MKII", "DSE 8610", "DSE 7310", "DSE L401"];
                      const isKnown = CONTROLLER_OPTIONS.includes(formData.controller);
                      const selectValue = isKnown ? formData.controller : (controllerCustomMode ? "__custom" : "");
                      return (
                        <>
                          <select
                            value={selectValue}
                            onChange={e => {
                              if (e.target.value === "__custom") {
                                setControllerCustomMode(true);
                                update("controller", "");
                              } else {
                                setControllerCustomMode(false);
                                update("controller", e.target.value);
                              }
                            }}
                            className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                            disabled={!isAdmin && !!editing}
                            data-testid="controller-select"
                          >
                            <option value="">Steuerung wählen...</option>
                            {CONTROLLER_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            <option value="__custom">Sonstige (Freitext)...</option>
                          </select>
                          {controllerCustomMode && (
                            <Input
                              value={formData.controller}
                              onChange={e => update("controller", e.target.value)}
                              placeholder="Steuerung eingeben..."
                              className="mt-1"
                              disabled={!isAdmin && !!editing}
                              data-testid="controller-custom-input"
                              autoFocus
                            />
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Motor</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Hersteller</Label>
                    <Input value={formData.engine_manufacturer} onChange={e => update("engine_manufacturer", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="engine-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.engine_type} onChange={e => update("engine_type", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="engine-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Motornummer</Label>
                    <Input value={formData.engine_number} onChange={e => update("engine_number", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="engine-num-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Generator</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Hersteller</Label>
                    <Input value={formData.generator_manufacturer} onChange={e => update("generator_manufacturer", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="gen-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.generator_type} onChange={e => update("generator_type", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="gen-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Generatornummer</Label>
                    <Input value={formData.generator_number} onChange={e => update("generator_number", e.target.value)} className="mt-1" disabled={!isAdmin && !!editing} data-testid="gen-num-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Weitere Daten</h3>
                <div>
                  <Label className="text-gray-700 text-sm">Erworben am</Label>
                  <Input type="date" value={formData.acquired_date} onChange={e => update("acquired_date", e.target.value)} className="mt-1" data-testid="acquired-date-input" />
                </div>
              </div>

              {/* DSE890 Gateway Setup - only for existing devices with admin */}
              {editing && isAdmin && (
                <DseGatewaySetupSection
                  controller={formData.controller}
                  serialNumber={formData.serial_number}
                  formData={formData}
                  update={update}
                />
              )}
            </>
          )}

          {/* Messkoffer-specific fields: Pi connection + Setup */}
          {formData.device_type === "messkoffer" && (
            <>
              {/* Pi Setup - all-in-one installer (only for existing devices) */}
              {editing && isAdmin && (
                <PiSetupSection deviceId={editing.id} deviceName={editing.serial_number} />
              )}
            </>
          )}

          {/* Notes */}
          <div>
            <Label className="text-gray-700 text-sm">Notizen</Label>
            <textarea
              value={formData.notes}
              onChange={e => update("notes", e.target.value)}
              rows={2}
              className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500"
              data-testid="notes-input"
            />
          </div>

          {/* Dateiablage (documents) */}
          {editing && (
            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Dateiablage ({documents.length})</h3>
                  <p className="text-[10px] text-gray-400">Handbücher, Schaltpläne, Motornummern etc.</p>
                </div>
                <label className="cursor-pointer">
                  <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" />
                  <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-fuchsia-50 text-fuchsia-600 rounded-lg text-xs font-medium hover:bg-fuchsia-100 transition-colors" data-testid="upload-doc-btn">
                    <Upload className="w-3.5 h-3.5" /> {uploading ? "Lädt..." : "Datei hochladen"}
                  </span>
                </label>
              </div>
              {documents.length === 0 ? (
                <p className="text-xs text-gray-400 py-3 text-center bg-gray-50 rounded-lg">Keine Dateien vorhanden</p>
              ) : (
                <div className="space-y-1.5">
                  {documents.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg" data-testid={`doc-${doc.id}`}>
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-4 h-4 text-fuchsia-400 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm text-gray-900 truncate">{doc.filename}</p>
                          <p className="text-[10px] text-gray-400">{(doc.size / 1024).toFixed(1)} KB · {new Date(doc.uploaded_at).toLocaleDateString("de-DE")}</p>
                        </div>
                      </div>
                      {isAdmin && (
                        <button onClick={() => handleDeleteDoc(doc.id)} className="text-gray-400 hover:text-red-500 flex-shrink-0 ml-2" data-testid={`delete-doc-${doc.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Ersatzteile (Parts) */}

        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
          <Button variant="outline" onClick={onClose} data-testid="cancel-btn">Abbrechen</Button>
          <Button onClick={() => onSave(pendingImage)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-device-btn">
            {editing ? "Speichern" : "Anlegen"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function DeviceManagementPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadDevices = useCallback(async () => {
    try {
      const res = await api.get("/devices");
      setDevices(res.data);
    } catch (err) {
      toast.error("Fehler beim Laden der Geräte");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDevices(); }, [loadDevices]);

  const openCreate = () => {
    setEditing(null);
    setFormData({ ...EMPTY_FORM });
    setModalOpen(true);
  };

  const openEdit = (device) => {
    setEditing(device);
    setFormData({
      device_type: device.device_type || "stromerzeuger",
      serial_number: device.serial_number || "",
      user_field: device.user_field || "",
      latitude: device.latitude ?? "",
      longitude: device.longitude ?? "",
      model: device.model || "",
      engine_manufacturer: device.engine_manufacturer || "",
      engine_type: device.engine_type || "",
      engine_number: device.engine_number || "",
      generator_manufacturer: device.generator_manufacturer || "",
      generator_type: device.generator_type || "",
      generator_number: device.generator_number || "",
      year_of_manufacture: device.year_of_manufacture ?? "",
      power_output: device.power_output || "",
      controller: device.controller || "",
      last_maintenance: device.last_maintenance || "",
      next_maintenance: device.next_maintenance || "",
      notes: device.notes || "",
      pi_hostname: device.pi_hostname || "",
      pi_ip: device.pi_ip || "",
      pi_port: device.pi_port || "",
      pi_username: device.pi_username || "",
      pi_password: device.pi_password || "",
      pi_notes: device.pi_notes || "",
      mqtt_username: device.mqtt_username || "",
      mqtt_password: device.mqtt_password || "",
    });
    setModalOpen(true);
  };

  const handleSave = async (pendingImageFile) => {
    if (!formData.serial_number.trim()) {
      toast.error(formData.device_type === "messkoffer" ? "Gerätenummer ist erforderlich" : "Seriennummer ist erforderlich");
      return;
    }
    const payload = {
      ...formData,
      year_of_manufacture: formData.year_of_manufacture ? parseInt(formData.year_of_manufacture) : null,
    };
    // Pass copy_from_device_id for backend to copy image/parts/docs
    if (!editing && formData.copy_docs_from) {
      payload.copy_from_device_id = formData.copy_docs_from;
    }
    // Remove frontend-only fields
    delete payload.copy_image_from;
    delete payload.copy_docs_from;
    try {
      if (editing) {
        await api.put(`/devices/${editing.id}`, payload);
        toast.success("Gerät aktualisiert");
        setModalOpen(false);
      } else {
        const res = await api.post("/devices", payload);
        // Upload pending image if exists
        if (pendingImageFile && res.data?.id) {
          try {
            const fd = new FormData();
            fd.append("file", pendingImageFile);
            await api.post(`/devices/${res.data.id}/image`, fd, { headers: { "Content-Type": "multipart/form-data" } });
          } catch { /* silent - device created but image upload failed */ }
        }
        toast.success("Gerät angelegt");
        setModalOpen(false);
      }
      loadDevices();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler beim Speichern");
    }
  };

  const handleCopy = async (deviceId) => {
    try {
      const res = await api.post(`/devices/${deviceId}/copy`);
      toast.success("Gerät kopiert – bitte Seriennummer anpassen");
      setModalOpen(false);
      loadDevices();
      setTimeout(() => openEdit(res.data), 300);
    } catch (err) {
      toast.error("Fehler beim Kopieren");
    }
  };

  const handleDelete = async (deviceId) => {
    try {
      await api.delete(`/devices/${deviceId}`);
      toast.success("Gerät gelöscht");
      setDeleteConfirm(null);
      loadDevices();
    } catch {
      toast.error("Fehler beim Löschen");
    }
  };

  const handleToggleStatus = async (device) => {
    try {
      const res = await api.post(`/devices/${device.id}/ausser-betrieb`);
      toast.success(res.data.message);
      loadDevices();
    } catch {
      toast.error("Fehler beim Statuswechsel");
    }
  };

  const filtered = devices.filter(d => {
    const matchType = typeFilter === "all" || d.device_type === typeFilter;
    const matchStatus = statusFilter === "all" ||
      (statusFilter === "aktiv" && d.status !== "ausser_betrieb") ||
      (statusFilter === "ausser_betrieb" && d.status === "ausser_betrieb");
    const q = search.toLowerCase();
    const matchSearch = !search ||
      (d.serial_number || "").toLowerCase().includes(q) ||
      (d.user_field || "").toLowerCase().includes(q) ||
      (d.model || "").toLowerCase().includes(q) ||
      (d.engine_manufacturer || "").toLowerCase().includes(q) ||
      (d.device_code || "").toLowerCase().includes(q) ||
      (d.notes || "").toLowerCase().includes(q);
    return matchType && matchStatus && matchSearch;
  });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="device-management">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Geräteverwaltung</h1>
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-device-btn">
                <Plus className="w-4 h-4 mr-1" /> Neues Gerät
              </Button>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Suche nach Seriennummer, Benutzerfeld, Modell..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500"
              data-testid="device-search"
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {[{ value: "all", label: "Alle" }, ...DEVICE_TYPES].map(t => (
              <button
                key={t.value}
                onClick={() => setTypeFilter(t.value)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  typeFilter === t.value ? "bg-fuchsia-600 text-white" : "bg-white text-gray-500 hover:text-gray-700 border border-gray-200"
                }`}
                data-testid={`filter-${t.value}`}
              >
                {t.label}
              </button>
            ))}
            <div className="w-px bg-gray-200 mx-1" />
            <button
              onClick={() => setStatusFilter(statusFilter === "ausser_betrieb" ? "all" : "ausser_betrieb")}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === "ausser_betrieb" ? "bg-red-500 text-white" : "bg-white text-gray-500 hover:text-gray-700 border border-gray-200"
              }`}
              data-testid="filter-ausser-betrieb"
            >
              Außer Betrieb
            </button>
          </div>
        </div>

        {/* Device Table */}
        {loading ? (
          <div className="text-center py-20 text-gray-400">Laden...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20">
            <Settings className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">{devices.length === 0 ? "Keine Geräte angelegt" : "Keine Treffer"}</p>
            {devices.length === 0 && isAdmin && (
              <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                <Plus className="w-4 h-4 mr-1" /> Erstes Gerät anlegen
              </Button>
            )}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="device-table">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">Typ</th>
                    <th className="px-4 py-3 text-left">Seriennummer</th>
                    <th className="px-4 py-3 text-left hidden md:table-cell">Modell</th>
                    <th className="px-4 py-3 text-left hidden md:table-cell">Benutzerfeld</th>
                    <th className="px-4 py-3 text-left hidden lg:table-cell">Leistung</th>
                    <th className="px-4 py-3 text-left hidden lg:table-cell">Wartung</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(device => {
                    const TypeIcon = DEVICE_TYPES.find(t => t.value === device.device_type)?.icon || Settings;
                    const nextMaint = device.next_maintenance ? new Date(device.next_maintenance) : null;
                    const isOverdue = nextMaint && nextMaint < new Date();
                    const isOutOfService = device.status === "ausser_betrieb";
                    return (
                      <tr key={device.id} className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${isOutOfService ? "opacity-60" : ""}`} data-testid={`device-row-${device.serial_number}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {device.image_gridfs_id ? (
                              <img src={`${BACKEND_URL}/api/devices/${device.id}/image`} alt="" className="w-8 h-8 rounded object-cover border border-gray-200" />
                            ) : (
                              <TypeIcon className="w-4 h-4 text-fuchsia-500" />
                            )}
                            <span className="text-xs text-gray-500">{TYPE_LABELS[device.device_type] || device.device_type}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-gray-900">
                          {device.serial_number}
                          {device.device_code && <span className="block text-[10px] text-gray-400 font-normal">{device.device_code}</span>}
                        </td>
                        <td className="px-4 py-3 text-gray-600 hidden md:table-cell">{device.model || "–"}</td>
                        <td className="px-4 py-3 text-gray-500 hidden md:table-cell truncate max-w-[200px]">{device.user_field || "–"}</td>
                        <td className="px-4 py-3 text-gray-600 hidden lg:table-cell">{device.power_output || "–"}</td>
                        <td className="px-4 py-3 hidden lg:table-cell">
                          {device.next_maintenance ? (
                            <span className={`text-xs ${isOverdue ? "text-red-500 font-medium" : "text-gray-500"}`}>
                              {new Date(device.next_maintenance).toLocaleDateString("de-DE")}
                              {isOverdue && " (überfällig)"}
                            </span>
                          ) : "–"}
                        </td>
                        <td className="px-4 py-3">
                          {isOutOfService ? (
                            <span className="inline-flex items-center gap-1 text-xs text-red-500 font-medium">
                              <PowerOff className="w-3 h-3" /> Außer Betrieb
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <Power className="w-3 h-3" /> Aktiv
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => openEdit(device)} className="p-1.5 text-gray-400 hover:text-fuchsia-600 transition-colors" title="Bearbeiten" data-testid={`edit-${device.serial_number}`}>
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleToggleStatus(device)}
                              className={`p-1.5 transition-colors ${isOutOfService ? "text-emerald-500 hover:text-emerald-600" : "text-amber-500 hover:text-amber-600"}`}
                              title={isOutOfService ? "Wieder in Betrieb nehmen" : "Außer Betrieb setzen"}
                              data-testid={`toggle-status-${device.serial_number}`}
                            >
                              {isOutOfService ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
                            </button>
                            {isAdmin && (
                              <>
                                <button onClick={() => setDeleteConfirm(device)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" title="Löschen" data-testid={`delete-${device.serial_number}`}>
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t border-gray-100">
              {filtered.length} von {devices.length} Geräte
            </div>
          </div>
        )}
      </main>

      <DeviceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        formData={formData}
        setFormData={setFormData}
        onSave={handleSave}
        editing={editing}
        isAdmin={isAdmin}
        allDevices={devices}
      />

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm mx-4" data-testid="delete-confirm">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Gerät löschen?</h3>
            <p className="text-sm text-gray-500 mb-4">
              <strong>{deleteConfirm.serial_number}</strong> wird unwiderruflich gelöscht, inklusive aller Dokumente.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Abbrechen</Button>
              <Button onClick={() => handleDelete(deleteConfirm.id)} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-delete-btn">Löschen</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
