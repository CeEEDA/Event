import { X } from "lucide-react";

export function DatenschutzModal({ show, onClose }) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="datenschutz-modal">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Datenschutzerklärung</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" data-testid="datenschutz-close"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 overflow-y-auto max-h-[70vh] space-y-6 text-sm text-gray-700 leading-relaxed">
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">1. Datenschutz auf einen Blick</h3>
            <h4 className="font-semibold text-gray-900 mt-3 mb-1">Allgemeine Hinweise</h4>
            <p>Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren personenbezogenen Daten passiert, wenn Sie unsere Website besuchen. Personenbezogene Daten sind alle Daten, mit denen Sie persönlich identifiziert werden können. Ausführliche Informationen zum Thema Datenschutz entnehmen Sie unserer unter diesem Text aufgeführten Datenschutzerklärung.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Datenerfassung auf unserer Website</h4>
            <p className="font-medium text-gray-800 mt-2 mb-1">Wer ist verantwortlich für die Datenerfassung auf dieser Website?</p>
            <p>Die Datenverarbeitung auf dieser Website erfolgt durch den Websitebetreiber. Dessen Kontaktdaten können Sie dem Impressum dieser Website entnehmen.</p>
            <p className="font-medium text-gray-800 mt-3 mb-1">Wie erfassen wir Ihre Daten?</p>
            <p>Ihre Daten werden zum einen dadurch erhoben, dass Sie uns diese mitteilen. Hierbei kann es sich z.B. um Daten handeln, die Sie in ein Kontaktformular eingeben.</p>
            <p className="mt-2">Andere Daten werden automatisch beim Besuch der Website durch unsere IT-Systeme erfasst. Das sind vor allem technische Daten (z.B. Internetbrowser, Betriebssystem oder Uhrzeit des Seitenaufrufs). Die Erfassung dieser Daten erfolgt automatisch, sobald Sie unsere Website betreten.</p>
            <p className="font-medium text-gray-800 mt-3 mb-1">Wofür nutzen wir Ihre Daten?</p>
            <p>Ein Teil der Daten wird erhoben, um eine fehlerfreie Bereitstellung der Website zu gewährleisten. Andere Daten können zur Analyse Ihres Nutzerverhaltens verwendet werden.</p>
            <p className="font-medium text-gray-800 mt-3 mb-1">Welche Rechte haben Sie bezüglich Ihrer Daten?</p>
            <p>Sie haben jederzeit das Recht unentgeltlich Auskunft über Herkunft, Empfänger und Zweck Ihrer gespeicherten personenbezogenen Daten zu erhalten. Sie haben außerdem ein Recht, die Berichtigung, Sperrung oder Löschung dieser Daten zu verlangen. Hierzu sowie zu weiteren Fragen zum Thema Datenschutz können Sie sich jederzeit unter der im Impressum angegebenen Adresse an uns wenden. Des Weiteren steht Ihnen ein Beschwerderecht bei der zuständigen Aufsichtsbehörde zu.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Analyse-Tools und Tools von Drittanbietern</h4>
            <p>Beim Besuch unserer Website kann Ihr Surf-Verhalten statistisch ausgewertet werden. Das geschieht vor allem mit Cookies und mit sogenannten Analyseprogrammen. Die Analyse Ihres Surf-Verhaltens erfolgt in der Regel anonym; das Surf-Verhalten kann nicht zu Ihnen zurückverfolgt werden. Sie können dieser Analyse widersprechen oder sie durch die Nichtbenutzung bestimmter Tools verhindern. Detaillierte Informationen dazu finden Sie in der folgenden Datenschutzerklärung.</p>
            <p className="mt-2">Sie können dieser Analyse widersprechen. Über die Widerspruchsmöglichkeiten werden wir Sie in dieser Datenschutzerklärung informieren.</p>
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">2. Allgemeine Hinweise und Pflichtinformationen</h3>
            <h4 className="font-semibold text-gray-900 mb-1">Datenschutz</h4>
            <p>Die Betreiber dieser Seiten nehmen den Schutz Ihrer persönlichen Daten sehr ernst. Wir behandeln Ihre personenbezogenen Daten vertraulich und entsprechend der gesetzlichen Datenschutzvorschriften sowie dieser Datenschutzerklärung.</p>
            <p className="mt-2">Wenn Sie diese Website benutzen, werden verschiedene personenbezogene Daten erhoben. Personenbezogene Daten sind Daten, mit denen Sie persönlich identifiziert werden können. Die vorliegende Datenschutzerklärung erläutert, welche Daten wir erheben und wofür wir sie nutzen. Sie erläutert auch, wie und zu welchem Zweck das geschieht.</p>
            <p className="mt-2">Wir weisen darauf hin, dass die Datenübertragung im Internet (z.B. bei der Kommunikation per E-Mail) Sicherheitslücken aufweisen kann. Ein lückenloser Schutz der Daten vor dem Zugriff durch Dritte ist nicht möglich.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Hinweis zur verantwortlichen Stelle</h4>
            <p>Die verantwortliche Stelle für die Datenverarbeitung auf dieser Website ist:</p>
            <p className="mt-2">Christian Ecker<br/>Niederbieberer Str. 126<br/>56567 Neuwied</p>
            <p className="mt-2">Telefon: 02631-94 37 37 0</p>
            <p className="mt-2">Verantwortliche Stelle ist die natürliche oder juristische Person, die allein oder gemeinsam mit anderen über die Zwecke und Mittel der Verarbeitung von personenbezogenen Daten (z.B. Namen, E-Mail-Adressen o. Ä.) entscheidet.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Widerruf Ihrer Einwilligung zur Datenverarbeitung</h4>
            <p>Viele Datenverarbeitungsvorgänge sind nur mit Ihrer ausdrücklichen Einwilligung möglich. Sie können eine bereits erteilte Einwilligung jederzeit widerrufen. Dazu reicht eine formlose Mitteilung per E-Mail an uns. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitung bleibt vom Widerruf unberührt.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Beschwerderecht bei der zuständigen Aufsichtsbehörde</h4>
            <p>Im Falle datenschutzrechtlicher Verstöße steht dem Betroffenen ein Beschwerderecht bei der zuständigen Aufsichtsbehörde zu. Zuständige Aufsichtsbehörde in datenschutzrechtlichen Fragen ist der Landesdatenschutzbeauftragte des Bundeslandes, in dem unser Unternehmen seinen Sitz hat. Eine Liste der Datenschutzbeauftragten sowie deren Kontaktdaten können folgendem Link entnommen werden: <a href="https://www.bfdi.bund.de/DE/Infothek/Anschriften_Links/anschriften_links-node.html" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.bfdi.bund.de</a>.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Recht auf Datenübertragbarkeit</h4>
            <p>Sie haben das Recht, Daten, die wir auf Grundlage Ihrer Einwilligung oder in Erfüllung eines Vertrags automatisiert verarbeiten, an sich oder an einen Dritten in einem gängigen, maschinenlesbaren Format aushändigen zu lassen. Sofern Sie die direkte Übertragung der Daten an einen anderen Verantwortlichen verlangen, erfolgt dies nur, soweit es technisch machbar ist.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">SSL- bzw. TLS-Verschlüsselung</h4>
            <p>Diese Seite nutzt aus Sicherheitsgründen und zum Schutz der Übertragung vertraulicher Inhalte, wie zum Beispiel Bestellungen oder Anfragen, die Sie an uns als Seitenbetreiber senden, eine SSL-bzw. TLS-Verschlüsselung. Eine verschlüsselte Verbindung erkennen Sie daran, dass die Adresszeile des Browsers von &quot;http://&quot; auf &quot;https://&quot; wechselt und an dem Schloss-Symbol in Ihrer Browserzeile.</p>
            <p className="mt-2">Wenn die SSL- bzw. TLS-Verschlüsselung aktiviert ist, können die Daten, die Sie an uns übermitteln, nicht von Dritten mitgelesen werden.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Verschlüsselter Zahlungsverkehr auf dieser Website</h4>
            <p>Besteht nach dem Abschluss eines kostenpflichtigen Vertrags eine Verpflichtung, uns Ihre Zahlungsdaten (z.B. Kontonummer bei Einzugsermächtigung) zu übermitteln, werden diese Daten zur Zahlungsabwicklung benötigt.</p>
            <p className="mt-2">Der Zahlungsverkehr über die gängigen Zahlungsmittel (Visa/MasterCard, Lastschriftverfahren) erfolgt ausschließlich über eine verschlüsselte SSL- bzw. TLS-Verbindung. Eine verschlüsselte Verbindung erkennen Sie daran, dass die Adresszeile des Browsers von &quot;http://&quot; auf &quot;https://&quot; wechselt und an dem Schloss-Symbol in Ihrer Browserzeile.</p>
            <p className="mt-2">Bei verschlüsselter Kommunikation können Ihre Zahlungsdaten, die Sie an uns übermitteln, nicht von Dritten mitgelesen werden.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Auskunft, Sperrung, Löschung</h4>
            <p>Sie haben im Rahmen der geltenden gesetzlichen Bestimmungen jederzeit das Recht auf unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren Herkunft und Empfänger und den Zweck der Datenverarbeitung und ggf. ein Recht auf Berichtigung, Sperrung oder Löschung dieser Daten. Hierzu sowie zu weiteren Fragen zum Thema personenbezogene Daten können Sie sich jederzeit unter der im Impressum angegebenen Adresse an uns wenden.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Widerspruch gegen Werbe-Mails</h4>
            <p>Der Nutzung von im Rahmen der Impressumspflicht veröffentlichten Kontaktdaten zur Übersendung von nicht ausdrücklich angeforderter Werbung und Informationsmaterialien wird hiermit widersprochen. Die Betreiber der Seiten behalten sich ausdrücklich rechtliche Schritte im Falle der unverlangten Zusendung von Werbeinformationen, etwa durch Spam-E-Mails, vor.</p>
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">3. Datenerfassung auf unserer Website</h3>
            <h4 className="font-semibold text-gray-900 mb-1">Cookies</h4>
            <p>Die Internetseiten verwenden teilweise so genannte Cookies. Cookies richten auf Ihrem Rechner keinen Schaden an und enthalten keine Viren. Cookies dienen dazu, unser Angebot nutzerfreundlicher, effektiver und sicherer zu machen. Cookies sind kleine Textdateien, die auf Ihrem Rechner abgelegt werden und die Ihr Browser speichert.</p>
            <p className="mt-2">Die meisten der von uns verwendeten Cookies sind so genannte &quot;Session-Cookies&quot;. Sie werden nach Ende Ihres Besuchs automatisch gelöscht. Andere Cookies bleiben auf Ihrem Endgerät gespeichert bis Sie diese löschen. Diese Cookies ermöglichen es uns, Ihren Browser beim nächsten Besuch wiederzuerkennen.</p>
            <p className="mt-2">Sie können Ihren Browser so einstellen, dass Sie über das Setzen von Cookies informiert werden und Cookies nur im Einzelfall erlauben, die Annahme von Cookies für bestimmte Fälle oder generell ausschließen sowie das automatische Löschen der Cookies beim Schließen des Browser aktivieren. Bei der Deaktivierung von Cookies kann die Funktionalität dieser Website eingeschränkt sein.</p>
            <p className="mt-2">Cookies, die zur Durchführung des elektronischen Kommunikationsvorgangs oder zur Bereitstellung bestimmter, von Ihnen erwünschter Funktionen (z.B. Warenkorbfunktion) erforderlich sind, werden auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO gespeichert. Der Websitebetreiber hat ein berechtigtes Interesse an der Speicherung von Cookies zur technisch fehlerfreien und optimierten Bereitstellung seiner Dienste. Soweit andere Cookies (z.B. Cookies zur Analyse Ihres Surfverhaltens) gespeichert werden, werden diese in dieser Datenschutzerklärung gesondert behandelt.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Server-Log-Dateien</h4>
            <p>Der Provider der Seiten erhebt und speichert automatisch Informationen in so genannten Server-Log-Dateien, die Ihr Browser automatisch an uns übermittelt. Dies sind:</p>
            <ul className="list-disc list-inside mt-2 space-y-1 ml-2">
              <li>Browsertyp und Browserversion</li>
              <li>verwendetes Betriebssystem</li>
              <li>Referrer URL</li>
              <li>Hostname des zugreifenden Rechners</li>
              <li>Uhrzeit der Serveranfrage</li>
              <li>IP-Adresse</li>
            </ul>
            <p className="mt-2">Eine Zusammenführung dieser Daten mit anderen Datenquellen wird nicht vorgenommen.</p>
            <p className="mt-2">Grundlage für die Datenverarbeitung ist Art. 6 Abs. 1 lit. f DSGVO, der die Verarbeitung von Daten zur Erfüllung eines Vertrags oder vorvertraglicher Maßnahmen gestattet.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Kontaktformular</h4>
            <p>Wenn Sie uns per Kontaktformular Anfragen zukommen lassen, werden Ihre Angaben aus dem Anfrageformular inklusive der von Ihnen dort angegebenen Kontaktdaten zwecks Bearbeitung der Anfrage und für den Fall von Anschlussfragen bei uns gespeichert. Diese Daten geben wir nicht ohne Ihre Einwilligung weiter.</p>
            <p className="mt-2">Die Verarbeitung der in das Kontaktformular eingegebenen Daten erfolgt somit ausschließlich auf Grundlage Ihrer Einwilligung (Art. 6 Abs. 1 lit. a DSGVO). Sie können diese Einwilligung jederzeit widerrufen. Dazu reicht eine formlose Mitteilung per E-Mail an uns. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitungsvorgänge bleibt vom Widerruf unberührt.</p>
            <p className="mt-2">Die von Ihnen im Kontaktformular eingegebenen Daten verbleiben bei uns, bis Sie uns zur Löschung auffordern, Ihre Einwilligung zur Speicherung widerrufen oder der Zweck für die Datenspeicherung entfällt (z.B. nach abgeschlossener Bearbeitung Ihrer Anfrage). Zwingende gesetzliche Bestimmungen – insbesondere Aufbewahrungsfristen – bleiben unberührt.</p>
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">4. Analyse Tools und Werbung</h3>
            <h4 className="font-semibold text-gray-900 mb-1">Google Analytics</h4>
            <p>Diese Website nutzt Funktionen des Webanalysedienstes Google Analytics. Anbieter ist die Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA.</p>
            <p className="mt-2">Google Analytics verwendet so genannte &quot;Cookies&quot;. Das sind Textdateien, die auf Ihrem Computer gespeichert werden und die eine Analyse der Benutzung der Website durch Sie ermöglichen. Die durch den Cookie erzeugten Informationen über Ihre Benutzung dieser Website werden in der Regel an einen Server von Google in den USA übertragen und dort gespeichert.</p>
            <p className="mt-2">Die Speicherung von Google-Analytics-Cookies erfolgt auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO. Der Websitebetreiber hat ein berechtigtes Interesse an der Analyse des Nutzerverhaltens, um sowohl sein Webangebot als auch seine Werbung zu optimieren.</p>
          </div>
          <div>
            <p className="font-medium text-gray-800 mb-1">IP Anonymisierung</p>
            <p>Wir haben auf dieser Website die Funktion IP-Anonymisierung aktiviert. Dadurch wird Ihre IP-Adresse von Google innerhalb von Mitgliedstaaten der Europäischen Union oder in anderen Vertragsstaaten des Abkommens über den Europäischen Wirtschaftsraum vor der Übermittlung in die USA gekürzt. Nur in Ausnahmefällen wird die volle IP-Adresse an einen Server von Google in den USA übertragen und dort gekürzt. Im Auftrag des Betreibers dieser Website wird Google diese Informationen benutzen, um Ihre Nutzung der Website auszuwerten, um Reports über die Websiteaktivitäten zusammenzustellen und um weitere mit der Websitenutzung und der Internetnutzung verbundene Dienstleistungen gegenüber dem Websitebetreiber zu erbringen. Die im Rahmen von Google Analytics von Ihrem Browser übermittelte IP-Adresse wird nicht mit anderen Daten von Google zusammengeführt.</p>
          </div>
          <div>
            <p className="font-medium text-gray-800 mb-1">Browser Plugin</p>
            <p>Sie können die Speicherung der Cookies durch eine entsprechende Einstellung Ihrer Browser-Software verhindern; wir weisen Sie jedoch darauf hin, dass Sie in diesem Fall gegebenenfalls nicht sämtliche Funktionen dieser Website vollumfänglich werden nutzen können. Sie können darüber hinaus die Erfassung der durch den Cookie erzeugten und auf Ihre Nutzung der Website bezogenen Daten (inkl. Ihrer IP-Adresse) an Google sowie die Verarbeitung dieser Daten durch Google verhindern, indem Sie das unter dem folgenden Link verfügbare Browser-Plugin herunterladen und installieren: <a href="https://tools.google.com/dlpage/gaoptout?hl=de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://tools.google.com/dlpage/gaoptout?hl=de</a>.</p>
          </div>
          <div>
            <p className="font-medium text-gray-800 mb-1">Widerspruch gegen Datenerfassung</p>
            <p>Sie können die Erfassung Ihrer Daten durch Google Analytics verhindern, indem Sie auf folgenden Link klicken. Es wird ein Opt-Out-Cookie gesetzt, der die Erfassung Ihrer Daten bei zukünftigen Besuchen dieser Website verhindert: Google Analytics deaktivieren.</p>
            <p className="mt-2">Mehr Informationen zum Umgang mit Nutzerdaten bei Google Analytics finden Sie in der Datenschutzerklärung von Google: <a href="https://support.google.com/analytics/answer/6004245?hl=de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://support.google.com/analytics/answer/6004245?hl=de</a>.</p>
          </div>
          <div>
            <p className="font-medium text-gray-800 mb-1">Auftragsdatenverarbeitung</p>
            <p>Wir haben mit Google einen Vertrag zur Auftragsdatenverarbeitung abgeschlossen und setzen die strengen Vorgaben der deutschen Datenschutzbehörden bei der Nutzung von Google Analytics vollständig um.</p>
          </div>
          <div>
            <p className="font-medium text-gray-800 mb-1">Demografische Merkmale bei Google Analytics</p>
            <p>Diese Website nutzt die Funktion &quot;demografische Merkmale&quot; von Google Analytics. Dadurch können Berichte erstellt werden, die Aussagen zu Alter, Geschlecht und Interessen der Seitenbesucher enthalten. Diese Daten stammen aus interessenbezogener Werbung von Google sowie aus Besucherdaten von Drittanbietern. Diese Daten können keiner bestimmten Person zugeordnet werden. Sie können diese Funktion jederzeit über die Anzeigeneinstellungen in Ihrem Google-Konto deaktivieren oder die Erfassung Ihrer Daten durch Google Analytics wie im Punkt &quot;Widerspruch gegen Datenerfassung&quot; dargestellt generell untersagen.</p>
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 mb-2">5. Plugins und Tools</h3>
            <h4 className="font-semibold text-gray-900 mb-1">YouTube</h4>
            <p>Unsere Website nutzt Plugins der von Google betriebenen Seite YouTube. Betreiber der Seiten ist die YouTube, LLC, 901 Cherry Ave., San Bruno, CA 94066, USA.</p>
            <p className="mt-2">Wenn Sie eine unserer mit einem YouTube-Plugin ausgestatteten Seiten besuchen, wird eine Verbindung zu den Servern von YouTube hergestellt. Dabei wird dem YouTube-Server mitgeteilt, welche unserer Seiten Sie besucht haben.</p>
            <p className="mt-2">Wenn Sie in Ihrem YouTube-Account eingeloggt sind, ermöglichen Sie YouTube, Ihr Surfverhalten direkt Ihrem persönlichen Profil zuzuordnen. Dies können Sie verhindern, indem Sie sich aus Ihrem YouTube-Account ausloggen.</p>
            <p className="mt-2">Die Nutzung von YouTube erfolgt im Interesse einer ansprechenden Darstellung unserer Online-Angebote. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
            <p className="mt-2">Weitere Informationen zum Umgang mit Nutzerdaten finden Sie in der Datenschutzerklärung von YouTube unter: <a href="https://www.google.de/intl/de/policies/privacy" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.google.de/intl/de/policies/privacy</a>.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Google Web Fonts</h4>
            <p>Diese Seite nutzt zur einheitlichen Darstellung von Schriftarten so genannte Web Fonts, die von Google bereitgestellt werden. Beim Aufruf einer Seite lädt Ihr Browser die benötigten Web Fonts in ihren Browsercache, um Texte und Schriftarten korrekt anzuzeigen.</p>
            <p className="mt-2">Zu diesem Zweck muss der von Ihnen verwendete Browser Verbindung zu den Servern von Google aufnehmen. Hierdurch erlangt Google Kenntnis darüber, dass über Ihre IP-Adresse unsere Website aufgerufen wurde. Die Nutzung von Google Web Fonts erfolgt im Interesse einer einheitlichen und ansprechenden Darstellung unserer Online-Angebote. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
            <p className="mt-2">Wenn Ihr Browser Web Fonts nicht unterstützt, wird eine Standardschrift von Ihrem Computer genutzt.</p>
            <p className="mt-2">Weitere Informationen zu Google Web Fonts finden Sie unter <a href="https://developers.google.com/fonts/faq" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">https://developers.google.com/fonts/faq</a> und in der Datenschutzerklärung von Google: <a href="https://www.google.com/policies/privacy/" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">https://www.google.com/policies/privacy/</a>.</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-1">Google Maps</h4>
            <p>Diese Seite nutzt über eine API den Kartendienst Google Maps. Anbieter ist die Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA.</p>
            <p className="mt-2">Zur Nutzung der Funktionen von Google Maps ist es notwendig, Ihre IP Adresse zu speichern. Diese Informationen werden in der Regel an einen Server von Google in den USA übertragen und dort gespeichert. Der Anbieter dieser Seite hat keinen Einfluss auf diese Datenübertragung.</p>
            <p className="mt-2">Die Nutzung von Google Maps erfolgt im Interesse einer ansprechenden Darstellung unserer Online-Angebote und an einer leichten Auffindbarkeit der von uns auf der Website angegebenen Orte. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
            <p className="mt-2">Mehr Informationen zum Umgang mit Nutzerdaten finden Sie in der Datenschutzerklärung von Google: <a href="https://www.google.de/intl/de/policies/privacy/" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.google.de/intl/de/policies/privacy/</a>.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
