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
  FileBarChart, ChevronDown, ChevronRight,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const api = axios.create({ baseURL: `${API}/api` });
api.interceptors.request.use(cfg => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

const BESITZER_OPTIONS = ["ES Besitz und Verwaltung GmbH & Co. KG"];
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
  const [expanded, setExpanded] = useState({});    // group_id -> bool
  const [stats, setStats] = useState(null);

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
            onClick={() => toast.info("Auswertung/Export folgt im naechsten Schritt")}
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
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <StatCard label="Positionen" value={stats.total_items} />
            <StatCard label="Einkauf gesamt" value={fmtEUR(stats.total_einkauf)} />
            <StatCard label="Bilanzwert" value={fmtEUR(stats.total_bilanz)} highlight />
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
    </div>
  );
}


function StatCard({ label, value, highlight }) {
  return (
    <div className={`rounded-lg border p-2 sm:p-3 ${highlight ? "bg-fuchsia-50 border-fuchsia-200" : "bg-white border-gray-200"}`}>
      <div className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`text-sm sm:text-lg font-bold tabular-nums ${highlight ? "text-fuchsia-700" : "text-gray-900"}`}>{value}</div>
    </div>
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
          {item.aktueller_bilanzwert > 0 && <span className="text-fuchsia-600 font-medium">· {fmtEUR(item.aktueller_bilanzwert)}</span>}
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

  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);

  const save = async () => {
    if (!form.bezeichnung.trim()) {
      toast.error("Bezeichnung ist Pflicht");
      return;
    }
    if (!form.group_id) {
      toast.error("Bitte eine Gruppe auswaehlen");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        einkaufspreis: parseFloat(form.einkaufspreis) || 0,
        aktueller_bilanzwert: parseFloat(form.aktueller_bilanzwert) || 0,
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

          {/* Einkaufspreis */}
          <div className="grid grid-cols-2 gap-2">
            <Field label="Einkaufspreis (EUR)" type="number" step="0.01" value={form.einkaufspreis} onChange={v => setForm(f => ({ ...f, einkaufspreis: v }))} testid="inv-einkauf" />
            <Field label="Aktueller Bilanzwert (EUR)" type="number" step="0.01" value={form.aktueller_bilanzwert} onChange={v => setForm(f => ({ ...f, aktueller_bilanzwert: v }))} testid="inv-bilanz" />
          </div>

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
              {/* Kamera-Aufnahme (iOS/iPad triggert direkt Camera) */}
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={e => uploadImages(e.target.files)}
              />
              <Button
                variant="outline"
                size="sm"
                type="button"
                disabled={!createdItemId || uploadingImg}
                onClick={() => cameraInputRef.current?.click()}
                className="h-11 text-sm"
                data-testid="inv-camera-btn"
              >
                <Camera className="w-4 h-4 mr-1" /> Foto aufnehmen
              </Button>
              {/* Galerie */}
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
            {uploadingImg && <p className="text-xs text-gray-500 mt-1">Bild wird hochgeladen…</p>}
          </div>
        </div>

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
