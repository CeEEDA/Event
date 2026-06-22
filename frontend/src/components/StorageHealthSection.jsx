/**
 * Storage-Health-Card fuer Admin-Settings.
 * Zeigt den Live-Pfad der Dokumentenablage, Free-Disk-Space,
 * Anzahl Dateien und die juengsten 10 Dateien als Beleg, dass
 * das System auf das richtige Laufwerk schreibt (z.B. E:\Eventenergie\...).
 */
import { useState, useEffect, useCallback } from "react";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { HardDrive, RefreshCw, CheckCircle, XCircle, AlertTriangle, FileText } from "lucide-react";

const fmt = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }); } catch { return iso; }
};

export default function StorageHealthSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/storage/health");
      setData(r.data);
    } catch (e) {
      toast.error(`Storage-Check fehlgeschlagen: ${getErrorMsg(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <section className="bg-white border border-gray-200 rounded-xl p-5">Lade Speicher-Status…</section>;
  if (!data) return null;

  const platformLabel = data.platform === "nt" ? "Windows" : (data.platform === "posix" ? "Linux/Mac" : data.platform);
  const ok = data.exists && data.writable;
  const lowDisk = data.free_gb !== null && data.free_gb < 5;
  const mismatch = data.file_count > 0 && data.db_documents_with_local_path > 0
                    && Math.abs(data.file_count - data.db_documents_with_local_path) > data.db_documents_with_local_path * 0.5;

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5" data-testid="storage-health-section">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-cyan-100 flex items-center justify-center">
            <HardDrive className="w-5 h-5 text-cyan-600" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Dokumentenablage / Storage</h2>
            <p className="text-xs text-gray-500">Physischer Ablage-Pfad und Speicher-Status der Live-Umgebung</p>
          </div>
        </div>
        <button onClick={load} className="text-xs text-gray-400 hover:text-cyan-600 flex items-center gap-1" data-testid="storage-refresh-btn">
          <RefreshCw className="w-3.5 h-3.5" /> Aktualisieren
        </button>
      </div>

      {/* Status-Banner */}
      <div className={`mb-4 px-3 py-2 rounded-md text-xs flex items-center gap-2 ${ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
        {ok ? <CheckCircle className="w-4 h-4 shrink-0" /> : <XCircle className="w-4 h-4 shrink-0" />}
        <span>
          {ok
            ? `Speicher OK - Schreibtest erfolgreich auf ${platformLabel}`
            : data.exists
              ? `Pfad existiert, ist aber NICHT beschreibbar: ${data.write_error || "?"}`
              : `Pfad existiert NICHT - Dateien koennen nicht abgelegt werden!`}
        </span>
      </div>

      {lowDisk && (
        <div className="mb-3 px-3 py-2 rounded-md text-xs bg-amber-50 text-amber-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Warnung: nur noch {data.free_gb} GB frei auf der Partition
        </div>
      )}

      {mismatch && (
        <div className="mb-3 px-3 py-2 rounded-md text-xs bg-amber-50 text-amber-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          DB sagt {data.db_documents_with_local_path} Dateien, physisch gefunden: {data.file_count}. Eventuell unsynchron.
        </div>
      )}

      {/* Key-Value Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4 text-xs">
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <div className="text-[10px] text-gray-400 uppercase font-semibold">Aktiver Pfad</div>
          <div className="font-mono text-sm break-all" data-testid="storage-path-display">{data.configured_path}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">
            {data.configured_via_env
              ? <>per ENV <code className="bg-white border border-gray-200 rounded px-1">LOCAL_STORAGE_PATH</code></>
              : <span className="text-amber-700">⚠ Default-Wert (keine ENV gesetzt)</span>}
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <div className="text-[10px] text-gray-400 uppercase font-semibold">Plattform</div>
          <div className="font-semibold text-sm">{platformLabel}</div>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <div className="text-[10px] text-gray-400 uppercase font-semibold">Freier Speicher</div>
          <div className="font-semibold text-sm">{data.free_gb ?? "—"} GB <span className="text-gray-400">von {data.total_gb ?? "—"} GB ({data.used_percent ?? "—"}% belegt)</span></div>
        </div>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <div className="text-[10px] text-gray-400 uppercase font-semibold">Dateien physisch / DB</div>
          <div className="font-semibold text-sm">
            <span data-testid="storage-file-count">{data.file_count}</span>
            <span className="text-gray-400"> / {data.db_documents_with_local_path} mit local_path </span>
            <span className="text-gray-400">(Gesamt-DB: {data.db_documents_total})</span>
          </div>
        </div>
      </div>

      {/* Recent files */}
      {data.recent_files?.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1.5">10 zuletzt geschriebene Dateien</div>
          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 overflow-hidden" data-testid="storage-recent-files">
            {data.recent_files.map((f, i) => (
              <div key={i} className="px-3 py-1.5 text-xs flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                  <span className="font-mono text-[11px] truncate" title={f.rel_path}>{f.rel_path}</span>
                </div>
                <div className="text-[10px] text-gray-400 ml-3 shrink-0">{f.size_kb} KB · {fmt(f.modified)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-gray-400 mt-3">
        Letzter Check: {fmt(data.checked_at)} · Konfiguration in <code className="bg-gray-100 px-1 rounded">backend/.env</code> via <code className="bg-gray-100 px-1 rounded">LOCAL_STORAGE_PATH</code>
      </p>
    </section>
  );
}
