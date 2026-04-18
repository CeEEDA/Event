import { Check, LayoutDashboard } from "lucide-react";
import { Button } from "../../components/ui/button";

export function PaymentSuccessStep({ amount, onContinue }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-success-step">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-100 flex items-center justify-center">
        <Check className="w-8 h-8 text-emerald-600" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Zahlung erfolgreich!</h2>
      <p className="text-sm text-gray-500 mb-1">
        Vielen Dank – Ihre Kaution wurde erfolgreich bezahlt.
      </p>
      {typeof amount === "number" && amount > 0 && (
        <p className="text-sm font-medium text-gray-900 mb-4">
          Betrag: {amount.toFixed(2)} EUR
        </p>
      )}
      <p className="text-xs text-gray-400 mb-6">
        Sie erhalten in Kürze eine Bestätigung per E-Mail. Ihre Anmeldung ist jetzt aktiviert.
      </p>
      <Button
        onClick={onContinue}
        className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white w-full"
        data-testid="payment-success-continue-btn"
      >
        <LayoutDashboard className="w-4 h-4 mr-1" /> Zum Portal / Anmeldung
      </Button>
    </div>
  );
}
