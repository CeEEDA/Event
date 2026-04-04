import { X } from "lucide-react";

export function AgbModal({ show, onClose }) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="agb-modal">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Allgemeine Geschäftsbedingungen</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" data-testid="agb-close"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 overflow-y-auto max-h-[70vh] space-y-6 text-sm text-gray-700 leading-relaxed">
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Abrechnung</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Die angebotenen Preise sind Nettopreise und werden zuzüglich der jeweils geltenden gesetzlichen Mehrwertsteuer berechnet.</li>
              <li>Falls in unserem Angebot oder Auftrag eine Anzahlungsaufforderung enthalten ist, beachten Sie bitte Folgendes: Überweisen Sie den angegebenen Betrag der Brutto-Angebots- oder Auftragssumme auf unser Konto. Unsere Kontoverbindung finden Sie auf unserem Geschäftspapier im unteren Abschnitt. Um den Betrag zuordnen zu können, geben Sie bitte immer unsere Referenz Nummer an (Angebots- oder Rechnungsnummer). Eine eventuelle Rückerstattung der Anzahlung erfolgt in der Schlussrechnung zum Mietvertrag. Selbstverständlich lassen wir Ihnen nach Rücksprache im Vorfeld eine Rechnung zukommen. Bei Nichteinhaltung der Anzahlung erfolgt keine Lieferung (oder Bereitstellung für Selbstabholer) unseres Mietmaterials und keine Dienstleistungen. Ihr Auftrag (Bestellung) wird zu unseren weiter unten angegebenen Stornierungskosten berechnet und anschließend von uns geschlossen.</li>
              <li><strong>Stromverbrauch:</strong> Der aktuelle Zählerstand unseres geeichten Zählers wird bei Aufbau notiert. Beim Abbau wird der neue Stand ebenfalls notiert und 1:1 an das jeweilige EVU gemeldet. Diese schreiben die Rechnung an den Kunden.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Versorgung</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Sämtliche Anschlussarbeiten an Fremdgewerke sind vor Inbetriebnahme der Anlagen durch den Anlagenverantwortlichen des jeweiligen Fremdgewerks auf Richtigkeit zu prüfen. Unsere Installation wird eigenständig geprüft und freigegeben. Der Anschlusspunkt (z.B. Steckdose) ist der Übergabepunkt zum Fremdgewerk. Für den ordnungsgemäßen Anschluss der Anlagen ist somit das Inbetriebsetzen Unternehmen verantwortlich. Der Potenzialausgleich in den Fremdgewerken endet mit Montage eines Übergabepunktes. Der örtliche Potenzialausgleich wird durch das Gewerk realisiert.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Kalkulation</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Grundsätzlich gelten für unsere Kalkulation nur die in Verbindung stehenden Planunterlagen, Ausschreibungen, Details, und Leistungsverzeichnisse. Darüber hinaus zur Verfügung gestellte Pläne der Fremdgewerke sind nur informativ und finden in unserer Kalkulation keine Berücksichtigung. Bei unserer Kalkulation sind wir davon ausgegangen, dass wir eine koordinierte Ausführungsplanung erhalten, die den anerkannten Regeln und Richtlinien entspricht. Dies ist die Grundlage zur Erstellung unserer Werks- und Montageplanung.</li>
              <li>Wir setzen voraus, dass alle Montagetätigkeiten zügig ohne Unterbrechung und während unserer normalen Arbeitszeit Mo-Do 7:30-16:30 und Fr. 7:30 - 15:15 Uhr, ausgeführt werden können. Mehraufwand durch Montagezeiten außerhalb dieser Zeiten werden gesondert berechnet. Wartezeiten, die nicht von uns verschuldet werden, sowie Mehraufwand durch Schwierigkeiten oder nicht kalkulierten Arbeiten, werden zusätzlich nach tatsächlichem Aufwand berechnet.</li>
              <li>Etwaige Anforderungen durch das Amt für Immissionsschutz wurden nicht berücksichtigt.</li>
              <li>Unsere Kalkulation basiert auf den zurzeit gültigen Vorschriften- und Gesetzesstand. Sollten sich diese während der Projektphase ändern, so weisen wir darauf hin, dass wir dem Auftraggeber ein Angebot unterbreiten, welches wir nach entsprechender Beauftragung umsetzen werden.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Kraftstoff / Aggregate</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Fuel-Management wird durch Eventenergie Deutschland GmbH & Co. KG durchgeführt, wenn nicht ausdrücklich anders vereinbart. Zum Zeitpunkt der Betankung legen wir, zur Abrechnung an den Veranstalter, den tagesaktuellen Heizölpreis zuzüglich einer Handling-Pauschale von 35% zugrunde.</li>
              <li><strong>Kraftstoffregelung Deutschland:</strong> Hinweis für Betreiber (Mieter) von Kraftstoffanlagen gemäß WHG (Wasserhaushaltsgesetz). Nach §5 Wasserhaushaltsgesetz (WHG) und §2 Abs. 9 der Anlagenverordnung (AwSV) darf keine nachteilige Veränderung der Gewässereigenschaften durch die Anlage (auch Miet-Anlagen) entstehen. Anlagen mit einem Tank größer 1.001 Liter, welche länger als ein halbes Jahr betrieben werden, sind fachbetriebspflichtig und müssen von einem Sachverständigen abgenommen werden. Außerdem gehören diese Anlagen 6 Wochen vor dem Betrieb, der unteren Wasserbehörde angezeigt. Die Verantwortung für die Einhaltung dieser Vorgaben übernimmt der Mieter. Er verpflichtet sich evtl. Verstöße an den Vermieter mitzuteilen.</li>
              <li><strong>Betriebsarten / Leistungsabgabe:</strong> Standardausführung zum Mietmaterial. 400V / 50 Hz für die Netzform TN-C-S. Änderungen sind auf Anfrage und gegen Aufpreis möglich. Unter Berücksichtigung der im Angebot angegebenen Leistung (entspricht 100%) sind unsere Aggregate für folgende Betriebsarten/Leistungsabgaben geeignet:
                <ul className="list-disc pl-5 mt-1 space-y-0.5">
                  <li>Dauerbetrieb bis max. 80 % der angegebenen Leistung</li>
                  <li>Kurzzeitbetrieb bis 100 % der angegebenen Leistung (Max. 3-5 Betriebsstunden)</li>
                  <li>Stoßlasten max. 50 % der angegebenen Leistung</li>
                  <li>Schieflasten max. 20 % der angegebenen Leistung</li>
                </ul>
                <p className="mt-1">Alle Angaben nur während des Betriebs möglich, nicht aus dem Stand-by-Betrieb während der Anlaufphase.</p>
              </li>
              <li>Bitte beachten Sie bei Ihrer Planung die gewünschte Versorgungssicherheit der Mietanlage. Wenn in Ihrer Planung Aggregate zum Einsatz kommen beachten Sie bitte, dass sich in allen Aggregaten drehende, mechanische und elektronische Teile befinden. Es gibt somit keine 100 % Garantie, dass es nie zu einem Störfall (Ausfall) kommen kann.</li>
              <li><strong>Folgende Planungsmöglichkeiten bieten wir an:</strong>
                <ul className="list-disc pl-5 mt-1 space-y-1">
                  <li><strong>Ein Single Aggregat:</strong> Im Störfall kann eine Versorgungsunterbrechung einen längeren Zeitraum andauern.</li>
                  <li><strong>Zwei oder mehr Aggregate (Redundanz mit kurzzeitiger Unterbrechung):</strong> Im Störfall erfolgt eine automatische Umschaltung von einem zum anderen Aggregat. Die Versorgungsunterbrechung beträgt ca. 15-20 Sekunden.</li>
                  <li><strong>Zwei oder mehrere Aggregate gleichzeitig betrieben:</strong> Im Störfall wird eine unterbrechungsfreie Versorgungssicherheit, durch das oder die anderen Aggregate gewährleistet.</li>
                </ul>
              </li>
              <li>Stromerzeuger, Tanks und Lichtmasten werden vollgetankt ausgeliefert - wenn nicht anders vereinbart. (Zusatztanks nur Festland, Inseln auf Anfrage).</li>
              <li>Unsere Aggregate und Zusatztanks können mit HEL (Heizöl extra leicht) DIN 51 603-01 betankt werden. Das HEL muss ausreichend mit Kälteadditiv (Sommer wie Winter) additiviert sein (bis -20°C). Damit die Kältesicherheit gewährleistet ist, muss das Kälteadditiv vor dem Frost bei über 0°C zum HEL gegeben werden. Das Verwenden von nicht additiviertem Heizöl kann bei niedrigen Temperaturen zum Stillstand der Maschine führen. Dadurch entstehende Kosten werden dem Auftraggeber gesondert nach Aufwand berechnet.</li>
              <li>Bei Nutzung eines externen Tanks, kann der interne Tank nur bedingt genutzt werden. (Umschaltung am 3 Wege-Kraftstoffventil nur bei Motorstillstand zulässig). Zusätzlich empfehlen wir Ihnen unser Winterset mit zu bestellen.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Transport</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Auf- und Abbau wird durch einen Techniker der Eventenergie Deutschland GmbH & Co. KG durchgeführt.</li>
              <li>Bei Anlieferungen sind 2 Stunden Abladezeit Inklusive. Jede weitere angefangene Wartestunde berechnen wir mit 65€ pro Stunde. Zum Aufladen bei Abholung ist 1 Stunde inklusive, jede weitere angefangene Stunde berechnen wir ebenfalls mit 65€ pro Stunde.</li>
              <li>Für alle Bestellungen und Lieferungen unter 10 Tage gilt: Die Auslieferung zum Mietmaterial erfolgt nach Absprache und Prüfung der Verfügbarkeit, jedoch frühestens 8-10 Tage nach Erhalt Ihrer Bestellung. Expresslieferungen und Notfälle müssen gesondert schriftlich vereinbart werden und gehen mit einer Erhöhung von 20% der angebotenen Mietartikel einher.</li>
              <li><strong>GPS-Tracking:</strong> Der Vermieter weist darauf hin, dass die Mietgeräte teilweise mit einem GPS-Ortungssystem ausgerüstet sind. Die an den Vermieter bei Aktivierung übermittelten Daten, dienen der Erfassung von technischen Betriebszuständen des Mietgeräts.</li>
              <li>Aus gegebenem Anlass zum stark variierenden Kraftstoffpreis, behalten wir uns eine Anpassung zum angebotenen Transportpreis ab Bestelleingang vor.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Pflichten des Mieters</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Der Mietgegenstand darf nur zu den vereinbarten Arbeiten und an dem vereinbarten Ort genutzt werden. Der Mieter ist ohne Zustimmung des Vermieters nicht berechtigt, den Mietgegenstand einem Dritten zu überlassen oder den Mietgegenstand weiter zu vermieten.</li>
              <li>Zeigen sich Störungen, muss der Mieter dies dem Vermieter unverzüglich schriftlich anzeigen. Der Mieter ist nicht berechtigt, ohne Zustimmung des Vermieters Reparaturen an dem Mietgegenstand durchzuführen. <strong>Wir weisen ausdrücklich darauf hin, dass wir keine Haftung, Ausfallkosten oder an uns gerichtete Regressansprüche übernehmen, die durch einen Störfall verursacht wurden.</strong></li>
              <li>Der Mieter ist verpflichtet, den Mietgegenstand nur durch eingewiesenes und fachkundiges Personal bedienen zu lassen.</li>
              <li>Die Mietobjekte sind in gleichem Zustand wie geliefert bereitzustellen. Für Diebstahl, Schäden und Verunreinigungen jeglicher Art, haftet der Mieter. Gitterboxen sind entsprechend dem Auslieferungszustand gepackt zu übergeben. Bei Missachtung behalten wir uns vor, erforderliche Arbeiten und/oder Reinigungskosten in Rechnung zu stellen.</li>
              <li>Der Mieter ist verpflichtet, zur Abdeckung der Risiken gegen Verlust oder Beschädigung des Mietgegenstandes eine Versicherung in Höhe des Wiederbeschaffungswertes des Mietgegenstandes abzuschließen und diese auf Verlangen des Vermieters nachzuweisen.</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Mietvertrag</h3>
            <ol className="list-decimal pl-5 space-y-2">
              <li>Ein Vertrag (Mietvertrag) ist abgeschlossen, wenn der Mieter den Auftrag (Angebot) schriftlich bestätigt oder wenn ein Vertrag von den Parteien wechselseitig unterzeichnet wird.</li>
              <li>Das Mietverhältnis beginnt mit dem Tag der Anlieferung (Berechnung voller Miettag). Ist bei der Auftragserteilung durch den Kunden kein Mietende angegeben (nur werktags Mo.-Do. 07:30-16:30 Uhr und Fr. 07:30 - 15:15 Uhr möglich, samstags, sonn- und feiertags nur nach vorheriger Absprache und Mehrkostenaufwand) gilt: Freimeldungen (für den gleichen Werktag der Abmeldung) müssen bis spätestens 11:00 Uhr schriftlich unserem Büro gemeldet werden. Ihre Freimeldung senden Sie bitte an: <a href="mailto:info@eventenergie-deutschland.de" className="text-blue-600 hover:underline">info@eventenergie-deutschland.de</a></li>
              <li>Unser Mietmaterial unterliegt vor der Auslieferung einer hausinternen Werksprüfung. Weitere Prüfungen zum Mietmaterial während der Mietperiode sind nicht im Mietpreis enthalten. Diese werden vom Mieter nach eigener Gefährdungsbeurteilung durchgeführt. Die Kosten trägt der Mieter. Der Mieter hat den Mietgegenstand bei Übergabe zu prüfen.</li>
              <li>Mängel hat der Mieter dem Vermieter unverzüglich, spätestens jedoch einen Tag nach Übergabe schriftlich anzuzeigen und zu rügen. Nach Ablauf der Rügefrist gilt der Mietgegenstand als vertragsgemäß mängelfrei übergeben.</li>
              <li>Das Mietmaterial unterliegt während der Mietzeit der Obhutspflicht des Mieters. Der Mieter erklärt sich damit einverstanden, dass bei einem Verlust der Mietsache der aktuelle Wiederbeschaffungswert unabhängig vom Zeitwert der Mietsache berechnet wird.</li>
              <li>Eine Rückvergütung der Mietsache gegenüber bereits geleisteten Zahlungen oder offenen Forderungen erfolgt nicht.</li>
              <li>Im Störfall einer Mietsache stehen wir Ihnen innerhalb unserer o.a. Bürozeiten und selbstverständlich mit unserem 24 Stunden Service außerhalb der Bürozeiten jederzeit unter der Nummer <strong>0171/7775543</strong> zur Verfügung. Wir sind bemüht, schnellstmöglich den Störfall zu beheben.</li>
              <li>Eine Mietminderung erfolgt nur, wenn der Mieter den Störfall unverzüglich anzeigt, sich der Mietgegenstand innerhalb von Deutschland befindet und der Mangel durch uns nicht innerhalb von 24 Stunden behoben werden kann (ab Störfall-Meldeeingang beim Vermieter und bei nachweislichem Nichtverschulden des Mieters).</li>
            </ol>
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base mb-2">Stornierungskosten</h3>
            <p className="mb-2">Sofern der Mieter vor Auslieferung bzw. Beginn des Mietzeitraums vom Vertrag zurücktritt oder den Vertrag storniert, ist der Vermieter berechtigt, folgende pauschalierten Sätze zu berechnen:</p>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-1">
              <div className="flex justify-between text-sm"><span>56 und länger Tage vor Auslieferung</span><span className="font-semibold">25 %</span></div>
              <div className="flex justify-between text-sm"><span>28 Tage vor Auslieferung</span><span className="font-semibold">50 %</span></div>
              <div className="flex justify-between text-sm"><span>14 Tage vor Auslieferung</span><span className="font-semibold">75 %</span></div>
              <div className="flex justify-between text-sm"><span>7 Tage vor Auslieferung</span><span className="font-semibold">90 %</span></div>
              <div className="flex justify-between text-sm border-t border-gray-300 pt-1 mt-1"><span>Stornierung einer Expresslieferung</span><span className="font-bold text-red-600">100 %</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
