import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  ArrowLeft, HelpCircle, Plus, Search, Edit2, Trash2, ChevronDown, ChevronRight, Save,
} from "lucide-react";

export default function FAQPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [faqs, setFaqs] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(new Set());
  const [loading, setLoading] = useState(true);

  const [showDialog, setShowDialog] = useState(false);
  const [editingFaq, setEditingFaq] = useState(null);
  const [formQ, setFormQ] = useState("");
  const [formA, setFormA] = useState("");
  const [formCat, setFormCat] = useState("Allgemein");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/employee/faq?token=${token}${search ? `&q=${encodeURIComponent(search)}` : ""}`);
      setFaqs(res.data.faqs || []);
      setCategories(res.data.categories || []);
    } catch {
      toast.error("Konnte FAQs nicht laden");
    }
    setLoading(false);
  }, [token, search]);

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  const toggle = (id) => {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    setExpanded(next);
  };

  const openNew = () => {
    setEditingFaq(null);
    setFormQ(""); setFormA(""); setFormCat("Allgemein");
    setShowDialog(true);
  };

  const openEdit = (faq) => {
    setEditingFaq(faq);
    setFormQ(faq.question); setFormA(faq.answer); setFormCat(faq.category);
    setShowDialog(true);
  };

  const save = async () => {
    if (!formQ.trim() || !formA.trim()) {
      toast.error("Frage und Antwort erforderlich");
      return;
    }
    setSaving(true);
    try {
      const payload = { question: formQ.trim(), answer: formA.trim(), category: formCat.trim() || "Allgemein" };
      if (editingFaq) {
        await api.put(`/employee/faq/${editingFaq.id}?token=${token}`, payload);
        toast.success("Aktualisiert");
      } else {
        await api.post(`/employee/faq?token=${token}`, payload);
        toast.success("Angelegt");
      }
      setShowDialog(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Speichern");
    }
    setSaving(false);
  };

  const remove = async (faq) => {
    if (!window.confirm(`FAQ "${faq.question}" wirklich löschen?`)) return;
    try {
      await api.delete(`/employee/faq/${faq.id}?token=${token}`);
      toast.success("Gelöscht");
      load();
    } catch {
      toast.error("Fehler");
    }
  };

  // Gruppiere nach Kategorie
  const grouped = {};
  faqs.forEach(f => {
    const c = f.category || "Allgemein";
    if (!grouped[c]) grouped[c] = [];
    grouped[c].push(f);
  });
  const categoriesOrder = [...new Set([...Object.keys(grouped), ...categories])];

  return (
    <div className="min-h-screen bg-gray-50" data-testid="faq-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="faq-back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <HelpCircle className="w-5 h-5 text-indigo-600" />
          <h1 className="text-lg font-semibold text-gray-900">FAQ &amp; Wissensdatenbank</h1>
          {isAdmin && (
            <Button size="sm" className="ml-auto bg-indigo-600 hover:bg-indigo-700" onClick={openNew} data-testid="faq-new-btn">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Neuer Eintrag
            </Button>
          )}
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-5 space-y-4">
        {/* Suchfeld */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="FAQ durchsuchen..."
            className="pl-9"
            data-testid="faq-search"
          />
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">Lade...</div>
        ) : faqs.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <HelpCircle className="w-10 h-10 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">
              {search ? `Keine Ergebnisse für "${search}"` : "Noch keine FAQs angelegt."}
            </p>
            {isAdmin && !search && (
              <Button size="sm" className="mt-3 bg-indigo-600 hover:bg-indigo-700" onClick={openNew}>
                <Plus className="w-3.5 h-3.5 mr-1.5" /> Ersten Eintrag anlegen
              </Button>
            )}
          </div>
        ) : (
          categoriesOrder.filter(c => grouped[c]).map(cat => (
            <div key={cat} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`faq-category-${cat}`}>
              <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200">
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{cat}</p>
              </div>
              <div className="divide-y divide-gray-100">
                {grouped[cat].map(faq => {
                  const isOpen = expanded.has(faq.id);
                  return (
                    <div key={faq.id} className="px-4 py-3" data-testid={`faq-${faq.id}`}>
                      <div className="flex items-start gap-2">
                        <button
                          onClick={() => toggle(faq.id)}
                          className="flex-1 text-left flex items-start gap-2 group"
                          data-testid={`faq-toggle-${faq.id}`}
                        >
                          {isOpen ? (
                            <ChevronDown className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0 group-hover:text-indigo-500" />
                          )}
                          <span className="text-sm font-medium text-gray-900 group-hover:text-indigo-700">{faq.question}</span>
                        </button>
                        {isAdmin && (
                          <div className="flex items-center gap-1 flex-shrink-0">
                            <button onClick={() => openEdit(faq)} className="text-gray-300 hover:text-indigo-600" title="Bearbeiten" data-testid={`faq-edit-${faq.id}`}>
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => remove(faq)} className="text-gray-300 hover:text-red-500" title="Löschen" data-testid={`faq-delete-${faq.id}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                      {isOpen && (
                        <div className="mt-2 ml-6 pl-2 border-l-2 border-indigo-100">
                          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{faq.answer}</p>
                          <p className="text-[10px] text-gray-400 mt-2">
                            {faq.author_name} · {new Date(faq.updated_at || faq.created_at).toLocaleDateString("de-DE")}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Neuer/Bearbeiten Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="sm:max-w-lg" data-testid="faq-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-indigo-600" />
              {editingFaq ? "FAQ bearbeiten" : "Neue FAQ anlegen"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-1">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Kategorie</label>
              <Select value={formCat} onValueChange={setFormCat}>
                <SelectTrigger data-testid="faq-category-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {categories.map(c => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Frage</label>
              <Input
                value={formQ}
                onChange={e => setFormQ(e.target.value)}
                placeholder="z.B. Wie beantrage ich Urlaub?"
                data-testid="faq-question-input"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Antwort</label>
              <textarea
                value={formA}
                onChange={e => setFormA(e.target.value)}
                rows={6}
                placeholder="Detaillierte Antwort..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                data-testid="faq-answer-input"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setShowDialog(false)} disabled={saving}>Abbrechen</Button>
              <Button size="sm" onClick={save} disabled={saving} className="bg-indigo-600 hover:bg-indigo-700" data-testid="faq-save-btn">
                <Save className="w-3.5 h-3.5 mr-1.5" /> {saving ? "Speichern..." : "Speichern"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
