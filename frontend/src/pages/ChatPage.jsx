import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { BACKEND_URL } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, Send, Plus, Users, User, Paperclip, Image,
  MessageSquare, X, Search, Check, CheckCheck, Loader2,
} from "lucide-react";

const API = BACKEND_URL;

export default function ChatPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [conversations, setConversations] = useState([]);
  const [activeConvo, setActiveConvo] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMsg, setNewMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [showNewChat, setShowNewChat] = useState(false);
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [chatUsers, setChatUsers] = useState([]);
  const [groupName, setGroupName] = useState("");
  const [selectedMembers, setSelectedMembers] = useState([]);
  const [searchUsers, setSearchUsers] = useState("");
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.get(`/chat/conversations?token=${token}`);
      setConversations(res.data);
    } catch {}
  }, [token]);

  const loadMessages = useCallback(async (convId) => {
    try {
      const res = await api.get(`/chat/conversations/${convId}/messages?token=${token}`);
      setMessages(res.data);
    } catch {}
  }, [token]);

  useEffect(() => {
    loadConversations();
    api.get(`/chat/users?token=${token}`).then(r => setChatUsers(r.data)).catch(() => {});
  }, [loadConversations, token]);

  // Polling
  useEffect(() => {
    const poll = setInterval(() => {
      loadConversations();
      if (activeConvo) loadMessages(activeConvo.id);
    }, 4000);
    pollRef.current = poll;
    return () => clearInterval(poll);
  }, [activeConvo, loadConversations, loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openConvo = async (convo) => {
    setActiveConvo(convo);
    loadMessages(convo.id);
  };

  const sendMessage = async (e) => {
    e?.preventDefault();
    if (!newMsg.trim() || !activeConvo || sending) return;
    setSending(true);
    try {
      const formData = new FormData();
      formData.append("text", newMsg.trim());
      await api.post(`/chat/conversations/${activeConvo.id}/messages?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setNewMsg("");
      loadMessages(activeConvo.id);
      loadConversations();
    } catch { toast.error("Fehler beim Senden"); }
    finally { setSending(false); }
  };

  const sendFile = async (file) => {
    if (!activeConvo || !file) return;
    setSending(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("text", "");
      await api.post(`/chat/conversations/${activeConvo.id}/messages?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      loadMessages(activeConvo.id);
      loadConversations();
    } catch { toast.error("Datei-Upload fehlgeschlagen"); }
    finally { setSending(false); }
  };

  const startDirectChat = async (otherUser) => {
    try {
      const res = await api.post(`/chat/conversations?token=${token}`, {
        type: "direct", members: [user.id, otherUser.id]
      });
      setShowNewChat(false);
      const convo = { ...res.data, display_name: otherUser.name };
      setActiveConvo(convo);
      loadMessages(convo.id);
      loadConversations();
    } catch { toast.error("Fehler"); }
  };

  const createGroup = async () => {
    if (!groupName.trim() || selectedMembers.length === 0) return;
    try {
      const res = await api.post(`/chat/conversations?token=${token}`, {
        type: "group", name: groupName.trim(), members: [user.id, ...selectedMembers]
      });
      const convo = { ...res.data, display_name: groupName.trim() };
      setShowNewGroup(false);
      setGroupName("");
      setSelectedMembers([]);
      setActiveConvo(convo);
      loadMessages(res.data.id);
      loadConversations();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const isAdmin = user?.role === "admin";
  const filteredUsers = chatUsers.filter(u =>
    u.name.toLowerCase().includes(searchUsers.toLowerCase()) ||
    u.email.toLowerCase().includes(searchUsers.toLowerCase())
  );

  const formatTime = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50" data-testid="chat-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-2.5 flex items-center gap-3 flex-shrink-0">
        <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600" data-testid="chat-back-btn">
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <MessageSquare className="w-5 h-5 text-fuchsia-600" />
        <h1 className="text-base font-semibold text-gray-900">Team Chat</h1>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Conversation List */}
        <aside className="w-72 lg:w-80 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
          <div className="p-3 border-b border-gray-100 flex items-center gap-2">
            <Button size="sm" onClick={() => setShowNewChat(true)} className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs" data-testid="new-chat-btn">
              <User className="w-3.5 h-3.5 mr-1" /> Direktnachricht
            </Button>
            {isAdmin && (
              <Button size="sm" variant="outline" onClick={() => setShowNewGroup(true)} className="text-xs" data-testid="new-group-btn">
                <Users className="w-3.5 h-3.5 mr-1" /> Gruppe
              </Button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="p-6 text-center text-gray-400 text-sm">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
                Noch keine Chats
              </div>
            ) : conversations.map(c => (
              <button
                key={c.id}
                onClick={() => openConvo(c)}
                className={`w-full text-left px-3 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors flex items-center gap-3 ${activeConvo?.id === c.id ? "bg-fuchsia-50 border-l-2 border-l-fuchsia-500" : ""}`}
                data-testid={`convo-${c.id}`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${c.type === "group" ? "bg-blue-100" : "bg-gray-100"}`}>
                  {c.type === "group" ? <Users className="w-4 h-4 text-blue-600" /> : <User className="w-4 h-4 text-gray-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 truncate">{c.display_name}</span>
                    {c.last_message?.sent_at && <span className="text-[10px] text-gray-400 flex-shrink-0 ml-1">{formatTime(c.last_message.sent_at)}</span>}
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-gray-500 truncate">{c.last_message?.text || "Keine Nachrichten"}</p>
                    {c.unread_count > 0 && (
                      <span className="ml-1 w-5 h-5 rounded-full bg-fuchsia-600 text-white text-[10px] flex items-center justify-center flex-shrink-0">{c.unread_count}</span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Chat Area */}
        <main className="flex-1 flex flex-col min-w-0">
          {!activeConvo ? (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Wählen Sie einen Chat aus</p>
              </div>
            </div>
          ) : (
            <>
              {/* Chat Header */}
              <div className="bg-white border-b border-gray-200 px-4 py-2.5 flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${activeConvo.type === "group" ? "bg-blue-100" : "bg-gray-100"}`}>
                  {activeConvo.type === "group" ? <Users className="w-4 h-4 text-blue-600" /> : <User className="w-4 h-4 text-gray-500" />}
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">{activeConvo.display_name}</h2>
                  {activeConvo.type === "group" && <p className="text-[10px] text-gray-400">{activeConvo.members?.length} Mitglieder</p>}
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1" data-testid="messages-area">
                {messages.map(m => {
                  const isMine = m.sender_id === user?.id;
                  const isImage = m.attachment?.content_type?.startsWith("image/");
                  return (
                    <div key={m.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[70%] ${isMine ? "order-2" : ""}`}>
                        {!isMine && activeConvo.type === "group" && (
                          <span className="text-[10px] text-gray-400 ml-1">{m.sender_name}</span>
                        )}
                        <div className={`rounded-2xl px-3 py-2 ${isMine ? "bg-fuchsia-600 text-white rounded-br-md" : "bg-white border border-gray-200 text-gray-900 rounded-bl-md"}`}>
                          {m.attachment && (
                            <div className="mb-1">
                              {isImage ? (
                                <img
                                  src={`${API}/api/chat/conversations/${activeConvo.id}/file/${m.attachment.id}?token=${token}`}
                                  alt={m.attachment.filename}
                                  className="rounded-lg max-w-full max-h-48 cursor-pointer"
                                  onClick={() => window.open(`${API}/api/chat/conversations/${activeConvo.id}/file/${m.attachment.id}?token=${token}`, "_blank")}
                                />
                              ) : (
                                <a
                                  href={`${API}/api/chat/conversations/${activeConvo.id}/file/${m.attachment.id}?token=${token}`}
                                  target="_blank" rel="noreferrer"
                                  className={`text-xs underline flex items-center gap-1 ${isMine ? "text-white/90" : "text-fuchsia-600"}`}
                                >
                                  <Paperclip className="w-3 h-3" /> {m.attachment.filename}
                                </a>
                              )}
                            </div>
                          )}
                          {m.text && <p className="text-sm whitespace-pre-wrap break-words">{m.text}</p>}
                          <div className={`flex items-center justify-end gap-1 mt-0.5 ${isMine ? "text-white/60" : "text-gray-400"}`}>
                            <span className="text-[10px]">{formatTime(m.created_at)}</span>
                            {isMine && <CheckCheck className="w-3 h-3" />}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <form onSubmit={sendMessage} className="bg-white border-t border-gray-200 px-3 py-2 flex items-center gap-2" data-testid="chat-input-form">
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={e => { if (e.target.files[0]) sendFile(e.target.files[0]); e.target.value = ""; }}
                />
                <Button type="button" variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} className="text-gray-400 hover:text-fuchsia-600 flex-shrink-0" data-testid="attach-file-btn">
                  <Paperclip className="w-4 h-4" />
                </Button>
                <Input
                  value={newMsg}
                  onChange={e => setNewMsg(e.target.value)}
                  placeholder="Nachricht schreiben..."
                  className="flex-1 border-0 bg-gray-100 focus-visible:ring-0 text-sm"
                  data-testid="chat-message-input"
                />
                <Button type="submit" size="sm" disabled={!newMsg.trim() || sending} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white flex-shrink-0" data-testid="send-message-btn">
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </form>
            </>
          )}
        </main>
      </div>

      {/* New Direct Chat Modal */}
      {showNewChat && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={() => setShowNewChat(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()} data-testid="new-chat-modal">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Neue Nachricht</h3>
              <button onClick={() => setShowNewChat(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-400" />
                <Input value={searchUsers} onChange={e => setSearchUsers(e.target.value)} placeholder="Suchen..." className="pl-8 text-sm" data-testid="search-users-input" />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-3">
              {filteredUsers.map(u => (
                <button key={u.id} onClick={() => startDirectChat(u)} className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-gray-50 flex items-center gap-3" data-testid={`start-chat-${u.id}`}>
                  <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                    <User className="w-4 h-4 text-gray-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{u.name}</p>
                    <p className="text-xs text-gray-400">{u.role}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* New Group Modal */}
      {showNewGroup && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={() => setShowNewGroup(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()} data-testid="new-group-modal">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Neue Gruppe</h3>
              <button onClick={() => setShowNewGroup(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-3 space-y-3">
              <Input value={groupName} onChange={e => setGroupName(e.target.value)} placeholder="Gruppenname..." className="text-sm" data-testid="group-name-input" />
              <p className="text-xs text-gray-500">Mitglieder auswählen:</p>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-3">
              {chatUsers.map(u => {
                const sel = selectedMembers.includes(u.id);
                return (
                  <button key={u.id} onClick={() => setSelectedMembers(prev => sel ? prev.filter(x => x !== u.id) : [...prev, u.id])}
                    className={`w-full text-left px-3 py-2 rounded-lg flex items-center gap-3 ${sel ? "bg-fuchsia-50" : "hover:bg-gray-50"}`}
                    data-testid={`group-member-${u.id}`}
                  >
                    <div className={`w-5 h-5 rounded border flex items-center justify-center ${sel ? "bg-fuchsia-600 border-fuchsia-600" : "border-gray-300"}`}>
                      {sel && <Check className="w-3 h-3 text-white" />}
                    </div>
                    <span className="text-sm text-gray-900">{u.name}</span>
                    <span className="text-xs text-gray-400">{u.role}</span>
                  </button>
                );
              })}
            </div>
            <div className="p-3 border-t border-gray-200">
              <Button onClick={createGroup} disabled={!groupName.trim() || selectedMembers.length === 0} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="create-group-btn">
                Gruppe erstellen ({selectedMembers.length} Mitglieder)
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
