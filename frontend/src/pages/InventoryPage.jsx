/* Inventar-Modul – Mobile-first, iPad/iPhone kompatibel.
 * Kamera-Aufnahme via input[capture="environment"] (nativ auf iOS).
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Plus, Search, Camera, ImageIcon, Trash2, Edit3, X, Package,
  FileBarChart, ChevronDown, ChevronRight, FileText, Paperclip, Download,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${API}/api` });
api.interceptors.request.use(cfg => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

const BESITZER_OPTIONS = [
  "ES Besitz und Verwaltung GmbH & Co. KG",
  "Eventenergie Deutschland GmbH & Co. KG",
];
const MONATE = [
  { v: 1, n: "Januar" }, { v: 2, n: "Februar" }, { v: 3, n: "Maerz" },
  { v: 4, n: "April" }, { v: 5, n: "Mai" }, { v: 6, n: "Juni" },
  { v: 7, n: "Juli" }, { v: 8, n: "August" }, { v: 9, n: "September" },
  { v: 10, n: "Oktober" }, { v: 11, n: "November" }, { v: 12, n: "Dezember" },
];
const CURRENT_YEAR = new Date().getFullYear();
const JAHRE = Array.from({ length: 30 }, (_, i) => CURRENT_YEAR - i);

const fmtEUR = (v) => (v == null ? "-" : new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(v));

export default function InventoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [groups, setGroups] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [stats, setStats] = useState(null);
  const [showReport, setShowReport] = useState(false);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/inventory/items", { params: q ? { q } : {} });
      setItems(r.data.items || []);
    } catch { toast.error("Konnte Inventar nicht laden"); }
    setLoading(false);
  }, [q]);

  const loadGroups = async () => {
    try {
      const r = await api.get("/inventory/groups");
      setGroups(r.data.groups || []);
    } catch { /* ignore */ }
  };

  const loadStats = async () => {
    try {
      const r = await api.get("/inventory/stats");
      setStats(r.data);
    } catch { /* ignore */ }
  };

  useEffect(() => { loadGroups(); loadStats(); }, []);
  useEffect(() => {
    const t = setTimeout(loadItems, 300);
    return () => clearTimeout(t);
  }, [q, loadItems]);

  const handleDelete = async (id) => {
    if (!window.confirm("Diese Position wirklich loeschen?")) return;
    try {
      await api.delete(`/inventory/items/${id}`);
      toast.success("Geloescht");
      loadItems(); loadStats();
    } catch { toast.error("Fehler beim Loeschen"); }
  };

  // Gruppieren fuer die Anzeige
  const grouped = items.reduce((acc, it) => {
    const key = it.group_id || "sonstiges";
    if (!acc[key]) acc[key] = { name: it.group_name || key, color: it.group_color || "gray", items: [] };
    acc[key].items.push(it);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50 pb-20" data-testid="inventory-page">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-3 py-2 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")}
            className="text-gray-600 hover:text-fuchsia-600 h-8 px-2" data-testid="inv-back-btn">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Package className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
            <h1 className="text-base font-semibold text-gray-900 truncate">Inventar</h1>
          </div>
          <Button
            size="sm" variant="outline" className="h-8 px-2 text-xs"
            onClick={() => setShowReport(true)}
            data-testid="inv-report-btn"
          >
            <FileBarChart className="w-4 h-4 sm:mr-1" />
            <span className="hidden sm:inline">Auswertung</span>
          </Button>
          <Button
            size="sm" className="h-8 px-2 text-xs bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            onClick={() => { setEditItem(null); setShowForm(true); }}
            data-testid="inv-add-btn"
          >
            <Plus className="w-4 h-4 sm:mr-1" />
            <span className="hidden sm:inline">Anlegen</span>
          </Button>
        </div>

        {/* Suchleiste */}
        <div className="max-w-5xl mx-auto px-3 pb-2">
          <div className="relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              type="search"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Suchen: Bezeichnung, Anlagenr., Notiz…"
              className="pl-9 h-9 text-sm"
              data-testid="inv-search"
            />
            {q && (
              <button onClick={() => setQ("")} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-700">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 py-4 space-y-3">
        {/* Stats */}
        {stats && !q && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            <StatCard label="Positionen" value={stats.total_items} />
            <StatCard label="Einkauf gesamt" value={fmtEUR(stats.total_einkauf)} />
            <StatCard label="Bilanzwert" value={fmtEUR(stats.total_bilanz)} highlight />
            <StatCard label="Marktwert" value={fmtEUR(stats.total_markt)} accent />
          </div>
        )}

        {loading && (
          <div className="text-center py-8 text-sm text-gray-400">Lade…</div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-16 border border-dashed border-gray-200 rounded-lg bg-white">
            <Package className="w-10 h-10 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">
              {q ? "Keine Treffer" : "Noch keine Inventar-Positionen"}
            </p>
            {!q && (
              <Button size="sm" className="mt-3 bg-fuchsia-600 hover:bg-fuchsia-700 text-white" onClick={() => setShowForm(true)}>
                <Plus className="w-4 h-4 mr-1" /> Erste Position anlegen
              </Button>
            )}
          </div>
        )}

        {/* Nach Gruppen */}
        {Object.entries(grouped).map(([gid, g]) => (
          <div key={gid} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded(e => ({ ...e, [gid]: !e[gid] }))}
              className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition"
              data-testid={`inv-group-toggle-${gid}`}
            >
              <div className="flex items-center gap-2">
                {expanded[gid] === false ? <ChevronRight className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                <div className={`w-2 h-2 rounded-full bg-${g.color}-500`} />
                <span className="text-sm font-semibold text-gray-800">{g.name}</span>
                <span className="text-xs text-gray-400">({g.items.length})</span>
              </div>
            </button>
            {expanded[gid] !== false && (
              <div className="divide-y divide-gray-100">
                {g.items.map(it => (
                  <ItemRow key={it.id} item={it} onEdit={() => { setEditItem(it); setShowForm(true); }} onDelete={() => handleDelete(it.id)} />
                ))}
              </div>
            )}
          </div>
        ))}
      </main>

      {/* Formular als Slide-Up-Panel (Mobile-first) */}
      {showForm && (
        <ItemFormPanel
          item={editItem}
          groups={groups}
          onClose={() => { setShowForm(false); setEditItem(null); }}
          onSaved={() => { setShowForm(false); setEditItem(null); loadItems(); loadStats(); loadGroups(); }}
        />
      )}

      {showReport && (
        <ReportDialog stats={stats} groups={groups} onClose={() => setShowReport(false)} />
      )}
    </div>
  );
}


