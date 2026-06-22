/**
 * Ollama-Konfiguration und Test-Sektion fuer Admin-Einstellungen.
 *
 * - URL/IP, API-Key, Modell, Text-Modell pflegbar
 * - Live-Status-Check (erreichbar? welche Modelle installiert?)
 * - Test-Upload einer Beispielrechnung -> Anzeige des KI-Analyse-Resultats
 */
import { useState, useEffect, useRef, useCallback } from "react";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Brain, Save, Activity, Upload, CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function OllamaConfigSection() {
  const [config, setConfig] = useState({ url: "", api_key: "", model: "", text_model: "" });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const fileInputRef = useRef(null);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/ollama-config");
      setConfig({
        url: r.data.url || "",
        api_key: r.data.api_key || "",
        model: r.data.model || "",
        text_model: r.data.text_model || "",
      });
    } catch (e) {
      toast.error(`Laden fehlgeschlagen: ${getErrorMsg(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const r = await api.get("/admin/ollama-config/status");
      setStatus(r.data);
    } catch {
      setStatus({ reachable: false });
    }
  }, []);

  useEffect(() => { loadConfig(); loadStatus(); }, [loadConfig, loadStatus]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.put("/admin/ollama-config", config);
      toast.success("Ollama-Konfiguration gespeichert");
      await loadStatus();
    } catch (e) {
      toast.error(`Speichern fehlgeschlagen: ${getErrorMsg(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setTesting(true);
    setTestResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.post("/admin/ollama-config/test-document", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 600000,
      });
      setTestResult(r.data);
      toast.success(`Analyse fertig in ${r.data.duration_seconds}s`);
    } catch (err) {
      toast.error(`Analyse fehlgeschlagen: ${getErrorMsg(err)}`);
      setTestResult({ ok: false, error: getErrorMsg(err) });
    } finally {
      setTesting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5" data-testid="ollama-config-section">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-purple-100 flex items-center justify-center">
            <Brain className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Ollama / KI-Dokumentanalyse</h2>
            <p className="text-xs text-gray-500">Lokale Ollama-Instanz für die automatische Rechnungs-/Dokumentenerkennung</p>
          </div>
        </div>
        <button onClick={loadStatus} className="text-xs text-gray-400 hover:text-purple-600 flex items-center gap-1" data-testid="ollama-refresh-status">
          <Activity className="w-3.5 h-3.5" /> Status prüfen
        </button>
      </div>

      {/* Status-Banner */}
      {status && (
        <div className={`mb-4 px-3 py-2 rounded-md text-xs flex items-center justify-between ${status.reachable ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}
             data-testid="ollama-status-banner">
          <div className="flex items-center gap-2">
            {status.reachable ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            <span>
              {status.reachable
                ? `Erreichbar (${status.available_models?.length || 0} Modelle installiert)`
                : `Nicht erreichbar – ${status.url}`}
            </span>
          </div>
          {status.reachable && status.available_models?.length > 0 && (
            <span className="font-mono text-[10px] text-emerald-600 truncate max-w-md" title={status.available_models.join(", ")}>
              {status.available_models.slice(0, 4).join(", ")}{status.available_models.length > 4 ? ` +${status.available_models.length - 4}` : ""}
            </span>
          )}
        </div>
      )}

      {/* Config-Felder */}
      {loading ? (
        <div className="text-center py-10 text-gray-400">Laden…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <Label className="text-xs text-gray-500">URL / IP</Label>
            <Input
              data-testid="ollama-url-input"
              placeholder="http://95.88.138.67:11434"
              value={config.url}
              onChange={e => setConfig(c => ({ ...c, url: e.target.value }))}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-gray-400 mt-1">Inkl. Schema (http/https) und Port. Trailing-Slash wird automatisch entfernt.</p>
          </div>

          <div className="md:col-span-2">
            <Label className="text-xs text-gray-500">API-Key (optional)</Label>
            <Input
              data-testid="ollama-apikey-input"
              type="password"
              placeholder="leer lassen wenn keine Authentifizierung nötig"
              value={config.api_key}
              onChange={e => setConfig(c => ({ ...c, api_key: e.target.value }))}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-gray-400 mt-1">Wird als Bearer-Token gesendet (für vorgeschaltete Reverse-Proxys mit Auth).</p>
          </div>

          <div>
            <Label className="text-xs text-gray-500">Modell (Vision / Fallback)</Label>
            <Input
              data-testid="ollama-model-input"
              placeholder="gemma3:4b-it-qat"
              value={config.model}
              onChange={e => setConfig(c => ({ ...c, model: e.target.value }))}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-gray-400 mt-1">Vision-fähiges Modell für Scans/Bilder ohne extrahierbaren Text.</p>
          </div>

          <div>
            <Label className="text-xs text-gray-500">Text-Modell (Standard)</Label>
            <Input
              data-testid="ollama-textmodel-input"
              placeholder="gemma2:2b"
              value={config.text_model}
              onChange={e => setConfig(c => ({ ...c, text_model: e.target.value }))}
              className="font-mono text-sm"
            />
            <p className="text-[10px] text-gray-400 mt-1">Schnelles Text-Modell für PDFs mit extrahierbarem Text.</p>
          </div>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between flex-wrap gap-2">
        <Button onClick={saveConfig} disabled={saving || loading} size="sm" className="bg-purple-600 hover:bg-purple-700" data-testid="ollama-save-btn">
          <Save className="w-3.5 h-3.5 mr-1.5" /> {saving ? "Speichern…" : "Speichern"}
        </Button>

        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,image/*"
            onChange={handleTestFile}
            className="hidden"
            data-testid="ollama-test-file-input"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={testing}
            size="sm"
            variant="outline"
            className="border-purple-200 text-purple-700 hover:bg-purple-50"
            data-testid="ollama-test-upload-btn"
          >
            {testing ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            {testing ? "Analysiere…" : "Testrechnung hochladen"}
          </Button>
        </div>
      </div>

      {/* Test-Resultat */}
      {testResult && (
        <div className="mt-4 border border-gray-200 rounded-lg p-3 bg-gray-50" data-testid="ollama-test-result">
          {testResult.ok ? (
            <>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-gray-700">
                  ✓ Analyse-Resultat <span className="text-gray-400 font-normal">({testResult.filename}, {testResult.duration_seconds}s, {(testResult.size_bytes/1024).toFixed(0)} KB)</span>
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 mb-2 text-xs">
                {testResult.result?.document_type && (
                  <div className="bg-white rounded px-2 py-1.5 border border-gray-200">
                    <span className="text-gray-400">Typ:</span> <span className="font-semibold">{testResult.result.document_type}</span>
                  </div>
                )}
                {testResult.result?.suggested_folder && (
                  <div className="bg-white rounded px-2 py-1.5 border border-gray-200">
                    <span className="text-gray-400">Ordner:</span> <span className="font-semibold">{testResult.result.suggested_folder}</span>
                  </div>
                )}
              </div>
              <details className="text-xs">
                <summary className="cursor-pointer text-gray-500 hover:text-gray-700">Vollständige JSON-Antwort anzeigen</summary>
                <pre className="mt-2 bg-white p-2 rounded border border-gray-200 overflow-x-auto text-[10px] font-mono whitespace-pre-wrap break-words max-h-80">
{JSON.stringify(testResult.result, null, 2)}
                </pre>
              </details>
            </>
          ) : (
            <p className="text-xs text-red-700">✗ Fehler: {testResult.error}</p>
          )}
        </div>
      )}
    </section>
  );
}
