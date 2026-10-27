// Texte fuer Meldungen und Ereignisprotokoll – 1:1 aus texte.js der SPS-Firma (nicht aendern)
export const MELDUNGEN = {
  0: ["S", "Not-Aus betätigt", "Not-Aus entriegeln, dann quittieren."],
  1: ["S", "Isowächter 1 ausgelöst", "Isolationsfehler im Generatornetz. Generator fährt herunter."],
  2: ["S", "Isowächter 2 ausgelöst", "Isolationsfehler im Generatornetz. Generator fährt herunter."],
  3: ["S", "Störung allgemein", ""],
  4: ["S", "Störung Generator-Motor", "Generator fährt herunter. Motorsteuergerät prüfen."],
  5: ["S", "Sicherheitswanne ausgelöst", "Leckage? Generator fährt herunter."],
  6: ["S", "Störung Akkupack", "Akkupack wird abgeschaltet, Brücke geschlossen."],
  7: ["I", "Batterie-Unterspannung", "Im Generatorbetrieb wird die Batterie automatisch geladen."],
  8: ["I", "Windalarm - Mast fährt auf sichere Höhe", "Heben gesperrt, bis der Wind nachlässt."],
  9: ["S", "Drahtbruch Füllstand interner Tank", ""],
  10: ["S", "Drahtbruch Füllstand externer Tank", ""],
  11: ["S", "Drahtbruch Temperatur Gehäuse", ""],
  12: ["S", "Drahtbruch Temperatur Netzteil", ""],
  13: ["S", "Zeitüberschreitung Mast automatisch senken", "Sensor sichere Höhe prüfen."],
  14: ["S", "Generator startet nicht", "Keine Rückmeldung Betriebsbereit innerhalb der Startzeit."],
  15: ["S", "Generator ausgefallen", "Rückmeldung Betriebsbereit im Betrieb weggefallen."],
  16: ["I", "Überbrückung aktiv", "Eine Schutzfunktion ist im Admin-Menü überbrückt."],
  17: ["I", "Generator gesperrt", "Motorstart ist gesperrt (z. B. Halle)."],
  18: ["I", "Uhrzeit ungültig - bitte Systemzeit stellen", "Zeitschaltuhr arbeitet erst mit gültiger Uhrzeit."],
  19: ["I", "Netzausfall - Notbetrieb aktiv", ""],
  20: ["S", "Externer Tank: Füllstand unplausibel", "Es wird aus dem internen Tank gefahren."],
  21: ["I", "Externer Tank leer - Umschaltung auf internen Tank", ""],
  22: ["I", "Wartung fällig", "Nach der Wartung zurücksetzen."],
  23: ["I", "Tankfüllstand niedrig", "Bitte nachtanken."],
  24: ["I", "Tankfüllstand kritisch", "Bitte umgehend nachtanken."],
  25: ["I", "Wartung bald fällig", ""],
  26: ["I", "Wartungsmodus aktiv - Generator gesperrt", "Generator kann nicht starten."],
  27: ["I", "Zusatzmodul abgelaufen", "Die Laufzeit eines gebuchten Moduls ist überschritten."],
  28: ["I", "Akkupack angeschlossen, aber nicht freigeschaltet", "Modul Akkupack ist nicht gebucht."],
};

export const EREIGNISSE = {
  1: "SPS-Anlauf", 2: "Netzausfall", 3: "Netz wieder da", 4: "Notbetrieb gestartet", 5: "Notbetrieb beendet",
  6: "Generator läuft (betriebsbereit)", 7: "Generator aus", 8: "Licht ein", 9: "Licht aus", 10: "Probelauf gestartet",
  11: "Probelauf erfolgreich", 12: "Probelauf fehlgeschlagen", 13: "Batterieladung gestartet", 14: "Batterieladung beendet",
  15: "Wartungsmodus ein", 16: "Wartungsmodus aus", 17: "Fernbedienung freigegeben", 18: "Fernbedienung gesperrt",
  24: "Betriebsart Hand", 25: "Betriebsart Auto", 26: "Betriebsart Einrichten",
  27: "Versorgung Netz", 28: "Versorgung Generator", 29: "Generator gesperrt", 30: "Generator freigegeben",
  31: "Umschaltung auf externen Tank", 32: "Umschaltung auf internen Tank", 33: "Akkupack zugeschaltet", 34: "Akkupack abgeschaltet",
  35: "Netzüberwachung ein", 36: "Netzüberwachung aus", 37: "Modul Audio freigeschaltet", 38: "Modul Akkupack freigeschaltet",
  39: "Modul Netzüberwachung freigeschaltet", 40: "Modul Fernzugriff freigeschaltet", 41: "Modul Audio gesperrt / abgelaufen",
  42: "Modul Akkupack gesperrt / abgelaufen", 43: "Modul Netzüberwachung gesperrt / abgelaufen", 44: "Modul Fernzugriff gesperrt / abgelaufen",
  45: "Stumpfelbox an", 46: "Stumpfelbox aus", 47: "Tankumschaltung gesperrt", 48: "Tankumschaltung freigegeben",
};

export const BEFEHLSTEXTE = ["Quittieren", "Betriebsart Hand", "Betriebsart Auto", "Betriebsart Einrichten", "Teach Tank intern leer",
  "Teach Tank intern voll", "Teach Tank extern leer", "Teach Tank extern voll", "Versorgung Netz gewählt", "Versorgung Generator gewählt",
  "Generator Start", "Generator Stop", "Schnellstart", "Schnellstop", "Lampen ein", "Lampen aus", "Lampe 1 umgeschaltet",
  "Lampe 2 umgeschaltet", "Lampe 3 umgeschaltet", "Lampe 4 umgeschaltet", "Lampe 5 umgeschaltet", "Wochenprogramm gespeichert",
  "Wochenprogramm auf alle Tage", "Wochenprogramm auf Auswahl", "Datums-Schaltzeit hinzugefügt", "Datums-Schaltzeit gelöscht",
  "Steckdose 1 umgeschaltet", "Steckdose 3+4 umgeschaltet", "Stumpfelbox ein/aus", "Durchsage ein/aus", "Audio-Signal 1",
  "Audio-Signal 2", "Audio-Signal 3", "Audio-Signal 4", "Audio-Signal 5", "Audio-Signal 6", "Wartung quittiert",
  "Kundenzähler zurückgesetzt", "", "Systemzeit gestellt", "Probelauf gestartet (Taste)", "Automatik Dämmerung an/ab",
  "Automatik Uhr an/ab", "Automatik ein/aus", "Automatik Astro an/ab", "Netzüberwachung ein/aus"];

export function codeText(code) {
  if (!code) return "";
  if (code < 100) return EREIGNISSE[code] || "Ereignis " + code;
  if (code < 200) { const m = MELDUNGEN[code - 100]; return "Meldung: " + (m ? m[1] : code - 100); }
  if (code < 300) return "Vor Ort: " + (BEFEHLSTEXTE[code - 200] || "Befehl " + (code - 200));
  if (code < 400) return "Fern: " + (BEFEHLSTEXTE[code - 300] || "Befehl " + (code - 300));
  return "Code " + code;
}
