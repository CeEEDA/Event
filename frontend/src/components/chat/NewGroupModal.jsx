/**
 * Neuer-Gruppe-Modal aus ChatPage.jsx extrahiert.
 */
import { X, Check } from "lucide-react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";

export default function NewGroupModal({
  open,
  onClose,
  groupName,
  setGroupName,
  chatUsers,
  selectedMembers,
  setSelectedMembers,
  createGroup,
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()} data-testid="new-group-modal">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Neue Gruppe</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
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
  );
}
