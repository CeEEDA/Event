/**
 * Generator-Monitoring-App-Karte im UserEditModal.
 */
import { Activity, Zap, CalendarDays } from "lucide-react";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";
import { Switch } from "../../ui/switch";

export default function GeneratorMonitoringCard({
  formData,
  updateGeneratorMonitoringApp,
  toggleGeneratorId,
  allGenerators,
}) {
  const gm = formData.apps.generator_monitoring;
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-4 mt-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-fuchsia-600" />
          <Label className="text-gray-900 font-medium">Generator-Monitoring</Label>
        </div>
        <Switch
          checked={gm.enabled}
          onCheckedChange={(checked) => updateGeneratorMonitoringApp("enabled", checked)}
          data-testid="monitoring-enabled-toggle"
        />
      </div>

      {gm.enabled && (
        <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
          <div className="flex items-center justify-between">
            <Label className="text-gray-600 text-sm">Zugriff auf alle Generatoren</Label>
            <Switch
              checked={gm.access_all}
              onCheckedChange={(checked) => updateGeneratorMonitoringApp("access_all", checked)}
              data-testid="monitoring-access-all-toggle"
            />
          </div>

          {!gm.access_all && (
            <div className="space-y-2">
              <Label className="text-gray-600 text-sm">Einzelne Generatoren auswählen</Label>
              <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                {allGenerators.length === 0 ? (
                  <p className="text-xs text-gray-400 p-3">Keine Generatoren vorhanden</p>
                ) : (
                  allGenerators.map((gen) => {
                    const isSelected = (gm.generator_ids || []).includes(gen.id);
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
                {(gm.generator_ids || []).length} von {allGenerators.length} ausgewählt
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
                checked={gm.share_electrical !== false}
                onCheckedChange={(checked) => updateGeneratorMonitoringApp("share_electrical", checked)}
                data-testid="gen-share-electrical-toggle"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-gray-600 text-sm">Mechanische Daten (RPM, Öl, Temp, Tank, Batt)</Label>
              <Switch
                checked={gm.share_mechanical !== false}
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
                    value={gm.data_access_start?.split("T")[0] || ""}
                    onChange={(e) => updateGeneratorMonitoringApp("data_access_start", e.target.value ? new Date(e.target.value).toISOString() : "")}
                    className="border-gray-300 text-sm"
                    data-testid="gen-data-access-start"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-500 text-xs">Bis</Label>
                  <Input
                    type="date"
                    value={gm.data_access_end?.split("T")[0] || ""}
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
  );
}
