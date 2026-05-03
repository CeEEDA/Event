import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api, { getErrorMsg, BACKEND_URL } from "../lib/api";
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
  Wifi,
  WifiOff,
  ChevronDown,
  ChevronUp,
  Clock,
  Activity,
  Key,
  Copy,
  Eye,
  EyeOff,
  Shield,
  MapPin,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import EventLog from "../components/EventLog";
import { openExternal } from "../lib/openExternal";


// Pi-Health-Panel: LTE-IP, Signal, Provider, HAT-Stack, GPS pro Pi
function PiHealthPanel({ health }) {
  if (!health) return null;
  const csq = health.lte_csq;
  const dbm = health.lte_signal_dbm;
  const sigColor =
    csq == null || csq === 99 ? "bg-gray-200 text-gray-600"
      : csq >= 20 ? "bg-emerald-100 text-emerald-700"
      : csq >= 10 ? "bg-amber-100 text-amber-700"
      : "bg-red-100 text-red-700";
  const sigLabel = csq == null || csq === 99 ? "—" : `${csq}/31`;
  const recvSecs = health.received_at
    ? Math.round((Date.now() - new Date(health.received_at).getTime()) / 1000)
    : null;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-3" data-testid="pi-health-panel">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Pi-Status</p>
        {recvSecs !== null && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${recvSecs < 120 ? "bg-emerald-100 text-emerald-700" : recvSecs < 600 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
            {recvSecs < 60 ? `${recvSecs}s` : recvSecs < 3600 ? `${Math.round(recvSecs/60)}m` : `${Math.round(recvSecs/3600)}h`} her
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
        <HealthCell label="LTE-IP" value={health.lte_ip || "—"} mono />
        <HealthCell
          label="Signal"
          value={
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${sigColor}`}>
              {sigLabel}{dbm ? ` (${dbm} dBm)` : ""}
            </span>
          }
        />
        <HealthCell label="Provider" value={health.lte_operator ? `${health.lte_operator} ${health.lte_act || ""}`.trim() : "—"} />
        <HealthCell label="HAT-Stack" value={health.hat_stack !== null && health.hat_stack !== undefined ? `Lvl ${health.hat_stack}` : "—"} mono />
        <HealthCell label="GPS-Fix" value={
          health.gps_lat
            ? `${Number(health.gps_lat).toFixed(4)}, ${Number(health.gps_lon).toFixed(4)} (${health.gps_mode === 3 ? "3D" : health.gps_mode === 2 ? "2D" : "?"})`
            : "—"
        } />
        <HealthCell label="Pi-Version" value={health.script_version || "—"} mono />
        <HealthCell label="Hostname" value={health.hostname || "—"} mono />
        <HealthCell label="Pi-ID" value={health.pi_id ? health.pi_id.slice(0, 8) + "…" : "—"} mono />
      </div>

      {Array.isArray(health.meters) && health.meters.length > 0 && (
        <div className="mt-3 border-t border-gray-200 pt-2">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Live-Zaehlerstaende</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-3 gap-y-1">
            {health.meters.map((m) => (
              <div key={m.meter_id} className="text-[11px] flex items-baseline gap-1.5">
                <span className="text-gray-500 font-mono">K{m.channel}</span>
                <span className="font-semibold text-gray-800 font-mono">{Number(m.kwh_total ?? 0).toFixed(3)}</span>
                <span className="text-[9px] text-gray-400">kWh</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HealthCell({ label, value, mono }) {
  return (
    <div className="bg-white border border-gray-100 rounded px-2 py-1">
      <p className="text-[9px] text-gray-400 uppercase tracking-wider">{label}</p>
      <p className={`text-[11px] text-gray-800 ${mono ? "font-mono" : "font-medium"} truncate`}>{value}</p>
    </div>
  );
}


// Pi Setup Section for Messkoffer / Kirmeskiste (Standard 4-Meter / 8Z S0-Pulse)
function PiSetupSection({ deviceId, deviceName, deviceType, kirmeskisteVariant }) {
  const [loading, setLoading] = useState(false);
  const [wgetCommand, setWgetCommand] = useState(null);
  const isKirmeskiste = deviceType === "kirmeskiste";
  const is8Z = isKirmeskiste && kirmeskisteVariant === "8z";

  const handleGenerateSetup = async () => {
    if (!window.confirm("Ein neuer Geräteschlüssel wird generiert und in das Setup-Skript eingebettet.\n\nFalls bereits ein Schlüssel existiert, wird er ersetzt.\n\nFortfahren?")) return;
    setLoading(true);
    try {
      const endpoint = is8Z
        ? `/energy-monitoring/devices/${deviceId}/kirmeskiste-8z-setup`
        : isKirmeskiste
        ? `/energy-monitoring/devices/${deviceId}/kirmeskiste-setup`
        : `/energy-monitoring/devices/${deviceId}/setup-script`;
      const res = await api.post(endpoint);
      const url = res.data.download_url;
      setWgetCommand(`wget "${url}" -O setup.sh && sudo bash setup.sh`);
      toast.success("Setup-Skript generiert!");
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Unbekannter Fehler";
      toast.error(`Fehler beim Generieren des Setup-Skripts: ${detail}`);
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
        {is8Z
          ? "Generiert ein Installations-Skript fuer Pi 5 + Sequent 16-LV HAT + SIM7600 LTE/GPS + 8x ABB D11/D13 (S0-Pulse). Inkl. lokaler DB, Telekom APN, OTA-Auto-Update."
          : isKirmeskiste
          ? "Generiert ein Installations-Skript mit 4x EMU Pro II Modbus-Anbindung, GPS, lokaler Datenbank und Portal-Sync."
          : "Generiert ein Installations-Skript mit Shelly-Logger, GPS-Anbindung, lokaler Datenbank und Portal-Sync."}
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
      <p className="text-[10px] text-gray-400 mt-2">
        {is8Z
          ? "Enthält: Sequent-CLI + S0-Pulse-Logger + SIM7600 LTE/GPS + Lokale DB + Schlüssel + OTA + Systemd"
          : isKirmeskiste
          ? "Enthält: 4x EMU Modbus-Logger + GPS + Lokale DB + Schlüssel + Systemd-Dienst"
          : "Enthält: Shelly-Logger + GPS + Lokale DB + Schlüssel + Systemd-Dienst"}
      </p>

      {/* 8Z: kWh-Anfangsstaende eintragen + 8 QR-Print-Buttons */}
      {is8Z && (
        <Kirmeskiste8zMeterPanel deviceId={deviceId} />
      )}

      {/* Standard Kirmeskiste 4-Meter: feste IPs + 4 QR-Print-Buttons */}
      {isKirmeskiste && !is8Z && (
        <div className="mt-3 bg-gray-50 rounded-lg border border-gray-200 p-3">
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Feste LAN-Adressen</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] font-mono text-gray-600">
            <span>Zaehler 1: 192.168.88.240</span>
            <span>Zaehler 2: 192.168.88.241</span>
            <span>Zaehler 3: 192.168.88.242</span>
            <span>Zaehler 4: 192.168.88.243</span>
            <span className="col-span-2 mt-1 text-gray-500">Pi: 192.168.88.249</span>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-3">
            {[1,2,3,4].map(i => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                className="text-xs text-gray-600 hover:text-fuchsia-600"
                data-testid={`print-label-${i}`}
                onClick={async (e) => {
                  e.preventDefault();
                  try {
                    const resp = await fetch(`${BACKEND_URL}/api/kirmes/devices/${deviceId}/print-label/${i}`, {
                      method: "POST",
                      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
                    });
                    if (!resp.ok) {
                      const err = await resp.json().catch(() => ({}));
                      throw new Error(err.detail || "Druckfehler");
                    }
                    const contentType = resp.headers.get("content-type");
                    if (contentType && contentType.includes("application/json")) {
                      const data = await resp.json();
                      toast.success(data.message || `Zaehler ${i} gedruckt`);
                    } else {
                      const printError = resp.headers.get("x-print-error");
                      const blob = await resp.blob();
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `label_zaehler_${i}.png`;
                      a.click();
                      window.URL.revokeObjectURL(url);
                      if (printError) {
                        toast.error(`Drucker-Fehler: ${printError}. Label als Bild heruntergeladen.`);
                      } else {
                        toast.info("Kein Drucker konfiguriert. Label als Bild heruntergeladen.");
                      }
                    }
                  } catch (err) { toast.error(err.message || "Label konnte nicht gedruckt werden"); }
                }}
              >
                <Printer className="w-3 h-3 mr-1" /> Zaehler {i}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// Kirmeskiste 8 Zaehler: Anfangs-kWh-Staende + QR-Druck
function Kirmeskiste8zMeterPanel({ deviceId }) {
  const [meters, setMeters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);

  const loadMeters = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/energy-monitoring/devices/${deviceId}/meters`);
      // Sort by hat_channel (or meter_name fallback)
      const sorted = [...res.data].sort((a, b) => {
        const ca = a.hat_channel ?? 99, cb = b.hat_channel ?? 99;
        if (ca !== cb) return ca - cb;
        return (a.meter_name || "").localeCompare(b.meter_name || "");
      });
      setMeters(sorted);
    } catch (err) {
      // Wenn noch keine Meter existieren: leeres Array
      setMeters([]);
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  useEffect(() => { loadMeters(); }, [loadMeters]);

  const updateOffset = async (meter, val) => {
    setSavingId(meter.id);
    try {
      const kwh = parseFloat(String(val).replace(",", "."));
      if (Number.isNaN(kwh) || kwh < 0) {
        toast.error("Ungueltiger kWh-Wert");
        return;
      }
      await api.put(
        `/energy-monitoring/devices/${deviceId}/meters/${meter.id}/kwh-offset`,
        { kwh_offset: kwh }
      );
      toast.success(`${meter.meter_name}: Anfangsstand gespeichert`);
      loadMeters();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Speichern fehlgeschlagen");
    } finally {
      setSavingId(null);
    }
  };

  const printLabel = async (idx) => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/kirmes/devices/${deviceId}/print-label/${idx}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || "Druckfehler");
      }
      const ct = resp.headers.get("content-type");
      if (ct && ct.includes("application/json")) {
        const data = await resp.json();
        toast.success(data.message || `Zaehler ${idx} gedruckt`);
      } else {
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `label_zaehler_${idx}.png`;
        a.click();
        window.URL.revokeObjectURL(url);
        toast.info("Kein Drucker konfiguriert. Label als Bild heruntergeladen.");
      }
    } catch (err) {
      toast.error(err.message || "Label konnte nicht gedruckt werden");
    }
  };

  if (loading) {
    return <p className="mt-3 text-[11px] text-gray-400">Zaehler werden geladen...</p>;
  }

  if (!meters.length) {
    return (
      <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3">
        <p className="text-[11px] text-amber-700">
          Noch keine Zaehler angelegt. Klicke "Setup generieren" – die 8 Zaehler werden dann automatisch erstellt.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 bg-gray-50 rounded-lg border border-gray-200 p-3" data-testid="kirmeskiste-8z-meter-panel">
      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Zaehler ({meters.length}) – Anfangsstand vom Display ablesen
      </p>
      <div className="space-y-1.5">
        {meters.slice(0, 8).map((m, idx) => {
          const channel = m.hat_channel ?? (idx + 1);
          return (
            <MeterOffsetRow
              key={m.id}
              meter={m}
              channel={channel}
              index={idx + 1}
              saving={savingId === m.id}
              onSave={(val) => updateOffset(m, val)}
              onPrint={() => printLabel(idx + 1)}
            />
          );
        })}
      </div>
      <p className="text-[10px] text-gray-400 mt-2">
        Hinweis: Der Pi zaehlt die Pulse autark weiter – der Anfangsstand wird beim ersten Sync uebernommen.
        Pulses/kWh werden auf dem Pi konfiguriert (Default 1000).
      </p>
    </div>
  );
}


