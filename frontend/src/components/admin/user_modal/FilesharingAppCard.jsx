/**
 * FileSharing-App-Karte im UserEditModal (Kunde-Rolle).
 */
import { FolderOpen } from "lucide-react";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";
import { Switch } from "../../ui/switch";

export default function FilesharingAppCard({ formData, updateFilesharingApp }) {
  const fs = formData.apps.filesharing;
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FolderOpen className="w-5 h-5 text-fuchsia-600" />
          <Label className="text-gray-900 font-medium">FileShare</Label>
        </div>
        <Switch
          checked={fs.enabled}
          onCheckedChange={(checked) => updateFilesharingApp("enabled", checked)}
          data-testid="filesharing-enabled-toggle"
        />
      </div>

      {fs.enabled && (
        <div className="space-y-3 pl-8 border-l-2 border-fuchsia-300">
          <div className="space-y-2">
            <Label className="text-gray-600 text-sm">Max. Dateigröße (MB)</Label>
            <Input
              type="number"
              value={fs.max_upload_size_mb}
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
              checked={fs.can_write}
              onCheckedChange={(checked) => updateFilesharingApp("can_write", checked)}
              data-testid="filesharing-write-toggle"
            />
          </div>

          <div className="flex items-center justify-between">
            <Label className="text-gray-600 text-sm">Löschen erlaubt (Gemeinsamer Bereich)</Label>
            <Switch
              checked={fs.can_delete}
              onCheckedChange={(checked) => updateFilesharingApp("can_delete", checked)}
              data-testid="filesharing-delete-toggle"
            />
          </div>
        </div>
      )}
    </div>
  );
}
