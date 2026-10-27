// M-Box V3.0 – OPC-UA-Bedienprogramm (Test)
// Startet einen kleinen Webserver auf http://localhost:8080 und spricht per OPC UA mit der SPS.
// Befehle werden nach DB_Fern.Cmd geschrieben (wirken nur, wenn Modul Fernzugriff freigeschaltet,
// "Fernbedienung erlaubt" an und kein Wartungsmodus aktiv ist).
// Die NodeIds werden beim Verbinden automatisch gesucht (Server-Schnittstelle "M-Box" bevorzugt,
// sonst Standard-SIMATIC-Schnittstelle). Variablen werden nur per Name angegeben, z. B. "DB_HMI.Status.Versorgung".

const express = require("express");
const path = require("path");
const {
  OPCUAClient, MessageSecurityMode, SecurityPolicy, AttributeIds, DataType, VariantArrayType, UserTokenType
} = require("node-opcua");

// ===================== Einstellungen =====================
// Werte kommen aus der Datei ".env" im Programmordner (Vorlage: .env.beispiel) oder aus Umgebungsvariablen.
// Zugangsdaten gehoeren NICHT in den Quellcode.
(function envLaden() {
  const datei = path.join(__dirname, ".env");
  if (!require("fs").existsSync(datei)) return;
  for (const zeile of require("fs").readFileSync(datei, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/.exec(zeile);
    if (m && !zeile.trim().startsWith("#") && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
})();
const KONFIG = {
  endpoint: process.env.OPCUA_ENDPOINT || "opc.tcp://192.168.0.100:4840",
  // Test: "None"/"None" + in TIA "Keine Sicherheit" erlaubt. Betrieb: "SignAndEncrypt"/"Basic256Sha256".
  securityMode: process.env.OPCUA_SECURITY_MODE || "None",        // "None" | "Sign" | "SignAndEncrypt"
  securityPolicy: process.env.OPCUA_SECURITY_POLICY || "None",    // "None" | "Basic256Sha256"
  benutzer: process.env.OPCUA_BENUTZER || "",                     // leer = Gastzugang (anonym)
  passwort: process.env.OPCUA_PASSWORT || "",
  webHost: process.env.WEB_HOST || "127.0.0.1",                   // 127.0.0.1 = nur lokal / hinter Reverse-Proxy erreichbar
  webPort: Number(process.env.WEB_PORT || 8080)
};
// =========================================================

const SIEMENS_NS_URI = "http://www.siemens.com/simatic-s7-opcua";

// Erlaubte Befehle (Name in DB_Fern.Cmd). Einrichten, Teach, Uhr stellen und Schaltuhr-Bearbeitung
// bleiben bewusst dem Panel vor Ort vorbehalten.
const BEFEHLE = ["Quittieren", "Hand", "Auto", "Auto_Umschalten",
                 "Schnellstart", "Schnellstop", "Lampen_Ein", "Lampen_Aus",
                 "Gen_Start", "Gen_Stop", "Netzbetrieb", "Generatorbetrieb",
                 "Steckdose_1_Umschalten", "Steckdose_34_Umschalten", "Stumpfelbox_Umschalten",
                 "Auto_Daemmerung_Umschalten", "Auto_Uhr_Umschalten", "Auto_Astro_Umschalten",
                 "Wartung_Reset", "Kundenzaehler_Reset", "Probelauf_Start", "Netzueberwachung_Umschalten"];
// Befehls-Arrays: Name -> [kleinster Index, Anzahl]
const BEFEHL_ARRAYS = { Lampe_Umschalten: [1, 5], Audio_Umschalten: [0, 7] };

// Einstellungen, die von aussen geschrieben werden duerfen (nur bei "Fernbedienung erlaubt")
const EINSTELLUNGEN = {
  "DB_Astro.Versatz_Ein": { typ: DataType.Int16, min: -120, max: 120, ganz: true },
  "DB_Astro.Versatz_Aus": { typ: DataType.Int16, min: -120, max: 120, ganz: true },
  "DB_Parameter.Daemmerung_Ein": { typ: DataType.Float, min: 10, max: 400 },
  "DB_Parameter.Daemmerung_Hysterese": { typ: DataType.Float, min: 5, max: 100 }
};

let client = null, session = null, ns = 3, verbindet = null, lebenszeichen = 0;
let karte = new Map();          // "DB_HMI.Status.Versorgung" -> NodeId
let karteInfo = { knoten: 0, variablen: 0, schnittstellen: [] };
const angefragt = new Set();    // alle Namen, die die Webseite schon gelesen hat (fuer /api/knoten)

// Namenspfad vereinheitlichen: ["Protokoll", "[1]", "Code"] bzw. ["Protokoll", "Protokoll[1]", "Code"] -> "Protokoll[1].Code"
function schluesselAus(teile) {
  const aus = [];
  for (const t of teile) {
    const nurIndex = /^\[[\d,\s]+\]$/.test(t);
    const mitName = /^(.+?)(\[[\d,\s]+\])$/.exec(t);
    if (nurIndex && aus.length) aus[aus.length - 1] += t.replace(/\s/g, "");
    else if (mitName && aus.length && aus[aus.length - 1] === mitName[1]) aus[aus.length - 1] = t.replace(/\s/g, "");
    else aus.push(t);
  }
  return aus.join(".");
}

// Eigene Server-Schnittstellen ("M-Box") nummerieren Array-Elemente immer ab 0, unabhaengig von der Deklaration
// (Woche[1..7, 1..7] erscheint als Woche[0..6, 0..6]). Die Standard-SIMATIC-Schnittstelle nutzt die deklarierten Indizes.
// Damit die Webseite ueberall mit den Indizes aus TIA arbeiten kann, wird hier um die Untergrenze verschoben.
// Nicht aufgefuehrte Arrays beginnen bei 0 (z. B. Audio_Name[0..6], Alarm[0..1]).
const UNTERGRENZE = {
  "DB_Schaltuhr.Woche": 1, "DB_Schaltuhr.Datum": 1,
  "DB_Fern.Uhr.Woche": 1, "DB_Fern.Uhr.Kopieren_Auf": 1, "DB_Fern.Protokoll": 1, "DB_Fern.Cmd.Lampe_Umschalten": 1,
  "DB_HMI.Uhr.Woche": 1, "DB_HMI.Uhr.Kopieren_Auf": 1, "DB_HMI.Protokoll.Anzeige": 1, "DB_HMI.Cmd.Lampe_Umschalten": 1,
  "DB_HMI.Status.Lampe": 1, "DB_HMI.Module.Aktiv": 1, "DB_HMI.Module.Abgelaufen": 1, "DB_HMI.Module.Rest_Tage": 1,
  "DB_Parameter.Lampen_Auswahl": 1, "DB_Module.Modul": 1
};
function aufDeklariert(schluessel) {
  const ohneIndex = [];
  return schluessel.split(".").map(t => {
    const m = /^(.+?)\[([\d,]+)\]$/.exec(t);
    ohneIndex.push(m ? m[1] : t);
    if (!m) return t;
    const ug = UNTERGRENZE[ohneIndex.join(".")] || 0;
    return `${m[1]}[${m[2].split(",").map(x => Number(x) + ug).join(",")}]`;
  }).join(".");
}
// Durchsucht den Server ab "Objects" und merkt sich zu jedem Knoten unterhalb eines DB_... den Namenspfad.
async function karteAufbauen(sess) {
  const neu = new Map(), besucht = new Set(), schnittstellen = new Set();
  let ebene = [{ nodeId: "ns=0;i=85", pfad: [] }];
  let gezaehlt = 0;
  for (let tiefe = 0; tiefe < 10 && ebene.length && gezaehlt < 12000; tiefe++) {
    const naechste = [];
    for (let i = 0; i < ebene.length; i += 50) {
      const teil = ebene.slice(i, i + 50);
      const ergebnisse = await sess.browse(teil.map(t => ({
        nodeId: t.nodeId, referenceTypeId: "HierarchicalReferences", includeSubtypes: true,
        browseDirection: 0, nodeClassMask: 0, resultMask: 63
      })));
      for (let j = 0; j < teil.length; j++) {
        let r = ergebnisse[j];
        const refs = r.references ? [...r.references] : [];
        while (r.continuationPoint && r.continuationPoint.length) {
          r = await sess.browseNext(r.continuationPoint, false);
          if (r.references) refs.push(...r.references);
        }
        for (const ref of refs) {
          const id = ref.nodeId.toString();
          if (ref.nodeId.namespace === 0 || besucht.has(id)) continue;   // Standardknoten (Server, Typen) auslassen
          besucht.add(id); gezaehlt++;
          const pfad = [...teil[j].pfad, ref.browseName.name];
          const start = pfad.findIndex(n => /^DB_/.test(n));
          if (start >= 0) {
            let schluessel = schluesselAus(pfad.slice(start));
            if (ref.nodeId.namespace !== ns) schluessel = aufDeklariert(schluessel);   // eigene Schnittstelle: Index ab 0
            const vorhanden = neu.get(schluessel);
            // eigene Schnittstelle ("M-Box") hat Vorrang vor der Standard-SIMATIC-Schnittstelle
            if (!vorhanden || (vorhanden.ns === ns && ref.nodeId.namespace !== ns)) {
              neu.set(schluessel, { id, ns: ref.nodeId.namespace });
            }
            if (start === pfad.length - 1) schnittstellen.add(pfad.slice(0, start).join(" / ") + "  (ns=" + ref.nodeId.namespace + ")");
            if (/^DB_Protokoll$/.test(pfad[start])) continue;   // 200 Eintraege, wird nicht gebraucht
          }
          if (/^iDB_/.test(ref.browseName.name)) continue;          // Instanz-DBs (nur Standard-Schnittstelle) nicht durchsuchen
          naechste.push({ nodeId: id, pfad });
        }
      }
    }
    ebene = naechste;
  }
  karte = new Map([...neu].map(([k, v]) => [k, v.id]));
  karteInfo = { knoten: gezaehlt, variablen: karte.size, schnittstellen: [...schnittstellen] };
  console.log(`Knoten durchsucht: ${gezaehlt}, Variablen gefunden: ${karte.size}`);
  for (const s of schnittstellen) console.log("  DBs unter: " + s);
}

// Jeder OPC-UA-Aufruf bekommt ein Zeitlimit. Haengt eine Anfrage (z. B. weil die Verbindung im Hintergrund
// weggebrochen ist), wird die Verbindung verworfen und bei der naechsten Abfrage neu aufgebaut.
const ZEITLIMIT_MS = 8000;
function mitZeitlimit(versprechen, was, ms = ZEITLIMIT_MS) {
  let t;
  const ablauf = new Promise((_, nein) => { t = setTimeout(() => nein(new Error(`Zeitüberschreitung: ${was} (${ms / 1000} s)`)), ms); });
  return Promise.race([versprechen, ablauf]).finally(() => clearTimeout(t));
}

async function verbinden() {
  if (session) return session;
  if (verbindet) return verbindet;
  verbindet = (async () => {
    client = OPCUAClient.create({
      applicationName: "MBox-Fernbedienung",
      connectionStrategy: { initialDelay: 1000, maxRetry: 1 },
      securityMode: MessageSecurityMode[KONFIG.securityMode],
      securityPolicy: SecurityPolicy[KONFIG.securityPolicy],
      endpointMustExist: false,
      keepSessionAlive: true
    });
    client.on("connection_lost", () => { console.log("Verbindung zur SPS verloren"); trennen(); });
    await mitZeitlimit(client.connect(KONFIG.endpoint), "Verbinden", 8000);
    const identitaet = KONFIG.benutzer
      ? { type: UserTokenType.UserName, userName: KONFIG.benutzer, password: KONFIG.passwort }
      : undefined;
    const s = await mitZeitlimit(client.createSession(identitaet), "Sitzung anlegen", 8000);
    const nsArray = await mitZeitlimit(s.readNamespaceArray(), "Namespaces lesen");
    const idx = nsArray.indexOf(SIEMENS_NS_URI);
    if (idx >= 0) ns = idx;
    console.log(`Verbunden mit ${KONFIG.endpoint}`);
    nsArray.forEach((u, i) => console.log(`  ns=${i}: ${u}`));
    if (karte.size === 0) await mitZeitlimit(karteAufbauen(s), "Variablen suchen", 120000);   // nur beim ersten Mal suchen, nicht bei jedem Neuverbinden
    session = s;
    return session;
  })();
  try { return await verbindet; }
  catch (e) { await trennen(); throw e; }
  finally { verbindet = null; }
}

async function trennen() {
  // sofort freigeben, das Schliessen laeuft im Hintergrund (darf nicht selbst haengen bleiben)
  const s = session, c = client;
  session = null; client = null;
  if (s) mitZeitlimit(s.close(), "Sitzung schliessen", 3000).catch(() => {});
  if (c) mitZeitlimit(c.disconnect(), "Trennen", 3000).catch(() => {});
}

// Name -> NodeId (gefunden), sonst Schema der Standard-SIMATIC-Schnittstelle
const knoten = (name) => karte.get(name) ||
  `ns=${ns};s=` + name.split(".").map(t => { const m = /^(.+?)(\[.*\])$/.exec(t); return m ? `"${m[1]}"${m[2]}` : `"${t}"`; }).join(".");

async function lesen(namen) {
  const sess = await verbinden();
  const ergebnis = {};
  for (let i = 0; i < namen.length; i += 100) {
    const teil = namen.slice(i, i + 100);
    const start = Date.now();
    const werte = await mitZeitlimit(sess.read(teil.map(n => ({ nodeId: knoten(n), attributeId: AttributeIds.Value }))), "Lesen");
    if (Date.now() - start > 2000) console.log(`Lesen von ${teil.length} Werten dauerte ${Date.now() - start} ms`);
    teil.forEach((n, j) => {
      angefragt.add(n);
      if (!werte[j].statusCode.isGood()) { ergebnis[n] = { fehler: werte[j].statusCode.name }; return; }
      const v = werte[j].value ? werte[j].value.value : null;
      ergebnis[n] = (v && typeof v === "object" && v.length !== undefined && typeof v !== "string") ? Array.from(v) : v;
    });
  }
  return ergebnis;
}

async function schreiben(liste) {   // liste: [{ name, dataType, wert, array }]
  const sess = await verbinden();
  const status = await mitZeitlimit(sess.write(liste.map(e => ({
    nodeId: knoten(e.name), attributeId: AttributeIds.Value,
    value: { value: e.array
      ? { dataType: e.dataType, arrayType: VariantArrayType.Array, value: e.wert }
      : { dataType: e.dataType, value: e.wert } }
  }))), "Schreiben an SPS");
  const fehler = liste.map((e, i) => status[i].isGood() ? null : `${e.name}: ${status[i].toString()}`).filter(Boolean);
  if (fehler.length) throw new Error("Schreiben " + fehler.join("; "));
}

async function antwort(res, fn) {
  try { res.json({ ok: true, ...(await fn()) }); }
  catch (e) {
    console.log("Fehler:", e.message);
    if (!/^(Schreiben |Abgelehnt)/.test(e.message)) await trennen();
    res.json({ ok: false, fehler: e.message });
  }
}

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Werte lesen: POST /api/lesen  { "namen": ["DB_HMI.Status.Versorgung", ...] }
app.post("/api/lesen", (req, res) => antwort(res, async () => {
  const namen = Array.isArray(req.body.namen) ? req.body.namen.filter(n => typeof n === "string" && /^DB_\w+/.test(n)) : [];
  return { werte: await lesen(namen.slice(0, 1500)) };
}));

// Befehl: POST /api/befehl/Schnellstart   bzw.  /api/befehl/Lampe_Umschalten?index=3
app.post("/api/befehl/:name", (req, res) => antwort(res, async () => {
  const name = req.params.name;
  if (BEFEHLE.includes(name)) {
    await schreiben([{ name: "DB_Fern.Cmd." + name, dataType: DataType.Boolean, wert: true }]);
  } else if (BEFEHL_ARRAYS[name]) {
    const [erster, anzahl] = BEFEHL_ARRAYS[name], idx = Number(req.query.index);
    if (!Number.isInteger(idx) || idx < erster || idx >= erster + anzahl) throw new Error("Abgelehnt: Index ungültig");
    const feld = new Array(anzahl).fill(false); feld[idx - erster] = true;   // SPS setzt alle Bits wieder zurueck
    await schreiben([{ name: "DB_Fern.Cmd." + name, dataType: DataType.Boolean, wert: feld, array: true }]);
  } else {
    throw new Error("Abgelehnt: unbekannter Befehl");
  }
  console.log("Befehl gesendet:", name, req.query.index ?? "");
  return {};
}));

// ===================== Zeitschaltuhr =====================
// Eigener Puffer DB_Fern.Uhr: erst Daten schreiben, dann Befehl. Die SPS prueft, uebernimmt, sortiert
// und meldet das Ergebnis in DB_Fern.Uhr.Meldung (1 gespeichert, 2 ungueltig, 3 Vergangenheit, 4 voll, 5 geloescht).
const UHR_MELDUNG = { 1: "gespeichert", 2: "Eingabe ungültig", 3: "liegt in der Vergangenheit", 4: "Liste voll (max. 20)", 5: "gelöscht" };

async function uhrBefehl(daten, befehl) {
  const ganz = (x, min, max) => { const n = Number(x); if (!Number.isInteger(n) || n < min || n > max) throw new Error(`Abgelehnt: Wert ${x} ungültig`); return n; };
  const erlaubt = (await lesen(["DB_HMI.Status.Fern_Erlaubt"]))["DB_HMI.Status.Fern_Erlaubt"];
  if (erlaubt !== true) throw new Error("Abgelehnt: am Panel ist \"Fernbedienung erlaubt\" aus");
  await schreiben([{ name: "DB_Fern.Uhr.Meldung", dataType: DataType.Int16, wert: 0 }, ...daten(ganz)]);
  await schreiben([{ name: "DB_Fern.Cmd." + befehl, dataType: DataType.Boolean, wert: true }]);
  // Rueckmeldung der SPS abwarten (max. 2 s)
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 200));
    const m = (await lesen(["DB_Fern.Uhr.Meldung"]))["DB_Fern.Uhr.Meldung"];
    if (m) { console.log("Schaltuhr:", befehl, "->", UHR_MELDUNG[m] || m); if (m === 1 || m === 5) return { meldung: UHR_MELDUNG[m] }; throw new Error("Abgelehnt: " + (UHR_MELDUNG[m] || m)); }
  }
  throw new Error("Abgelehnt: keine Rückmeldung der SPS (Befehl angenommen? Modul Fernzugriff / Wartungsmodus prüfen)");
}

