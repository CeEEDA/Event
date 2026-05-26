/**
 * Admin-Manual-Expiry-Dialog aus AdminPage.js extrahiert.
 *
 * Kleiner Dialog der erscheint wenn die KI beim Doc-Upload kein Ablaufdatum
 * erkannt hat. Admin gibt es manuell ein.
 */
import { Button } from "../ui/button";

export default function AdminManualExpiryDialog({
  open,
  onClose,
  value,
  onChange,
  onSave,
}) {
  if (!open) return null;
  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-[60]" onClick={onClose} />
      <div
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl shadow-2xl border border-gray-200 p-6 z-[61] w-[90%] max-w-sm"
        data-testid="admin-expiry-dialog"
      >
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Ablaufdatum eingeben</h3>
        <p className="text-xs text-gray-500 mb-4">
          Die KI konnte kein Ablaufdatum erkennen. Bitte manuell eingeben:
        </p>
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
          autoFocus
          data-testid="admin-manual-expiry-input"
        />
        <div className="flex gap-2">
          <Button
            onClick={onSave}
            className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            data-testid="admin-save-expiry-btn"
          >
            Speichern
          </Button>
          <Button
            variant="outline"
            onClick={onClose}
            className="flex-1"
            data-testid="admin-skip-expiry-btn"
          >
            Überspringen
          </Button>
        </div>
      </div>
    </>
  );
}
