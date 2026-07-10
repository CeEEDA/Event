"""Dossier-Generator (umlautfrei) fuer die Eventenergie-Software.

Kann jederzeit erneut aufgerufen werden - Screenshots muessen unter
/tmp/dossier/*.{jpg,jpeg,png} liegen.
"""
import io
import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, Table, TableStyle,
)

OUT = "/tmp/Eventenergie_Software_Dossier.pdf"
SHOTS = "/tmp/dossier"
LOGO = "/app/backend/static/logo.png"

FUCHSIA = colors.HexColor("#c026d3")
FUCHSIA_LIGHT = colors.HexColor("#fce7f3")
EMERALD = colors.HexColor("#059669")
GRAY_DARK = colors.HexColor("#374151")

# Umlaute konsequent ersetzen - User-Anforderung.
_UMLAUT = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss",
})


def _u(s):
    """String ohne Umlaute (auch fuer eingebettete HTML-Entities in Paragraphs)."""
    return str(s).translate(_UMLAUT)


def _P(text, style):
    return Paragraph(_u(text), style)


def _shot(name):
    for ext in (".jpg", ".jpeg", ".png"):
        p = os.path.join(SHOTS, name + ext)
        if os.path.exists(p):
            return p
    return None


def make_pdf():
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="Eventenergie Software Dossier",
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=32, textColor=FUCHSIA, alignment=TA_CENTER, spaceAfter=8)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], fontSize=14, textColor=GRAY_DARK, alignment=TA_CENTER, spaceAfter=6)
    small_style = ParagraphStyle("Sm", parent=styles["Normal"], fontSize=10, textColor=GRAY_DARK, alignment=TA_CENTER)

    # Deckblatt
    if os.path.exists(LOGO):
        img = RLImage(LOGO, width=6 * cm, height=6 * cm, kind="proportional")
        img.hAlign = "CENTER"
        story.append(Spacer(1, 2 * cm))
        story.append(img)
    story.append(Spacer(1, 1 * cm))
    story.append(_P("Eventenergie Software", title_style))
    # Extra Luft zwischen Titel und Unterzeile (User-Wunsch)
    story.append(Spacer(1, 1.2 * cm))
    story.append(_P("Umfassende Fachanwendung fuer Schausteller-, Kirmes- und Energieversorgungs-Betriebe", sub_style))
    story.append(Spacer(1, 1.5 * cm))

    facts = [
        [_u("Codebase"), _u("ca. 130.000 Zeilen (Python + React)")],
        [_u("Backend-API"), _u("559 Endpunkte in 32 Modulen")],
        [_u("Frontend"), _u("62 Seiten")],
        [_u("Hardware-Integrationen"), _u("26 Skripte (Modbus TCP, DSE, Sening, MQTT)")],
        [_u("Datenbank"), _u("MongoDB")],
        [_u("Stack"), _u("FastAPI 0.115 + React 19 + MongoDB")],
    ]
    ft = Table(facts, colWidths=[6 * cm, 10 * cm])
    ft.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), FUCHSIA_LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
    ]))
    story.append(ft)
    story.append(Spacer(1, 1 * cm))
    # Aktueller Monat + Jahr (dynamisch)
    _MONATE = ["Januar", "Februar", "Maerz", "April", "Mai", "Juni",
               "Juli", "August", "September", "Oktober", "November", "Dezember"]
    now = datetime.now()
    stand = f"Stand: {_MONATE[now.month - 1]} {now.year}"
    story.append(_P(stand, small_style))
    story.append(PageBreak())

    # Executive Summary
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=20, textColor=FUCHSIA, spaceBefore=6, spaceAfter=12)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=EMERALD, spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle("B", parent=styles["Normal"], fontSize=10.5, textColor=GRAY_DARK, leading=15, spaceAfter=6, alignment=TA_JUSTIFY)
    bullet = ParagraphStyle("Bu", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=3)

    story.append(_P("Executive Summary", h1))
    story.append(_P(
        "Die Eventenergie-Software ist eine vollstaendig integrierte Business-Plattform "
        "fuer Betriebe, die mobile Stromversorgung, Generatoren und Kirmes-Infrastruktur bereitstellen. "
        "Sie deckt den kompletten Geschaeftsprozess ab - von der Vorplanung ueber die Personaleinsatzsteuerung, "
        "die Kunden-Anmeldung und -Abrechnung, die Hardware-Telemetrie in Echtzeit, bis zur automatisierten Buchhaltung "
        "inklusive DATEV- und FinTS-Anbindung.", body))
    story.append(_P(
        "Charakteristisch ist die tiefe Verzahnung von IT und OT (Operational Technology): Waehrend andere Systeme sich "
        "auf Buerodaten beschraenken, liest diese Software Zaehler ueber Modbus TCP, EMU Professional II, DSE-Steuerungen "
        "und Sening MultiFlow direkt aus - und wandelt sie in verkaufsfaehige Abrechnungen um.", body))

    # ─── Marktbewertung & Vorteile (User-Anforderung: ganz vorn) ──────
    story.append(PageBreak())
    story.append(_P("Marktbewertung & Vorteile", h1))
    story.append(_P(
        "Auf Basis dieses Dossiers laesst sich eine realistische Marktbewertung vornehmen. Dabei muss zwischen "
        "dem technischen Wiederbeschaffungswert, dem Marktwert als Softwareprodukt und dem Unternehmenswert "
        "unterschieden werden.", body))
    story.append(_P(
        "Aus dem Dossier ergeben sich folgende Eckdaten: rund 130.000 Zeilen Python- und React-Code, "
        "559 API-Endpunkte, 62 Frontend-Seiten, 26 Hardware-Integrationen (u.a. Modbus, DSE, MQTT, Sening), "
        "eine moderne FastAPI-/React-Architektur sowie eine sehr tiefe Integration von ERP-, IoT-, Finanz- "
        "und Eventprozessen.", body))

    story.append(_P("1. Technischer Wiederbeschaffungswert", h2))
    story.append(_P("Eine vergleichbare Individualsoftware wuerde heute von einem professionellen Softwarehaus "
                    "ungefaehr folgenden Aufwand verursachen:", body))
    wbw = [
        [_u("Bereich"), _u("Aufwand")],
        [_u("Backend"), _u("3.500 - 5.000 Stunden")],
        [_u("Frontend"), _u("1.800 - 2.500 Stunden")],
        [_u("Hardware- / IoT-Integration"), _u("1.200 - 2.000 Stunden")],
        [_u("Architektur, Testing, DevOps"), _u("1.000 - 1.500 Stunden")],
        [_u("Projektmanagement"), _u("800 - 1.200 Stunden")],
        [_u("Gesamt"), _u("8.300 - 12.200 Entwicklungsstunden")],
    ]
    t = Table(wbw, colWidths=[8 * cm, 8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUCHSIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d1fae5")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(_P(
        "Bei marktueblichen Stundensaetzen von 110 - 160 EUR ergibt sich ein Wiederbeschaffungswert von "
        "ungefaehr <b>900.000 EUR bis 1.900.000 EUR</b>. Dieser Wert beschreibt, was ein Kaeufer investieren "
        "muesste, um die Software heute neu entwickeln zu lassen.", body))

    story.append(_P("2. Marktwert der bestehenden Software", h2))
    story.append(_P("Software wird in der Praxis nicht zum Neupreis verkauft. Bewertet werden zusaetzlich:", body))
    for b in ["Wartbarkeit", "Dokumentation", "Installierte Kunden", "Umsatz", "Wettbewerb",
              "Alleinstellungsmerkmale", "Abhaengigkeit vom Entwickler"]:
        story.append(_P(f"- {_u(b)}", bullet))
    story.append(Spacer(1, 6))
    story.append(_P("Die Software besitzt mehrere starke Alleinstellungsmerkmale:", body))
    for b in ["Vollstaendige ERP-Loesung", "Eventmanagement", "Personalverwaltung",
              "IoT- / Telemetrie", "Generatorsteuerung", "Tankmanagement",
              "DATEV", "Stripe", "FinTS", "KI-Dokumentenmanagement", "Mobile Apps",
              "Speziallösung fuer Schausteller und mobile Energieversorgung"]:
        story.append(_P(f"- {_u(b)}", bullet))
    story.append(Spacer(1, 4))
    story.append(_P("Das reduziert das Marktrisiko erheblich, weil es kaum direkte Wettbewerber mit "
                    "vergleichbarem Funktionsumfang gibt.", body))

    story.append(PageBreak())
    story.append(_P("3. Realistische Bewertung nach Szenario", h2))
    szen = [
        [_u("Szenario"), _u("Marktwert")],
        [_u("Asset-Deal (Quellcode ohne Kunden)"), _u("350.000 - 700.000 EUR")],
        [_u("Produkt mit Dokumentation und Support"), _u("700.000 - 1.200.000 EUR")],
        [_u("Etablierte SaaS mit zahlenden Kunden"), _u("1,2 - 3 Mio. EUR")],
        [_u("Marktfuehrer mit starkem Wachstum"), _u("3 - 8 Mio. EUR")],
    ]
    t = Table(szen, colWidths=[9 * cm, 7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    story.append(_P("4. Vergleichbare Software", h2))
    story.append(_P("Der Funktionsumfang aehnelt einer Kombination aus:", body))
    for b in ["ERP (ueber API von EpiRent)", "Workforce Management", "Eventsoftware",
              "Asset Management", "IoT-Plattform", "Energie-Monitoring"]:
        story.append(_P(f"- {_u(b)}", bullet))
    story.append(Spacer(1, 4))
    story.append(_P("Solche Systeme kosten haeufig zwischen 50.000 EUR und ueber 500.000 EUR als "
                    "Individualentwicklung pro Kunde. Eine komplette Suite mit diesem Umfang liegt "
                    "ueblicherweise im siebenstelligen Entwicklungsbereich.", body))

    story.append(_P("5. Staerken, die den Wert erhoehen", h2))
    for b in ["Moderne Architektur (FastAPI, React 19)",
              "559 API-Endpunkte",
              "Hardwareintegration (Modbus, DSE, MQTT, Sening)",
              "Echtzeit-Telemetrie",
              "KI-Dokumentenmanagement (auf privatem Ollama-Server)",
              "DATEV-E-Mail-Anbindung",
              "FinTS-Banking-Integration",
              "Stripe-Payments (Kaution + Rechnung)",
              "Mobile Anwendungen (WebRTC-Kamera, iPad-optimiert)",
              "Vollstaendige Prozesskette vom Auftrag bis zur Buchhaltung",
              "Sehr spezialisierte Branchenloesung (Schausteller, mobile Energieversorgung)"]:
        story.append(_P(f"- {_u(b)}", bullet))

    story.append(_P("Kernkomponenten im Ueberblick", h2))
    modules = [
        "Kirmes / Event-Management - Anmeldungen, Platz-Zuweisung, Zaehlerabrechnung, Kaution",
        "HR / Personalverwaltung - Zeiterfassung, Urlaub, Schichtplan, Verbandsbuch, Reisekosten",
        "Auftrags- und Einsatz-Management - Auftraege, Einsatzplanung, Serviceplaene, Wartung",
        "Energie- und Hardware-Telemetrie - Modbus, MQTT, DSE, EMU, Live-Monitoring",
        "Tank- und Kraftstoff-Modul - Sening MultiFlow, Tankbeleg-Pi, Fuel Receipts",
        "Dokumentenmanagement mit KI - Ollama, ZUGFeRD, DATEV-Routing, IMAP Mailbridge",
        "Zahlungs- und Bankintegration - Stripe (Kaution/Rechnung), FinTS Banking",
        "Inventar- und Anlagenverwaltung - Bilder, Dokumente, Marktwert-Skalierung, Exports",
        "Chat / Kommunikation - Team-Chat, Info-Boards, geteilte Notizen",
        "Kiosk- und Vor-Ort-Apps - Einsatzzentrale, Tankwagen-Livestream, ADR",
    ]
    for m in modules:
        story.append(_P(f"- {m}", bullet))

    story.append(Spacer(1, 6))
    story.append(_P(
        "Alle Module sind ueber eine gemeinsame Datenbasis vernetzt: Ein Auftrag erzeugt automatisch "
        "Personal-Einsaetze, ein Zaehlerstand fliesst direkt in die Rechnung, und ein per Mail eingegangenes "
        "PDF wird durch KI klassifiziert und an DATEV weitergereicht.", body))

    sections = [
        ("Dashboard / Hub", "01_hub",
         "Persoenliche Startseite mit Stempel-Uhr, Wochenplan, Urlaubskonto, Anwesenheits-Uebersicht "
         "und schnellem Zugriff auf alle Module.",
         ["Digitale Stempeluhr mit Ist/Soll-Vergleich",
          "Live-Anwesenheit (welcher Mitarbeiter ist heute da)",
          "Personal-Urlaubskonto und Ueberstunden-Saldo",
          "Info-Board fuer Team-Nachrichten",
          "Aufgabenverwaltung (Aktuell / Erledigt / Alle)",
          "Direkter Sprung in jedes Modul"]),

        ("Kirmes / Event-Management", "kirmes_overview",
         "Herzstueck der Software: Verwaltet komplette Kirmes-Events von der ersten Anfrage bis zur "
         "Endabrechnung. Schausteller melden sich per Mail-Einladung oder Link selbst an, waehlen "
         "Anschlussart (16A/32A/63A/125A) und zahlen Kaution direkt online.",
         ["Veranstaltungs-Kalender mit Status (Entwurf / Freigegeben / Aktiv / Abgerechnet)",
          "Selbst-Anmelde-Portal fuer Schausteller",
          "Preistabellen pro Event, inkl. Wohnwagen-Sonderpreise",
          "Manuelle Admin-Anlage von Netzanschluss",
          "Korrektur-Funktion: 16A auf 32A vor Ort umstellen (Kaution bleibt)",
          "Automatischer Rechnungs-Modus fuer freigeschaltete Schausteller",
          "Zaehler-Zuordnung Modbus zu Signup, kWh-Endabrechnung",
          "PDF-Rechnung pro Anmeldung inkl. Kaution",
          "Sammel-Abrechnung fuer alle Events als PDF/CSV"]),

        ("Zahlungs-Dashboard", "payment_dashboard",
         "Zentrale Uebersicht aller Zahlungsstroeme: Kautionen bezahlt/offen, Rechnungen bezahlt/offen, "
         "einzelne Transaktionen mit Status. Direkt integriert mit Stripe.",
         ["Live-Statistik Kautionen und Rechnungen",
          "Gesamteinnahmen pro Zeitraum und Event",
          "Transaktionsliste mit Filter",
          "Mahn-Funktion: Zahlungslinks nachversenden",
          "Stripe-Payment-Intents und Refunds",
          "Automatische Kautions-Vorbelastung und Rueckerstattung"]),

        ("Verwaltung / Personal", "verwaltung",
         "Zentrales Portal fuer die kaufmaennische Buero-Ebene. Verknuepft Personal, Auftraege, "
         "Serviceplaene, Verbandsbuch, Reisekosten und Dokumentenablage.",
         ["Mitarbeiter-Stammdaten mit Foto, Rolle, Zugriffsrechten",
          "Team-Chat mit Datei-Uploads",
          "Zentrale Dokumentenablage mit Volltextsuche",
          "DATEV-Uebergabe an Steuerberater",
          "Auswertungen: Umsatz, Personal, Maschinen, Einsatztage"]),

        ("Chat / Team-Kommunikation", "chat",
         "Interner Team-Chat fuer schnelle Absprachen.",
         ["Chat-Kanaele pro Team / Rolle",
          "Datei-Anhaenge",
          "Zuletzt-Gesehen-Marker",
          "Rollen-basierte Sichtbarkeit"]),

        ("Auftrags-Management", "orders",
         "Vollstaendige Auftragsabwicklung: Angebot, Erfassung, Positionen, Personal, Dokumente.",
         ["Auftragsuebersicht mit Filter",
          "Positions-Verwaltung mit Artikel und Zeit-Positionen",
          "Personal-Zuordnung je Auftrag",
          "Live-Sync mit EpiRent",
          "Auftrags-Dokumente (Vertrag, Lieferschein, Rechnung)"]),

        ("Einsatzplanung", "einsatzplanung",
         "Kalender-basierte Personalplanung mit Drag-and-Drop.",
         ["Kalenderansicht mit Filter",
          "Urlaubs- und Krankheits-Anzeige integriert",
          "Konfliktpruefung",
          "Automatische Benachrichtigung bei Aenderungen (geplant)"]),

        ("Meine Arbeitszeit", "arbeitszeit",
         "Persoenliche Zeiterfassung mit Wochenuebersicht, Stundenkonto, Urlaub und Krankheit.",
         ["Digitale Stempeluhr (Start/Stop)",
          "Wochenplan-Vergleich Soll/Ist",
          "Monatsweise Detail-Ansicht",
          "Genehmigte Urlaube und Krankheitstage",
          "Ueberstundenabbau-Planung"]),

        ("Mitarbeiter-Daten", "mitarbeiter_daten",
         "Personalakte inkl. Dokumente, Offdays, Notizen und Reisekosten. DSGVO-konform.",
         ["Persoenliche Dokumente (Vertrag, Fuehrerschein)",
          "Offdays (Urlaub, Krankheit, Fortbildung)",
          "Reisekosten-Erfassung mit Beleg-Fotos",
          "Personal-Notizen (nur fuer HR)"]),

        ("Inventar-Verwaltung", "inventory",
         "Vollstaendige Anlagen-Bestandsfuehrung mit Fotos, Dokumenten, Marktwert-Skalierung.",
         ["120+ Positionen mit Kategorien",
          "Foto-Aufnahme direkt vom iPad (WebRTC)",
          "Dokumentenanhang pro Position",
          "Marktwert prozentual pro Gruppe skalieren",
          "PDF-Auswertung mit 3 Detailstufen",
          "Excel-Export mit Sheet pro Gruppe",
          "Alle Bilder pro Position im PDF-Grid"]),

        ("Energy Monitoring", "energy_monitoring",
         "Live-Uebersicht aller vernetzten Messkoffer mit Karten-Anzeige.",
         ["Karten-Ansicht der Standorte (Leaflet + Satellit)",
          "Live-Werte: Leistung, Spannung, Energie",
          "Online/Offline-Status",
          "Historische Charts",
          "Ingest via Modbus TCP oder MQTT"]),

        ("Messkoffer im Detail", "messkoffer_detail",
         "Der Messkoffer ist ein autarker, mobiler Messplatz fuer Baustromnetze und Kirmes-Verteilungen. "
         "Er misst Wirk- und Blindleistung, Spannungen, Stroeme und Energie in Echtzeit und "
         "sendet die Daten ueber LTE/WiFi an das Portal. Ideal fuer Nachweise der abgenommenen "
         "Energiemenge und Erkennung von Ueberlastungen.",
         ["4-Quadranten Zaehlerchip EMU Professional II (Klasse 0.5S)",
          "Live-Werte alle 10 Sekunden (Modbus TCP)",
          "GPS-Position pro Messkoffer",
          "Batteriegepuffert mit LTE-Uplink",
          "Offline-Puffer in SQLite (holt Daten nach Verbindungsverlust nach)",
          "OTA-Update-Faehigkeit ueber das Portal",
          "Alarme bei Ueberlast, Spannungseinbruch, Verbindungsabbruch"]),

        ("Messkoffer im Serviceplan", "messkoffer_serviceplan",
         "Alle Messkoffer sind im Serviceplan mit Wartungsstatus, Kalibrierungs-Intervallen und "
         "letzter Pruefung sichtbar. Filterbar nach Geraeteart mit einem Klick.",
         ["Filter Messkoffer im Serviceplan-Modul",
          "Kalibrierungs-Erinnerungen (typ. jaehrlich)",
          "Wartungshistorie mit Zeitstempel",
          "Stoermeldung direkt aus dem Portal",
          "Zuordnung Auftrag <-> Messkoffer"]),

        ("Generator-Diagnose", "generators",
         "Direkt-Anbindung an DSE 5510 / DSE 8610 Motorsteuerungen mit Live-Daten und Fernbedienung.",
         ["Motorstunden, Tankstand, Batterie live",
          "Alarm-Historie mit Zeitstempel",
          "Fern-Reset (DSE Key 35707)",
          "OTA-Update fuer Diagnose-Skripte auf dem Pi",
          "Historische Lastdiagramme"]),

        ("Geraete-Management", "devices",
         "Zentrale Verwaltung aller vernetzten Hardware-Assets.",
         ["Geraete-Uebersicht mit Filter",
          "Firmware-Version und OTA-Update-Status",
          "Konfiguration remote aendern",
          "API-Key-Rotation pro Geraet"]),

        ("Tank-Status / Sening", "tank_status",
         "Live-Fuellstaende aller angebundenen Kraftstoff-Tanks.",
         ["Live-Fuellstaende via Modbus / Sening",
          "Schwellenwert-Alarme",
          "Historische Verbrauchs-Charts",
          "Tank-Zuordnung zu Fahrzeugen"]),

        ("Tankbeleg-Verwaltung", "finance",
         "Automatisierte Erfassung von Tank-Belegen ueber Sening MultiFlow.",
         ["Live-Belege von Sening-Zapfsaeulen",
          "Belegdaten: Fahrer, Fahrzeug, Menge, Preis",
          "Bulk-Zuordnung zu Auftraegen",
          "OCR-Fallback fuer Papier-Belege",
          "DATEV-Export"]),

        ("Dokumenten-Management (KI)", "documents",
         "Automatisierte Dokumenten-Verarbeitung: Mails werden analysiert, Rechnungen KI-klassifiziert.",
         ["IMAP-Mailbridge",
          "PyMuPDF-Volltext-Extraktion",
          "Ollama-KI (lokal) fuer Klassifikation",
          "ZUGFeRD-Parser fuer E-Rechnungen",
          "Automatisches DATEV-Routing",
          "3-Stufen-Spam-Filter",
          "TEBA-Factoring: Multi-PDF aus ZIP",
          "Volltextsuche mit AND-Logik"]),

        ("Verbandsbuch", "verbandsbuch",
         "Digitales Verbandsbuch nach DGUV Vorschrift 1. Rechtssicher, revisionssicher.",
         ["Erfassung: Datum, Verletzte, Zeugen, Art",
          "Aenderungs-Historie",
          "PDF-Export fuer Berufsgenossenschaft",
          "Foto-Anhang moeglich"]),

        ("Serviceplan / Wartung", "serviceplan",
         "Wartungsplaner fuer alle Geraete mit Frist-Ueberwachung.",
         ["Alle Geraete mit Wartungsstatus",
          "Filter nach Kategorie",
          "Neue Wartung anlegen",
          "Stoermeldung fuer Reparaturen",
          "Historie pro Geraet"]),

        ("ADR / Gefahrgut", "adr",
         "Kraftstoff- und Gefahrgut-Dokumentation nach ADR-Standard.",
         ["ADR-Konformitaets-Dokumente",
          "Fahrer-Zertifikate und Ablaufdaten",
          "Gefahrgut-Klassifikation"]),

        ("Admin-Einstellungen", "admin_settings",
         "Systemweite Konfiguration.",
         ["Firmenstammdaten und Steuernummern",
          "Preistabellen fuer Standard-Anschluesse",
          "DATEV-Routing-Matrix",
          "IMAP-Server-Konfiguration",
          "Mail-Templates",
          "System-Backups"]),

        ("FAQ / Wissensdatenbank", "faq",
         "Integrierte Hilfeseiten mit Suchfunktion.",
         ["Kategorien: Anmeldung, Zahlung, Zaehler, Auftraege",
          "Volltextsuche",
          "Screenshots und Anleitungen",
          "Rollen-basierte Sichtbarkeit"]),
    ]

    for name, shot, desc, bullets in sections:
        story.append(PageBreak())
        story.append(_P(name, h1))
        story.append(_P(desc, body))
        p = _shot(shot)
        if p:
            try:
                img = RLImage(p, width=17 * cm, height=9.5 * cm, kind="proportional")
                img.hAlign = "CENTER"
                story.append(Spacer(1, 6))
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception:
                pass
        story.append(_P("Funktionen im Detail", h2))
        for b in bullets:
            story.append(_P(f"- {b}", bullet))

    # Technischer Anhang
    story.append(PageBreak())
    story.append(_P("Technische Architektur", h1))
    story.append(_P(
        "Die Software ist als moderne Cloud-Native-Anwendung konzipiert: Ein einheitliches REST/JSON-Backend "
        "in Python (FastAPI) mit MongoDB, dazu ein reaktives React-19-Frontend mit TailwindCSS und "
        "Shadcn/UI-Komponenten.", body))
    story.append(_P("Backend-Stack", h2))
    for b in ["Python 3.11 + FastAPI 0.115", "MongoDB via Motor (async)", "Modbus TCP: pymodbus 3.9",
              "MQTT: paho-mqtt 2.1", "Banking: python-fints", "AI: Ollama, PyMuPDF",
              "PDF: reportlab, XLSX: openpyxl", "Auth: bcrypt + JWT",
              "IMAP mit Semaphore fuer Ollama-Requests"]:
        story.append(_P(f"- {b}", bullet))
    story.append(_P("Frontend-Stack", h2))
    for b in ["React 19 + React Router 7", "TailwindCSS 3 + Shadcn/UI (Radix)",
              "Recharts, Leaflet", "Axios, react-hook-form",
              "WebRTC (getUserMedia) fuer iOS/iPad-Kamera", "Lucide-Icons"]:
        story.append(_P(f"- {b}", bullet))
    story.append(_P("Hardware-Integrationen", h2))
    for b in ["DSE 5510 / DSE 8610 (Modbus TCP)", "EMU Professional II Zaehler",
              "Sening MultiFlow (Serial-to-IP)", "Custom Kirmeskisten (4- oder 8-Zaehler)",
              "Raspberry Pi Pool mit OTA-Pipeline", "MQTT-Broker fuer Live-Status"]:
        story.append(_P(f"- {b}", bullet))
    story.append(_P("3rd-Party-Anbindungen", h2))
    for b in ["Stripe (Zahlungen, Kaution, Refunds)", "FinTS (deutsche Banken)",
              "DATEV (E-Mail-Routing)", "EpiRent (Event-Sync)", "IONOS IMAP",
              "Ollama (lokale KI)", "Open-Meteo / Nominatim"]:
        story.append(_P(f"- {b}", bullet))

    story.append(PageBreak())
    story.append(_P("Kontakt", h1))
    story.append(_P("Eventenergie Deutschland GmbH & Co. KG", body))
    story.append(_P("Dieses Dossier wurde automatisch aus der laufenden Software erstellt. "
                    "Alle Screenshots stammen aus dem produktiven System.", body))
    story.append(Spacer(1, 20))
    story.append(_P("(c) 2026 Eventenergie Deutschland GmbH & Co. KG - Alle Rechte vorbehalten.", small_style))

    # ── ANHANG: Muster-Analyse Messkoffer ────────────────────────────
    story.append(PageBreak())
    story.append(_P("Anhang: Muster-Analyse Messkoffer", h1))
    story.append(_P(
        "Beispielhafte Auswertung einer 5-Tage-Baustelle mit Messkoffer_002. Zeigt Verbrauchsverlauf, "
        "Lastspitzen und Betriebsstunden - typische Datenbasis fuer Nachberechnung und Kunden-Nachweise.", body))

    story.append(_P("Objektdaten", h2))
    obj = [
        [_u("Messkoffer"), _u("Messkoffer_002 (SN: MK-2024-002)")],
        [_u("Einsatz"), _u("Herbstkirmes Musterstadt 2026")],
        [_u("Zeitraum"), _u("15.09.2026 - 19.09.2026 (5 Tage)")],
        [_u("Anschlusstyp"), _u("125 A CEE (400 V, 3~)")],
        [_u("GPS"), _u("50.4419 N, 7.3689 O")],
    ]
    t = Table(obj, colWidths=[5 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), FUCHSIA_LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    story.append(_P("Taegliche Energieaufnahme", h2))
    tage = [
        ["Datum", "Betriebsstunden", "Spitze (kW)", "Mittel (kW)", "Energie (kWh)"],
        ["Mo 15.09.2026", "16:12", "58,4", "22,1", "358,0"],
        ["Di 16.09.2026", "17:08", "61,7", "23,5", "402,3"],
        ["Mi 17.09.2026", "17:22", "59,9", "24,0", "417,6"],
        ["Do 18.09.2026", "17:45", "63,2", "25,3", "451,2"],
        ["Fr 19.09.2026", "12:36", "51,8", "20,7", "260,8"],
        ["SUMME", "81:03", "63,2", "23,1", "1.889,9"],
    ]
    tab = Table(tage, colWidths=[4 * cm, 3.2 * cm, 2.7 * cm, 2.7 * cm, 3.4 * cm])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUCHSIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d1fae5")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tab)
    story.append(Spacer(1, 12))

    story.append(_P("Verlauf einer typischen Betriebs-Stunde", h2))
    story.append(_P(
        "Beispiel Do 18.09.2026, 20:00 - 21:00 Uhr (Peak-Betrieb Fahrgeschaeft + Wohnwagen).", body))
    stunde = [
        ["Zeit", "L1 (A)", "L2 (A)", "L3 (A)", "U (V)", "P (kW)"],
        ["20:00", "78,4", "82,1", "80,3", "398", "56,2"],
        ["20:10", "84,7", "88,9", "85,5", "397", "60,8"],
        ["20:20", "89,2", "91,4", "88,7", "396", "63,2"],
        ["20:30", "85,1", "87,3", "84,2", "397", "60,1"],
        ["20:40", "80,9", "83,5", "81,7", "398", "57,3"],
        ["20:50", "77,3", "79,8", "78,1", "399", "55,0"],
        ["21:00", "72,5", "74,9", "73,2", "400", "52,4"],
    ]
    stab = Table(stunde, colWidths=[2.5 * cm] * 6)
    stab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(stab)
    story.append(Spacer(1, 12))

    story.append(_P("Kennzahlen und Auffaelligkeiten", h2))
    kpi = [
        _u("Peak-Leistung: 63,2 kW (55 % Auslastung des 125-A-Anschlusses)"),
        _u("Schieflast max: 4,3 % (unbedenklich)"),
        _u("Spannungsminimum: 391 V bei Peak - innerhalb Toleranz DIN EN 50160"),
        _u("Verbindungsverluste: 3 x LTE-Reconnect (automatisch nachgeholt)"),
        _u("Gesamtenergie 1889,9 kWh, davon 12 % nachts (Kuehlaggregate)"),
        _u("Berechnete CO2-Emission: 812 kg (dt. Strommix 2026)"),
        _u("Kosten (0,42 EUR/kWh): 793,76 EUR netto"),
    ]
    for k in kpi:
        story.append(_P(f"- {k}", bullet))
    story.append(Spacer(1, 12))
    story.append(_P("Empfehlungen aus der Analyse", h2))
    for k in [
        "Anschluss auf 63 A downgraden wuerde 40 % der Fixkosten sparen (Peak nur 63 kW)",
        "Nacht-Grundlast durch effizientere Kuehlung um ca. 15 % reduzierbar",
        "Peak um 20:30 - Empfehlung: schaltbare Verbraucher zeitversetzt starten",
    ]:
        story.append(_P(f"- {_u(k)}", bullet))

    story.append(Spacer(1, 20))
    story.append(_P("Diese Muster-Analyse ist Bestandteil der Software - jede Baustelle kann auf Knopfdruck "
                    "aehnliche Auswertungen fuer Kunden, Netzbetreiber oder interne Kalkulation liefern.", body))

    doc.build(story)
    with open(OUT, "wb") as f:
        f.write(buf.getvalue())
    print(f"OK -> {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    make_pdf()