// Wochenprogramm: POST /api/uhr/woche
// { tag: 1..7, paare: [ {aktivEin, einStd, einMin, aktivAus, ausStd, ausMin} x7 ], ziel: "tag" | "alle" | "auswahl", kopieren: [7 x bool] }
app.post("/api/uhr/woche", (req, res) => antwort(res, async () => {
  const { tag, paare, ziel, kopieren } = req.body;
  if (!Array.isArray(paare) || paare.length !== 7) throw new Error("Abgelehnt: 7 Paare erwartet");
  const befehl = { tag: "Woche_Speichern", alle: "Woche_Auf_Alle_Tage", auswahl: "Woche_Auf_Auswahl" }[ziel];
  if (!befehl) throw new Error("Abgelehnt: Ziel ungültig");
  return uhrBefehl(ganz => {
    const liste = [{ name: "DB_Fern.Uhr.Tag", dataType: DataType.Int16, wert: ganz(tag, 1, 7) }];
    paare.forEach((p, i) => {
      const b = `DB_Fern.Uhr.Woche[${i + 1}].`;
      liste.push(
        { name: b + "Aktiv_Ein", dataType: DataType.Boolean, wert: !!p.aktivEin },
        { name: b + "Aktiv_Aus", dataType: DataType.Boolean, wert: !!p.aktivAus },
        { name: b + "Ein_Std", dataType: DataType.Int16, wert: ganz(p.einStd, 0, 23) },
        { name: b + "Ein_Min", dataType: DataType.Int16, wert: ganz(p.einMin, 0, 59) },
        { name: b + "Aus_Std", dataType: DataType.Int16, wert: ganz(p.ausStd, 0, 23) },
        { name: b + "Aus_Min", dataType: DataType.Int16, wert: ganz(p.ausMin, 0, 59) });
    });
    if (ziel === "auswahl") {
      if (!Array.isArray(kopieren) || kopieren.length !== 7) throw new Error("Abgelehnt: Zieltage fehlen");
      liste.push({ name: "DB_Fern.Uhr.Kopieren_Auf", dataType: DataType.Boolean, wert: kopieren.map(Boolean), array: true });
    }
    return liste;
  }, befehl);
}));

