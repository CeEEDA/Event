import { X } from "lucide-react";

export function ImpressumModal({ show, onClose }) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="impressum-modal">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Impressum</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" data-testid="impressum-close"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 overflow-y-auto max-h-[70vh] space-y-4 text-sm text-gray-700">
          <div>
            <p className="text-xs text-gray-500 mb-2">Diensteanbieter:</p>
            <p className="font-semibold text-gray-900">Eventenergie Deutschland GmbH & Co. KG</p>
            <p>Geschäftsführung: Christian Ecker</p>
          </div>
          <div>
            <p>Thyssenstraße 10</p>
            <p>56626 Andernach</p>
            <p className="mt-2">Tel.: 02632 30921 0</p>
            <p className="mt-1"><a href="mailto:info@eventenergie-deutschland.de" className="text-fuchsia-600 hover:underline">info@eventenergie-deutschland.de</a></p>
            <p><a href="https://www.eventenergie-deutschland.de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">www.eventenergie-deutschland.de</a></p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Verantwortlich für den Inhalt</p>
            <p>Christian Ecker, Thyssenstraße 10, 56626 Andernach</p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Umsatzsteuer-ID</p>
            <p>Umsatzsteuer-Identifikationsnummer gemäß §27 a Umsatzsteuergesetz: DE29/200/02826</p>
            <p>Steuer-ID: DE333489815</p>
            <p className="mt-1">Finanzamt Mayen</p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Handelsregister</p>
            <p>Handelsregister Nummer: HRA 22723</p>
            <p>Amtsgericht Koblenz</p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Persönlich haftende Gesellschafterin / Komplementärin</p>
            <p>ES Verwaltungs GmbH</p>
            <p>Sitz: Andernach</p>
            <p>Registergericht: Koblenz HR B 26935</p>
            <p>Geschäftsführer: Christian Ecker</p>
          </div>
          <div>
            <p>Herr Christian Ecker ist Elektrotechnikermeister (gesetzliche Berufsbezeichnung), verliehen in der Bundesrepublik Deutschland. Herr Christian Ecker ist Mitglied der Handwerkskammer Koblenz.</p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Berufsrechtliche Regelungen</p>
            <p>Handwerksordnung, einsehbar u.a. unter <a href="http://www.gesetze-im-internet.de/bundesrecht/hwo/gesamt.pdf" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">www.gesetze-im-internet.de</a></p>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-1">Copyright</p>
            <p>Alle auf unseren Seiten enthaltenen Fotos sind urheberrechtlich geschützt und dürfen nicht kopiert werden.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
