import { Karte, Btn } from "./MBoxUi";
import { BOX, text } from "./mboxVars";

export function AudioTab({ h, befehl, darf }) {
  const { v, s } = h;
  const audioModul = (v("DB_HMI.Module.Aktiv") || [])[0];
  const bz = s("Stumpfelbox_Zustand"), kanal = s("Audio_Kanal"), namen = v("DB_Parameter.Audio_Name") || [];
  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="mbox-tab-audio">
      <Karte titel="Steckdosen">
        <div className="flex flex-wrap gap-2">
          <Btn variant={s("Steckdose_1") ? "an" : undefined} disabled={!darf} onClick={() => befehl("Steckdose_1_Umschalten")} testId="mbox-btn-steckdose-1">Steckdose 1: {s("Steckdose_1") ? "an" : "aus"}</Btn>
          <Btn variant={s("Steckdose_34") ? "an" : undefined} disabled={!darf} onClick={() => befehl("Steckdose_34_Umschalten")} testId="mbox-btn-steckdose-34">Steckdose 3+4: {s("Steckdose_34") ? "an" : "aus"}</Btn>
        </div>
      </Karte>
      <Karte titel="Stumpfelbox / Audio">
        {audioModul === false ? (
          <p className="text-xs text-gray-500">Das Modul Audio ist nicht freigeschaltet.</p>
        ) : (
          <>
            <div className="mb-2">
              <Btn variant={bz === 2 ? "an" : bz === 1 ? "laeuft" : undefined} disabled={!darf} onClick={() => befehl("Stumpfelbox_Umschalten")} testId="mbox-btn-stumpfelbox">Stumpfelbox: {text(BOX, bz)}</Btn>
            </div>
            <div className="flex flex-wrap gap-2">
              {[0, 1, 2, 3, 4, 5, 6].map(i => (
                <Btn key={i} variant={kanal === i ? "an" : undefined} disabled={!darf} onClick={() => befehl("Audio_Umschalten", i)} testId={`mbox-btn-audio-${i}`}>
                  {namen[i] || (i ? "Signal " + i : "Durchsage")}
                </Btn>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">{s("Audio_Bereit") ? "Audio bereit. Nochmal tippen schaltet aus." : "Erst die Stumpfelbox einschalten (10 s Hochlauf)."}</p>
          </>
        )}
      </Karte>
    </div>
  );
}
