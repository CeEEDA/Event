import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Users, QrCode, Copy } from "lucide-react";
import api, { getErrorMsg } from "../../lib/api";
import { Button } from "../ui/button";
import { Karte } from "../mbox/MBoxUi";

// Messe-Team: Mitarbeiter anklicken -> bekommen waehrend der Messe im Hub einen QR-Code mit ihrer Kontaktkarte
export function MesseTeam({ messe, onChange }) {
  const [options, setOptions] = useState([]);
  const [busy, setBusy] = useState(false);
  const selected = messe.staff_ids || [];
  const tokens = messe.staff_tokens || {};

  useEffect(() => {
    api.get("/messe/staff-options").then(r => setOptions(r.data || [])).catch(() => {});
  }, []);

  const toggle = async (id) => {
    const next = selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id];
    setBusy(true);
    try {
      await api.patch(`/messe/${messe.id}`, { staff_ids: next });
      onChange();
    } catch (e) {
      toast.error(getErrorMsg(e, "Speichern fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  const copy = (uid) => {
    navigator.clipboard?.writeText(`${window.location.origin}/messe/kontakt/${tokens[uid]}`);
    toast.success("Kontakt-Link kopiert");
  };

  return (
    <Karte titel={`Messe-Team (${selected.length})`} testId="messe-team">
      <p className="text-xs text-gray-500 mb-3 flex items-center gap-1"><QrCode className="w-3.5 h-3.5 text-fuchsia-500" /> Ausgewählte Mitarbeiter sehen während der Messe im Hub einen QR-Code, über den Besucher ihre Kontaktdaten übernehmen können.</p>
      {options.length === 0 && <p className="text-sm text-gray-400">Keine Mitarbeiter gefunden.</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map(u => {
          const on = selected.includes(u.id);
          return (
            <div key={u.id} className={`rounded-xl border-2 px-3 py-2 flex items-center gap-3 transition ${on ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 bg-white"}`} data-testid={`messe-staff-${u.id}`}>
              <button type="button" onClick={() => toggle(u.id)} disabled={busy} className="flex-1 min-w-0 flex items-center gap-3 text-left" data-testid={`messe-staff-toggle-${u.id}`}>
                <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${on ? "border-fuchsia-600 bg-fuchsia-600 text-white" : "border-gray-300"}`}>{on && <Check className="w-3 h-3" />}</span>
                <Users className={`w-4 h-4 shrink-0 ${on ? "text-fuchsia-600" : "text-gray-400"}`} />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-gray-900 truncate">{u.name}</span>
                  <span className="block text-[11px] text-gray-500 truncate">{u.email}</span>
                </span>
              </button>
              {on && tokens[u.id] && (
                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs shrink-0" onClick={() => copy(u.id)} title="Kontakt-Link kopieren" data-testid={`messe-staff-copy-${u.id}`}><Copy className="w-3.5 h-3.5" /></Button>
              )}
            </div>
          );
        })}
      </div>
    </Karte>
  );
}
