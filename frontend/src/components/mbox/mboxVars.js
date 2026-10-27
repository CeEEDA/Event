// Variablennamen exakt wie im SPS-Programm (index.html der SPS-Firma) – nicht aendern
export const ST = "DB_HMI.Status.";
export const STATUS_NAMEN = ["Betriebsart","Versorgung","Netzwaechter","Licht_Ein","Lampen_Alle_An","Lampen_Alle_Aus","Notbetrieb",
  "NUB_Rueckkehr_Laeuft","NUB_Rest_Min","NUB_Rest_Sek","Gen_Zustand","Netzschuetz","Generatorschuetz","Lampe","Ladung_Aktiv",
  "Abschaltung_Aktiv","Umschalten_Gesperrt","Uhr_Gueltig","Uhrzeit_Text","Datum_Text","Datum_Uebersteuert","Auto_Licht_Soll",
  "Auto_Daemmerung","Auto_Uhr","Auto_Astro","Astro_An","Astro_Aufgang","Astro_Untergang","Astro_Ein","Astro_Aus","Astro_Sonderfall",
  "GPS_Aktuell","Dunkel","Mast_Zustand","Mast_Heben_Gesperrt","Mast_Senken_Gesperrt","Windalarm","Sammelstoerung","Stoerung_Zustand",
  "Steckdose_1","Steckdose_34","Stumpfelbox","Stumpfelbox_Zustand","Audio_Bereit","Audio_Kanal","Tank_Extern_Angeschlossen",
  "Tank_Extern_Plausibel","Tank_Extern_Aktiv","Probelauf_Aktiv","Probelauf_Ergebnis","Tank_Niedrig","Tank_Kritisch","Wartungsmodus",
  "Fern_Erlaubt","Fern_Verbunden","Lebenszeichen","Akku_Zustand"];
export const ZAEHLER_NAMEN = ["Betrieb_h","Betrieb_min","Wartung_Bei_h","Wartung_Rest_h","Wartung_Rest_min","Wartung_Faellig","Wartung_Vorwarnung",
  "Wartung_Datum_Jahr","Wartung_Datum_Monat","Wartung_Datum_Tag","Wartung_Rest_Tage","Kunde_h","Kunde_min","Kunde_Minuten_Gesamt"];