// Datums-Schaltzeit hinzufuegen: POST /api/uhr/datum  { jahr, monat, tag, std, min, einschalten }
app.post("/api/uhr/datum", (req, res) => antwort(res, async () => {
  const d = req.body;
  return uhrBefehl(ganz => [
    { name: "DB_Fern.Uhr.Neu.Jahr", dataType: DataType.Int16, wert: ganz(d.jahr, 2024, 2099) },
    { name: "DB_Fern.Uhr.Neu.Monat", dataType: DataType.Int16, wert: ganz(d.monat, 1, 12) },
    { name: "DB_Fern.Uhr.Neu.Tag", dataType: DataType.Int16, wert: ganz(d.tag, 1, 31) },
    { name: "DB_Fern.Uhr.Neu.Std", dataType: DataType.Int16, wert: ganz(d.std, 0, 23) },
    { name: "DB_Fern.Uhr.Neu.Min", dataType: DataType.Int16, wert: ganz(d.min, 0, 59) },
    { name: "DB_Fern.Uhr.Neu.Einschalten", dataType: DataType.Boolean, wert: !!d.einschalten }
  ], "Datum_Hinzufuegen");
}));

// Datums-Schaltzeit loeschen: POST /api/uhr/datum_loeschen  { index: 1..20 }
app.post("/api/uhr/datum_loeschen", (req, res) => antwort(res, async () =>
  uhrBefehl(ganz => [{ name: "DB_Fern.Uhr.Loesch_Index", dataType: DataType.Int16, wert: ganz(req.body.index, 1, 20) }], "Datum_Loeschen")));

