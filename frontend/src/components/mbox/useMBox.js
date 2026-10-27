import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../lib/api";
import { toast } from "sonner";
import { BASIS, EXTRA } from "./mboxVars";

// Polling alle 2 s (Takt, Schutz gegen parallele Abfragen, Zeitlimit wie im Original)
export function useMBox(deviceId, seite) {
  const [W, setW] = useState({});
  const [verbindung, setVerbindung] = useState({ ok: false, text: "verbinde …", detail: "" });
  const [info, setInfo] = useState(null);
  const laeuft = useRef(false);
  const seiteRef = useRef(seite);
  seiteRef.current = seite;

  const aktualisieren = useCallback(async () => {
    if (laeuft.current || !deviceId) return;
    laeuft.current = true;
    try {
      const r = await api.post(`/mbox/${deviceId}/lesen`, { namen: [...BASIS, ...(EXTRA[seiteRef.current] || [])] }, { timeout: 30000 });
      if (!r.data.ok) {
        setVerbindung({ ok: false, text: "keine Verbindung", detail: r.data.fehler || "" });
        return;
      }
      setW(prev => ({ ...prev, ...r.data.werte }));
      setVerbindung({ ok: true, text: "Stand " + new Date().toLocaleTimeString("de-DE"), detail: "letzte erfolgreiche Abfrage" });
    } catch (e) {
      const msg = e.response?.data?.detail || e.message;
      setVerbindung({ ok: false, text: e.response?.status === 403 ? "kein Zugriff" : "Dienst nicht erreichbar", detail: msg });
    } finally {
      laeuft.current = false;
    }
  }, [deviceId]);

  useEffect(() => {
    if (!deviceId) return;
    const lade = () => api.get(`/mbox/${deviceId}/status`).then(r => setInfo(r.data)).catch(e => {
      setInfo(prev => prev && !prev.error ? prev : { error: e.response?.data?.detail || "Status nicht ladbar", level: "none" });
    });
    lade();
    const t = setInterval(lade, 10000);
    return () => clearInterval(t);
  }, [deviceId]);

  useEffect(() => {
    aktualisieren();
    const t = setInterval(aktualisieren, 2000);
    const vis = () => { if (!document.hidden) aktualisieren(); };
    document.addEventListener("visibilitychange", vis);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", vis); };
  }, [aktualisieren]);

  useEffect(() => { aktualisieren(); }, [seite, aktualisieren]);

  const post = useCallback(async (pfad, body, params) => {
    try {
      const r = await api.post(`/mbox/${deviceId}/${pfad}`, body ?? {}, { params, timeout: 30000 });
      return r.data;
    } catch (e) {
      return { ok: false, fehler: e.response?.data?.detail || e.message };
    }
  }, [deviceId]);

  const befehl = useCallback(async (name, index) => {
    const r = await post("befehl/" + name, undefined, index !== undefined && index !== null ? { index } : undefined);
    if (!r.ok) { toast.error(r.fehler); return false; }
    const fe = W["DB_HMI.Status.Fern_Erlaubt"], wm = W["DB_HMI.Status.Wartungsmodus"];
    const gesperrt = fe === false || wm === true;
    if (gesperrt) toast.warning("gesendet – wird aber ignoriert (Fernbedienung gesperrt)");
    else toast.success("gesendet");
    setTimeout(aktualisieren, 400);
    return true;
  }, [post, W, aktualisieren]);

  return { W, verbindung, info, aktualisieren, post, befehl };
}