export const BASIS = [
  ...STATUS_NAMEN.map(n => ST + n),
  ...["Wind","Daemmerung","Fuellstand_Intern","Fuellstand_Extern"].map(n => "DB_HMI.Analog." + n),
  "DB_Parameter.NUB_Ausfall_Verz", "DB_Parameter.NUB_Rueckkehr_Zeit",
  "DB_HMI.Module.Aktiv", "DB_HMI.Module.Abgelaufen", "DB_HMI.Module.Rest_Tage", "DB_HMI.Alarm",
  ...ZAEHLER_NAMEN.map(n => "DB_HMI.Zaehler." + n),
  "DB_Parameter.Lampen_Auswahl", "DB_Parameter.Audio_Name", "DB_Parameter.Daemmerung_Ein", "DB_Parameter.Daemmerung_Hysterese",
  "DB_Parameter.Generator_Gesperrt", "DB_Parameter.Netzueberwachung_Ein",
  "DB_Astro.Breite", "DB_Astro.Laenge", "DB_Astro.Position_Gueltig", "DB_Astro.Versatz_Ein", "DB_Astro.Versatz_Aus",
];
const ZEIT = ["Jahr","Monat","Tag","Std","Min","Sek"];
export const EXTRA = {
  meldungen: Array.from({ length: 30 }, (_, i) => [...ZEIT.map(z => `DB_Fern.Protokoll[${i + 1}].Zeit.${z}`), `DB_Fern.Protokoll[${i + 1}].Code`]).flat(),
  uhr: [
    ...Array.from({ length: 49 }, (_, k) => ["Aktiv_Ein","Aktiv_Aus","Ein_Std","Ein_Min","Aus_Std","Aus_Min"]
      .map(f => `DB_Schaltuhr.Woche[${Math.floor(k / 7) + 1},${k % 7 + 1}].${f}`)).flat(),
    ...Array.from({ length: 20 }, (_, i) => ["Belegt","Einschalten","Jahr","Monat","Tag","Std","Min"].map(f => `DB_Schaltuhr.Datum[${i + 1}].${f}`)).flat(),
  ],
  diagnose: ["DI_NotAus_OK","DI_Isowaechter_1","DI_Isowaechter_2","DI_Stoerung_Allgemein","DI_Motor_Betriebsbereit","DI_Motor_Stoerung",
    "DI_Batterieueberwachung","DI_Taster_Mast_Ab","DI_Taster_Mast_Auf","DI_Mast_Einfahrposition","DI_Mast_SichereHoehe","DI_Tank_Extern_Stecker",
    "DI_Sicherheitswanne_OK","DI_Netzwaechter","DI_Akkupack_Angeschlossen","DI_Akkupack_Stoerung","AI_Windsensor","AI_Daemmerungssensor",
    "AI_Fuellstand_Intern","AI_Fuellstand_Extern","AI_Temp_Gehaeuse","AI_Temp_Netzteil","DQ_Netzschuetz","DQ_Generatorschuetz",
    "DQ_Akku_Einspeisung","DQ_Akku_Bruecke","DQ_Akku_Abgabe","DQ_Lampe_1","DQ_Lampe_2","DQ_Lampe_3","DQ_Lampe_4","DQ_Lampe_5",
    "DQ_Audiosignal_1","DQ_Audiosignal_2","DQ_Audiosignal_3","DQ_Audiosignal_4","DQ_Audiosignal_5","DQ_Audiosignal_6","DQ_Steckdose_1",
    "DQ_Steckdose_3_4","DQ_Hydraulikmotor","DQ_Mast_Senken","DQ_Generator_RemoteStart","DQ_StumpfelBox","DQ_Audioverstaerker",
    "DQ_Akku_Extern_EinAus","DQ_Tank_Umschaltventil","DQ_Generator_DisplayFreigabe"].map(n => "DB_HMI.IO." + n),
};

export const GEN = { 0: "Aus", 10: "Startet", 20: "Läuft", 30: "Fährt herunter" };
export const AKKU = { 0: "kein Akkupack", 10: "Brücke offen", 20: "Einspeisung", 30: "Betrieb", 99: "Not-Aus" };
export const PROBE = { 0: "noch keiner", 1: "OK", 2: "Fehler", 3: "abgebrochen" };
export const SONDER = { 0: "normal", 1: "Polarnacht (immer an)", 2: "Mitternachtssonne (immer aus)", 3: "keine Position oder Uhrzeit" };
export const BOX = { 0: "aus", 1: "fährt hoch (10 s)", 2: "bereit" };
export const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
export const MODULE = ["Audio", "Akkupack", "Netzüberwachung", "Fernzugriff"];
export const EINSTELLUNGEN = [
  { name: "DB_Astro.Versatz_Ein", label: "Astro: Ein [min nach Untergang]", min: -120, max: 120 },
  { name: "DB_Astro.Versatz_Aus", label: "Astro: Aus [min nach Aufgang]", min: -120, max: 120 },
  { name: "DB_Parameter.Daemmerung_Ein", label: "Dämmerung: Ein unter [Lux]", min: 10, max: 400 },
  { name: "DB_Parameter.Daemmerung_Hysterese", label: "Dämmerung: Hysterese [Lux]", min: 5, max: 100 },
];

// Werte-Helfer (Semantik wie im Original)
export const mkHelpers = (W) => {
  const roh = n => W[n];
  const v = n => { const x = W[n]; return (x && typeof x === "object" && !Array.isArray(x) && x.fehler) ? undefined : x; };
  const s = n => v(ST + n);
  return { roh, v, s };
};
export const ja = b => b === true ? "ja" : b === false ? "nein" : "–";
export const z2 = x => String(typeof x === "number" ? x : 0).padStart(2, "0");
export const zahl = (x, st = 1) => typeof x === "number" ? x.toLocaleString("de-DE", { minimumFractionDigits: st, maximumFractionDigits: st }) : "–";
export const text = (map, x) => map[x] ?? (x === undefined ? "–" : x);
