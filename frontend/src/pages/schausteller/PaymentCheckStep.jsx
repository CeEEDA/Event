import { Check } from "lucide-react";

export function PaymentCheckStep({ paymentChecking, timedOut, errorMsg, onContinue, onRetry }) {
  if (timedOut || errorMsg) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-check-timeout">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center">
          <svg className="w-8 h-8 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Zahlungsstatus konnte nicht geprüft werden</h2>
        <p className="text-sm text-gray-500 mb-2">
          {errorMsg ? errorMsg : "Die Prüfung hat zu lange gedauert. Ihre Zahlung wurde eventuell erfolgreich durchgeführt."}
        </p>
        <p className="text-xs text-gray-400 mb-6">
          Bitte prüfen Sie Ihren Status im Portal oder wenden Sie sich an uns, falls der Betrag abgebucht wurde.
        </p>
        <div className="flex flex-col gap-3">
          {onRetry && (
            <button onClick={onRetry} className="px-4 py-2 text-sm rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50" data-testid="payment-check-retry-btn">
              Erneut prüfen
            </button>
          )}
          <button onClick={onContinue} className="px-4 py-2 text-sm rounded-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="payment-check-continue-btn">
            Zum Portal / Anmeldung
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-check-step">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-blue-100 flex items-center justify-center animate-pulse">
        <Check className="w-8 h-8 text-blue-600" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Zahlung wird geprüft...</h2>
      <p className="text-sm text-gray-500 mb-4">Bitte warten Sie, während wir Ihre Zahlung bestätigen.</p>
      {paymentChecking && (
        <div className="flex items-center justify-center gap-2 text-sm text-blue-600">
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25"/><path d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" fill="currentColor"/></svg>
          Prüfe Zahlungsstatus...
        </div>
      )}
    </div>
  );
}
