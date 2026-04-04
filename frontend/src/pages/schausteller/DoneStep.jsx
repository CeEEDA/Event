import { Button } from "../../components/ui/button";
import { Check, Plus, LayoutDashboard } from "lucide-react";

export function DoneStep({ selectedEvent, completedBookings, signupForm, onAnotherSignup, onToDashboard }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="done-step">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-100 flex items-center justify-center"><Check className="w-8 h-8 text-emerald-600" /></div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Anmeldung erfolgreich!</h2>
      <p className="text-sm text-gray-500 mb-4">Sie wurden für <strong>{selectedEvent?.name}</strong> angemeldet. Sie erhalten eine Bestätigung per E-Mail.</p>
      <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-3 mb-6">
        {completedBookings.map((b, i) => (
          <div key={i} className={i > 0 ? "border-t border-gray-200 pt-3" : ""}>
            <div className="flex justify-between items-start">
              <div>
                <p className="font-semibold text-gray-900">{b.fahrgeschaeft || "Anschluss"} – {b.connection_type}</p>
                <p className="text-gray-500 text-xs">Platz: {b.platznummer}</p>
              </div>
              <span className="font-medium text-gray-800">{b.price.toFixed(2)} EUR</span>
            </div>
            {b.deposit > 0 && (
              <div className="flex justify-between mt-1">
                <span className="text-amber-600 text-xs">Kaution {b.connection_type}</span>
                <span className="text-amber-700 text-xs font-medium">{b.deposit.toFixed(2)} EUR</span>
              </div>
            )}
          </div>
        ))}
        <div className="border-t border-gray-300 pt-2 flex justify-between">
          <span className="font-bold text-gray-900">Gesamt (netto)</span>
          <span className="font-bold text-fuchsia-700">{completedBookings.reduce((s, b) => s + b.price + b.deposit, 0).toFixed(2)} EUR</span>
        </div>
        <div className="text-xs text-gray-500">
          Zahlungsmittel: <strong>{signupForm.payment_method === "rechnung" ? "Auf Rechnung" : signupForm.payment_method === "paypal" ? "PayPal" : "Kreditkarte"}</strong>
        </div>
      </div>
      <div className="flex flex-col gap-3">
        <Button onClick={onAnotherSignup} variant="outline" className="border-fuchsia-200 text-fuchsia-600 hover:bg-fuchsia-50" data-testid="another-signup-btn">
          <Plus className="w-4 h-4 mr-1" /> Weiteren Stand anmelden
        </Button>
        <Button onClick={onToDashboard} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="to-dashboard-btn">
          <LayoutDashboard className="w-4 h-4 mr-1" /> Zu meinem Bereich
        </Button>
      </div>
    </div>
  );
}
