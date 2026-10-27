import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lightbulb, ChevronRight, Radio } from "lucide-react";
import api from "../../lib/api";

// Liste der M-Box Lichtmasten fuer das Power-Monitoring-Dashboard
export function MBoxSection({ search = "" }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.get("/mbox/devices").then(r => alive && setData(r.data)).catch(() => alive && setData({ devices: [], hidden: true }));
    load();
    const t = setInterval(load, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!data || data.hidden || !data.devices?.length) return null;
  const q = search.toLowerCase();
  const list = data.devices.filter(d => !q || (d.user_field || "").toLowerCase().includes(q) || (d.serial_number || "").toLowerCase().includes(q));
  if (!list.length) return null;

  return (
    <section className="mb-6" data-testid="mbox-section">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        <h2 className="text-sm font-semibold text-gray-900">M-Box Lichtmasten</h2>
        <span className="text-xs text-gray-400">{list.length} Gerät{list.length !== 1 ? "e" : ""} · Fernbedienung</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {list.map(d => {
          const run = d.runtime?.running;
          return (
            <button key={d.id} type="button" onClick={() => navigate(`/mbox/${d.id}`)}
              className="bg-white border border-gray-200 rounded-lg p-4 text-left hover:border-fuchsia-400 hover:shadow-md transition-all group"
              data-testid={`mbox-card-${d.serial_number}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{d.user_field || d.serial_number}</p>
                  <p className="text-xs text-gray-400 font-mono truncate">{d.serial_number}</p>
                </div>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium shrink-0 ${run ? "bg-emerald-500 text-white" : d.status === "ausser_betrieb" ? "bg-gray-300 text-gray-700" : "bg-amber-500 text-white"}`}>
                  <Radio className="w-3 h-3" />{run ? "Dienst aktiv" : d.status === "ausser_betrieb" ? "Außer Betrieb" : "Dienst aus"}
                </span>
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                <span className="text-[11px] text-gray-400 font-mono truncate">{d.mbox_endpoint}</span>
                <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-600 transition-colors shrink-0" />
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
