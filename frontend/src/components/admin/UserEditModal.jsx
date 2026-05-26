/**
 * User-Edit-Modal aus AdminPage.js extrahiert.
 *
 * State bleibt komplett im Parent (AdminPage.js) - die Komponente bekommt alle
 * State-Werte + Setter + Handler ueber Props. Dadurch koennen Side-Effects
 * (loadData, etc.) im Parent zentral verwaltet werden und das Refactor ist
 * regression-arm (1:1 JSX-Move ohne Logik-Aenderungen).
 */
import {
  FolderOpen,
  Activity,
  Zap,
  CalendarDays,
  Search,
  Briefcase,
  Truck,
} from "lucide-react";
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
                <div className="border-t border-gray-200 pt-4 mt-2">
                  <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                    <Briefcase className="w-4 h-4 text-amber-600" />
                    Auftragszuweisung
                  </h3>
                  <p className="text-xs text-gray-500 mb-3">
                    Der Freelancer sieht nur die hier ausgewählten Aufträge.
                    Sie werden 5 Tage nach Job-Ende automatisch ausgeblendet.
                    Tankbelege und Kundendaten bleiben in der Auftragsmaske verborgen.
                  </p>

                  <div className="bg-amber-50 rounded-lg px-3 py-2 mb-3 flex items-center justify-between">
                    <span className="text-sm font-semibold text-amber-900" data-testid="freelancer-assigned-count">
                      {freelancerOrderPks.length === 1
                        ? "1 Auftrag zugewiesen"
                        : `${freelancerOrderPks.length} Aufträge zugewiesen`}
                    </span>
                    {freelancerOrderPks.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setFreelancerOrderPks([])}
                        className="text-xs text-amber-700 hover:text-amber-900 underline"
                        data-testid="freelancer-clear-all-btn"
                      >
                        Alle entfernen
                      </button>
                    )}
                  </div>

                  {/* Zugewiesene Aufträge (immer sichtbar) */}
                  {freelancerAssignedOrders.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs font-medium text-gray-700 mb-1.5 uppercase tracking-wide">Zugewiesen</p>
                      <div className="border border-amber-200 rounded-lg overflow-hidden bg-amber-50/40">
                        {freelancerAssignedOrders.map(o => {
                          const checked = freelancerOrderPks.includes(o.primary_key);
                          return (
                            <label
                              key={`a-${o.primary_key}`}
                              className="flex items-start gap-3 px-3 py-2.5 border-b border-amber-100 last:border-b-0 cursor-pointer hover:bg-amber-50 transition-colors"
                              data-testid={`freelancer-assigned-row-${o.primary_key}`}
                            >
                              <input
                                type="checkbox"
                                className="mt-1 w-4 h-4 accent-amber-600 flex-shrink-0"
                                checked={checked}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setFreelancerOrderPks(prev => prev.includes(o.primary_key) ? prev : [...prev, o.primary_key]);
                                  } else {
                                    setFreelancerOrderPks(prev => prev.filter(p => p !== o.primary_key));
                                  }
                                }}
                                data-testid={`freelancer-order-toggle-${o.primary_key}`}
                              />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-sm font-semibold text-gray-900">{o.order_no}</span>
                                  {o.event_start && (
                                    <span className="text-xs text-gray-500">
                                      {o.event_start}{o.event_end && o.event_end !== o.event_start ? ` – ${o.event_end}` : ""}
                                    </span>
                                  )}
                                </div>
                                {o.event && <div className="text-sm text-gray-700 break-words">{o.event}</div>}
                                {o.address && <div className="text-xs text-gray-500 break-words">{o.address}</div>}
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Suche fuer weitere Aufträge */}
                  <p className="text-xs font-medium text-gray-700 mb-1.5 uppercase tracking-wide">Aufträge hinzufügen</p>
                  <div className="relative mb-2">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      placeholder="Suchen (Nr., Event, Adresse...)"
                      value={freelancerSearchQ}
                      onChange={e => setFreelancerSearchQ(e.target.value)}
                      className="pl-9 border-gray-300"
                      data-testid="freelancer-order-search"
                    />
                  </div>

                  <div className="border border-gray-200 rounded-lg max-h-72 overflow-y-auto bg-white">
                    {freelancerSearchLoading ? (
                      <div className="p-4 text-center text-sm text-gray-400">Lade...</div>
                    ) : (() => {
                      const assignedSet = new Set(freelancerOrderPks);
                      const filtered = freelancerSearchResults.filter(o => !assignedSet.has(o.primary_key));
                      if (filtered.length === 0) {
                        return <div className="p-4 text-center text-sm text-gray-400">Keine weiteren Aufträge gefunden</div>;
                      }
                      return filtered.map(o => (
                        <label
                          key={`s-${o.primary_key}`}
                          className="flex items-start gap-3 px-3 py-2.5 border-b border-gray-100 last:border-b-0 cursor-pointer hover:bg-amber-50/50 transition-colors"
                          data-testid={`freelancer-order-row-${o.primary_key}`}
                        >
                          <input
                            type="checkbox"
                            className="mt-1 w-4 h-4 accent-amber-600 flex-shrink-0"
                            checked={false}
                            onChange={() => {
                              setFreelancerOrderPks(prev => prev.includes(o.primary_key) ? prev : [...prev, o.primary_key]);
                              setFreelancerAssignedOrders(prev => prev.find(x => x.primary_key === o.primary_key) ? prev : [...prev, o]);
                            }}
                            data-testid={`freelancer-order-toggle-${o.primary_key}`}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold text-gray-900">{o.order_no}</span>
                              {o.event_start && (
                                <span className="text-xs text-gray-500">
                                  {o.event_start}{o.event_end && o.event_end !== o.event_start ? ` – ${o.event_end}` : ""}
                                </span>
                              )}
                            </div>
                            {o.event && <div className="text-sm text-gray-700 break-words">{o.event}</div>}
                            {o.address && <div className="text-xs text-gray-500 break-words">{o.address}</div>}
                          </div>
                        </label>
                      ));
                    })()}
                  </div>
                </div>
              )}

              {/* App Permissions Section (nur für Kunden – steuert Geräte-Zugriff) */}
              {formData.role === "kunde" && (
              <div className="border-t border-gray-200 pt-4 mt-4">
                <h3 className="font-semibold text-gray-900 mb-4">App-Berechtigungen</h3>

                {/* FileShare App */}
                <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FolderOpen className="w-5 h-5 text-fuchsia-600" />
                      <Label className="text-gray-900 font-medium">FileShare</Label>
                    </div>
                    <Switch
                      checked={formData.apps.filesharing.enabled}
                      onCheckedChange={(checked) => updateFilesharingApp("enabled", checked)}
                      data-testid="filesharing-enabled-toggle"
                    />
                  </div>

                  {formData.apps.filesharing.enabled && (
                    <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                      <div className="space-y-2">
                        <Label className="text-gray-600 text-sm">Max. Dateigröße (MB)</Label>
                        <Input
                          type="number"
                          value={formData.apps.filesharing.max_upload_size_mb}
                          onChange={(e) => updateFilesharingApp("max_upload_size_mb", parseInt(e.target.value) || 100)}
                          className="border-gray-300 w-32"
                          min={1}
                          max={10000}
                          data-testid="filesharing-max-size-input"
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label className="text-gray-600 text-sm">Schreiben erlaubt (Gemeinsamer Bereich)</Label>
                        <Switch
                          checked={formData.apps.filesharing.can_write}
                          onCheckedChange={(checked) => updateFilesharingApp("can_write", checked)}
                          data-testid="filesharing-write-toggle"
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label className="text-gray-600 text-sm">Löschen erlaubt (Gemeinsamer Bereich)</Label>
                        <Switch
                          checked={formData.apps.filesharing.can_delete}
                          onCheckedChange={(checked) => updateFilesharingApp("can_delete", checked)}
                          data-testid="filesharing-delete-toggle"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Generator Monitoring App */}
                <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Activity className="w-5 h-5 text-fuchsia-600" />
                      <Label className="text-gray-900 font-medium">Generator-Monitoring</Label>
                    </div>
                    <Switch
                      checked={formData.apps.generator_monitoring.enabled}
                      onCheckedChange={(checked) => updateGeneratorMonitoringApp("enabled", checked)}
                      data-testid="monitoring-enabled-toggle"
                    />
                  </div>

                  {formData.apps.generator_monitoring.enabled && (
                    <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                      <div className="flex items-center justify-between">
                        <Label className="text-gray-600 text-sm">Zugriff auf alle Generatoren</Label>
                        <Switch
                          checked={formData.apps.generator_monitoring.access_all}
                          onCheckedChange={(checked) => updateGeneratorMonitoringApp("access_all", checked)}
                          data-testid="monitoring-access-all-toggle"
                        />
                      </div>

                      {!formData.apps.generator_monitoring.access_all && (
                        <div className="space-y-2">
                          <Label className="text-gray-600 text-sm">Einzelne Generatoren auswählen</Label>
                          <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                            {allGenerators.length === 0 ? (
                              <p className="text-xs text-gray-400 p-3">Keine Generatoren vorhanden</p>
                            ) : (
                              allGenerators.map((gen) => {
                                const isSelected = (formData.apps.generator_monitoring.generator_ids || []).includes(gen.id);
                                return (
                                  <label
                                    key={gen.id}
                                    className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? "bg-fuchsia-50" : ""}`}
                                    data-testid={`gen-select-${gen.serial_number}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      onChange={() => toggleGeneratorId(gen.id)}
                                      className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                                    />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm text-gray-900 truncate">{gen.name}</p>
                                      <p className="text-[10px] text-gray-400 font-mono">{gen.serial_number} · {gen.location_name || "–"}</p>
                                    </div>
                                  </label>
                                );
                              })
                            )}
                          </div>
                          <p className="text-[10px] text-gray-400">
                            {(formData.apps.generator_monitoring.generator_ids || []).length} von {allGenerators.length} ausgewählt
                          </p>
                        </div>
                      )}

                      {/* Datenfreigabe: Elektrisch / Mechanisch */}
                      <div className="space-y-2 pt-3 border-t border-fuchsia-200">
                        <Label className="text-gray-600 text-sm flex items-center gap-1">
                          <Zap className="w-3.5 h-3.5" />
                          Datenfreigabe
                        </Label>
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Elektrische Daten (U, I, P, kWh, Hz)</Label>
                          <Switch
                            checked={formData.apps.generator_monitoring.share_electrical !== false}
                            onCheckedChange={(checked) => updateGeneratorMonitoringApp("share_electrical", checked)}
                            data-testid="gen-share-electrical-toggle"
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <Label className="text-gray-600 text-sm">Mechanische Daten (RPM, Öl, Temp, Tank, Batt)</Label>
                          <Switch
                            checked={formData.apps.generator_monitoring.share_mechanical !== false}
                            onCheckedChange={(checked) => updateGeneratorMonitoringApp("share_mechanical", checked)}
                            data-testid="gen-share-mechanical-toggle"
                          />
                        </div>
                      </div>

                      {/* Zeitraum fuer Kunden */}
                      {formData.role === "kunde" && (
                        <div className="space-y-2 pt-3 border-t border-fuchsia-200">
                          <Label className="text-gray-600 text-sm flex items-center gap-1">
                            <CalendarDays className="w-3.5 h-3.5" />
                            Verfügbare Messdaten (Zeitraum)
                          </Label>
                          <p className="text-[10px] text-gray-400">Begrenzt den Datenzugriff des Kunden auf den angegebenen Zeitraum</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Von</Label>
                              <Input
                                type="date"
                                value={formData.apps.generator_monitoring.data_access_start?.split("T")[0] || ""}
                                onChange={(e) => updateGeneratorMonitoringApp("data_access_start", e.target.value ? new Date(e.target.value).toISOString() : "")}
                                className="border-gray-300 text-sm"
                                data-testid="gen-data-access-start"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Bis</Label>
                              <Input
                                type="date"
                                value={formData.apps.generator_monitoring.data_access_end?.split("T")[0] || ""}
                                onChange={(e) => updateGeneratorMonitoringApp("data_access_end", e.target.value ? new Date(e.target.value + "T23:59:59Z").toISOString() : "")}
                                className="border-gray-300 text-sm"
                                data-testid="gen-data-access-end"
                              />
                            </div>
                          </div>
                          <p className="text-[10px] text-gray-400">Leer lassen = keine Einschränkung</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Energy Monitoring App */}
                <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Zap className="w-5 h-5 text-fuchsia-600" />
                      <Label className="text-gray-900 font-medium">Energy Monitoring</Label>
                    </div>
                    <Switch
                      checked={formData.apps.energy_monitoring.enabled}
                      onCheckedChange={(checked) => updateEnergyMonitoringApp("enabled", checked)}
                      data-testid="energy-monitoring-enabled-toggle"
                    />
                  </div>

                  {formData.apps.energy_monitoring.enabled && (
                    <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                      <div className="flex items-center justify-between">
                        <Label className="text-gray-600 text-sm">Zugriff auf alle Messkoffer</Label>
                        <Switch
                          checked={formData.apps.energy_monitoring.access_all}
                          onCheckedChange={(checked) => updateEnergyMonitoringApp("access_all", checked)}
                          data-testid="energy-access-all-toggle"
                        />
                      </div>

                      {!formData.apps.energy_monitoring.access_all && (
                        <div className="space-y-2">
                          <Label className="text-gray-600 text-sm">Einzelne Messkoffer auswählen</Label>
                          <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                            {allMesskoffer.length === 0 ? (
                              <p className="text-xs text-gray-400 p-3">Keine Messkoffer vorhanden</p>
                            ) : (
                              allMesskoffer.map((mk) => {
                                const isSelected = (formData.apps.energy_monitoring.device_ids || []).includes(mk.id);
                                return (
                                  <label
                                    key={mk.id}
                                    className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0 ${isSelected ? "bg-fuchsia-50" : ""}`}
                                    data-testid={`energy-select-${mk.serial_number}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      onChange={() => toggleEnergyDeviceId(mk.id)}
                                      className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                                    />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm text-gray-900 truncate">{mk.user_field || mk.serial_number}</p>
                                      <p className="text-[10px] text-gray-400 font-mono">{mk.serial_number}</p>
                                    </div>
                                  </label>
                                );
                              })
                            )}
                          </div>
                          <p className="text-[10px] text-gray-400">
                            {(formData.apps.energy_monitoring.device_ids || []).length} von {allMesskoffer.length} ausgewählt
                          </p>
                        </div>
                      )}

                      {/* Data access range for Kunden */}
                      {formData.role === "kunde" && (
                        <div className="space-y-2 pt-3 border-t border-fuchsia-200">
                          <Label className="text-gray-600 text-sm flex items-center gap-1">
                            <CalendarDays className="w-3.5 h-3.5" />
                            Verfügbare Messdaten (Zeitraum)
                          </Label>
                          <p className="text-[10px] text-gray-400">Begrenzt den Datenzugriff des Kunden auf den angegebenen Zeitraum</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Von</Label>
                              <Input
                                type="date"
                                value={formData.apps.energy_monitoring.data_access_start?.split("T")[0] || ""}
                                onChange={(e) => updateEnergyMonitoringApp("data_access_start", e.target.value ? new Date(e.target.value).toISOString() : "")}
                                className="border-gray-300 text-sm"
                                data-testid="data-access-start-input"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-gray-500 text-xs">Bis</Label>
                              <Input
                                type="date"
                                value={formData.apps.energy_monitoring.data_access_end?.split("T")[0] || ""}
                                onChange={(e) => updateEnergyMonitoringApp("data_access_end", e.target.value ? new Date(e.target.value + "T23:59:59Z").toISOString() : "")}
                                className="border-gray-300 text-sm"
                                data-testid="data-access-end-input"
                              />
                            </div>
                          </div>
                          <p className="text-[10px] text-gray-400">Leer lassen = keine Einschränkung</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Time-based access for Kunden - Account level */}
                {formData.role === "kunde" && (
                  <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
                    <div className="flex items-center gap-3">
                      <CalendarDays className="w-5 h-5 text-fuchsia-600" />
                      <Label className="text-gray-900 font-medium">Konto-Verfügbarkeit</Label>
                    </div>
                    <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, access_type: "permanent" }))}
                          className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                            formData.access_type === "permanent"
                              ? "bg-fuchsia-50 border-fuchsia-400 text-fuchsia-700"
                              : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                          }`}
                          data-testid="access-type-permanent"
                        >
                          Dauerhaft
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, access_type: "temporary" }))}
                          className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                            formData.access_type === "temporary"
                              ? "bg-fuchsia-50 border-fuchsia-400 text-fuchsia-700"
                              : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                          }`}
                          data-testid="access-type-temporary"
                        >
                          Fester Zeitraum
                        </button>
                      </div>

                      {formData.access_type === "temporary" && (
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label className="text-gray-500 text-xs">Von</Label>
                            <Input
                              type="date"
                              value={formData.access_start?.split("T")[0] || ""}
                              onChange={(e) => setFormData(prev => ({ ...prev, access_start: e.target.value ? new Date(e.target.value).toISOString() : "" }))}
                              className="border-gray-300 text-sm"
                              data-testid="access-start-input"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-gray-500 text-xs">Bis</Label>
                            <Input
                              type="date"
                              value={formData.access_end?.split("T")[0] || ""}
                              onChange={(e) => setFormData(prev => ({ ...prev, access_end: e.target.value ? new Date(e.target.value + "T23:59:59Z").toISOString() : "" }))}
                              className="border-gray-300 text-sm"
                              data-testid="access-end-input"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
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
                        data-testid="module-toggle-adr"
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
