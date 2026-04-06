import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, Plus, Trash2, Save, Paperclip, FileText, Image,
  ChevronDown, ChevronUp, Download, X, Calendar, User,
} from "lucide-react";

export default function MitarbeiterNotizenPage() {
  const { user } = useAuth();
  const { userId } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [notes, setNotes] = useState([]);
  const [empName, setEmpName] = useState("");
  const [expandedNote, setExpandedNote] = useState(null);
  const [editing, setEditing] = useState(null);
  const [newNote, setNewNote] = useState(null);

  const loadNotes = useCallback(async () => {
    try {
      const res = await api.get(`/employee/notes/${userId}?token=${token}`);
      setNotes(res.data || []);
    } catch {}
  }, [token, userId]);

  useEffect(() => {
    loadNotes();
    api.get(`/chat/users?token=${token}`).then(r => {
      const u = (r.data || []).find(u => u.id === userId);
      if (u) setEmpName(u.name);
    }).catch(() => {});
  }, [loadNotes, token, userId]);

  const createNote = async () => {
    if (!newNote?.title?.trim()) return toast.error("Titel erforderlich");
    try {
      const res = await api.post(`/employee/notes/${userId}?token=${token}`, newNote);
      setNewNote(null);
      setExpandedNote(res.data.id);
      loadNotes();
      toast.success("Notiz erstellt");
    } catch { toast.error("Fehler"); }
  };

  const updateNote = async (noteId) => {
    if (!editing) return;
    try {
      await api.put(`/employee/notes/entry/${noteId}?token=${token}`, editing);
      setEditing(null);
      loadNotes();
      toast.success("Gespeichert");
    } catch { toast.error("Fehler"); }
  };

  const deleteNote = async (noteId) => {
    if (!window.confirm("Notiz löschen?")) return;
    try {
      await api.delete(`/employee/notes/entry/${noteId}?token=${token}`);
      loadNotes();
      toast.success("Gelöscht");
    } catch { toast.error("Fehler"); }
  };

  const uploadFile = async (noteId, file) => {
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post(`/employee/notes/entry/${noteId}/upload?token=${token}`, form);
      loadNotes();
      toast.success("Datei hochgeladen");
    } catch { toast.error("Upload fehlgeschlagen"); }
  };

  const deleteFile = async (noteId, fileId) => {
    try {
      await api.delete(`/employee/notes/files/${noteId}/${fileId}?token=${token}`);
      loadNotes();
    } catch { toast.error("Fehler"); }
  };

  const fileUrl = (noteId, fileId) =>
    `${process.env.REACT_APP_BACKEND_URL}/api/employee/notes/files/${noteId}/${fileId}?token=${token}`;

  const isImage = (ct) => ct?.startsWith("image/");

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <User className="w-5 h-5 text-amber-600" />
          <h1 className="text-lg font-semibold text-gray-900">{empName}</h1>
          <span className="text-gray-400">/</span>
          <span className="text-gray-500">Notizen</span>
        </div>

        {/* New Note */}
        {newNote ? (
          <div className="bg-white rounded-xl border-2 border-amber-300 p-4 mb-4 space-y-3" data-testid="new-note-form">
            <input type="text" placeholder="Titel / Betreff" value={newNote.title || ""} onChange={e => setNewNote(p => ({ ...p, title: e.target.value }))}
              className="w-full text-base font-semibold border-b border-gray-200 pb-2 focus:outline-none focus:border-amber-400" autoFocus data-testid="new-note-title" />
            <div className="flex gap-3">
              <input type="date" value={newNote.date || new Date().toISOString().slice(0, 10)} onChange={e => setNewNote(p => ({ ...p, date: e.target.value }))}
                className="border border-gray-200 rounded px-2 py-1 text-sm" data-testid="new-note-date" />
            </div>
            <textarea placeholder="Gesprächsnotiz..." value={newNote.text || ""} onChange={e => setNewNote(p => ({ ...p, text: e.target.value }))}
              rows={4} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-400 resize-y" data-testid="new-note-text" />
            <div className="flex gap-2">
              <Button onClick={createNote} size="sm" className="bg-amber-600 hover:bg-amber-700" data-testid="save-new-note-btn">
                <Save className="w-3.5 h-3.5 mr-1" /> Erstellen
              </Button>
              <Button onClick={() => setNewNote(null)} size="sm" variant="outline" data-testid="cancel-new-note-btn">Abbrechen</Button>
            </div>
          </div>
        ) : (
          <Button onClick={() => setNewNote({ title: "", text: "", date: new Date().toISOString().slice(0, 10) })} className="mb-4 bg-amber-600 hover:bg-amber-700" data-testid="add-note-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Neue Notiz
          </Button>
        )}

        {/* Notes List */}
        <div className="space-y-3">
          {notes.map(note => {
            const isOpen = expandedNote === note.id;
            const isEditing = editing && editing._id === note.id;
            return (
              <div key={note.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`note-${note.id}`}>
                {/* Header */}
                <button onClick={() => { setExpandedNote(isOpen ? null : note.id); setEditing(null); }}
                  className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{note.title || "Ohne Titel"}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-gray-400 flex items-center gap-1">
                        <Calendar className="w-2.5 h-2.5" />
                        {new Date(note.date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}
                      </span>
                      <span className="text-[10px] text-gray-400">von {note.created_by_name}</span>
                      {(note.files || []).length > 0 && (
                        <span className="text-[10px] text-amber-600 flex items-center gap-0.5">
                          <Paperclip className="w-2.5 h-2.5" /> {note.files.length}
                        </span>
                      )}
                    </div>
                  </div>
                  {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </button>

                {/* Expanded Content */}
                {isOpen && (
                  <div className="px-4 pb-4 border-t border-gray-100">
                    {isEditing ? (
                      <div className="space-y-3 pt-3">
                        <input type="text" value={editing.title} onChange={e => setEditing(p => ({ ...p, title: e.target.value }))}
                          className="w-full font-semibold border-b border-gray-200 pb-1 focus:outline-none focus:border-amber-400" />
                        <input type="date" value={editing.date} onChange={e => setEditing(p => ({ ...p, date: e.target.value }))}
                          className="border border-gray-200 rounded px-2 py-1 text-sm" />
                        <textarea value={editing.text} onChange={e => setEditing(p => ({ ...p, text: e.target.value }))}
                          rows={5} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-400 resize-y" />
                        <div className="flex gap-2">
                          <Button onClick={() => updateNote(note.id)} size="sm" className="bg-amber-600 hover:bg-amber-700">
                            <Save className="w-3.5 h-3.5 mr-1" /> Speichern
                          </Button>
                          <Button onClick={() => setEditing(null)} size="sm" variant="outline">Abbrechen</Button>
                        </div>
                      </div>
                    ) : (
                      <div className="pt-3">
                        <p className="text-sm text-gray-700 whitespace-pre-wrap mb-3">{note.text || "—"}</p>
                        <div className="flex gap-2 mb-3">
                          <Button onClick={() => setEditing({ _id: note.id, title: note.title, text: note.text, date: note.date })} size="sm" variant="outline">
                            Bearbeiten
                          </Button>
                          <Button onClick={() => deleteNote(note.id)} size="sm" variant="outline" className="text-red-600 border-red-200 hover:bg-red-50">
                            <Trash2 className="w-3.5 h-3.5 mr-1" /> Löschen
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Files */}
                    <div className="border-t border-gray-100 pt-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Dokumente & Bilder</span>
                        <label className="cursor-pointer">
                          <input type="file" className="hidden" onChange={e => { if (e.target.files[0]) uploadFile(note.id, e.target.files[0]); e.target.value = ""; }} data-testid={`upload-file-${note.id}`} />
                          <span className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium">
                            <Plus className="w-3 h-3" /> Datei hinzufügen
                          </span>
                        </label>
                      </div>
                      {(note.files || []).length === 0 && (
                        <p className="text-xs text-gray-300 italic">Keine Dateien</p>
                      )}
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        {(note.files || []).map(f => (
                          <div key={f.id} className="border border-gray-200 rounded-lg overflow-hidden group relative">
                            {isImage(f.content_type) ? (
                              <a href={fileUrl(note.id, f.id)} target="_blank" rel="noreferrer">
                                <img src={fileUrl(note.id, f.id)} alt={f.filename} className="w-full h-24 object-cover" />
                              </a>
                            ) : (
                              <a href={fileUrl(note.id, f.id)} target="_blank" rel="noreferrer" className="flex items-center gap-2 p-2.5 hover:bg-gray-50">
                                <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />
                                <span className="text-xs text-gray-600 truncate">{f.filename}</span>
                              </a>
                            )}
                            <button onClick={() => deleteFile(note.id, f.id)}
                              className="absolute top-1 right-1 bg-white/80 rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50" data-testid={`delete-file-${f.id}`}>
                              <X className="w-3 h-3 text-red-500" />
                            </button>
                            {isImage(f.content_type) && (
                              <p className="text-[10px] text-gray-500 truncate px-2 py-1">{f.filename}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {notes.length === 0 && !newNote && (
            <p className="text-center text-gray-400 py-8">Noch keine Notizen vorhanden</p>
          )}
        </div>
      </div>
    </div>
  );
}
