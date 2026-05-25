/**
 * Schausteller-Edit-Modal aus AdminPage.js extrahiert.
 *
 * Kontrolliert von außen via Props - keine eigene State-Logik (form/loaders
 * bleiben im Parent damit alle Side-Effects an einem Ort sind).
 */
import { Tent, KeyRound } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Button } from "../ui/button";

export default function SchaustellerEditModal({
  open,
  onOpenChange,
  form,
  setForm,
  newPassword,
  setNewPassword,
  onSetPassword,
  onSave,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="schausteller-modal">
        <DialogHeader>
          <DialogTitle className="text-gray-900 flex items-center gap-2">
            <Tent className="w-5 h-5 text-amber-600" />
            Schausteller bearbeiten
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Firma</Label>
              <Input value={form.firma} onChange={e => setForm(f => ({ ...f, firma: e.target.value }))} className="border-gray-300" data-testid="sch-firma-input" />
            </div>
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">Name</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="border-gray-300" data-testid="sch-name-input" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-gray-700 text-sm">Straße</Label>
            <Input value={form.strasse} onChange={e => setForm(f => ({ ...f, strasse: e.target.value }))} className="border-gray-300" data-testid="sch-strasse-input" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-gray-700 text-sm">PLZ</Label>
              <Input value={form.plz} onChange={e => setForm(f => ({ ...f, plz: e.target.value }))} className="border-gray-300" data-testid="sch-plz-input" />
            </div>
            <div className="col-span-2 space-y-1">
              <Label className="text-gray-700 text-sm">Ort</Label>
              <Input value={form.ort} onChange={e => setForm(f => ({ ...f, ort: e.target.value }))} className="border-gray-300" data-testid="sch-ort-input" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-gray-700 text-sm">Steuernummer</Label>
            <Input value={form.steuernummer} onChange={e => setForm(f => ({ ...f, steuernummer: e.target.value }))} className="border-gray-300" data-testid="sch-steuernummer-input" />
          </div>
          <div className="space-y-1">
            <Label className="text-gray-700 text-sm">E-Mail</Label>
            <Input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="border-gray-300" data-testid="sch-email-input" />
          </div>
          <div className="space-y-1">
            <Label className="text-gray-700 text-sm">Telefon</Label>
            <Input value={form.telefon} onChange={e => setForm(f => ({ ...f, telefon: e.target.value }))} className="border-gray-300" data-testid="sch-telefon-input" />
          </div>
          <div className="space-y-1">
            <Label className="text-gray-700 text-sm">Rechnungs-E-Mail</Label>
            <Input type="email" value={form.rechnungs_email} onChange={e => setForm(f => ({ ...f, rechnungs_email: e.target.value }))} className="border-gray-300" data-testid="sch-rechnungs-email-input" />
            <p className="text-[10px] text-gray-400">Rechnungen werden an diese Adresse versendet</p>
          </div>
          <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
            <input
              type="checkbox"
              id="kauf_auf_rechnung"
              checked={form.kauf_auf_rechnung || false}
              onChange={e => setForm(f => ({ ...f, kauf_auf_rechnung: e.target.checked }))}
              className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
              data-testid="sch-kauf-auf-rechnung"
            />
            <label htmlFor="kauf_auf_rechnung" className="text-sm text-gray-700 cursor-pointer">
              Kauf auf Rechnung <span className="text-xs text-gray-400">(keine Zahlungsmittel-Hinterlegung nötig)</span>
            </label>
          </div>

          {/* Password Management */}
          <div className="pt-3 border-t border-gray-200 space-y-3">
            <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-fuchsia-600" />
              Passwort verwalten
            </h4>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-500 mb-2">Neues Passwort setzen</p>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Neues Passwort (min. 6 Zeichen)"
                  className="border-gray-300 flex-1"
                  data-testid="sch-new-password-input"
                />
                <Button
                  type="button"
                  onClick={onSetPassword}
                  disabled={!newPassword || newPassword.length < 6}
                  className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                  data-testid="sch-set-password-btn"
                >
                  Setzen
                </Button>
              </div>
              <p className="text-[10px] text-gray-400 mt-1">Setzt das Passwort und markiert die E-Mail als bestätigt</p>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Abbrechen</Button>
          <Button onClick={onSave} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-schausteller-btn">Speichern</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
