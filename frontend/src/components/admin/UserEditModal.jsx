/**
 * User-Edit-Modal aus AdminPage.js extrahiert.
 *
 * State bleibt komplett im Parent (AdminPage.js) - die Komponente bekommt alle
 * State-Werte + Setter + Handler ueber Props. Dadurch koennen Side-Effects
 * (loadData, etc.) im Parent zentral verwaltet werden und das Refactor ist
 * regression-arm (1:1 JSX-Move ohne Logik-Aenderungen).
 *
 * Sektionen sind weiter in Sub-Komponenten unter `user_modal/` zerlegt:
 * - FreelancerAssignment      (Freelancer-Auftrags-Liste)
 * - FilesharingAppCard        (Kunde: FileShare)
 * - GeneratorMonitoringCard   (Kunde: Generator-Monitoring)
 * - EnergyMonitoringCard      (Kunde: Energy-Monitoring)
 * - AccountAvailabilityCard   (Kunde: Konto-Verfuegbarkeit)
 */
import { Truck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../ui/dialog";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { Button } from "../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import FreelancerAssignment from "./user_modal/FreelancerAssignment";
import FilesharingAppCard from "./user_modal/FilesharingAppCard";
import GeneratorMonitoringCard from "./user_modal/GeneratorMonitoringCard";
import EnergyMonitoringCard from "./user_modal/EnergyMonitoringCard";
import AccountAvailabilityCard from "./user_modal/AccountAvailabilityCard";

export default function UserEditModal({
  open,
  onOpenChange,
  editingUser,
  formData,
  setFormData,
  onSubmit,
  // App-Updaters
  updateFilesharingApp,
  updateGeneratorMonitoringApp,
  updateEnergyMonitoringApp,
  toggleGeneratorId,
  toggleEnergyDeviceId,
  // Listen
  allGenerators,
  allMesskoffer,
  // Freelancer-Auftragsauswahl
  freelancerOrderPks,
  setFreelancerOrderPks,
  freelancerAssignedOrders,
  setFreelancerAssignedOrders,
  freelancerSearchQ,
  setFreelancerSearchQ,
  freelancerSearchResults,
  freelancerSearchLoading,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="user-modal">
        <DialogHeader>
          <DialogTitle className="text-gray-900">
            {editingUser ? "Benutzer bearbeiten" : "Neuer Benutzer"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-gray-700">Name</Label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Max Mustermann"
              className="border-gray-300"
              required
              data-testid="user-name-input"
            />
          </div>

          {!editingUser && (
            <>
              <div className="space-y-2">
                <Label className="text-gray-700">E-Mail</Label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="name@firma.de"
                  className="border-gray-300"
                  required
                  data-testid="user-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-gray-700">Passwort</Label>
                <Input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Mindestens 6 Zeichen"
                  className="border-gray-300"
                  required
                  data-testid="user-password-input"
                />
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label className="text-gray-700">Rolle</Label>
            <Select
              value={formData.role}
              onValueChange={(value) => setFormData({ ...formData, role: value })}
            >
              <SelectTrigger className="border-gray-300" data-testid="user-role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Administrator</SelectItem>
                <SelectItem value="mitarbeiter">Mitarbeiter</SelectItem>
                <SelectItem value="freelancer">Freelancer</SelectItem>
                <SelectItem value="kunde">Kunde</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {editingUser && (
            <>
              <div className="flex items-center justify-between py-2">
                <Label className="text-gray-700">Konto aktiv</Label>
                <Switch
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  data-testid="user-active-toggle"
                />
              </div>

              {formData.role === "mitarbeiter" && (
                <div className="border-t border-gray-200 pt-4 mt-2">
                  <h3 className="font-semibold text-gray-900 mb-3">Hub-Kacheln (Module)</h3>
                  <p className="text-xs text-gray-500 mb-3">Steuere welche Bereiche der Mitarbeiter im Hub sieht. <strong>Chat, Mitarbeiter-Daten und FAQ sind immer sichtbar.</strong></p>
                  <div className="bg-gray-50 rounded-lg p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {[
                      { key: "orders", label: "Aufträge" },
                      { key: "einsatzplanung", label: "Einsatzplanung" },
                      { key: "kirmes", label: "Kirmes" },
                      { key: "verwaltung", label: "Verwaltung" },
                      { key: "power_monitoring", label: "Power Monitoring" },
                      { key: "energy_monitoring", label: "Energy Monitoring" },
                      { key: "devices", label: "Geräte" },
                      { key: "fileshare", label: "FileShare" },
                      { key: "serviceplan", label: "Serviceplan" },
                    ].map(m => (
                      <div key={m.key} className="flex items-center justify-between bg-white rounded-md px-3 py-2 border border-gray-100">
                        <Label className="text-sm text-gray-800 cursor-pointer" htmlFor={`mod-${m.key}`}>{m.label}</Label>
                        <Switch
                          id={`mod-${m.key}`}
                          checked={formData.apps.modules?.[m.key] !== false}
                          onCheckedChange={(checked) => setFormData(p => ({ ...p, apps: { ...p.apps, modules: { ...(p.apps.modules || {}), [m.key]: checked } } }))}
                          data-testid={`module-toggle-${m.key}`}
                        />
                      </div>
                    ))}
                  </div>

                  {/* ADR – Tankwagen Betanker */}
                  <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 mt-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Truck className="w-5 h-5 text-rose-600" />
                        <div>
                          <Label className="text-gray-900 font-medium">ADR / Tankwagen-Betanker</Label>
                          <p className="text-xs text-gray-500 mt-0.5">Mitarbeiter mit gueltigem ADR-Schein. Wird automatisch im Tankwagen als Betanker eingetragen.</p>
                        </div>
                      </div>
                      <Switch
                        checked={!!formData.apps.modules?.adr}
                        onCheckedChange={(checked) => setFormData(p => ({ ...p, apps: { ...p.apps, modules: { ...(p.apps.modules || {}), adr: checked } } }))}
                        data-testid="module-toggle-adr"
                      />
                    </div>
                  </div>
                </div>
              )}

              {formData.role === "mitarbeiter" && (
                <div className="border-t border-gray-200 pt-4 mt-2">
                  <h3 className="font-semibold text-gray-900 mb-3">Sonderberechtigungen</h3>
                  <div className="bg-amber-50 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="text-gray-900 font-medium">Abrechnung</Label>
                        <p className="text-xs text-gray-500 mt-0.5">Kann Abrechnungen erstellen und versenden</p>
                      </div>
                      <Switch
                        checked={!!formData.permissions?.can_billing}
                        onCheckedChange={(checked) => setFormData({ ...formData, permissions: { ...formData.permissions, can_billing: checked } })}
                        data-testid="can-billing-toggle"
                      />
                    </div>
                  </div>
                </div>
              )}

              {formData.role === "freelancer" && (
                <FreelancerAssignment
                  freelancerOrderPks={freelancerOrderPks}
                  setFreelancerOrderPks={setFreelancerOrderPks}
                  freelancerAssignedOrders={freelancerAssignedOrders}
                  setFreelancerAssignedOrders={setFreelancerAssignedOrders}
                  freelancerSearchQ={freelancerSearchQ}
                  setFreelancerSearchQ={setFreelancerSearchQ}
                  freelancerSearchResults={freelancerSearchResults}
                  freelancerSearchLoading={freelancerSearchLoading}
                />
              )}

              {/* App Permissions Section (nur für Kunden – steuert Geräte-Zugriff) */}
              {formData.role === "kunde" && (
              <div className="border-t border-gray-200 pt-4 mt-4">
                <h3 className="font-semibold text-gray-900 mb-4">App-Berechtigungen</h3>

                {/* FileShare App */}
                <FilesharingAppCard
                  formData={formData}
                  updateFilesharingApp={updateFilesharingApp}
                />

                {/* Generator Monitoring App */}
                <GeneratorMonitoringCard
                  formData={formData}
                  updateGeneratorMonitoringApp={updateGeneratorMonitoringApp}
                  toggleGeneratorId={toggleGeneratorId}
                  allGenerators={allGenerators}
                />

                {/* Energy Monitoring App */}
                <EnergyMonitoringCard
                  formData={formData}
                  updateEnergyMonitoringApp={updateEnergyMonitoringApp}
                  toggleEnergyDeviceId={toggleEnergyDeviceId}
                  allMesskoffer={allMesskoffer}
                />

                {/* Time-based access for Kunden - Account level */}
                <AccountAvailabilityCard formData={formData} setFormData={setFormData} />
              </div>
              )}

              {formData.role === "admin" && (
                <div className="border-t border-gray-200 pt-4 mt-4">
                  <div className="bg-rose-50 border border-rose-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Truck className="w-5 h-5 text-rose-600" />
                        <div>
                          <Label className="text-gray-900 font-medium">ADR / Tankwagen-Betanker</Label>
                          <p className="text-xs text-gray-500 mt-0.5">Mitarbeiter mit gueltigem ADR-Schein. Wird automatisch im Tankwagen als Betanker eingetragen.</p>
                        </div>
                      </div>
                      <Switch
                        checked={!!formData.apps.modules?.adr}
                        onCheckedChange={(checked) => setFormData(p => ({ ...p, apps: { ...p.apps, modules: { ...(p.apps.modules || {}), adr: checked } } }))}
                        data-testid="module-toggle-adr-admin"
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Abbrechen
            </Button>
            <Button type="submit" className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-user-btn">
              {editingUser ? "Speichern" : "Erstellen"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
