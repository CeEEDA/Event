/**
 * Neuer-Direkt-Chat-Modal aus ChatPage.jsx extrahiert.
 */
import { X, Search, User } from "lucide-react";
import { Input } from "../ui/input";

export default function NewChatModal({
  open,
  onClose,
  searchUsers,
  setSearchUsers,
  filteredUsers,
  startDirectChat,
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()} data-testid="new-chat-modal">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Neue Nachricht</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
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
  );
}