function MeterOffsetRow({ meter, channel, index, saving, onSave, onPrint }) {
  const [val, setVal] = useState(
    meter.kwh_offset !== undefined && meter.kwh_offset !== null
      ? String(meter.kwh_offset).replace(".", ",")
      : ""
  );
  return (
    <div className="grid grid-cols-12 gap-2 items-center text-[11px]">
      <div className="col-span-1 font-mono text-gray-500 text-center">K{channel}</div>
      <div className="col-span-4 font-medium text-gray-700 truncate" title={meter.meter_name}>
        {meter.meter_name || `Zaehler ${index}`}
      </div>
      <div className="col-span-4">
        <Input
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onBlur={() => {
            const cur = (meter.kwh_offset !== undefined && meter.kwh_offset !== null)
              ? String(meter.kwh_offset).replace(".", ",")
              : "";
            if (val !== cur) onSave(val);
          }}
          placeholder="0,000"
          className="h-7 text-[11px] py-1"
          data-testid={`meter-offset-input-${index}`}
        />
      </div>
      <div className="col-span-1 text-gray-400 text-[10px]">kWh</div>
      <div className="col-span-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full h-7 text-[10px] text-gray-600 hover:text-fuchsia-600 px-1"
          onClick={onPrint}
          disabled={saving}
          data-testid={`print-label-8z-${index}`}
        >
          <Printer className="w-3 h-3 mr-1" /> QR
        </Button>
      </div>
    </div>
  );
}