// Einstellung schreiben: POST /api/einstellung  { "name": "DB_Astro.Versatz_Ein", "wert": 20 }
app.post("/api/einstellung", (req, res) => antwort(res, async () => {
  const { name } = req.body, def = EINSTELLUNGEN[name], wert = Number(req.body.wert);
  if (!def) throw new Error("Abgelehnt: Einstellung nicht freigegeben");
  if (!isFinite(wert) || wert < def.min || wert > def.max || (def.ganz && !Number.isInteger(wert)))
    throw new Error(`Abgelehnt: Wert muss zwischen ${def.min} und ${def.max} liegen`);
  const erlaubt = (await lesen(["DB_HMI.Status.Fern_Erlaubt"]))["DB_HMI.Status.Fern_Erlaubt"];
  if (erlaubt !== true) throw new Error("Abgelehnt: am Panel ist \"Fernbedienung erlaubt\" aus");
  await schreiben([{ name, dataType: def.typ, wert }]);
  console.log("Einstellung:", name, "=", wert);
  return {};
}));

// GPS-Position wie der Raspberry Pi schreiben: /api/gps?breite=53.55&laenge=9.99&fix=1
app.post("/api/gps", (req, res) => antwort(res, async () => {
  const breite = Number(req.query.breite), laenge = Number(req.query.laenge), fix = req.query.fix === "1";
  if (!isFinite(breite) || !isFinite(laenge)) throw new Error("Abgelehnt: Breite/Länge ungültig");
  await schreiben([
    { name: "DB_Fern.GPS.Breitengrad", dataType: DataType.Float, wert: breite },
    { name: "DB_Fern.GPS.Laengengrad", dataType: DataType.Float, wert: laenge },
    { name: "DB_Fern.GPS.Fix", dataType: DataType.Boolean, wert: fix }
  ]);
  console.log(`GPS gesendet: ${breite} / ${laenge} Fix=${fix}`);
  return {};
}));

