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
  FileText, Download, UserPlus, UserMinus, ChevronRight, Camera, Pencil,
  SmilePlus, MessageCircle, CornerDownRight,
} from "lucide-react";
import { openExternal } from "../lib/openExternal";

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
  const messagesScrollRef = useRef(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [hasNewBelow, setHasNewBelow] = useState(false);
  const lastMessageCountRef = useRef(0);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const pollRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [detailTab, setDetailTab] = useState("members");
  const [convoMembers, setConvoMembers] = useState([]);
  const [convoFiles, setConvoFiles] = useState([]);
  const [convoImages, setConvoImages] = useState([]);
  const [convoCreatedBy, setConvoCreatedBy] = useState(null);
  const [addMemberSearch, setAddMemberSearch] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [editName, setEditName] = useState("");
  const avatarInputRef = useRef(null);
  const [memberAvatars, setMemberAvatars] = useState({});
  // Teams-Style Thread + Reactions
  const [openThreadId, setOpenThreadId] = useState(null);
  const [threadReplies, setThreadReplies] = useState([]);
  const [threadInput, setThreadInput] = useState("");
  const [threadSending, setThreadSending] = useState(false);
  const [reactionPickerFor, setReactionPickerFor] = useState(null); // msg.id whose reaction bar is shown

  // iOS-Tastatur-Fix: passe Container-Höhe an die VisualViewport an,
  // damit das Eingabefeld nicht hinter der virtuellen Tastatur verschwindet.
  const [viewportHeight, setViewportHeight] = useState(null);
  useEffect(() => {
    const vp = typeof window !== "undefined" ? window.visualViewport : null;
    if (!vp) return;
    const update = () => setViewportHeight(vp.height);
    update();
    vp.addEventListener("resize", update);
    vp.addEventListener("scroll", update);
    return () => {
      vp.removeEventListener("resize", update);
      vp.removeEventListener("scroll", update);
    };
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.get(`/chat/conversations?token=${token}`);
      setConversations(res.data);
      // Load avatars for DM partners
      res.data.forEach(c => {
        if (c.type === "direct") {
          const partnerId = c.members?.find(id => id !== user?.id);
          if (partnerId && !memberAvatars[partnerId]) {
            api.get(`/employee/profile/${partnerId}?token=${token}`).then(r => {
              if (r.data.avatar_path) {
                setMemberAvatars(prev => ({ ...prev, [partnerId]: `${API}/api/employee/avatar/${partnerId}?token=${token}&_=${r.data.avatar_path}` }));
              }
            }).catch(() => {});
          }
        }
      });
    } catch {}
  }, [token, user?.id]);

  const loadMessages = useCallback(async (convId) => {
    try {
      const res = await api.get(`/chat/conversations/${convId}/messages?token=${token}`);
      setMessages(res.data);
      // Load unique sender avatars
      const senderIds = [...new Set(res.data.map(m => m.sender_id).filter(Boolean))];
      senderIds.forEach(sid => {
        if (!memberAvatars[sid]) {
          api.get(`/employee/profile/${sid}?token=${token}`).then(r => {
            if (r.data.avatar_path) {
              setMemberAvatars(prev => ({ ...prev, [sid]: `${API}/api/employee/avatar/${sid}?token=${token}&_=${r.data.avatar_path}` }));
            }
          }).catch(() => {});
        }
      });
    } catch {}
  }, [token, memberAvatars]);

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

  // Auto-Scroll: nur wenn User bereits unten ist. Wenn er hochgescrollt hat,
  // bleibt seine Position erhalten und es erscheint ein "↓ neue Nachrichten"-Button.
  useEffect(() => {
    const prevCount = lastMessageCountRef.current;
    const newCount = messages.length;
    lastMessageCountRef.current = newCount;
    if (newCount === 0) return;
    if (newCount > prevCount && !isAtBottom) {
      // Neue Nachrichten, aber User schaut weiter oben → nur Indikator zeigen
      setHasNewBelow(true);
      return;
    }
    if (isAtBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: prevCount === 0 ? "auto" : "smooth" });
      setHasNewBelow(false);
    }
  }, [messages, isAtBottom]);

  // Wenn der User zur aktiven Konversation wechselt, immer nach unten scrollen
  useEffect(() => {
    if (!activeConvo) return;
    setIsAtBottom(true);
    setHasNewBelow(false);
    lastMessageCountRef.current = 0;
  }, [activeConvo?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMessagesScroll = (e) => {
    const el = e.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom < 80; // 80px Toleranz
    setIsAtBottom(atBottom);
    if (atBottom) setHasNewBelow(false);
  };

  const scrollToBottomNow = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    setHasNewBelow(false);
    setIsAtBottom(true);
  };

  const loadThread = useCallback(async (msgId) => {
    if (!activeConvo || !msgId) return;
    try {
      const res = await api.get(`/chat/conversations/${activeConvo.id}/messages?token=${token}&parent_id=${msgId}`);
      setThreadReplies(res.data || []);
      // sender avatars
      const senderIds = [...new Set((res.data || []).map(m => m.sender_id).filter(Boolean))];
      senderIds.forEach(sid => {
        if (!memberAvatars[sid]) {
          api.get(`/employee/profile/${sid}?token=${token}`).then(r => {
            if (r.data.avatar_path) {
              setMemberAvatars(prev => ({ ...prev, [sid]: `${API}/api/employee/avatar/${sid}?token=${token}&_=${r.data.avatar_path}` }));
            }
          }).catch(() => {});
        }
      });
    } catch {}
  }, [activeConvo, token, memberAvatars]);

  const toggleThread = (msgId) => {
    if (openThreadId === msgId) {
      setOpenThreadId(null);
      setThreadReplies([]);
      setThreadInput("");
    } else {
      setOpenThreadId(msgId);
      setThreadInput("");
      loadThread(msgId);
    }
  };

  const sendThreadReply = async (e) => {
    e?.preventDefault();
    if (!threadInput.trim() || !activeConvo || !openThreadId || threadSending) return;
    setThreadSending(true);
    try {
      const formData = new FormData();
      formData.append("text", threadInput.trim());
      formData.append("parent_id", openThreadId);
      await api.post(`/chat/conversations/${activeConvo.id}/messages?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setThreadInput("");
      await loadThread(openThreadId);
      loadMessages(activeConvo.id);
    } catch { toast.error("Antwort fehlgeschlagen"); }
    finally { setThreadSending(false); }
  };

  const toggleReaction = async (msgId, emoji) => {
    try {
      const formData = new FormData();
      formData.append("emoji", emoji);
      const res = await api.post(`/chat/messages/${msgId}/react?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      // Inline State-Update fuer sofortiges Feedback
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, reactions: res.data.reactions } : m));
      setThreadReplies(prev => prev.map(m => m.id === msgId ? { ...m, reactions: res.data.reactions } : m));
      setReactionPickerFor(null);
    } catch { toast.error("Reaktion fehlgeschlagen"); }
  };

  const openConvo = async (convo) => {
    setActiveConvo(convo);
    setOpenThreadId(null);
    setThreadReplies([]);
    setReactionPickerFor(null);
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
      setIsAtBottom(true); // eigene Nachricht → ans Ende scrollen
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
      setIsAtBottom(true); // eigener Datei-Upload → ans Ende scrollen
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

  const openDetail = async () => {
    if (!activeConvo) return;
    setShowDetail(true);
    setDetailTab("members");
    try {
      const [membersRes, attachRes] = await Promise.all([
        api.get(`/chat/conversations/${activeConvo.id}/members?token=${token}`),
        api.get(`/chat/conversations/${activeConvo.id}/attachments-list?token=${token}`),
      ]);
      setConvoMembers(membersRes.data.members || []);
      setConvoCreatedBy(membersRes.data.created_by);
      setConvoFiles(attachRes.data.files || []);
      setConvoImages(attachRes.data.images || []);
    } catch { toast.error("Fehler beim Laden"); }
  };

  const addMember = async (uid) => {
    try {
      await api.put(`/chat/conversations/${activeConvo.id}/members?token=${token}`, { action: "add", user_id: uid });
      const res = await api.get(`/chat/conversations/${activeConvo.id}/members?token=${token}`);
      setConvoMembers(res.data.members || []);
      setActiveConvo(prev => ({ ...prev, members: res.data.members?.map(m => m.id) }));
      loadConversations();
      toast.success("Mitglied hinzugefügt");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const removeMember = async (uid) => {
    try {
      await api.put(`/chat/conversations/${activeConvo.id}/members?token=${token}`, { action: "remove", user_id: uid });
      const res = await api.get(`/chat/conversations/${activeConvo.id}/members?token=${token}`);
      setConvoMembers(res.data.members || []);
      setActiveConvo(prev => ({ ...prev, members: res.data.members?.map(m => m.id) }));
      loadConversations();
      toast.success("Mitglied entfernt");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const nonMembers = chatUsers.filter(u =>
    !convoMembers.some(m => m.id === u.id) &&
    u.name.toLowerCase().includes(addMemberSearch.toLowerCase())
  );

  const uploadAvatar = async (file) => {
    if (!file || !activeConvo) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", "");
      await api.put(`/chat/conversations/${activeConvo.id}/settings?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setActiveConvo(prev => ({ ...prev, avatar_path: "updated_" + Date.now() }));
      loadConversations();
      toast.success("Gruppenbild aktualisiert");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const saveGroupName = async () => {
    if (!editName.trim() || !activeConvo) return;
    try {
      const formData = new FormData();
      formData.append("name", editName.trim());
      await api.put(`/chat/conversations/${activeConvo.id}/settings?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setActiveConvo(prev => ({ ...prev, display_name: editName.trim(), name: editName.trim() }));
      setEditingName(false);
      loadConversations();
      toast.success("Name geändert");
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const getAvatarUrl = (convo) => {
    if (!convo?.avatar_path) return null;
    return `${API}/api/chat/conversations/${convo.id}/avatar?token=${token}&_=${convo.avatar_path}`;
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
    <div
      className="flex flex-col bg-gray-50 safe-area-pad"
      style={{ height: viewportHeight ? `${viewportHeight}px` : "100dvh" }}
      data-testid="chat-page"
    >
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
        <aside className={`${activeConvo ? "hidden md:flex" : "flex"} w-full md:w-72 lg:w-80 bg-white border-r border-gray-200 flex-col flex-shrink-0`}>
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
                <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden ${c.type === "group" ? "bg-blue-100" : "bg-gray-100"}`}>
                  {c.avatar_path ? (
                    <img src={getAvatarUrl(c)} alt="" className="w-full h-full object-cover" />
                  ) : c.type === "direct" && memberAvatars[c.members?.find(id => id !== user?.id)] ? (
                    <img src={memberAvatars[c.members?.find(id => id !== user?.id)]} alt="" className="w-full h-full object-cover" />
                  ) : c.type === "group" ? <Users className="w-4 h-4 text-blue-600" /> : <User className="w-4 h-4 text-gray-500" />}
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
        <main className={`${!activeConvo ? "hidden md:flex" : "flex"} flex-1 flex-col min-w-0`}>
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
                <button onClick={() => setActiveConvo(null)} className="md:hidden text-gray-500 hover:text-gray-700 flex-shrink-0" data-testid="chat-mobile-back">
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <button onClick={openDetail} className="flex items-center gap-3 flex-1 min-w-0 hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 transition-colors" data-testid="chat-header-detail-btn">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden ${activeConvo.type === "group" ? "bg-blue-100" : "bg-gray-100"}`}>
                    {activeConvo.avatar_path ? (
                      <img src={getAvatarUrl(activeConvo)} alt="" className="w-full h-full object-cover" />
                    ) : activeConvo.type === "group" ? <Users className="w-4 h-4 text-blue-600" /> : <User className="w-4 h-4 text-gray-500" />}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-gray-900 truncate">{activeConvo.display_name}</h2>
                    {activeConvo.type === "group" && <p className="text-[10px] text-gray-400">{activeConvo.members?.length} Mitglieder</p>}
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                </button>
              </div>

              {/* Messages */}
              <div
                ref={messagesScrollRef}
                className={`flex-1 overflow-y-auto px-4 py-3 space-y-1 transition-colors relative ${dragOver ? "bg-fuchsia-50/50 ring-2 ring-inset ring-fuchsia-400 ring-dashed" : ""}`}
                data-testid="messages-area"
                onScroll={handleMessagesScroll}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={e => { e.preventDefault(); setDragOver(false); }}
                onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) setPendingFile(e.dataTransfer.files[0]); }}
              >
                {dragOver && (
                  <div className="flex items-center justify-center py-8 pointer-events-none">
                    <div className="bg-white/90 rounded-xl px-6 py-4 shadow-lg border-2 border-dashed border-fuchsia-400 text-center">
                      <Paperclip className="w-6 h-6 text-fuchsia-500 mx-auto mb-1" />
                      <p className="text-sm text-fuchsia-600 font-medium">Datei hier ablegen</p>
                    </div>
                  </div>
                )}
                {messages.map(m => {
                  const isMine = m.sender_id === user?.id;
                  const isImage = m.attachment?.content_type?.startsWith("image/");
                  const senderAvatar = memberAvatars[m.sender_id];
                  const reactions = m.reactions || {};
                  const reactionEntries = Object.entries(reactions).filter(([, ids]) => (ids || []).length > 0);
                  const replyCount = m.reply_count || 0;
                  const isThreadOpen = openThreadId === m.id;
                  const showPicker = reactionPickerFor === m.id;
                  return (
                    <div key={m.id} className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}>
                      <div className={`flex ${isMine ? "justify-end" : "justify-start"} gap-2 w-full`}>
                        {!isMine && (
                          <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0 mt-4">
                            {senderAvatar ? <img src={senderAvatar} alt="" className="w-full h-full object-cover" /> : <User className="w-3.5 h-3.5 text-gray-400" />}
                          </div>
                        )}
                        <div className={`max-w-[70%] relative group`}>
                          {!isMine && activeConvo.type === "group" && (
                            <span className="text-[10px] text-gray-400 ml-1">{m.sender_name}</span>
                          )}
                          <div className={`relative rounded-2xl px-3 py-2 ${isMine ? "bg-fuchsia-600 text-white rounded-br-md" : "bg-white border border-gray-200 text-gray-900 rounded-bl-md"}`}>
                            {/* Hover-Reaction-Bar (Teams-Style) */}
                            <div className={`absolute ${isMine ? "right-1" : "left-1"} -top-7 hidden group-hover:flex items-center gap-0.5 bg-white border border-gray-200 rounded-full shadow-md px-1 py-0.5 z-10`} data-testid={`msg-actions-${m.id}`}>
                              {["👍", "❤️", "😂", "😮"].map(em => (
                                <button
                                  key={em}
                                  onClick={() => toggleReaction(m.id, em)}
                                  className="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center text-base transition-transform hover:scale-110"
                                  title={`Mit ${em} reagieren`}
                                  data-testid={`react-${em}-${m.id}`}
                                >{em}</button>
                              ))}
                              <button
                                onClick={() => setReactionPickerFor(showPicker ? null : m.id)}
                                className="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-500"
                                title="Weitere Reaktion"
                                data-testid={`react-more-${m.id}`}
                              ><SmilePlus className="w-3.5 h-3.5" /></button>
                              <div className="w-px h-4 bg-gray-200 mx-0.5" />
                              <button
                                onClick={() => toggleThread(m.id)}
                                className="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-500"
                                title="Antworten"
                                data-testid={`reply-${m.id}`}
                              ><MessageCircle className="w-3.5 h-3.5" /></button>
                            </div>
                            {/* Extended Reaction Picker */}
                            {showPicker && (
                              <div className={`absolute ${isMine ? "right-1" : "left-1"} -top-16 flex items-center gap-0.5 bg-white border border-gray-200 rounded-full shadow-lg px-2 py-1 z-20`} data-testid={`react-picker-${m.id}`}>
                                {["👍", "❤️", "😂", "😮", "😢", "😡", "🎉", "🙏", "🔥", "👏", "✅", "❓"].map(em => (
                                  <button
                                    key={em}
                                    onClick={() => toggleReaction(m.id, em)}
                                    className="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center text-base transition-transform hover:scale-110"
                                  >{em}</button>
                                ))}
                              </div>
                            )}
                            {m.attachment && (
                              <div className="mb-1">
                                {isImage ? (
                                  <img
                                    loading="lazy"
                                    src={`${API}/api/chat/conversations/${activeConvo.id}/file/${m.attachment.id}?token=${token}&thumbnail=1&size=400`}
                                    alt={m.attachment.filename}
                                    className="rounded-lg max-w-full max-h-48 cursor-pointer"
                                    onClick={() => openExternal(`${API}/api/chat/conversations/${activeConvo.id}/file/${m.attachment.id}?token=${token}`)}
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
                          {/* Reaction badges below the bubble */}
                          {reactionEntries.length > 0 && (
                            <div className={`flex flex-wrap gap-1 mt-1 ${isMine ? "justify-end" : "justify-start"}`} data-testid={`reactions-${m.id}`}>
                              {reactionEntries.map(([emoji, ids]) => {
                                const mineReacted = (ids || []).includes(user?.id);
                                return (
                                  <button
                                    key={emoji}
                                    onClick={() => toggleReaction(m.id, emoji)}
                                    className={`px-2 py-0.5 rounded-full text-xs flex items-center gap-1 border transition-colors ${
                                      mineReacted
                                        ? "bg-fuchsia-50 border-fuchsia-300 text-fuchsia-700"
                                        : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
                                    }`}
                                    data-testid={`reaction-badge-${emoji}-${m.id}`}
                                  >
                                    <span>{emoji}</span>
                                    <span className="text-[10px] font-medium">{(ids || []).length}</span>
                                  </button>
                                );
                              })}
                            </div>
                          )}
                          {/* Reply count link */}
                          {replyCount > 0 && (
                            <button
                              onClick={() => toggleThread(m.id)}
                              className={`mt-1 inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full hover:bg-fuchsia-50 ${isMine ? "self-end text-fuchsia-200 hover:text-fuchsia-700" : "text-fuchsia-600"}`}
                              data-testid={`reply-count-${m.id}`}
                            >
                              <CornerDownRight className="w-3 h-3" />
                              {replyCount} {replyCount === 1 ? "Antwort" : "Antworten"}
                              <ChevronRight className={`w-3 h-3 transition-transform ${isThreadOpen ? "rotate-90" : ""}`} />
                            </button>
                          )}
                        </div>
                      </div>
                      {/* Thread Replies (inline, indented) */}
                      {isThreadOpen && (
                        <div className={`w-full ${isMine ? "pr-9" : "pl-9"} mt-2 mb-1`} data-testid={`thread-${m.id}`}>
                          <div className="border-l-2 border-fuchsia-200 pl-3 space-y-2">
                            {threadReplies.length === 0 && (
                              <p className="text-[11px] text-gray-400 italic">Noch keine Antworten – starte die Diskussion.</p>
                            )}
                            {threadReplies.map(r => {
                              const rIsMine = r.sender_id === user?.id;
                              const rAvatar = memberAvatars[r.sender_id];
                              const rReactions = r.reactions || {};
                              const rReactionEntries = Object.entries(rReactions).filter(([, ids]) => (ids || []).length > 0);
                              return (
                                <div key={r.id} className="flex gap-2 items-start group/reply">
                                  <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0 mt-0.5">
                                    {rAvatar ? <img src={rAvatar} alt="" className="w-full h-full object-cover" /> : <User className="w-3 h-3 text-gray-400" />}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[11px] font-medium text-gray-700">{rIsMine ? "Du" : r.sender_name}</span>
                                      <span className="text-[10px] text-gray-400">{formatTime(r.created_at)}</span>
                                      {/* Inline reaction button on reply */}
                                      <button
                                        onClick={() => toggleReaction(r.id, "👍")}
                                        className="opacity-0 group-hover/reply:opacity-100 transition-opacity ml-auto p-1 rounded hover:bg-gray-100 text-gray-400"
                                        title="👍 reagieren"
                                        data-testid={`reply-react-${r.id}`}
                                      ><SmilePlus className="w-3 h-3" /></button>
                                    </div>
                                    {r.text && <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">{r.text}</p>}
                                    {rReactionEntries.length > 0 && (
                                      <div className="flex flex-wrap gap-1 mt-1">
                                        {rReactionEntries.map(([emoji, ids]) => {
                                          const mineReacted = (ids || []).includes(user?.id);
                                          return (
                                            <button
                                              key={emoji}
                                              onClick={() => toggleReaction(r.id, emoji)}
                                              className={`px-1.5 py-0.5 rounded-full text-xs flex items-center gap-1 border ${mineReacted ? "bg-fuchsia-50 border-fuchsia-300 text-fuchsia-700" : "bg-white border-gray-200 text-gray-600"}`}
                                            >
                                              <span>{emoji}</span><span className="text-[10px]">{(ids || []).length}</span>
                                            </button>
                                          );
                                        })}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                            {/* Reply input */}
                            <form onSubmit={sendThreadReply} className="flex items-center gap-2 mt-2">
                              <Input
                                value={threadInput}
                                onChange={e => setThreadInput(e.target.value)}
                                placeholder="Antworten..."
                                className="h-8 text-sm bg-white"
                                data-testid={`thread-input-${m.id}`}
                                autoFocus
                              />
                              <Button
                                type="submit"
                                size="sm"
                                disabled={!threadInput.trim() || threadSending}
                                className="h-8 px-3 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                                data-testid={`thread-send-${m.id}`}
                              >
                                {threadSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                              </Button>
                            </form>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />

                {/* Floating "↓ neue Nachrichten" Button — nur sichtbar wenn User hochgescrollt hat */}
                {(hasNewBelow || !isAtBottom) && (
                  <button
                    type="button"
                    onClick={scrollToBottomNow}
                    className={`sticky bottom-3 ml-auto mr-1 flex items-center gap-1.5 px-3 py-1.5 rounded-full shadow-lg text-xs font-semibold transition-all ${hasNewBelow ? "bg-fuchsia-600 text-white hover:bg-fuchsia-700 animate-bounce" : "bg-white text-gray-700 hover:bg-gray-100 border border-gray-200"}`}
                    data-testid="scroll-to-bottom-btn"
                  >
                    <ChevronRight className="w-3.5 h-3.5 rotate-90" />
                    {hasNewBelow ? "Neue Nachrichten" : "Nach unten"}
                  </button>
                )}
              </div>

              {/* Pending File Preview */}
              {pendingFile && (
                <div className="bg-gray-50 border-t border-gray-200 px-3 py-2 flex items-center gap-2">
                  <Paperclip className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
                  <span className="text-sm text-gray-700 flex-1 truncate">{pendingFile.name}</span>
                  <button onClick={() => setPendingFile(null)} className="text-gray-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                  <Button size="sm" onClick={() => { sendFile(pendingFile); setPendingFile(null); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs h-7" data-testid="send-pending-file-btn">
                    <Send className="w-3 h-3 mr-1" /> Senden
                  </Button>
                </div>
              )}

              {/* Input */}
              <form onSubmit={sendMessage} className="bg-white border-t border-gray-200 px-3 py-2 flex items-center gap-2" data-testid="chat-input-form">
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={e => { if (e.target.files[0]) setPendingFile(e.target.files[0]); e.target.value = ""; }}
                />
                <input
                  type="file"
                  ref={cameraInputRef}
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={e => { if (e.target.files[0]) setPendingFile(e.target.files[0]); e.target.value = ""; }}
                />
                <Button type="button" variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} className="text-gray-400 hover:text-fuchsia-600 flex-shrink-0" data-testid="attach-file-btn">
                  <Paperclip className="w-4 h-4" />
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => cameraInputRef.current?.click()} className="text-gray-400 hover:text-fuchsia-600 flex-shrink-0" data-testid="camera-btn">
                  <Camera className="w-4 h-4" />
                </Button>
                <Input
                  value={newMsg}
                  onChange={e => setNewMsg(e.target.value)}
                  onFocus={() => {
                    // iOS: nach dem Aufgehen der Tastatur ans Ende scrollen,
                    // aber NUR wenn der User ohnehin am Ende war (sonst bleibt seine Lese-Position erhalten).
                    if (isAtBottom) {
                      setTimeout(() => {
                        messagesEndRef.current?.scrollIntoView({ block: "end" });
                      }, 250);
                    }
                  }}
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

      {/* Chat Detail Panel */}
      {showDetail && activeConvo && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setShowDetail(false)} />
          <div className="fixed top-0 right-0 h-full w-full sm:w-[400px] bg-white border-l border-gray-200 z-50 flex flex-col shadow-2xl" data-testid="chat-detail-panel" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="px-4 py-4 border-b border-gray-200 flex-shrink-0">
              <div className="flex items-center justify-between mb-3">
                <div className="flex-1" />
                <button onClick={() => setShowDetail(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
              </div>
              <div className="flex flex-col items-center text-center">
                {/* Avatar */}
                <div className="relative mb-3">
                  <div className={`w-16 h-16 rounded-full flex items-center justify-center overflow-hidden ${activeConvo.type === "group" ? "bg-blue-100" : "bg-gray-100"}`}>
                    {activeConvo.avatar_path ? (
                      <img src={getAvatarUrl(activeConvo)} alt="" className="w-full h-full object-cover" />
                    ) : activeConvo.type === "group" ? <Users className="w-7 h-7 text-blue-600" /> : <User className="w-7 h-7 text-gray-500" />}
                  </div>
                  {isAdmin && activeConvo.type === "group" && (
                    <>
                      <input type="file" ref={avatarInputRef} accept="image/*" className="hidden" onChange={e => { if (e.target.files[0]) uploadAvatar(e.target.files[0]); e.target.value = ""; }} />
                      <button
                        onClick={() => avatarInputRef.current?.click()}
                        className="absolute -bottom-1 -right-1 w-7 h-7 bg-fuchsia-600 rounded-full flex items-center justify-center text-white hover:bg-fuchsia-700 transition-colors shadow-md"
                        title="Gruppenbild ändern"
                        data-testid="change-avatar-btn"
                      >
                        <Camera className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>
                {/* Name */}
                {editingName ? (
                  <div className="flex items-center gap-2 w-full max-w-[200px]">
                    <input
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") saveGroupName(); if (e.key === "Escape") setEditingName(false); }}
                      className="text-sm font-semibold text-center border border-fuchsia-300 rounded-lg px-2 py-1 w-full focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
                      autoFocus
                      data-testid="edit-group-name-input"
                    />
                    <button onClick={saveGroupName} className="text-fuchsia-600 hover:text-fuchsia-700"><Check className="w-4 h-4" /></button>
                    <button onClick={() => setEditingName(false)} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <h3 className="font-semibold text-gray-900 text-sm">{activeConvo.display_name}</h3>
                    {isAdmin && activeConvo.type === "group" && (
                      <button onClick={() => { setEditName(activeConvo.display_name || ""); setEditingName(true); }} className="text-gray-400 hover:text-fuchsia-600" title="Name ändern" data-testid="edit-name-btn">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                )}
                <p className="text-[10px] text-gray-400 mt-0.5">{activeConvo.type === "group" ? "Gruppenchat" : "Direktnachricht"}</p>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-100">
              {[
                { key: "members", label: "Mitglieder", icon: Users },
                { key: "files", label: "Dateien", icon: FileText },
                { key: "images", label: "Fotos", icon: Image },
              ].map(t => (
                <button
                  key={t.key}
                  onClick={() => setDetailTab(t.key)}
                  className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${detailTab === t.key ? "text-fuchsia-600 border-b-2 border-fuchsia-600" : "text-gray-500 hover:text-gray-700"}`}
                  data-testid={`detail-tab-${t.key}`}
                >
                  <t.icon className="w-3.5 h-3.5" />
                  {t.label}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {/* Members Tab */}
              {detailTab === "members" && (
                <div className="p-3 space-y-1">
                  <p className="text-[10px] text-gray-400 uppercase font-medium px-2 mb-2">{convoMembers.length} Mitglieder</p>
                  {convoMembers.map(m => (
                    <div key={m.id} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-50" data-testid={`member-${m.id}`}>
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                        <User className="w-4 h-4 text-gray-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {m.name} {m.id === user?.id && <span className="text-gray-400">(Du)</span>}
                        </p>
                        <p className="text-[10px] text-gray-400">{m.role}{m.id === convoCreatedBy ? " · Ersteller" : ""}</p>
                      </div>
                      {isAdmin && activeConvo.type === "group" && m.id !== convoCreatedBy && m.id !== user?.id && (
                        <button
                          onClick={() => removeMember(m.id)}
                          className="text-gray-400 hover:text-red-500 transition-colors p-1"
                          title="Entfernen"
                          data-testid={`remove-member-${m.id}`}
                        >
                          <UserMinus className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}

                  {/* Add Member Section (Admin + Group only) */}
                  {isAdmin && activeConvo.type === "group" && nonMembers.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-gray-100">
                      <p className="text-[10px] text-gray-400 uppercase font-medium px-2 mb-2">Mitglied hinzufügen</p>
                      <div className="relative px-2 mb-2">
                        <Search className="w-3.5 h-3.5 absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input
                          value={addMemberSearch}
                          onChange={e => setAddMemberSearch(e.target.value)}
                          placeholder="Suchen..."
                          className="w-full pl-8 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-fuchsia-400"
                          data-testid="add-member-search"
                        />
                      </div>
                      {nonMembers.map(u => (
                        <button
                          key={u.id}
                          onClick={() => addMember(u.id)}
                          className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-fuchsia-50 transition-colors"
                          data-testid={`add-member-${u.id}`}
                        >
                          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                            <User className="w-4 h-4 text-gray-500" />
                          </div>
                          <div className="flex-1 min-w-0 text-left">
                            <p className="text-sm text-gray-900 truncate">{u.name}</p>
                            <p className="text-[10px] text-gray-400">{u.role}</p>
                          </div>
                          <UserPlus className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Files Tab */}
              {detailTab === "files" && (
                <div className="p-3">
                  {convoFiles.length === 0 ? (
                    <div className="py-8 text-center text-gray-400">
                      <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-xs">Keine Dateien geteilt</p>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {convoFiles.map(f => (
                        <a
                          key={f.attachment_id}
                          href={`${API}/api/chat/conversations/${activeConvo.id}/file/${f.attachment_id}?token=${token}`}
                          target="_blank" rel="noreferrer"
                          className="flex items-center gap-3 px-2 py-2.5 rounded-lg hover:bg-gray-50 transition-colors group"
                          data-testid={`file-${f.attachment_id}`}
                        >
                          <div className="w-9 h-9 rounded-lg bg-fuchsia-50 flex items-center justify-center flex-shrink-0">
                            <FileText className="w-4 h-4 text-fuchsia-600" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-900 truncate">{f.filename}</p>
                            <p className="text-[10px] text-gray-400">{f.sender_name} · {new Date(f.created_at).toLocaleDateString("de-DE")}</p>
                          </div>
                          <Download className="w-4 h-4 text-gray-400 group-hover:text-fuchsia-600 flex-shrink-0" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Images Tab */}
              {detailTab === "images" && (
                <div className="p-3">
                  {convoImages.length === 0 ? (
                    <div className="py-8 text-center text-gray-400">
                      <Image className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-xs">Keine Fotos geteilt</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-3 gap-1.5">
                      {convoImages.map(img => (
                        <a
                          key={img.attachment_id}
                          href={`${API}/api/chat/conversations/${activeConvo.id}/file/${img.attachment_id}?token=${token}`}
                          target="_blank" rel="noreferrer"
                          className="aspect-square rounded-lg overflow-hidden bg-gray-100 hover:opacity-80 transition-opacity"
                          data-testid={`image-${img.attachment_id}`}
                        >
                          <img
                            loading="lazy"
                            src={`${API}/api/chat/conversations/${activeConvo.id}/file/${img.attachment_id}?token=${token}&thumbnail=1&size=240`}
                            alt={img.filename}
                            className="w-full h-full object-cover"
                          />
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}

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
