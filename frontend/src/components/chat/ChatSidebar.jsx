/**
 * Chat-Sidebar (Konversations-Liste) aus ChatPage.jsx extrahiert.
 */
import { MessageSquare, User, Users } from "lucide-react";
import { Button } from "../ui/button";

const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

export default function ChatSidebar({
  activeConvo,
  conversations,
  openConvo,
  isAdmin,
  setShowNewChat,
  setShowNewGroup,
  user,
  memberAvatars,
  getAvatarUrl,
}) {
  return (
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
  );
}