// Diagnose: welche NodeId wurde fuer welche Variable gefunden?
// Aufruf: http://localhost:8080/api/knoten          (alle Variablen, die die Webseite liest)
//         http://localhost:8080/api/knoten?alle=1   (alle gefundenen Variablen)
app.get("/api/knoten", async (req, res) => {
  try {
    await verbinden();
    const zeile = n => ({ name: n, nodeId: knoten(n), gefunden: karte.has(n) });
    const benutzt = [...angefragt].sort().map(zeile);
    res.json({
      ...karteInfo,
      siemensNamespace: ns,
      nichtGefunden: benutzt.filter(z => !z.gefunden).map(z => z.name),
      webseite: benutzt,
      alle: req.query.alle ? [...karte.keys()].sort().map(zeile) : "mit ?alle=1 anzeigen"
    });
  } catch (e) {
    res.json({ fehler: e.message });
  }
});

// Diagnose: Knoten des Servers durchklicken
// Aufruf: http://localhost:8080/api/browse            (Start: Objects)
//         http://localhost:8080/api/browse?node=<NodeId>
app.get("/api/browse", async (req, res) => {
  try {
    const sess = await verbinden();
    const start = req.query.node || "ns=0;i=85";   // 85 = Objects
    let ergebnis = await sess.browse({
      nodeId: start, referenceTypeId: "HierarchicalReferences", includeSubtypes: true,
      browseDirection: 0, nodeClassMask: 0, resultMask: 63
    });
    let refs = ergebnis.references ? [...ergebnis.references] : [];
    while (ergebnis.continuationPoint && ergebnis.continuationPoint.length) {
      ergebnis = await sess.browseNext(ergebnis.continuationPoint, false);
      if (ergebnis.references) refs.push(...ergebnis.references);
    }
    res.json({
      knoten: start,
      status: ergebnis.statusCode.name,
      anzahl: refs.length,
      kinder: refs.map(r => ({
        name: r.browseName.toString(),
        nodeId: r.nodeId.toString(),
        weiter: "/api/browse?node=" + encodeURIComponent(r.nodeId.toString())
      }))
    });
  } catch (e) {
    await trennen();
    res.json({ fehler: e.message });
  }
});

