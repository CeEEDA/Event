/**
 * Freelancer-Auftragszuweisung im UserEditModal.
 * State liegt im Parent (AdminPage.js); diese Komponente rendert nur JSX
 * und ruft die Setter aus den Props.
 */
import { Briefcase, Search } from "lucide-react";
import { Input } from "../../ui/input";

export default function FreelancerAssignment({
  freelancerOrderPks,
  setFreelancerOrderPks,
  freelancerAssignedOrders,
  setFreelancerAssignedOrders,
  freelancerSearchQ,
  setFreelancerSearchQ,
  freelancerSearchResults,
  freelancerSearchLoading,
}) {
  return (
    <div className="border-t border-gray-200 pt-4 mt-2">
      <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
        <Briefcase className="w-4 h-4 text-amber-600" />
        Auftragszuweisung
      </h3>
      <p className="text-xs text-gray-500 mb-3">
        Der Freelancer sieht nur die hier ausgewählten Aufträge.
        Sie werden 5 Tage nach Job-Ende automatisch ausgeblendet.
        Tankbelege und Kundendaten bleiben in der Auftragsmaske verborgen.
      </p>

      <div className="bg-amber-50 rounded-lg px-3 py-2 mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-amber-900" data-testid="freelancer-assigned-count">
          {freelancerOrderPks.length === 1
            ? "1 Auftrag zugewiesen"
            : `${freelancerOrderPks.length} Aufträge zugewiesen`}
        </span>
        {freelancerOrderPks.length > 0 && (
          <button
            type="button"
            onClick={() => setFreelancerOrderPks([])}
            className="text-xs text-amber-700 hover:text-amber-900 underline"
            data-testid="freelancer-clear-all-btn"
          >
            Alle entfernen
          </button>
        )}
      </div>

      {/* Zugewiesene Aufträge (immer sichtbar) */}
      {freelancerAssignedOrders.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-700 mb-1.5 uppercase tracking-wide">Zugewiesen</p>
          <div className="border border-amber-200 rounded-lg overflow-hidden bg-amber-50/40">
            {freelancerAssignedOrders.map(o => {
              const checked = freelancerOrderPks.includes(o.primary_key);
              return (
                <label
                  key={`a-${o.primary_key}`}
                  className="flex items-start gap-3 px-3 py-2.5 border-b border-amber-100 last:border-b-0 cursor-pointer hover:bg-amber-50 transition-colors"
                  data-testid={`freelancer-assigned-row-${o.primary_key}`}
                >
                  <input
                    type="checkbox"
                    className="mt-1 w-4 h-4 accent-amber-600 flex-shrink-0"
                    checked={checked}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setFreelancerOrderPks(prev => prev.includes(o.primary_key) ? prev : [...prev, o.primary_key]);
                      } else {
                        setFreelancerOrderPks(prev => prev.filter(p => p !== o.primary_key));
                      }
                    }}
                    data-testid={`freelancer-order-toggle-${o.primary_key}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-gray-900">{o.order_no}</span>
                      {o.event_start && (
                        <span className="text-xs text-gray-500">
                          {o.event_start}{o.event_end && o.event_end !== o.event_start ? ` – ${o.event_end}` : ""}
                        </span>
                      )}
                    </div>
                    {o.event && <div className="text-sm text-gray-700 break-words">{o.event}</div>}
                    {o.address && <div className="text-xs text-gray-500 break-words">{o.address}</div>}
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Suche fuer weitere Aufträge */}
      <p className="text-xs font-medium text-gray-700 mb-1.5 uppercase tracking-wide">Aufträge hinzufügen</p>
      <div className="relative mb-2">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input
          placeholder="Suchen (Nr., Event, Adresse...)"
          value={freelancerSearchQ}
          onChange={e => setFreelancerSearchQ(e.target.value)}
          className="pl-9 border-gray-300"
          data-testid="freelancer-order-search"
        />
      </div>

      <div className="border border-gray-200 rounded-lg max-h-72 overflow-y-auto bg-white">
        {freelancerSearchLoading ? (
          <div className="p-4 text-center text-sm text-gray-400">Lade...</div>
        ) : (() => {
          const assignedSet = new Set(freelancerOrderPks);
          const filtered = freelancerSearchResults.filter(o => !assignedSet.has(o.primary_key));
          if (filtered.length === 0) {
            return <div className="p-4 text-center text-sm text-gray-400">Keine weiteren Aufträge gefunden</div>;
          }
          return filtered.map(o => (
            <label
              key={`s-${o.primary_key}`}
              className="flex items-start gap-3 px-3 py-2.5 border-b border-gray-100 last:border-b-0 cursor-pointer hover:bg-amber-50/50 transition-colors"
              data-testid={`freelancer-order-row-${o.primary_key}`}
            >
              <input
                type="checkbox"
                className="mt-1 w-4 h-4 accent-amber-600 flex-shrink-0"
                checked={false}
                onChange={() => {
                  setFreelancerOrderPks(prev => prev.includes(o.primary_key) ? prev : [...prev, o.primary_key]);
                  setFreelancerAssignedOrders(prev => prev.find(x => x.primary_key === o.primary_key) ? prev : [...prev, o]);
                }}
                data-testid={`freelancer-order-toggle-${o.primary_key}`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-gray-900">{o.order_no}</span>
                  {o.event_start && (
                    <span className="text-xs text-gray-500">
                      {o.event_start}{o.event_end && o.event_end !== o.event_start ? ` – ${o.event_end}` : ""}
                    </span>
                  )}
                </div>
                {o.event && <div className="text-sm text-gray-700 break-words">{o.event}</div>}
                {o.address && <div className="text-xs text-gray-500 break-words">{o.address}</div>}
              </div>
            </label>
          ));
        })()}
      </div>
    </div>
  );
}
