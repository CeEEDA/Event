import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "../../components/ui/input";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const PASSWORD_RULES = [
  { re: /.{8,}/, label: "Mindestens 8 Zeichen" },
  { re: /[0-9]/, label: "Mindestens eine Ziffer" },
  { re: /[A-Z]/, label: "Mindestens ein Großbuchstabe" },
  { re: /[a-z]/, label: "Mindestens ein Kleinbuchstabe" },
  { re: /[^A-Za-z0-9]/, label: "Mindestens ein Sonderzeichen" },
];

export function isPasswordValid(pw) {
  return PASSWORD_RULES.every(r => r.re.test(pw));
}

export const api = {
  post: (path, data) => fetch(`${BACKEND_URL}/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(async r => { const d = await r.json().catch(() => ({})); if (!r.ok) throw { response: { status: r.status, data: d } }; return { data: d }; }),
  get: (path) => fetch(`${BACKEND_URL}/api${path}`).then(async r => { const d = await r.json().catch(() => ({})); if (!r.ok) throw { response: { status: r.status, data: d } }; return { data: d }; }),
};

export const PAYMENT_METHODS = [
  { value: "kreditkarte", label: "Kreditkarte / PayPal" },
  { value: "rechnung", label: "Auf Rechnung" },
];

export const STATUS_LABELS = {
  pending_payment: { text: "Zahlung ausstehend", cls: "bg-orange-100 text-orange-700" },
  ausstehend: { text: "Ausstehend", cls: "bg-amber-100 text-amber-700" },
  bestaetigt: { text: "Bestätigt", cls: "bg-blue-100 text-blue-700" },
  abgerechnet: { text: "Abgerechnet", cls: "bg-emerald-100 text-emerald-700" },
  erstellt: { text: "Erstellt", cls: "bg-gray-100 text-gray-600" },
  versendet: { text: "Versendet", cls: "bg-blue-100 text-blue-700" },
  bezahlt: { text: "Bezahlt", cls: "bg-emerald-100 text-emerald-700" },
  offen: { text: "Offen", cls: "bg-amber-100 text-amber-700" },
  faellig: { text: "Fällig", cls: "bg-orange-100 text-orange-700" },
  ueberfaellig: { text: "Überfällig", cls: "bg-red-100 text-red-700" },
  reserviert: { text: "Reserviert", cls: "bg-purple-100 text-purple-700" },
};

export function PasswordInput({ value, onChange, placeholder, testId }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} value={value} onChange={onChange} placeholder={placeholder} className="mt-1 pr-10" data-testid={testId} />
      <button type="button" onMouseDown={e => { e.preventDefault(); setVisible(v => !v); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" tabIndex={-1}>
        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}
