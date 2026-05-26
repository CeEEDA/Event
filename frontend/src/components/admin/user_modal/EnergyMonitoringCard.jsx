/**
 * Energy-Monitoring-App-Karte im UserEditModal.
 */
import { Zap, CalendarDays } from "lucide-react";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";
import { Switch } from "../../ui/switch";

export default function EnergyMonitoringCard({
  formData,
  updateEnergyMonitoringApp,
  toggleEnergyDeviceId,
  allMesskoffer,
}) {
  const em = formData.apps.energy_monitoring;
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="w-5 h-5 text-fuchsia-600" />
          <Label className="text-gray-900 font-medium">Energy Monitoring</Label>
        </div>
        <Switch
          checked={em.enabled}
          onCheckedChange={(checked) => updateEnergyMonitoringApp("enabled", checked)}
          data-testid="energy-monitoring-enabled-toggle"
        />
      </div>

      {em.enabled && (
        <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
          <div className="flex items-center justify-between">
            <Label className="text-gray-600 text-sm">Zugriff auf alle Messkoffer</Label>
            <Switch
              checked={em.access_all}
              onCheckedChange={(checked) => updateEnergyMonitoringApp("access_all", checked)}
              data-testid="energy-access-all-toggle"
            />
          </div>

          {!em.access_all && (
            <div className="space-y-2">
              <Label className="text-gray-600 text-sm">Einzelne Messkoffer auswählen</Label>
              <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                {allMesskoffer.length === 0 ? (
                  <p className="text-xs text-gray-400 p-3">Keine Messkoffer vorhanden</p>
                ) : (
                  allMesskoffer.map((mk) => {
                    const isSelected = (em.device_ids || []).includes(mk.id);
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
                {(em.device_ids || []).length} von {allMesskoffer.length} ausgewählt
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
                    value={em.data_access_start?.split("T")[0] || ""}
                    onChange={(e) => updateEnergyMonitoringApp("data_access_start", e.target.value ? new Date(e.target.value).toISOString() : "")}
                    className="border-gray-300 text-sm"
                    data-testid="data-access-start-input"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-500 text-xs">Bis</Label>
                  <Input
                    type="date"
                    value={em.data_access_end?.split("T")[0] || ""}
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
  );
}
