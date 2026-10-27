import { useState, useCallback } from "react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "../ui/alert-dialog";

export const Karte = ({ titel, children, action, className = "", testId }) => (
  <div className={`bg-white border border-gray-200 rounded-xl p-4 ${className}`} data-testid={testId}>
    {titel && (
      <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
        <h2 className="text-sm font-semibold text-gray-900">{titel}</h2>
        {action}
      </div>
    )}
    {children}
  </div>
);

export const Zeile = ({ label, children }) => (
  <tr className="border-b border-gray-100 last:border-0">
    <td className="py-1.5 pr-3 text-xs text-gray-500 align-top w-[45%]">{label}</td>
    <td className="py-1.5 text-sm text-gray-900">{children ?? "–"}</td>
  </tr>
);
export const Tab = ({ children }) => <table className="w-full"><tbody>{children}</tbody></table>;

export const Dot = ({ on, farbe = "gruen" }) => {
  const cls = on === true ? { gruen: "bg-emerald-500", gelb: "bg-amber-400", rot: "bg-red-500" }[farbe] : "bg-gray-300";
  return <span className={`inline-block w-3 h-3 rounded-full align-[-1px] mr-1 ${cls}`} />;
};

export const Balken = ({ p, warn, err }) => (
  <div className="h-3 bg-gray-200 rounded-full overflow-hidden mt-1">
    <div className={`h-full ${err ? "bg-red-500" : warn ? "bg-amber-400" : "bg-sky-700"}`} style={{ width: `${Math.max(0, Math.min(100, p || 0))}%` }} />
  </div>
);

export const Hinweis = ({ art, children, testId }) => (
  <div data-testid={testId} className={`px-3 py-2 rounded-lg text-sm border ${art === "err" ? "bg-red-50 border-red-200 text-red-800" : "bg-amber-50 border-amber-200 text-amber-900"}`}>{children}</div>
);

// Buttons: variant "haupt" | "an" | "laeuft" | default
export const Btn = ({ variant, disabled, onClick, children, testId, className = "", title }) => {
  const base = "text-sm px-3.5 py-2 rounded-lg border transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]";
  const v = {
    haupt: "bg-sky-800 text-white border-sky-800 hover:bg-sky-900",
    an: "bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700",
    laeuft: "bg-amber-300 border-amber-500 text-gray-900",
    gefahr: "bg-white text-red-700 border-red-300 hover:bg-red-50",
  }[variant] || "bg-white text-gray-800 border-gray-300 hover:bg-gray-50";
  return <button type="button" title={title} disabled={disabled} onClick={onClick} className={`${base} ${v} ${className}`} data-testid={testId}>{children}</button>;
};

export const Fehlt = ({ roh, name }) => {
  const x = roh(name);
  return x && x.fehler ? <span className="text-xs text-gray-400" title={x.fehler}> (nicht lesbar)</span> : null;
};

// Bestaetigungsdialog (ersetzt confirm(), bleibt aber Pflicht fuer kritische Befehle)
export function useConfirm() {
  const [state, setState] = useState(null);
  const confirm = useCallback((frage) => new Promise(resolve => setState({ frage, resolve })), []);
  const dialog = (
    <AlertDialog open={!!state} onOpenChange={(o) => { if (!o && state) { state.resolve(false); setState(null); } }}>
      <AlertDialogContent data-testid="mbox-confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Bitte bestätigen</AlertDialogTitle>
          <AlertDialogDescription>{state?.frage}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="mbox-confirm-cancel">Abbrechen</AlertDialogCancel>
          <AlertDialogAction data-testid="mbox-confirm-ok" onClick={() => { state.resolve(true); setState(null); }}>Ja, ausführen</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
  return { confirm, dialog };
}