function StatCard({ label, value, highlight, accent }) {
  const cls = highlight
    ? "bg-fuchsia-50 border-fuchsia-200"
    : accent
      ? "bg-emerald-50 border-emerald-200"
      : "bg-white border-gray-200";
  const txt = highlight
    ? "text-fuchsia-700"
    : accent
      ? "text-emerald-700"
      : "text-gray-900";
  return (
    <div className={`rounded-lg border p-2 sm:p-3 ${cls}`} data-testid={`inv-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`text-sm sm:text-lg font-bold tabular-nums ${txt}`}>{value}</div>
    </div>
  );
}


function ReportDialog({ stats, groups, onClose }) {
  const [downloading, setDownloading] = useState(null);
  const [pdfMode, setPdfMode] = useState("smart");
  // Alle Gruppen initial aktiv (leeres Set = alle)
  const [selectedGroups, setSelectedGroups] = useState(new Set(groups.map(g => g.id)));

  const toggleGroup = (gid) => {
    setSelectedGroups(prev => {
      const next = new Set(prev);
      if (next.has(gid)) next.delete(gid);
      else next.add(gid);
      return next;
    });
  };

  const setAll = (all) => {
    setSelectedGroups(all ? new Set(groups.map(g => g.id)) : new Set());
  };

  const allSelected = selectedGroups.size === groups.length;
  const noneSelected = selectedGroups.size === 0;

  const download = async (path, filename) => {
    if (noneSelected) {
      toast.error("Bitte mindestens eine Gruppe auswaehlen");
      return;
    }
    setDownloading(path);
    try {
      const token = localStorage.getItem("token");
      // Wenn alle -> kein filter, sonst comma-separiert
      const url = new URL(`${API}/api${path}`);
      if (!allSelected) {
        url.searchParams.set("groups", Array.from(selectedGroups).join(","));
      }
      const r = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        // Backend sendet bei 500 einen JSON-Body mit "detail" -> anzeigen,
        // sodass der Anwender die konkrete Ursache direkt sieht (kein Log-Grepping).
        let detail = `HTTP ${r.status}`;
        try {
          const body = await r.json();
          if (body?.detail) detail = body.detail;
        } catch { /* body ist evtl. HTML/binary - dann bleibt HTTP-Code */ }
        throw new Error(detail);
      }
      const blob = await r.blob();
      const dlUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = dlUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(dlUrl);
      toast.success(`${filename} heruntergeladen`);
    } catch (e) {
      toast.error("Download fehlgeschlagen: " + e.message);
    }
    setDownloading(null);
  };

  const today = new Date().toISOString().slice(0, 10);
  const gSuffix = allSelected ? "" : `_${selectedGroups.size}Gruppen`;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50" data-testid="inv-report-dialog">
      <div className="bg-white w-full sm:max-w-md sm:rounded-lg rounded-t-xl max-h-[92vh] overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <FileBarChart className="w-4 h-4 text-fuchsia-500" /> Auswertung
          </h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-gray-100 text-gray-500" data-testid="inv-report-close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          {stats && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs space-y-1">
              <div className="flex justify-between"><span className="text-gray-500">Positionen (gesamt):</span><span className="font-mono font-medium">{stats.total_items}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Einkauf:</span><span className="font-mono">{fmtEUR(stats.total_einkauf)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Bilanzwert:</span><span className="font-mono">{fmtEUR(stats.total_bilanz)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Marktschaetzwert:</span><span className="font-mono">{fmtEUR(stats.total_markt)}</span></div>
            </div>
          )}

          {/* Gruppen-Auswahl */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-semibold text-gray-900">Gruppen fuer Auswertung</div>
              <div className="flex gap-1 text-[11px]">
                <button
                  onClick={() => setAll(true)}
                  className="px-2 py-0.5 rounded border border-gray-300 hover:border-fuchsia-500 hover:text-fuchsia-600"
                  data-testid="inv-report-select-all"
                >
                  Alle
                </button>
                <button
                  onClick={() => setAll(false)}
                  className="px-2 py-0.5 rounded border border-gray-300 hover:border-gray-500"
                  data-testid="inv-report-select-none"
                >
                  Keine
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-1 max-h-48 overflow-y-auto">
              {groups.map(g => {
                const checked = selectedGroups.has(g.id);
                return (
                  <label
                    key={g.id}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded border cursor-pointer transition ${checked ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 hover:border-gray-300"}`}
                    data-testid={`inv-report-group-${g.id}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleGroup(g.id)}
                      className="w-4 h-4 accent-fuchsia-600"
                    />
                    <div className={`w-2 h-2 rounded-full bg-${g.color}-500`} />
                    <span className="text-sm text-gray-800 flex-1">{g.name}</span>
                    <span className="text-[11px] text-gray-400">{g.item_count || 0}</span>
                  </label>
                );
              })}
            </div>
            {noneSelected && (
              <p className="text-[11px] text-red-500 mt-2">Bitte mindestens eine Gruppe waehlen.</p>
            )}
          </div>

          {/* Excel */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="text-sm font-semibold text-gray-900 mb-1">Excel (XLSX)</div>
            <p className="text-xs text-gray-500 mb-3">Deckblatt mit Summen + je gewaehlter Gruppe ein eigenes Tabellenblatt.</p>
            <Button
              disabled={downloading === "/inventory/export/xlsx" || noneSelected}
              onClick={() => download("/inventory/export/xlsx", `Inventar${gSuffix}_${today}.xlsx`)}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white h-10"
              data-testid="inv-report-xlsx"
            >
              {downloading === "/inventory/export/xlsx" ? "Erstelle..." : "Excel herunterladen"}
            </Button>
          </div>

          {/* PDF */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="text-sm font-semibold text-gray-900 mb-2">PDF Auswertung</div>
            <div className="space-y-2 mb-3">
              <ModeRadio value="smart" current={pdfMode} setCurrent={setPdfMode} label="Smart" desc="Deckblatt + kompakte Tabelle aller Positionen." />
              <ModeRadio value="mittel" current={pdfMode} setCurrent={setPdfMode} label="Mittel" desc="+ je Gruppe ein Deckblatt und je Position eine Seite mit Bild." />
              <ModeRadio value="gross" current={pdfMode} setCurrent={setPdfMode} label="Gross" desc="Wie Mittel + Referenzen der angehaengten Dokumente." />
            </div>
            <Button
              disabled={(downloading?.startsWith("/inventory/export/pdf")) || noneSelected}
              onClick={() => download(`/inventory/export/pdf?mode=${pdfMode}`, `Inventar_${pdfMode}${gSuffix}_${today}.pdf`)}
              className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white h-10"
              data-testid="inv-report-pdf"
            >
              {downloading?.startsWith("/inventory/export/pdf") ? "Erstelle..." : "PDF herunterladen"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}


function ModeRadio({ value, current, setCurrent, label, desc }) {
  const selected = current === value;
  return (
    <button
      type="button"
      onClick={() => setCurrent(value)}
      className={`w-full text-left p-2 rounded-md border transition ${selected ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 hover:border-gray-300"}`}
      data-testid={`inv-pdf-mode-${value}`}
    >
      <div className="flex items-center gap-2 mb-0.5">
        <div className={`w-3 h-3 rounded-full border-2 ${selected ? "border-fuchsia-500 bg-fuchsia-500" : "border-gray-300"}`} />
        <span className={`text-sm font-medium ${selected ? "text-fuchsia-700" : "text-gray-800"}`}>{label}</span>
      </div>
      <div className="text-xs text-gray-500 ml-5">{desc}</div>
    </button>
  );
}


function ItemRow({ item, onEdit, onDelete }) {
  const firstImg = item.images?.[0];
  const anschaffung = item.anschaffung_monat && item.anschaffung_jahr
    ? `${String(item.anschaffung_monat).padStart(2, "0")}/${item.anschaffung_jahr}`
    : null;
  return (
    <div className="px-3 py-2 flex items-center gap-2 sm:gap-3 hover:bg-gray-50 active:bg-gray-100" data-testid={`inv-item-${item.id}`}>
      <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-md bg-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0 border border-gray-200">
        {firstImg ? (
          <img
            src={`${API}/api/inventory/items/${item.id}/images/${firstImg.id}`}
            alt=""
            className="w-full h-full object-cover"
            onError={e => { e.target.style.display = "none"; }}
          />
        ) : (
          <ImageIcon className="w-5 h-5 text-gray-300" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">{item.bezeichnung}</div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
          {item.anlagevermoegensnummer && <span className="font-mono">Nr. {item.anlagevermoegensnummer}</span>}
          {item.stueckzahl > 1 && <span>· {item.stueckzahl} Stk.</span>}
          {anschaffung && <span>· {anschaffung}</span>}
          {item.aktueller_bilanzwert > 0 && <span className="text-fuchsia-600 font-medium">· Bilanz {fmtEUR(item.aktueller_bilanzwert)}</span>}
          {item.marktschaetzwert > 0 && <span className="text-emerald-600 font-medium">· Markt {fmtEUR(item.marktschaetzwert)}</span>}
        </div>
      </div>
      <div className="flex items-center gap-0.5 flex-shrink-0">
        <button onClick={onEdit} className="p-1.5 rounded text-gray-400 hover:bg-blue-50 hover:text-blue-600" title="Bearbeiten" data-testid={`inv-edit-${item.id}`}>
          <Edit3 className="w-4 h-4" />
        </button>
        <button onClick={onDelete} className="p-1.5 rounded text-gray-400 hover:bg-red-50 hover:text-red-600" title="Loeschen" data-testid={`inv-delete-${item.id}`}>
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}


function ItemFormPanel({ item, groups, onClose, onSaved }) {
  const isEdit = !!item;
  const [form, setForm] = useState({
    bezeichnung: item?.bezeichnung || "",
    anlagevermoegensnummer: item?.anlagevermoegensnummer || "",
    besitzer: item?.besitzer || BESITZER_OPTIONS[0],
    einkaufspreis: item?.einkaufspreis ?? "",
    anschaffung_monat: item?.anschaffung_monat || "",
    anschaffung_jahr: item?.anschaffung_jahr || CURRENT_YEAR,
    aktueller_bilanzwert: item?.aktueller_bilanzwert ?? "",
    marktschaetzwert: item?.marktschaetzwert ?? "",
    stueckzahl: item?.stueckzahl || 1,
    notiz: item?.notiz || "",
    group_id: item?.group_id || (groups[0]?.id || ""),
  });
  const [saving, setSaving] = useState(false);
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [images, setImages] = useState(item?.images || []);
  const [uploadingImg, setUploadingImg] = useState(false);
  const [createdItemId, setCreatedItemId] = useState(item?.id || null);
  const [showCamera, setShowCamera] = useState(false);
  const [docs, setDocs] = useState(item?.documents || []);
  const [uploadingDoc, setUploadingDoc] = useState(false);

  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const docInputRef = useRef(null);

  const save = async () => {
    if (!form.bezeichnung.trim()) {
      toast.error("Bezeichnung ist Pflicht");
      return;
    }
    if (!form.group_id) {
      toast.error("Bitte eine Gruppe auswaehlen");
      return;
    }
    const bilanz = parseFloat(form.aktueller_bilanzwert) || 0;
    const markt = parseFloat(form.marktschaetzwert) || 0;
    if (bilanz <= 0 && markt <= 0) {
      toast.error("Bitte einen Bilanzwert ODER einen Marktschaetzwert eintragen.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        einkaufspreis: parseFloat(form.einkaufspreis) || 0,
        aktueller_bilanzwert: bilanz,
        marktschaetzwert: markt,
        stueckzahl: parseInt(form.stueckzahl) || 1,
        anschaffung_monat: form.anschaffung_monat ? parseInt(form.anschaffung_monat) : null,
        anschaffung_jahr: form.anschaffung_jahr ? parseInt(form.anschaffung_jahr) : null,
      };
      let r;
      if (isEdit) {
        r = await api.put(`/inventory/items/${item.id}`, payload);
      } else {
        r = await api.post("/inventory/items", payload);
        setCreatedItemId(r.data.id);
      }
      toast.success(isEdit ? "Gespeichert" : "Angelegt");
      if (isEdit || images.length === 0) {
        onSaved();
      } else {
        // Nach Anlage: Item bleibt offen fuer Bild-Upload
        toast.info("Bilder koennen jetzt hinzugefuegt werden");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Fehler beim Speichern");
    }
    setSaving(false);
  };

  const createNewGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    try {
      const r = await api.post("/inventory/groups", { name });
      // Selbst laden waere Overkill – wir haengen an und selektieren
      const newGrp = r.data.group;
      groups.push(newGrp);
      setForm(f => ({ ...f, group_id: newGrp.id }));
      setShowNewGroup(false);
      setNewGroupName("");
      toast.success(`Gruppe "${newGrp.name}" angelegt`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Konnte Gruppe nicht anlegen");
    }
  };

  const uploadImages = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    const targetId = createdItemId;
    if (!targetId) {
      toast.error("Bitte zuerst 'Speichern' klicken, dann Bilder hochladen");
      return;
    }
    setUploadingImg(true);
    for (const f of fileList) {
      try {
        const fd = new FormData();
        fd.append("file", f);
        const r = await api.post(`/inventory/items/${targetId}/images`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setImages(imgs => [...imgs, r.data]);
      } catch (e) {
        toast.error(`Bild ${f.name}: ${e?.response?.data?.detail || "Upload fehlgeschlagen"}`);
      }
    }
    setUploadingImg(false);
  };

  const removeImage = async (img_id) => {
    if (!window.confirm("Bild loeschen?")) return;
    try {
      await api.delete(`/inventory/items/${createdItemId}/images/${img_id}`);
      setImages(imgs => imgs.filter(i => i.id !== img_id));
    } catch { toast.error("Fehler beim Loeschen"); }
  };

  const uploadDocs = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    if (!createdItemId) {
      toast.error("Bitte zuerst 'Speichern' klicken");
      return;
    }
    setUploadingDoc(true);
    for (const f of fileList) {
      try {
        const fd = new FormData();
        fd.append("file", f);
        const r = await api.post(`/inventory/items/${createdItemId}/documents`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setDocs(ds => [...ds, r.data]);
      } catch (e) {
        toast.error(`Datei ${f.name}: ${e?.response?.data?.detail || "Upload fehlgeschlagen"}`);
      }
    }
    setUploadingDoc(false);
  };

  const removeDoc = async (doc_id) => {
    if (!window.confirm("Dokument loeschen?")) return;
    try {
      await api.delete(`/inventory/items/${createdItemId}/documents/${doc_id}`);
      setDocs(ds => ds.filter(d => d.id !== doc_id));
    } catch { toast.error("Fehler beim Loeschen"); }
  };

  const fmtBytes = (b) => {
    if (!b) return "";
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
    return `${(b / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50" data-testid="inv-form">
      <div className="bg-white w-full sm:max-w-lg sm:rounded-lg rounded-t-xl max-h-[95vh] overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {isEdit ? "Position bearbeiten" : "Inventar anlegen"}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-gray-100 text-gray-500" data-testid="inv-form-close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-3">
          {/* Gruppe */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Gruppe *</label>
            {!showNewGroup ? (
              <div className="flex gap-2">
                <select
                  value={form.group_id}
                  onChange={e => setForm(f => ({ ...f, group_id: e.target.value }))}
                  className="flex-1 h-10 px-2 border border-gray-300 rounded-md text-sm"
                  data-testid="inv-group-select"
                >
                  {groups.map(g => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
                <Button variant="outline" size="sm" onClick={() => setShowNewGroup(true)} className="text-xs h-10" data-testid="inv-new-group-btn">
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="flex gap-2">
                <Input
                  value={newGroupName}
                  onChange={e => setNewGroupName(e.target.value)}
                  placeholder="Neue Gruppe (z.B. Beleuchtung)"
                  className="h-10 text-sm"
                  autoFocus
                  data-testid="inv-new-group-input"
                />
                <Button size="sm" onClick={createNewGroup} className="h-10 bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                  OK
                </Button>
                <Button variant="ghost" size="sm" onClick={() => { setShowNewGroup(false); setNewGroupName(""); }} className="h-10">
                  <X className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>

          {/* Bezeichnung */}
          <Field label="Bezeichnung *" value={form.bezeichnung} onChange={v => setForm(f => ({ ...f, bezeichnung: v }))} testid="inv-bezeichnung" />

          {/* Anlagevermoegensnummer */}
          <Field label="Anlagevermoegensnummer" value={form.anlagevermoegensnummer} onChange={v => setForm(f => ({ ...f, anlagevermoegensnummer: v }))} testid="inv-anlagenr" placeholder="z.B. AV-2026-042" />

          {/* Besitzer */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Besitzer</label>
            <select
              value={form.besitzer}
              onChange={e => setForm(f => ({ ...f, besitzer: e.target.value }))}
              className="w-full h-10 px-2 border border-gray-300 rounded-md text-sm"
              data-testid="inv-besitzer"
            >
              {BESITZER_OPTIONS.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>

          {/* Einkaufspreis / Bilanzwert / Marktschaetzwert */}
          <div className="grid grid-cols-2 gap-2">
            <Field label="Einkaufspreis (EUR)" type="number" step="0.01" value={form.einkaufspreis} onChange={v => setForm(f => ({ ...f, einkaufspreis: v }))} testid="inv-einkauf" />
            <Field label="Aktueller Bilanzwert (EUR)" type="number" step="0.01" value={form.aktueller_bilanzwert} onChange={v => setForm(f => ({ ...f, aktueller_bilanzwert: v }))} testid="inv-bilanz" />
          </div>
          <Field
            label="Marktschaetzwert (EUR)"
            type="number"
            step="0.01"
            value={form.marktschaetzwert}
            onChange={v => setForm(f => ({ ...f, marktschaetzwert: v }))}
            placeholder="Alternative wenn kein Bilanzwert bekannt"
            testid="inv-markt"
          />
          <p className="text-[11px] text-amber-600 -mt-1">
            Bitte mindestens EINEN Wert eintragen (Bilanzwert oder Marktschaetzwert).
          </p>

          {/* Anschaffung Monat + Jahr */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Anschaffung</label>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.anschaffung_monat}
                onChange={e => setForm(f => ({ ...f, anschaffung_monat: e.target.value }))}
                className="h-10 px-2 border border-gray-300 rounded-md text-sm"
                data-testid="inv-monat"
              >
                <option value="">Monat</option>
                {MONATE.map(m => <option key={m.v} value={m.v}>{m.n}</option>)}
              </select>
              <select
                value={form.anschaffung_jahr}
                onChange={e => setForm(f => ({ ...f, anschaffung_jahr: e.target.value }))}
                className="h-10 px-2 border border-gray-300 rounded-md text-sm"
                data-testid="inv-jahr"
              >
                <option value="">Jahr</option>
                {JAHRE.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          </div>

          {/* Stueckzahl */}
          <Field label="Stueckzahl" type="number" min="1" value={form.stueckzahl} onChange={v => setForm(f => ({ ...f, stueckzahl: v }))} testid="inv-stueckzahl" />

          {/* Notiz */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Notiz</label>
            <textarea
              value={form.notiz}
              onChange={e => setForm(f => ({ ...f, notiz: e.target.value }))}
              rows={3}
              className="w-full px-2 py-2 border border-gray-300 rounded-md text-sm resize-y"
              placeholder="Optionale Bemerkung"
              data-testid="inv-notiz"
            />
          </div>

          {/* Bilder */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Bilder {images.length > 0 && <span className="text-gray-400">({images.length})</span>}
            </label>
            {images.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-2">
                {images.map(img => (
                  <div key={img.id} className="relative aspect-square rounded-md border border-gray-200 overflow-hidden bg-gray-100">
                    <img
                      src={`${API}/api/inventory/items/${createdItemId}/images/${img.id}`}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                    <button
                      onClick={() => removeImage(img.id)}
                      className="absolute top-1 right-1 p-1 rounded-full bg-black/60 text-white hover:bg-red-600"
                      title="Bild entfernen"
                      data-testid={`inv-img-remove-${img.id}`}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {!createdItemId && (
              <p className="text-xs text-amber-600 mb-2">
                Bitte zuerst speichern – danach koennen Bilder hinzugefuegt werden.
              </p>
            )}

            <div className="grid grid-cols-2 gap-2">
              {/* Kamera-Modal (getUserMedia - robust auf iPhone/iPad, auch Desktop-Modus) */}
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={!createdItemId || uploadingImg}
                onClick={() => setShowCamera(true)}
                className="h-11 text-sm"
                data-testid="inv-camera-btn"
              >
                <Camera className="w-4 h-4 mr-1" /> Foto aufnehmen
              </Button>
              {/* Galerie / Datei-Auswahl */}
              <input
                ref={galleryInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={e => uploadImages(e.target.files)}
              />
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={!createdItemId || uploadingImg}
                onClick={() => galleryInputRef.current?.click()}
                className="h-11 text-sm"
                data-testid="inv-gallery-btn"
              >
                <ImageIcon className="w-4 h-4 mr-1" /> Aus Galerie
              </Button>
            </div>
            {uploadingImg && <p className="text-xs text-gray-500 mt-1">Bild wird hochgeladen...</p>}
          </div>

          {/* Dokumente */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Dokumente {docs.length > 0 && <span className="text-gray-400">({docs.length})</span>}
            </label>
            {docs.length > 0 && (
              <div className="space-y-1 mb-2">
                {docs.map(d => (
                  <div key={d.id} className="flex items-center gap-2 px-2 py-1.5 border border-gray-200 rounded-md bg-gray-50">
                    <FileText className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gray-800 truncate">{d.filename}</div>
                      <div className="text-[10px] text-gray-400">{fmtBytes(d.size)}</div>
                    </div>
                    <a
                      href={`${API}/api/inventory/items/${createdItemId}/documents/${d.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1.5 rounded text-gray-500 hover:bg-blue-50 hover:text-blue-600"
                      title="Oeffnen / Herunterladen"
                      data-testid={`inv-doc-open-${d.id}`}
                    >
                      <Download className="w-3.5 h-3.5" />
                    </a>
                    <button
                      onClick={() => removeDoc(d.id)}
                      className="p-1.5 rounded text-gray-400 hover:bg-red-50 hover:text-red-600"
                      title="Loeschen"
                      data-testid={`inv-doc-remove-${d.id}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <input
              ref={docInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              multiple
              className="hidden"
              onChange={e => uploadDocs(e.target.files)}
            />
            <Button
              variant="outline"
              size="sm"
              type="button"
              disabled={!createdItemId || uploadingDoc}
              onClick={() => docInputRef.current?.click()}
              className="h-11 text-sm w-full"
              data-testid="inv-doc-upload-btn"
            >
              <Paperclip className="w-4 h-4 mr-1" /> Dokument hinzufuegen (PDF, Word, Excel...)
            </Button>
            {uploadingDoc && <p className="text-xs text-gray-500 mt-1">Datei wird hochgeladen...</p>}
          </div>
        </div>

        {showCamera && (
          <CameraCapture
            onClose={() => setShowCamera(false)}
            onCapture={async (blob) => {
              setShowCamera(false);
              const f = new File([blob], `foto_${Date.now()}.jpg`, { type: "image/jpeg" });
              await uploadImages([f]);
            }}
          />
        )}

        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-4 py-3 flex gap-2">
          <Button variant="outline" onClick={onClose} className="flex-1" data-testid="inv-form-cancel">
            {isEdit || createdItemId ? "Schliessen" : "Abbrechen"}
          </Button>
          <Button
            onClick={save}
            disabled={saving}
            className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            data-testid="inv-form-save"
          >
            {saving ? "Speichere…" : (isEdit ? "Aenderungen speichern" : (createdItemId ? "Aktualisieren" : "Speichern"))}
          </Button>
        </div>
      </div>
    </div>
  );
}


function Field({ label, value, onChange, type = "text", placeholder, step, min, testid }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
      <Input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        step={step}
        min={min}
        className="h-10 text-sm"
        inputMode={type === "number" ? "decimal" : undefined}
        data-testid={testid}
      />
    </div>
  );
}


/* CameraCapture: getUserMedia-basierte Kamera als Modal.
 * Funktioniert zuverlaessig auf iPhone/iPad (auch im Desktop-Modus) und Chrome/Firefox.
 * Rueckkamera bevorzugt via facingMode='environment'. Fallback auf beliebige Kamera. */
function CameraCapture({ onClose, onCapture }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const start = async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error("Kamera-API vom Browser nicht unterstuetzt (HTTPS erforderlich)");
        }
        let stream;
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
            audio: false,
          });
        } catch {
          // Fallback: beliebige Kamera (Front oder unbekannt)
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.setAttribute("playsinline", "true");
          await videoRef.current.play().catch(() => {});
          setReady(true);
        }
      } catch (e) {
        setError(e.message || "Kamera konnte nicht gestartet werden");
      }
    };
    start();
    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const snap = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !ready) return;
    const w = video.videoWidth || 1280;
    const h = video.videoHeight || 720;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, w, h);
    canvas.toBlob(
      (blob) => { if (blob) onCapture(blob); },
      "image/jpeg",
      0.85,
    );
  };

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-black" data-testid="inv-camera-modal">
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 text-white bg-black/70">
        <button onClick={onClose} className="p-2 rounded hover:bg-white/10" data-testid="inv-cam-close">
          <X className="w-6 h-6" />
        </button>
        <span className="text-sm font-medium">Foto aufnehmen</span>
        <div className="w-10" />
      </div>

      <div className="flex-1 flex items-center justify-center relative overflow-hidden bg-black">
        {error ? (
          <div className="text-center px-6 text-white">
            <p className="text-sm text-red-300 mb-2">Kamera-Fehler</p>
            <p className="text-xs text-white/70 mb-4">{error}</p>
            <Button variant="outline" onClick={onClose} className="text-white bg-transparent border-white/40">
              Schliessen
            </Button>
          </div>
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-contain" />
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>

      <div className="flex-shrink-0 flex items-center justify-center py-6 bg-black/70">
        <button
          onClick={snap}
          disabled={!ready || !!error}
          className="w-16 h-16 rounded-full border-4 border-white bg-white/20 hover:bg-white/40 active:bg-white/60 disabled:opacity-40 transition"
          data-testid="inv-cam-snap"
          aria-label="Aufnehmen"
        >
          <div className="w-full h-full rounded-full bg-white" />
        </button>
      </div>
    </div>
  );
}
