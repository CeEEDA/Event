import { Button } from "../../components/ui/button";
import { Zap, ArrowRight } from "lucide-react";

export function PaymentStep({ selectedEvent, signupForm, depositAmounts, onPayDeposit, onSkip, saving }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-step">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center">
        <Zap className="w-8 h-8 text-amber-600" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Kaution bezahlen</h2>
      <p className="text-sm text-gray-500 mb-4">
        Ihre Anmeldung für <strong>{selectedEvent?.name}</strong> wurde vorgemerkt. Die Buchung wird erst nach Zahlungseingang bestätigt.
      </p>
      <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-1 mb-4">
        <p><span className="text-gray-500">Platz:</span> <strong>{signupForm.platznummer}</strong></p>
        <p><span className="text-gray-500">Fahrgeschäft:</span> <strong>{signupForm.fahrgeschaeft}</strong></p>
        <p><span className="text-gray-500">Anschluss:</span> <strong>{signupForm.connection_type}</strong></p>
      </div>
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
        <div className="flex justify-between items-center">
          <span className="text-sm text-amber-700 font-medium">Kaution</span>
          <span className="text-2xl font-bold text-amber-800">{(depositAmounts[signupForm.connection_type] || 0).toFixed(2)} EUR</span>
        </div>
        <p className="text-[10px] text-amber-600 mt-1">Wird nach der Veranstaltung erstattet</p>
      </div>
      <div className="text-xs text-gray-500 mb-3">
        Zahlung per <strong className="text-gray-700">{signupForm.payment_method === "paypal" ? "PayPal" : "Kreditkarte"}</strong> · Sichere Abwicklung über Stripe
      </div>
      <Button onClick={onPayDeposit} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mb-3" data-testid="pay-deposit-btn">
        {saving ? "Weiterleitung..." : `Jetzt per ${signupForm.payment_method === "paypal" ? "PayPal" : "Kreditkarte"} bezahlen`} <ArrowRight className="w-4 h-4 ml-1" />
      </Button>
      <button onClick={onSkip} className="text-xs text-gray-400 hover:text-gray-600 underline" data-testid="skip-payment-btn">
        Später bezahlen (Buchung bleibt unbestätigt)
      </button>
    </div>
  );
}