// Diagnose: gefundene Variablen nach Namen filtern
// Aufruf: http://localhost:8080/api/suche?text=Schnellstart
app.get("/api/suche", async (req, res) => {
  const text = String(req.query.text || "DB_HMI").toLowerCase();
  try {
    await verbinden();
    const treffer = [...karte].filter(([k]) => k.toLowerCase().includes(text)).map(([k, v]) => ({ name: k, nodeId: v }));
    res.json({ gesucht: text, anzahl: treffer.length, treffer });
  } catch (e) {
    res.json({ fehler: e.message });
  }
});

// Karte neu aufbauen (z. B. nach Aenderung der Server-Schnittstelle in TIA)
app.post("/api/neu_verbinden", async (req, res) => {
  await trennen();
  karte = new Map();
  try { await verbinden(); res.json({ ok: true, ...karteInfo }); }
  catch (e) { res.json({ ok: false, fehler: e.message }); }
});

// Lebenszeichen der Gegenseite alle 10 s hochzaehlen -> in der SPS wird St_Fern_Verbunden = 1
setInterval(async () => {
  if (!session) return;
  try {
    lebenszeichen = (lebenszeichen + 1) % 32767;
    await schreiben([{ name: "DB_Fern.Lebenszeichen_Web", dataType: DataType.Int16, wert: lebenszeichen }]);
  } catch (e) {
    // Verbindung nur bei echten Verbindungsfehlern neu aufbauen, nicht bei "Variable unbekannt"
    console.log("Lebenszeichen:", e.message);
    if (!/^Schreiben/.test(e.message)) await trennen();
  }
}, 10000);

app.listen(KONFIG.webPort, KONFIG.webHost, () => {
  console.log(`Bedienprogramm laeuft: http://${KONFIG.webHost}:${KONFIG.webPort}`);
  console.log(`SPS-Endpunkt: ${KONFIG.endpoint}`);
});
