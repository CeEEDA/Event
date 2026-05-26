import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { BACKEND_URL } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, Send, Users, User, Paperclip,
  MessageSquare, X, CheckCheck, Loader2,
  ChevronRight, Camera,
  SmilePlus, MessageCircle, CornerDownRight,
} from "lucide-react";
import { openExternal } from "../lib/openExternal";
import ChatSidebar from "../components/chat/ChatSidebar";
import ChatDetailPanel from "../components/chat/ChatDetailPanel";
import NewChatModal from "../components/chat/NewChatModal";
import NewGroupModal from "../components/chat/NewGroupModal";

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
  // Zusaetzlich: ChatPage-Container ist `position: fixed inset-0`, dazu sperren
  // wir Body-Scroll, damit iOS Safari beim Tastatur-Aufgehen nicht den ganzen
  // Body nach oben scrollt und den Chat wegwischt.
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

  // Body-Scroll-Lock waehrend ChatPage gemountet ist (verhindert iOS Auto-Scroll).
  useEffect(() => {
    const prevBody = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevBody;
      document.documentElement.style.overflow = prevHtml;
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
      className="fixed inset-0 flex flex-col bg-gray-50 safe-area-pad"
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
        <ChatSidebar
          activeConvo={activeConvo}
          conversations={conversations}
          openConvo={openConvo}
          isAdmin={isAdmin}
          setShowNewChat={setShowNewChat}
          setShowNewGroup={setShowNewGroup}
          user={user}
          memberAvatars={memberAvatars}
          getAvatarUrl={getAvatarUrl}
        />

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
                                onFocus={(e) => {
                                  const inputEl = e.currentTarget;
                                  setTimeout(() => {
                                    try { inputEl.scrollIntoView({ block: "end", behavior: "smooth" }); } catch (_) { /* ignore */ }
                                  }, 300);
                                }}
                                placeholder="Antworten..."
                                autoComplete="off"
                                autoCorrect="off"
                                enterKeyHint="send"
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
                  onFocus={(e) => {
                    // iOS/Android Keyboard: nach dem Aufgehen der Tastatur das Eingabefeld
                    // selbst in den sichtbaren Bereich scrollen, damit der eingegebene Text
                    // immer sichtbar bleibt (Bug: Bild wischt weg / Text nicht lesbar auf Mobil).
                    const inputEl = e.currentTarget;
                    setTimeout(() => {
                      try {
                        inputEl.scrollIntoView({ block: "end", behavior: "smooth" });
                      } catch (_) { /* ignore */ }
                      if (isAtBottom) {
                        messagesEndRef.current?.scrollIntoView({ block: "end" });
                      }
                    }, 300);
                  }}
                  placeholder="Nachricht schreiben..."
                  autoComplete="off"
                  autoCorrect="off"
                  enterKeyHint="send"
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
      <ChatDetailPanel
        show={showDetail}
        onClose={() => setShowDetail(false)}
        activeConvo={activeConvo}
        isAdmin={isAdmin}
        user={user}
        getAvatarUrl={getAvatarUrl}
        avatarInputRef={avatarInputRef}
        uploadAvatar={uploadAvatar}
        editingName={editingName}
        setEditingName={setEditingName}
        editName={editName}
        setEditName={setEditName}
        saveGroupName={saveGroupName}
        detailTab={detailTab}
        setDetailTab={setDetailTab}
        convoMembers={convoMembers}
        convoCreatedBy={convoCreatedBy}
        removeMember={removeMember}
        nonMembers={nonMembers}
        addMemberSearch={addMemberSearch}
        setAddMemberSearch={setAddMemberSearch}
        addMember={addMember}
        convoFiles={convoFiles}
        convoImages={convoImages}
        API={API}
        token={token}
      />

      {/* New Direct Chat Modal */}
      <NewChatModal
        open={showNewChat}
        onClose={() => setShowNewChat(false)}
        searchUsers={searchUsers}
        setSearchUsers={setSearchUsers}
        filteredUsers={filteredUsers}
        startDirectChat={startDirectChat}
      />

      {/* New Group Modal */}
      <NewGroupModal
        open={showNewGroup}
        onClose={() => setShowNewGroup(false)}
        groupName={groupName}
        setGroupName={setGroupName}
        chatUsers={chatUsers}
        selectedMembers={selectedMembers}
        setSelectedMembers={setSelectedMembers}
        createGroup={createGroup}
      />
    </div>
  );
}
