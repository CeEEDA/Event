import { Check } from "lucide-react";

export function PaymentCheckStep({ paymentChecking }) {
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