// Pi Setup for DSE Controllers via USB/RS232 Modbus RTU
// Match flexibel: "DSE 8610", "DSE 8610 MKII", "DSE 8610 MK2", etc.
const PI_CONTROLLERS_EXACT = ["DSE 5510", "DSE 8610", "DSE 8610 MKII", "DSE 7310", "DSE L401", "DSE 4520 MKII"];
function isPiController(ctrl) {
  if (!ctrl) return false;
  const c = ctrl.toUpperCase().trim();
  if (PI_CONTROLLERS_EXACT.includes(ctrl)) return true;
  // Flexible match: "DSE 8610 ...", "DSE 7310 ...", "DSE L401 ...", "DSE 5510 ..."
  return /DSE\s*(8610|7310|L401|5510)/i.test(c);
}
function DSEPiSetupSection({ deviceId, deviceName, controller, connectionType }) {
  const [loading, setLoading] = useState(false);
  const [wgetCommand, setWgetCommand] = useState(null);
  const isUsbDirect = connectionType === "pi_usb";
  const [serialPort, setSerialPort] = useState(isUsbDirect ? "usb" : "/dev/ttyUSB0");
  const [baudRate, setBaudRate] = useState(19200);
  const [slaveId, setSlaveId] = useState(isUsbDirect ? 1 : 10);
  const [enableLte, setEnableLte] = useState(false);
  const [lteApn, setLteApn] = useState("internet.m2mportal.de");
  const [ltePort, setLtePort] = useState("/dev/ttyAMA0");

  const controllerLabel = controller || "DSE";
  const is3Phase = controller && (controller.includes("8610") || controller.includes("7310"));
  const connLabel = isUsbDirect ? "USB direkt" : "DSE USB/LAN Adapter";

  const handleGenerateSetup = async () => {
    if (!window.confirm("Ein neuer Geraeteschluessel wird generiert und in das Setup-Skript eingebettet.\n\nFalls bereits ein Schluessel existiert, wird er ersetzt.\n\nFortfahren?")) return;
    setLoading(true);
    try {
      const res = await api.post(`/energy-monitoring/devices/${deviceId}/dse5510-setup`, {
        serial_port: isUsbDirect ? "usb" : serialPort,
        baud_rate: baudRate,
        slave_id: slaveId,
        enable_lte: enableLte,
        lte_apn: lteApn,
        lte_port: ltePort,
        controller_type: controller,
        connection_type: connectionType,
      });
      setWgetCommand(`wget "${res.data.download_url}" -O setup.sh && sudo bash setup.sh`);
      toast.success(`${controllerLabel} Pi Setup generiert!`);
    } catch (err) {
      toast.error(`Fehler: ${err?.response?.data?.detail || err?.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-t border-gray-100 pt-4" data-testid="dse-pi-setup">
      <div className="flex items-center gap-2 mb-1">
        <Server className="w-4 h-4 text-fuchsia-600" />
        <h3 className="text-sm font-medium text-gray-900">{controllerLabel} Pi Setup ({connLabel})</h3>
      </div>
      <p className="text-[10px] text-gray-400 mb-3">
        {isUsbDirect
          ? `Raspberry Pi liest den ${controllerLabel} direkt ueber USB (pyusb). Kein Adapter noetig.`
          : `Raspberry Pi liest den ${controllerLabel} ueber den DSE USB/LAN Adapter (Modbus RTU).`
        }
      </p>

      {/* Konfigurationsfelder - bei USB direkt nur Slave ID, bei RS232 alles */}
      {isUsbDirect ? (
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="p-2 bg-gray-50 rounded border border-gray-200">
            <Label className="text-gray-500 text-[10px]">Verbindung</Label>
            <p className="text-xs font-medium text-gray-800">USB direkt (pyusb)</p>
          </div>
          <div>
            <Label className="text-gray-600 text-[11px]">Slave ID</Label>
            <Input type="number" value={slaveId} onChange={e => setSlaveId(parseInt(e.target.value) || 1)}
              min={1} max={247}
              className="mt-0.5 text-xs h-[30px]"
              data-testid="dse5510-slave-id" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div>
            <Label className="text-gray-600 text-[11px]">Serieller Port</Label>
            <select value={serialPort} onChange={e => setSerialPort(e.target.value)}
              className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs bg-white"
              data-testid="dse5510-serial-port">
              <option value="/dev/ttyUSB0">/dev/ttyUSB0</option>
              <option value="/dev/ttyUSB1">/dev/ttyUSB1</option>
              <option value="/dev/ttyAMA0">/dev/ttyAMA0</option>
              <option value="/dev/ttyS0">/dev/ttyS0</option>
            </select>
          </div>
          <div>
            <Label className="text-gray-600 text-[11px]">Baud Rate</Label>
            <select value={baudRate} onChange={e => setBaudRate(parseInt(e.target.value))}
              className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs bg-white"
              data-testid="dse5510-baud-rate">
              <option value={9600}>9600</option>
              <option value={19200}>19200</option>
              <option value={38400}>38400</option>
              <option value={115200}>115200</option>
            </select>
          </div>
          <div>
            <Label className="text-gray-600 text-[11px]">Slave ID</Label>
            <Input type="number" value={slaveId} onChange={e => setSlaveId(parseInt(e.target.value) || 10)}
              min={1} max={247}
              className="mt-0.5 text-xs h-[30px]"
              data-testid="dse5510-slave-id" />
          </div>
        </div>
      )}

      {/* LTE Konfiguration (SIM7600E-H) */}
      <div className="mt-3 border-t border-gray-100 pt-3">
        <label className="flex items-center gap-2 cursor-pointer" data-testid="dse5510-enable-lte">
          <input type="checkbox" checked={enableLte} onChange={e => setEnableLte(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500" />
          <span className="text-xs font-medium text-gray-700">LTE-Modem (SIM7600E-H)</span>
        </label>
        {enableLte && (
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <Label className="text-gray-600 text-[11px]">APN</Label>
              <Input type="text" value={lteApn} onChange={e => setLteApn(e.target.value)}
                className="mt-0.5 text-xs h-[30px]"
                data-testid="dse5510-lte-apn" />
            </div>
            <div>
              <Label className="text-gray-600 text-[11px]">Modem Port</Label>
              <select value={ltePort} onChange={e => setLtePort(e.target.value)}
                className="w-full mt-0.5 px-2 py-1.5 border border-gray-200 rounded text-xs bg-white"
                data-testid="dse5510-lte-port">
                <option value="/dev/ttyAMA0">/dev/ttyAMA0</option>
                <option value="/dev/serial0">/dev/serial0</option>
                <option value="/dev/ttyS0">/dev/ttyS0</option>
                <option value="/dev/ttyUSB2">/dev/ttyUSB2</option>
                <option value="/dev/ttyUSB3">/dev/ttyUSB3</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {wgetCommand && (
        <div className="mb-3 bg-emerald-50 border border-emerald-200 rounded-lg p-3" data-testid="dse5510-setup-instructions">
          <p className="text-xs text-emerald-800 font-medium mb-2">Diesen Befehl auf dem Pi ausfuehren:</p>
          <div className="flex items-start gap-2">
            <code className="flex-1 bg-white border border-emerald-300 px-3 py-2 rounded text-[11px] font-mono select-all break-all leading-relaxed">{wgetCommand}</code>
            <button onClick={() => { navigator.clipboard.writeText(wgetCommand); toast.success("Kopiert!"); }}
              className="shrink-0 px-2 py-2 bg-white border border-emerald-300 rounded hover:bg-emerald-100"
              data-testid="dse5510-copy-wget-btn" title="Kopieren">
              <Download className="w-4 h-4 text-emerald-600" />
            </button>
          </div>
          <p className="text-[10px] text-emerald-600 mt-2">Link ist 1 Stunde gueltig.</p>
        </div>
      )}

      <Button variant="outline" size="sm" onClick={handleGenerateSetup} disabled={loading}
        className="text-gray-600 hover:text-fuchsia-600" data-testid="dse5510-generate-setup-btn">
        <Download className="w-3.5 h-3.5 mr-1.5" />
        {loading ? "Wird generiert..." : "Setup generieren"}
      </Button>
      <p className="text-[10px] text-gray-400 mt-2">
        Enthält: USB Modbus RTU + GPS + Steuerung (Start/Stop/Auto) + Lokale DB + Systemd-Dienst
        {enableLte && " + LTE-Failover + gpsd (SIM7600E-H)"}
      </p>

      <div className="mt-3 bg-gray-50 rounded-lg border border-gray-200 p-3">
        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Modbus Register (GenComm)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] text-gray-600">
          <span>Page 4: Grundwerte (V, A, W, Hz, RPM)</span>
          <span>Page 6: Leistungsfaktor, kW</span>
          <span>Page 7: Betriebsstunden, kWh, Starts</span>
          <span>Page 8: Alarm-Codes (52 Alarme)</span>
          <span>Page 16: Steuerung (Start/Stop/Auto)</span>
          {is3Phase && <span>L1/L2/L3: Spannung, Strom, Leistung</span>}
        </div>
        <div className="mt-2 text-[11px] text-gray-600">
          <span className="font-medium">Steuerbefehle:</span> Stop, Auto, Manuell, Start, Generator Ein/Aus
        </div>
        {enableLte && (
          <div className="mt-2 pt-2 border-t border-gray-200 text-[11px] text-gray-600">
            <span className="font-medium">LTE Port-Schema:</span> ttyUSB2=GPS (gpsd), ttyUSB3=AT+PPP
            <br />
            <span className="font-medium">Routing:</span> eth0 (Metric 100) → wlan0 (600) → ppp0 (700)
            <br />
            <span className="font-medium">Tools:</span> lte-status, gps-status
          </div>
        )}
      </div>
    </div>
  );
}

const CONTROLLER_OPTIONS = ["DSE 8610 MKII", "DSE 8610", "DSE 4520 MKII", "DSE 7310", "DSE L401", "DSE 5510"];
const UNIVERSAL_TOPIC_LABEL = "DSE Universal Module Topics";

function MqttCopyRow({ label, value, copyValue, highlight = false }) {
  const toCopy = copyValue !== undefined ? copyValue : value;
  const handleCopy = () => {
    navigator.clipboard.writeText(toCopy);
    toast.success(`${label} kopiert`);
  };
  const wrap = highlight
    ? "flex justify-between items-center bg-amber-50 px-2 py-1.5 rounded border border-amber-200"
    : "flex justify-between items-center bg-white px-2 py-1.5 rounded border border-gray-100";
  const labelCls = highlight ? "text-amber-600" : "text-gray-400";
  const valCls = highlight ? "text-amber-800 font-semibold select-all" : "text-gray-900 select-all";
  return (
    <div className={wrap}>
      <span className={labelCls}>{label}</span>
      <div className="flex items-center gap-2">
        <span className={valCls}>{value}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="text-gray-400 hover:text-fuchsia-600 transition-colors"
          title={`${label} kopieren`}
          data-testid={`copy-mqtt-${label.replace(/\s+/g, "-").toLowerCase()}`}
        >
          <Copy className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

function DseGatewaySetupSection({ controller, serialNumber, formData, update, deviceId }) {
  // All DSE controllers use the same universal GenComm topic file
  const topicInfo = controller ? { filename: "dse_universal_module_topics.csv", label: UNIVERSAL_TOPIC_LABEL } : null;
  const brokerUrl = "217.86.214.29";
  const brokerPort = "1883";
  const groupName = "eventenergie";

  const [credInfo, setCredInfo] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [newCreds, setNewCreds] = useState(null);
  const [showPw, setShowPw] = useState(false);

  useEffect(() => {
    if (!deviceId) return;
    (async () => {
      try {
        const res = await api.get(`/mqtt/device-credentials/${deviceId}`);
        setCredInfo(res.data);
      } catch { setCredInfo(null); }
    })();
  }, [deviceId]);

  const handleGenerate = async () => {
    if (credInfo?.has_credentials && !window.confirm("Vorhandene Zugangsdaten werden ersetzt. Fortfahren?")) return;
    setGenerating(true);
    try {
      const res = await api.post(`/mqtt/device-credentials/${deviceId}/generate`, {});
      setNewCreds(res.data);
      setShowPw(true);
      setCredInfo({ has_credentials: true, mqtt_username: res.data.username, created_at: new Date().toISOString() });
      toast.success("MQTT-Zugangsdaten generiert");
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Generieren"));
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async () => {
    if (!window.confirm("MQTT-Zugangsdaten wirklich widerrufen? Das Gateway verliert den Zugang.")) return;
    try {
      await api.delete(`/mqtt/device-credentials/${deviceId}`);
      setCredInfo({ has_credentials: false, mqtt_username: "", created_at: "" });
      setNewCreds(null);
      toast.success("Zugangsdaten widerrufen");
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler"));
    }
  };

  const handleDownloadModuleTopics = () => {
    if (!controller || !topicInfo) return;
    openExternal(`${BACKEND_URL}/api/download-controller-topics/${encodeURIComponent(controller)}?t=${Date.now()}`);
  };

  const handleDownloadGatewayTopics = () => {
    openExternal(`${BACKEND_URL}/api/download-dse890-gateway-topics?t=${Date.now()}`);
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
          <MqttCopyRow label="Broker URL" value={brokerUrl} />
          <MqttCopyRow label="Port" value={String(brokerPort)} />
          <MqttCopyRow label="Connection Method" value="GSM" />
          <MqttCopyRow label="Clean Session" value="Ja (Haken setzen)" copyValue="true" />
          <MqttCopyRow label="Keep Alive" value="60" />
          <MqttCopyRow label="Group Name" value={groupName} highlight />
          <MqttCopyRow label="Use Login Credentials" value="Ja (Haken setzen)" copyValue="true" />
          <MqttCopyRow label="Use Secure MQTT" value="Nein" copyValue="false" />
        </div>
        <p className="text-[10px] text-amber-600 mt-2 font-medium">
          Alle Einstellungen unter DSE890 &gt; MQTT-Tab eintragen. Username und Password unten generieren und dort einfuegen.
        </p>
      </div>

      {/* LTE / GSM Settings */}
      <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 mb-3" data-testid="dse-lte-info">
        <p className="text-xs text-sky-700 font-medium mb-2 flex items-center gap-1.5">
          <Wifi className="w-3.5 h-3.5" /> LTE / GSM-Einstellungen im DSE890
        </p>
        <div className="space-y-1.5 text-xs font-mono">
          <MqttCopyRow label="Anbieter" value="Telekom" />
          <MqttCopyRow label="PIN" value="0000" />
          <MqttCopyRow label="APN" value="internet.m2mportal.de" />
        </div>
        <p className="text-[10px] text-sky-700 mt-2 leading-snug">
          Einstellungen unter DSE890 &gt; <b>GSM/LTE</b> (bzw. "Mobile Network") eintragen. Die SIM-Karte muss vorher in das Gateway eingesetzt sein.
        </p>
      </div>

      {/* MQTT Credentials */}
      {deviceId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3" data-testid="dse-module-uid-section">
          <p className="text-xs text-blue-700 font-medium mb-2 flex items-center gap-1.5">
            <Wifi className="w-3.5 h-3.5" /> USB ID des DSE-Moduls (für automatische MQTT-Zuordnung)
          </p>
          <Input
            value={formData.dse_module_uid || ""}
            onChange={e => update("dse_module_uid", e.target.value.trim())}
            placeholder="z.B. 692CCDE18D (USB ID aus DSE890 → Modules Connection)"
            className="font-mono text-sm"
            data-testid="dse-module-uid-input"
          />
          <p className="text-[10px] text-gray-400 mt-1">
            Die USB ID finden Sie im DSE890 Web-Interface unter "Modules Connection" in der Spalte "USB ID". Nicht die Gateway USBID aus dem Status-Tab verwenden!
          </p>

          {formData.dse_module_uid ? (
            <div className="mt-3 pt-3 border-t border-blue-200" data-testid="mqtt-clientid-hint">
              <p className="text-xs text-blue-700 font-medium mb-1.5 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5" /> MQTT Client Identifier (Pflichtfeld im DSE890 Gateway!)
              </p>
              <div className="flex items-center gap-2 bg-white px-2 py-1.5 rounded border border-blue-200">
                <span className="text-gray-900 font-mono text-sm select-all flex-1" data-testid="mqtt-client-id-value">
                  {`gw_${String(formData.dse_module_uid).trim()}`.slice(0, 23)}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    const v = `gw_${String(formData.dse_module_uid).trim()}`.slice(0, 23);
                    navigator.clipboard.writeText(v);
                    toast.success("Client-ID kopiert");
                  }}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="copy-client-id-btn"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[10px] text-amber-700 mt-1.5 leading-snug">
                ⚠️ Diesen Wert im DSE890 Web-Interface unter <b>MQTT Settings → Client Identifier</b> (bzw. "Client ID") eintragen. Ohne eindeutige Client-ID verweigert der Broker die Verbindung (MQTT-3.1.1-Spec).
              </p>
            </div>
          ) : (
            <div className="mt-3 pt-3 border-t border-blue-200 bg-amber-50 -mx-3 -mb-3 px-3 py-2 rounded-b-lg" data-testid="mqtt-clientid-missing">
              <p className="text-xs text-amber-700 font-medium flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5" /> MQTT Client Identifier noch nicht verfügbar
              </p>
              <p className="text-[11px] text-amber-800 mt-1 leading-snug">
                Bitte zuerst oben die <b>USB-ID des DSE-Moduls</b> eintragen. Sobald die USB-ID gesetzt ist, erscheint hier die Client-ID (z.B. <span className="font-mono">gw_6D2CCDC779</span>), die Sie im DSE890-Gateway einfügen müssen.
              </p>
            </div>
          )}
        </div>
      )}

      {/* MQTT Auth Credentials */}
      {deviceId && (
        <div className="bg-violet-50 border border-violet-200 rounded-lg p-3 mb-3" data-testid="dse-mqtt-credentials">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-violet-700 font-medium flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" /> MQTT-Zugangsdaten
            </p>
            <div className="flex items-center gap-1.5">
              <Button size="sm" variant={credInfo?.has_credentials ? "outline" : "default"} onClick={handleGenerate} disabled={generating} className="h-7 text-xs" data-testid="generate-device-cred-btn">
                {generating ? <span className="animate-spin mr-1">...</span> : <Key className="w-3 h-3 mr-1" />}
                {credInfo?.has_credentials ? "Neu generieren" : "Generieren"}
              </Button>
              {credInfo?.has_credentials && (
                <Button size="sm" variant="ghost" onClick={handleRevoke} className="h-7 text-xs text-red-500 hover:text-red-700" data-testid="revoke-device-cred-btn">
                  <Trash2 className="w-3 h-3" />
                </Button>
              )}
            </div>
          </div>
          <p className="text-[10px] text-gray-500 mb-2">
            Username wird automatisch aus der Seriennummer abgeleitet (z.B. <b>ml_254</b> → <b>gw_ml_254</b>). Beim Kopieren zuerst die Seriennummer oben ändern, dann Zugangsdaten generieren.
          </p>

          {newCreds ? (
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between items-center bg-white px-2 py-1.5 rounded border border-violet-100">
                <span className="text-gray-400">Username</span>
                <div className="flex items-center gap-1">
                  <span className="text-gray-900 select-all" data-testid="device-mqtt-username">{newCreds.username}</span>
                  <button onClick={() => { navigator.clipboard.writeText(newCreds.username); toast.success("Kopiert"); }} className="text-gray-400 hover:text-gray-600"><Copy className="w-3 h-3" /></button>
                </div>
              </div>
              <div className="flex justify-between items-center bg-white px-2 py-1.5 rounded border border-violet-100">
                <span className="text-gray-400">Password</span>
                <div className="flex items-center gap-1">
                  <span className="text-gray-900 select-all" data-testid="device-mqtt-password">{showPw ? newCreds.password : "••••••••••••"}</span>
                  <button onClick={() => setShowPw(!showPw)} className="text-gray-400 hover:text-gray-600">{showPw ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}</button>
                  <button onClick={() => { navigator.clipboard.writeText(newCreds.password); toast.success("Kopiert"); }} className="text-gray-400 hover:text-gray-600"><Copy className="w-3 h-3" /></button>
                </div>
              </div>
              <p className="text-[10px] text-amber-600 font-medium mt-1">Passwort wird nur jetzt angezeigt! Bitte sofort kopieren.</p>
            </div>
          ) : credInfo?.has_credentials ? (
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between items-center bg-white px-2 py-1.5 rounded border border-violet-100">
                <span className="text-gray-400">Username</span>
                <span className="text-gray-900 select-all">{credInfo.mqtt_username}</span>
              </div>
              <div className="flex justify-between items-center bg-white px-2 py-1.5 rounded border border-violet-100">
                <span className="text-gray-400">Password</span>
                <span className="text-gray-400 italic">••••••••  (gespeichert)</span>
              </div>
              <p className="text-[10px] text-gray-400">Erstellt: {new Date(credInfo.created_at).toLocaleString("de-DE")}</p>
            </div>
          ) : (
            <p className="text-[10px] text-gray-400">Noch keine Zugangsdaten. Klicken Sie "Generieren" um Username und Passwort zu erstellen.</p>
          )}
        </div>
      )}

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
  { value: "verteiler", label: "Verteiler", icon: Settings },
];

// Online status helper: online < 10min, idle < 1h, offline > 1h
function getOnlineStatus(lastSeen) {
  if (!lastSeen) return { status: "unknown", label: "Nie verbunden", color: "bg-gray-300", textColor: "text-gray-400" };
  const diff = Date.now() - new Date(lastSeen).getTime();
  const minutes = diff / 60000;
  if (minutes < 10) return { status: "online", label: "Online", color: "bg-emerald-500", textColor: "text-emerald-600" };
  if (minutes < 60) return { status: "idle", label: "Inaktiv", color: "bg-amber-400", textColor: "text-amber-600" };
  return { status: "offline", label: "Offline", color: "bg-red-400", textColor: "text-red-500" };
}

function formatLastSeen(lastSeen) {
  if (!lastSeen) return "–";
  const diff = Date.now() - new Date(lastSeen).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  return `vor ${days} Tag${days > 1 ? "en" : ""}`;
}

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
  dse_module_uid: "",
  kirmeskiste_variant: "standard",
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
  const [partCustomMode, setPartCustomMode] = useState(false);
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
      const KNOWN = ["DSE 8610 MKII", "DSE 8610", "DSE 4520 MKII", "DSE 7310", "DSE L401", "DSE 5510"];
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
      setPartCustomMode(false);
      setShowAddPart(false);
      loadParts();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
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
      kirmeskiste_variant: device.kirmeskiste_variant || "standard",
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
          {!editing && allDevices && allDevices.length > 0 && (
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
                  onClick={async () => {
                    try {
                      const resp = await fetch(`${BACKEND_URL}/api/kirmes/devices/${editing.id}/print-device-label`, {
                        method: "POST",
                        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
                      });
                      if (!resp.ok) {
                        const err = await resp.json().catch(() => ({}));
                        throw new Error(err.detail || "Druckfehler");
                      }
                      const contentType = resp.headers.get("content-type");
                      if (contentType && contentType.includes("application/json")) {
                        const data = await resp.json();
                        toast.success(data.message || "Label gedruckt");
                      } else {
                        const printError = resp.headers.get("x-print-error");
                        const blob = await resp.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `label_${editing.device_code}.png`;
                        a.click();
                        window.URL.revokeObjectURL(url);
                        toast.info(printError ? `Drucker-Fehler: ${printError}` : "Kein Drucker konfiguriert - Label heruntergeladen");
                      }
                    } catch (err) { toast.error(err.message || "Label konnte nicht gedruckt werden"); }
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
                        value={partCustomMode ? "__custom" : (PART_TYPES.includes(newPart.part_type) ? newPart.part_type : "")}
                        onChange={e => {
                          if (e.target.value === "__custom") {
                            setPartCustomMode(true);
                            setNewPart(p => ({ ...p, part_type: "" }));
                          } else {
                            setPartCustomMode(false);
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
                      {partCustomMode && (
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
          )}

          {/* Kirmeskiste-Variante: Sub-Selektor (nur wenn device_type === "kirmeskiste") */}
          {formData.device_type === "kirmeskiste" && (
            <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/40 p-3">
              <Label className="text-gray-700 text-sm mb-2 block">Variante</Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => update("kirmeskiste_variant", "standard")}
                  className={`p-3 rounded-lg border text-center text-xs font-medium transition-colors ${
                    (formData.kirmeskiste_variant || "standard") === "standard"
                      ? "border-fuchsia-500 bg-white text-fuchsia-700"
                      : "border-gray-200 bg-white/70 text-gray-500 hover:border-gray-300"
                  }`}
                  data-testid="kirmeskiste-variant-standard"
                >
                  <div className="font-semibold">Kirmeskiste</div>
                  <div className="text-[10px] text-gray-400 mt-0.5">Bestehende Variante (Live)</div>
                </button>
                <button
                  type="button"
                  onClick={() => update("kirmeskiste_variant", "8z")}
                  className={`p-3 rounded-lg border text-center text-xs font-medium transition-colors ${
                    formData.kirmeskiste_variant === "8z"
                      ? "border-fuchsia-500 bg-white text-fuchsia-700"
                      : "border-gray-200 bg-white/70 text-gray-500 hover:border-gray-300"
                  }`}
                  data-testid="kirmeskiste-variant-8z"
                >
                  <div className="font-semibold">Kirmeskiste 8 Zähler</div>
                  <div className="text-[10px] text-gray-400 mt-0.5">SIM7600 LTE+GPS · HAT · 8 Impuls-Zähler</div>
                </button>
              </div>
            </div>
          )}

          {/* Common Fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-gray-700 text-sm">{formData.device_type === "messkoffer" ? "Gerätenummer" : "Seriennummer"} *</Label>
              <Input value={formData.serial_number} onChange={e => update("serial_number", e.target.value)} className="mt-1" data-testid="serial-input" />
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
                    <Input value={formData.model} onChange={e => update("model", e.target.value)} className="mt-1" data-testid="model-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Baujahr</Label>
                    <Input type="number" value={formData.year_of_manufacture} onChange={e => update("year_of_manufacture", e.target.value)} className="mt-1" data-testid="year-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Leistung</Label>
                    <Input value={formData.power_output} onChange={e => update("power_output", e.target.value)} placeholder="z.B. 400 kVA" className="mt-1" data-testid="power-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Steuerung</Label>
                    {(() => {
                      const CONTROLLER_OPTIONS = ["DSE 8610 MKII", "DSE 8610", "DSE 4520 MKII", "DSE 7310", "DSE L401", "DSE 5510"];
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
                            data-testid="controller-select"
                          >
                            <option value="">Steuerung wählen...</option>
                            {CONTROLLER_OPTIONS.map(opt => <option key={opt} value={opt}>{opt === "DSE 5510" ? "DSE 5510 (Pi)" : opt}</option>)}
                            <option value="__custom">Sonstige (Freitext)...</option>
                          </select>
                          {controllerCustomMode && (
                            <Input
                              value={formData.controller}
                              onChange={e => update("controller", e.target.value)}
                              placeholder="Steuerung eingeben..."
                              className="mt-1"
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
                    <Input value={formData.engine_manufacturer} onChange={e => update("engine_manufacturer", e.target.value)} className="mt-1" data-testid="engine-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.engine_type} onChange={e => update("engine_type", e.target.value)} className="mt-1" data-testid="engine-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Motornummer</Label>
                    <Input value={formData.engine_number} onChange={e => update("engine_number", e.target.value)} className="mt-1" data-testid="engine-num-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Generator</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Hersteller</Label>
                    <Input value={formData.generator_manufacturer} onChange={e => update("generator_manufacturer", e.target.value)} className="mt-1" data-testid="gen-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.generator_type} onChange={e => update("generator_type", e.target.value)} className="mt-1" data-testid="gen-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Generatornummer</Label>
                    <Input value={formData.generator_number} onChange={e => update("generator_number", e.target.value)} className="mt-1" data-testid="gen-num-input" />
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

              {/* ===== Anbindung (Connection Type) ===== */}
              {editing && formData.controller && (
                <div className="border-t border-gray-100 pt-4" data-testid="connection-type-section">
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Anbindung</h3>
                  <p className="text-[10px] text-gray-400 mb-3">Wie ist die Steuerung mit dem Portal verbunden?</p>
                  <div className="grid grid-cols-1 gap-2">
                    {!/DSE\s*5510/i.test(formData.controller || "") && (
                      <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${formData.connection_type === "gateway" ? "border-fuchsia-400 bg-fuchsia-50 ring-1 ring-fuchsia-200" : "border-gray-200 hover:border-gray-300"}`}>
                        <input type="radio" name="connection_type" value="gateway" checked={formData.connection_type === "gateway" || !formData.connection_type} onChange={() => update("connection_type", "gateway")} className="mt-0.5" />
                        <div>
                          <span className="text-sm font-medium text-gray-900">DSE 890 Gateway (MQTT)</span>
                          <p className="text-[10px] text-gray-500">Steuerung verbunden ueber DSE 890 Gateway. Daten kommen via MQTT.</p>
                        </div>
                      </label>
                    )}
                    {isPiController(formData.controller) && !/DSE\s*5510/i.test(formData.controller || "") && (
                      <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${formData.connection_type === "pi_usb" ? "border-fuchsia-400 bg-fuchsia-50 ring-1 ring-fuchsia-200" : "border-gray-200 hover:border-gray-300"}`}>
                        <input type="radio" name="connection_type" value="pi_usb" checked={formData.connection_type === "pi_usb"} onChange={() => update("connection_type", "pi_usb")} className="mt-0.5" />
                        <div>
                          <span className="text-sm font-medium text-gray-900">Raspberry Pi + USB direkt</span>
                          <p className="text-[10px] text-gray-500">Steuerung per USB-Kabel direkt am Raspberry Pi. Kein Adapter noetig.</p>
                        </div>
                      </label>
                    )}
                    {/DSE\s*5510/i.test(formData.controller || "") && (
                      <label className={`flex items-start gap-3 p-3 rounded-lg border border-fuchsia-400 bg-fuchsia-50 ring-1 ring-fuchsia-200 cursor-pointer`}>
                        <input type="radio" name="connection_type" value="pi_rs232" checked={true} onChange={() => update("connection_type", "pi_rs232")} className="mt-0.5" />
                        <div>
                          <span className="text-sm font-medium text-gray-900">Raspberry Pi + DSE USB/LAN Adapter</span>
                          <p className="text-[10px] text-gray-500">DSE 5510 ueber den DSE USB/LAN Adapter am Raspberry Pi (Modbus RTU).</p>
                        </div>
                      </label>
                    )}
                  </div>
                </div>
              )}

              {/* DSE890 Gateway Setup - only when "gateway" connection selected */}
              {editing && (formData.connection_type === "gateway" || (!formData.connection_type && !/DSE\s*5510/i.test(formData.controller || ""))) && !/DSE\s*5510/i.test(formData.controller || "") && (
                <DseGatewaySetupSection
                  controller={formData.controller}
                  serialNumber={formData.serial_number}
                  formData={formData}
                  update={update}
                  deviceId={editing.id}
                />
              )}

              {/* DSE Pi Setup - when "pi_usb" or "pi_rs232" connection selected */}
              {editing && (formData.connection_type === "pi_usb" || formData.connection_type === "pi_rs232" || (/DSE\s*5510/i.test(formData.controller || "") && !formData.connection_type)) && (
                <DSEPiSetupSection deviceId={editing.id} deviceName={editing.serial_number} controller={formData.controller} connectionType={/DSE\s*5510/i.test(formData.controller || "") ? "pi_rs232" : (formData.connection_type || "pi_usb")} />
              )}
            </>
          )}

          {/* Messkoffer-specific fields: Pi connection + Setup */}
          {(formData.device_type === "messkoffer" || formData.device_type === "kirmeskiste") && (
            <>
              {/* Pi Setup - all-in-one installer (only for existing devices) */}
              {editing && (
                <PiSetupSection
                  deviceId={editing.id}
                  deviceName={editing.serial_number}
                  deviceType={formData.device_type}
                  kirmeskisteVariant={formData.kirmeskiste_variant || "standard"}
                />
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
                        <button onClick={() => handleDeleteDoc(doc.id)} className="text-gray-400 hover:text-red-500 flex-shrink-0 ml-2" data-testid={`delete-doc-${doc.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
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

// Expandable device detail row
function DeviceExpandedRow({ device, colSpan }) {
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/devices/${device.id}/quick-info`);
        if (!cancelled) setInfo(res.data);
      } catch {
        if (!cancelled) setInfo(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [device.id]);

  const formatDate = (iso) => {
    if (!iso) return "–";
    const d = new Date(iso);
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <tr data-testid={`device-expanded-${device.serial_number}`}>
      <td colSpan={colSpan} className="px-0 py-0">
        <div className="bg-gray-50 border-t border-b border-gray-200 px-6 py-4 animate-in slide-in-from-top-2 duration-200">
          {loading ? (
            <div className="text-xs text-gray-400 py-2">Laden...</div>
          ) : !info ? (
            <div className="text-xs text-gray-400 py-2">Keine Daten verfügbar</div>
          ) : (
            <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Last seen */}
              <div className="flex items-start gap-3" data-testid="quick-info-last-seen">
                <div className="w-8 h-8 rounded-lg bg-fuchsia-100 flex items-center justify-center flex-shrink-0">
                  <Clock className="w-4 h-4 text-fuchsia-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Letzter Kontakt</p>
                  <p className="text-sm font-semibold text-gray-900 mt-0.5">
                    {info.last_seen ? formatDate(info.last_seen) : "Noch nie verbunden"}
                  </p>
                  {info.telemetry_timestamp && (
                    <p className="text-[10px] text-gray-400 mt-0.5">Letzte Telemetrie: {formatDate(info.telemetry_timestamp)}</p>
                  )}
                </div>
              </div>

              {/* Meter Readings - only show if data exists */}
              {info.readings.length > 0 && (
              <div className="flex items-start gap-3" data-testid="quick-info-readings">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                  <Activity className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Zählerstände</p>
                    <div className="space-y-1">
                      {info.readings.map((r, i) => (
                        <div key={i}
                          className={`flex justify-between items-center bg-white rounded px-2.5 py-1.5 border border-gray-100 ${r.meter_id ? "cursor-pointer hover:border-fuchsia-300 hover:bg-fuchsia-50/30 transition-colors" : ""}`}
                          onClick={r.meter_id ? () => navigate(`/devices/${device.id}/meters/${r.meter_id}`) : undefined}
                          data-testid={`reading-${i}`}
                        >
                          <span className="text-xs text-gray-500 truncate mr-2">{r.label}</span>
                          <div className="text-right">
                            <span className="text-xs font-mono font-semibold text-gray-900 whitespace-nowrap">{r.value}</span>
                            {r.timestamp && <p className="text-[9px] text-gray-400">{formatDate(r.timestamp)}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                </div>
              </div>
              )}

              {/* Pi-Health Dashboard (LTE/GPS/HAT pro Pi) */}
              {info.pi_health && (
                <div className="md:col-span-2" data-testid="quick-info-pi-health">
                  <PiHealthPanel health={info.pi_health} />
                </div>
              )}

              {/* GPS Position */}
              {info.gps && info.gps.lat && info.gps.lon && (
                <div className="flex items-start gap-3 md:col-span-2" data-testid="quick-info-gps">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <MapPin className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">GPS Position</p>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono font-semibold text-gray-900">{Number(info.gps.lat).toFixed(6)}, {Number(info.gps.lon).toFixed(6)}</span>
                      <a
                        href={`https://www.google.com/maps?q=${info.gps.lat},${info.gps.lon}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800 underline"
                        onClick={e => e.stopPropagation()}
                      >
                        Google Maps
                      </a>
                    </div>
                    {info.gps.timestamp && (
                      <p className="text-[10px] text-gray-400 mt-0.5">Stand: {formatDate(info.gps.timestamp)}</p>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Ereignisprotokoll */}
            <div className="mt-4" data-testid="device-event-log">
              <EventLog deviceId={device.id} compact />
            </div>
            </>
          )}
        </div>
      </td>
    </tr>
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
  const [expandedId, setExpandedId] = useState(null);

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
      acquired_date: device.acquired_date || "",
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
      dse_module_uid: device.dse_module_uid || "",
      kirmeskiste_variant: device.kirmeskiste_variant || "standard",
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
      toast.error(getErrorMsg(err, "Fehler beim Speichern"));
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
              <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-device-btn">
                <Plus className="w-4 h-4 mr-1" /> Neues Gerät
              </Button>
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
            {devices.length === 0 && (
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
                    <th className="px-4 py-3 text-center">Verbindung</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(device => {
                    const TypeIcon = DEVICE_TYPES.find(t => t.value === device.device_type)?.icon || Settings;
                    const isOutOfService = device.status === "ausser_betrieb";
                    const onlineInfo = getOnlineStatus(device.last_seen);
                    const isExpanded = expandedId === device.id;
                    return (
                      <>
                      <tr key={device.id} onClick={() => setExpandedId(isExpanded ? null : device.id)} className={`border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer ${isOutOfService ? "opacity-60" : ""} ${isExpanded ? "bg-gray-50" : ""}`} data-testid={`device-row-${device.serial_number}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400 transition-transform duration-200" style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0)" }}>
                              <ChevronDown className="w-4 h-4" />
                            </span>
                            {device.image_gridfs_id ? (
                              <img src={`${BACKEND_URL}/api/devices/${device.id}/image?thumbnail=1&size=64`} loading="lazy" alt="" className="w-8 h-8 rounded object-cover border border-gray-200" />
                            ) : (
                              <TypeIcon className="w-4 h-4 text-fuchsia-500" />
                            )}
                            <span className="text-xs text-gray-500">{TYPE_LABELS[device.device_type] || device.device_type}</span>
                            {device.device_type === "kirmeskiste" && device.kirmeskiste_variant === "8z" && (
                              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-fuchsia-100 text-fuchsia-700" title="Kirmeskiste 8 Zähler">8Z</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-gray-900">
                          {device.serial_number}
                          {device.device_code && <span className="block text-[10px] text-gray-400 font-normal">{device.device_code}</span>}
                        </td>
                        <td className="px-4 py-3 text-gray-600 hidden md:table-cell">{device.model || "–"}</td>
                        <td className="px-4 py-3 text-gray-500 hidden md:table-cell truncate max-w-[200px]">{device.user_field || "–"}</td>
                        <td className="px-4 py-3 text-gray-600 hidden lg:table-cell">{device.power_output || "–"}</td>
                        <td className="px-4 py-3 text-center" data-testid={`online-status-${device.serial_number}`}>
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="relative flex h-3 w-3" title={`${onlineInfo.label} - ${formatLastSeen(device.last_seen)}`}>
                              {onlineInfo.status === "online" && (
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              )}
                              <span className={`relative inline-flex rounded-full h-3 w-3 ${onlineInfo.color}`}></span>
                            </span>
                            <span className={`text-[10px] ${onlineInfo.textColor}`}>{formatLastSeen(device.last_seen)}</span>
                          </div>
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
                        <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
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
                      {isExpanded && <DeviceExpandedRow key={`exp-${device.id}`} device={device} colSpan={8} />}
                      </>
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
