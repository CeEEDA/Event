/**
 * Konto-Verfuegbarkeit-Karte im UserEditModal (Kunde-Rolle).
 * Schaltet zwischen "permanent" und "temporary" Account-Zugriff um.
 */
import { CalendarDays } from "lucide-react";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";

export default function AccountAvailabilityCard({ formData, setFormData }) {
  return (
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
  );
}
