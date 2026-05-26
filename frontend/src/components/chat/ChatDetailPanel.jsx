/**
 * Chat-Detail-Panel aus ChatPage.jsx extrahiert.
 *
 * Sliding right panel with three tabs:
 *  - Mitglieder (members)
 *  - Dateien (files)
 *  - Fotos (images)
 *
 * State liegt im Parent (ChatPage.jsx), Props werden 1:1 durchgereicht.
 */
import { X, Camera, Pencil, Check, Users, FileText, Image, User, UserMinus, UserPlus, Search, Download } from "lucide-react";

export default function ChatDetailPanel({
  show,
  onClose,
  activeConvo,
  isAdmin,
  user,
  getAvatarUrl,
  avatarInputRef,
  uploadAvatar,
  editingName,
  setEditingName,
  editName,
  setEditName,
  saveGroupName,
  detailTab,
  setDetailTab,
  convoMembers,
  convoCreatedBy,
  removeMember,
  nonMembers,
  addMemberSearch,
  setAddMemberSearch,
  addMember,
  convoFiles,
  convoImages,
  API,
  token,
}) {
  if (!show || !activeConvo) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-full sm:w-[400px] bg-white border-l border-gray-200 z-50 flex flex-col shadow-2xl" data-testid="chat-detail-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-4 py-4 border-b border-gray-200 flex-shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex-1" />
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
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
  );
}
