import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import api, { getErrorMsg } from "../lib/api";
import {
  ArrowLeft, Save, Loader2, Upload, Trash2, FileText, Brain, Lightbulb,
  Clock, Check, AlertTriangle, File, Eye,
} from "lucide-react";

export default function KiTrainingPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [instructions, setInstructions] = useState("");
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Training samples
  const [samples, setSamples] = useState([]);
  const [loadingSamples, setLoadingSamples] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [sampleFile, setSampleFile] = useState(null);
  const [sampleError, setSampleError] = useState("");
  const [sampleCorrection, setSampleCorrection] = useState("");

  useEffect(() => {
    api.get("/documents/ai-settings").then(res => {
      setInstructions(res.data.custom_instructions || "");
      setOriginal(res.data.custom_instructions || "");
      setLastUpdated(res.data.updated_at);
    }).catch(() => {});
    loadSamples();
  }, []);

  const loadSamples = async () => {
    try {
      const res = await api.get("/documents/ai-training-samples", { headers: { Authorization: `Bearer ${token}` } });
      setSamples(res.data?.samples || []);
    } catch {}
    setLoadingSamples(false);
  };

  const saveInstructions = async () => {
    setSaving(true);
    try {
      const res = await api.put("/documents/ai-settings", { custom_instructions: instructions });
      setOriginal(instructions);
      setLastUpdated(res.data.updated_at);
      toast.success("KI-Anweisungen gespeichert");
    } catch (error) {
      toast.error(getErrorMsg(error) || "Fehler beim Speichern");
    } finally { setSaving(false); }
  };

  const uploadSample = async () => {
    if (!sampleFile) { toast.error("Bitte Datei auswählen"); return; }
    if (!sampleError.trim()) { toast.error("Bitte den Fehler beschreiben"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", sampleFile);
      fd.append("error_description", sampleError.trim());
      fd.append("correction", sampleCorrection.trim());
      await api.post("/documents/ai-training-samples", fd, {
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "multipart/form-data" },
      });
      toast.success("Trainingsbeispiel hochgeladen");
      setSampleFile(null); setSampleError(""); setSampleCorrection(""); setShowUpload(false);
      loadSamples();
    } catch (e) { toast.error(getErrorMsg(e)); }
    setUploading(false);
  };

  const deleteSample = async (id) => {
    try {
      await api.delete(`/documents/ai-training-samples/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Trainingsbeispiel gelöscht");
      loadSamples();
    } catch (e) { toast.error(getErrorMsg(e)); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung")} className="p-2 hover:bg-gray-200 rounded-lg transition-colors" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">KI-Training</h1>
            <p className="text-xs text-gray-400">Dokumentenerkennung verbessern und Fehler korrigieren</p>
          </div>
        </div>

        {/* Anweisungen */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="ai-instructions-section">
          <div className="bg-gradient-to-r from-fuchsia-600 to-purple-600 px-5 py-3 flex items-center gap-2">
            <Brain className="w-5 h-5 text-white" />
            <h2 className="text-sm font-semibold text-white">KI-Anweisungen</h2>
          </div>
          <div className="p-5 space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <Lightbulb className="w-4 h-4 text-amber-600" />
                <h3 className="text-xs font-medium text-amber-800">Beispiele für Anweisungen:</h3>
              </div>
              <ul className="text-xs text-amber-700 space-y-0.5 list-disc pl-4">
                <li>HalloPetra GmbH Rechnungen immer in "rechnungseingang" einordnen</li>
                <li>Dokumente von Stadtwerk Andernach sind immer Eingangsrechnungen</li>
                <li>Wenn "Netzantrag" im Dokument steht, in "anfragen_projekte" ablegen</li>
                <li>Rechnungen von TEBA immer in den Ordner "teba" statt "rechnungseingang"</li>
              </ul>
            </div>

            <div className="space-y-1.5">
              <Label className="text-sm text-gray-600">Zusätzliche KI-Anweisungen</Label>
              <textarea
                value={instructions}
                onChange={e => setInstructions(e.target.value)}
                placeholder="Geben Sie hier Ihre Anweisungen für die KI-Dokumentenerkennung ein..."
                className="w-full h-40 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-fuchsia-500 focus:border-fuchsia-500 resize-y font-mono bg-white"
                maxLength={5000}
                data-testid="ai-instructions-textarea"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">{instructions.length} / 5000 Zeichen</span>
                {lastUpdated && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Zuletzt: {new Date(lastUpdated).toLocaleString("de-DE")}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button size="sm" onClick={saveInstructions} disabled={saving || instructions === original}
                className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-ai-settings-btn">
                {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
                Anweisungen speichern
              </Button>
              {instructions !== original && <span className="text-xs text-amber-600">Ungespeicherte Änderungen</span>}
            </div>
          </div>
        </div>

        {/* Trainingsbeispiele */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="ai-samples-section">
          <div className="bg-gradient-to-r from-orange-500 to-red-500 px-5 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-white" />
              <h2 className="text-sm font-semibold text-white">Fehler-Korrektur & Training</h2>
              {samples.length > 0 && <span className="bg-white/20 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">{samples.length}</span>}
            </div>
            <Button size="sm" onClick={() => setShowUpload(!showUpload)} className="bg-white/20 hover:bg-white/30 text-white text-xs" data-testid="add-sample-toggle">
              <Upload className="w-3.5 h-3.5 mr-1" /> Fehler melden
            </Button>
          </div>

          <div className="p-5 space-y-4">
            <p className="text-xs text-gray-500">
              Laden Sie Dokumente hoch, bei denen die KI einen Fehler gemacht hat. Beschreiben Sie den Fehler und die richtige Zuordnung – die KI lernt daraus.
            </p>

            {/* Upload Form */}
            {showUpload && (
              <div className="border border-dashed border-orange-300 rounded-lg p-4 bg-orange-50/30 space-y-3" data-testid="sample-upload-form">
                <div>
                  <Label className="text-xs text-gray-600">Dokument hochladen</Label>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" onChange={e => setSampleFile(e.target.files?.[0] || null)}
                    className="mt-1 text-xs w-full" data-testid="sample-file-input" />
                </div>
                <div>
                  <Label className="text-xs text-gray-600">Was hat die KI falsch gemacht?</Label>
                  <textarea value={sampleError} onChange={e => setSampleError(e.target.value)}
                    placeholder='z.B. "Wurde als Rechnung erkannt, ist aber ein Lieferschein" oder "Falschem Mitarbeiter zugeordnet"'
                    className="mt-1 w-full h-20 px-3 py-2 text-sm border border-gray-200 rounded-lg resize-y" data-testid="sample-error-input" />
                </div>
                <div>
                  <Label className="text-xs text-gray-600">Richtige Zuordnung / Korrektur</Label>
                  <textarea value={sampleCorrection} onChange={e => setSampleCorrection(e.target.value)}
                    placeholder='z.B. "Gehört in Ordner rechnungseingang" oder "Ist eine Lohnabrechnung von Max Mustermann"'
                    className="mt-1 w-full h-20 px-3 py-2 text-sm border border-gray-200 rounded-lg resize-y" data-testid="sample-correction-input" />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={uploadSample} disabled={uploading} className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="sample-upload-btn">
                    {uploading ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Upload className="w-3.5 h-3.5 mr-1" />}
                    Trainingsbeispiel speichern
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => { setShowUpload(false); setSampleFile(null); setSampleError(""); setSampleCorrection(""); }}>Abbrechen</Button>
                </div>
              </div>
            )}

            {/* Samples list */}
            {loadingSamples ? (
              <div className="flex items-center gap-2 text-gray-400 text-xs"><Loader2 className="w-4 h-4 animate-spin" /> Laden...</div>
            ) : samples.length === 0 ? (
              <div className="text-center py-6 text-gray-400">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-xs">Noch keine Trainingsbeispiele. Melden Sie Fehler, um die KI zu verbessern.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {samples.map(s => (
                  <div key={s.id} className="border border-gray-200 rounded-lg px-4 py-3 space-y-1.5 hover:bg-gray-50 transition-colors" data-testid={`sample-${s.id}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <File className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-gray-800 truncate">{s.filename}</span>
                        <span className="text-[10px] text-gray-400">{s.created_at?.slice(0, 10)}</span>
                      </div>
                      <button onClick={() => deleteSample(s.id)} className="text-gray-400 hover:text-red-600 flex-shrink-0" data-testid={`delete-sample-${s.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-red-50 border border-red-100 rounded px-2.5 py-1.5">
                        <p className="text-[10px] font-semibold text-red-500 uppercase mb-0.5">Fehler</p>
                        <p className="text-gray-700">{s.error_description}</p>
                      </div>
                      <div className="bg-green-50 border border-green-100 rounded px-2.5 py-1.5">
                        <p className="text-[10px] font-semibold text-green-600 uppercase mb-0.5">Korrektur</p>
                        <p className="text-gray-700">{s.correction || "—"}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
