import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Copy, ExternalLink, Download } from "lucide-react";
import { toast } from "sonner";

export const DownloadLinkDialog = ({ open, onClose, url, filename }) => {
  const copyLink = () => {
    navigator.clipboard.writeText(url).then(() => {
      toast.success("Link kopiert");
    }).catch(() => {
      // Fallback for older browsers
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      toast.success("Link kopiert");
    });
  };

  const openInNewTab = () => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="download-link-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <Download className="w-5 h-5 text-fuchsia-600" />
            Datei herunterladen
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
            Downloads sind in der Vorschau-Umgebung eingeschränkt. Nutzen Sie eine der folgenden Optionen:
          </div>

          <div className="space-y-2">
            <p className="text-sm text-gray-500">Dateiname</p>
            <p className="font-medium text-gray-900">{filename}</p>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-gray-500">Download-Link</p>
            <div className="flex items-start gap-2">
              <code className="text-xs text-fuchsia-600 bg-fuchsia-50 p-2 rounded border border-fuchsia-200 break-all flex-1 max-h-20 overflow-y-auto">
                {url}
              </code>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Button
              onClick={openInNewTab}
              className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
              data-testid="download-open-new-tab"
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              In neuem Tab öffnen
            </Button>
            <Button
              variant="outline"
              onClick={copyLink}
              className="w-full border-gray-300"
              data-testid="download-copy-link"
            >
              <Copy className="w-4 h-4 mr-2" />
              Link kopieren
            </Button>
          </div>

          <p className="text-xs text-gray-400 text-center">
            Tipp: Im deployten Zustand funktionieren Downloads automatisch.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
