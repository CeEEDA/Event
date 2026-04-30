import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { ArrowLeft, FileText, Plus, Pencil, Trash2, Save, Loader2, Search } from "lucide-react";

export default function TextbausteineAdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [newText, setNewText] = useState("");
  const [newBezeichnung, setNewBezeichnung] = useState("");
  const [newKategorie, setNewKategorie] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [editBezeichnung, setEditBezeichnung] = useState("");
  const [editKategorie, setEditKategorie] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/project-reports/work-templates");
      setTemplates(data || []);
    } catch { setTemplates([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async () => {
    if (!newBezeichnung.trim() || !newText.trim()) { toast.error("Bezeichnung und Text sind erforderlich"); return; }
    try {
      await api.post("/project-reports/work-templates", { bezeichnung: newBezeichnung.trim(), text: newText.trim(), kategorie: newKategorie.trim() });
      setNewBezeichnung(""); setNewText(""); setNewKategorie("");
      toast.success("Textbaustein angelegt");
      load();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const handleUpdate = async (id) => {
    try {
      await api.put(`/project-reports/work-templates/${id}`, { bezeichnung: editBezeichnung.trim(), text: editText.trim(), kategorie: editKategorie.trim() });
      setEditingId(null);
      toast.success("Aktualisiert");
      load();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Textbaustein wirklich loeschen?")) return;
    try {
      await api.delete(`/project-reports/work-templates/${id}`);
      toast.success("Geloescht");
      load();
    } catch (err) { toast.error(getErrorMsg(err, "Fehler")); }
  };

  const filtered = templates.filter(t => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      (t.bezeichnung || "").toLowerCase().includes(q) ||
      (t.text || "").toLowerCase().includes(q) ||
      (t.kategorie || "").toLowerCase().includes(q)
    );
  });

  // Gruppieren nach Kategorie
  const groups = {};
  filtered.forEach(t => {
    const k = (t.kategorie || "").trim() || "Allgemein";
    if (!groups[k]) groups[k] = [];
    groups[k].push(t);
  });
  const groupNames = Object.keys(groups).sort((a, b) => {
    if (a === "Allgemein") return 1;
    if (b === "Allgemein") return -1;
    return a.localeCompare(b, "de");
  });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="textbausteine-admin-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <FileText className="w-5 h-5 text-fuchsia-600" />
          <div>
            <h1 className="text-base font-semibold text-gray-900">Textbausteine</h1>
            <p className="text-[11px] text-gray-500 -mt-0.5">Vordefinierte Texte für das Arbeitsprotokoll im Projektbericht</p>
          </div>
          <span className="ml-auto text-xs text-gray-400">{filtered.length} / {templates.length}</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-5 space-y-4">
        {/* Add new */}
        <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="add-template-form">
          <div className="text-xs font-medium text-gray-700 mb-2 flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5 text-fuchsia-600" /> Neuer Textbaustein
          </div>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
            <div className="md:col-span-3">
              <Label className="text-[11px] text-gray-500">Bezeichnung</Label>
              <Input value={newBezeichnung} onChange={e => setNewBezeichnung(e.target.value)} placeholder="Kurzname" className="mt-0.5 h-9 text-sm" data-testid="new-template-bezeichnung" />
            </div>
            <div className="md:col-span-2">
              <Label className="text-[11px] text-gray-500">Kategorie</Label>
              <Input value={newKategorie} onChange={e => setNewKategorie(e.target.value)} placeholder="optional" className="mt-0.5 h-9 text-sm" data-testid="new-template-kategorie" />
            </div>
            <div className="md:col-span-5">
              <Label className="text-[11px] text-gray-500">Text</Label>
              <Input value={newText} onChange={e => setNewText(e.target.value)} placeholder="Fertiger Text der eingefuegt wird..."
                className="mt-0.5 h-9 text-sm" onKeyDown={e => e.key === "Enter" && handleAdd()} data-testid="new-template-text" />
            </div>
            <div className="md:col-span-2">
              <Button size="sm" onClick={handleAdd} className="h-9 w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="add-template-btn">
                <Plus className="w-4 h-4 mr-1" /> Hinzufügen
              </Button>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Suchen (Bezeichnung, Text, Kategorie)..."
            className="pl-9 h-10 bg-white"
            data-testid="templates-search"
          />
        </div>

        {/* List */}
        {loading ? (
          <div className="text-center py-10"><Loader2 className="w-6 h-6 animate-spin mx-auto text-fuchsia-500" /></div>
        ) : filtered.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-10 text-center text-gray-400" data-testid="templates-empty">
            <FileText className="w-10 h-10 mx-auto mb-3 text-gray-300" />
            {templates.length === 0 ? "Noch keine Textbausteine angelegt." : "Keine Treffer für deine Suche."}
          </div>
        ) : (
          <div className="space-y-4" data-testid="templates-list">
            {groupNames.map(g => (
              <div key={g} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 text-[10px] uppercase tracking-wider font-semibold text-gray-500">
                  {g}
                </div>
                <div className="divide-y divide-gray-100">
                  {groups[g].map(t => (
                    <div key={t.id} className="px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors" data-testid={`template-${t.id}`}>
                      {editingId === t.id ? (
                        <>
                          <Input value={editBezeichnung} onChange={e => setEditBezeichnung(e.target.value)} className="w-40 h-8 text-sm" placeholder="Bezeichnung" />
                          <Input value={editKategorie} onChange={e => setEditKategorie(e.target.value)} className="w-32 h-8 text-sm" placeholder="Kategorie" />
                          <Input value={editText} onChange={e => setEditText(e.target.value)} className="flex-1 h-8 text-sm" placeholder="Text"
                            onKeyDown={e => e.key === "Enter" && handleUpdate(t.id)} />
                          <Button size="sm" onClick={() => handleUpdate(t.id)} className="h-8 bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                            <Save className="w-3.5 h-3.5" />
                          </Button>
                          <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600 text-xs px-1">Abbrechen</button>
                        </>
                      ) : (
                        <>
                          <span className="text-sm font-medium text-gray-900 shrink-0 min-w-[120px]">{t.bezeichnung || "—"}</span>
                          <span className="text-xs text-gray-300">→</span>
                          <span className="flex-1 text-sm text-gray-600 truncate">{t.text}</span>
                          <button onClick={() => { setEditingId(t.id); setEditBezeichnung(t.bezeichnung || ""); setEditText(t.text); setEditKategorie(t.kategorie || ""); }}
                            className="text-gray-400 hover:text-fuchsia-600 p-1.5 rounded hover:bg-fuchsia-50 transition-colors" data-testid={`edit-template-${t.id}`}>
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button onClick={() => handleDelete(t.id)} className="text-gray-400 hover:text-red-500 p-1.5 rounded hover:bg-red-50 transition-colors" data-testid={`delete-template-${t.id}`}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
