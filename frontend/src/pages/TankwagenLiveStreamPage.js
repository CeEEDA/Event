import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ArrowLeft, Pause, Play, Trash2, Download, ArrowDown, ArrowUp, Activity } from "lucide-react";

// ====== Hex / ASCII helpers ======

function bytesFromHex(hex) {
  const s = (hex || "").replace(/\s+/g, "");
  const out = new Uint8Array(s.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(s.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function asciiPreview(bytes) {
  let s = "";
  for (const b of bytes) {
    if (b >= 0x20 && b < 0x7f) s += String.fromCharCode(b);
    else s += ".";
  }
  return s;
}

function fmtHex(hex) {
  const s = (hex || "").replace(/\s+/g, "").toLowerCase();
  return s.match(/.{1,2}/g)?.join(" ") || "";
}

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

// Heuristisches Parser-Annotat: erkennt bekannte Sening / Epson-Sequenzen.
function annotate(hex, direction) {
  const b = bytesFromHex(hex);
  if (b.length === 0) return null;
  if (direction === "rx") {
    if (b.length >= 3 && b[0] === 0x1b && b[1] === 0xb3) return `Sening-Poll (Zone 0x${b[2].toString(16)})`;
    if (b.length >= 3 && b[0] === 0x10 && b[1] === 0x04) return `DLE EOT ${b[2]} (Status-Query)`;
    if (b.length >= 3 && b[0] === 0x10 && b[1] === 0x05) return `DLE ENQ ${b[2]} (Realtime-Query)`;
    if (b.length >= 2 && b[0] === 0x1b && b[1] === 0x76) return "ESC v (Paper-Sensor)";
    if (b.length >= 2 && b[0] === 0x1b && b[1] === 0x75) return "ESC u (Peripheral-Status)";
    if (b.length >= 3 && b[0] === 0x1d && b[1] === 0x72) return `GS r ${b[2]} (Transmit-Status)`;
    if (b.length > 30) return "Print-Job (Beleg-Druck)";
    return null;
  }
  // tx
  if (b.length === 1) {
    if (b[0] === 0x12) return "Reply: 0x12 (online / paper OK)";
    if (b[0] === 0x00) return "Reply: 0x00 (ok)";
    return `Reply: 0x${b[0].toString(16).padStart(2, "0")}`;
  }
  return null;
}

// ====== Page ======

export default function TankwagenLiveStreamPage() {
  const navigate = useNavigate();
  const [pis, setPis] = useState([]);
  const [piId, setPiId] = useState("");
  const [items, setItems] = useState([]);
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState("all"); // all | rx | tx
  const sinceRef = useRef(0);
  const itemsRef = useRef([]);
  const listEndRef = useRef(null);

  // Polling-Loop
  const fetchTail = useCallback(async () => {
    if (paused) return;
    try {
      const params = new URLSearchParams();
      if (piId) params.set("pi_id", piId);
      if (sinceRef.current) params.set("since_ts", String(sinceRef.current));
      params.set("limit", "500");
      const res = await api.get(`/system/tankwagen/raw-stream/tail?${params.toString()}`);
      if (res.data?.pis) setPis(res.data.pis);
      const newItems = res.data?.items || [];
      if (newItems.length) {
        sinceRef.current = newItems[newItems.length - 1].ts;
        itemsRef.current = [...itemsRef.current, ...newItems].slice(-2000); // max 2000 in UI
        setItems(itemsRef.current);
      }
    } catch (err) {
      // Silent retry - der Pi sendet evtl. gerade nichts oder Backend ist kurz weg
      console.debug("tail fetch error", err);
    }
  }, [piId, paused]);

  useEffect(() => {
    const id = setInterval(fetchTail, 1000);
    fetchTail();
    return () => clearInterval(id);
  }, [fetchTail]);

  // Auto-Scroll
  useEffect(() => {
    if (autoScroll && !paused && listEndRef.current) {
      listEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [items, autoScroll, paused]);

  const onClear = async () => {
    try {
      const params = new URLSearchParams();
      if (piId) params.set("pi_id", piId);
      await api.delete(`/system/tankwagen/raw-stream${params.toString() ? `?${params}` : ""}`);
      itemsRef.current = [];
      sinceRef.current = 0;
      setItems([]);
      toast.success("Stream geleert");
    } catch (err) {
      toast.error("Konnte Stream nicht leeren");
    }
  };

  const onExport = () => {
    const lines = items.map((i) =>
      `${fmtTime(i.ts)}  ${i.direction.toUpperCase()}  ${fmtHex(i.hex).padEnd(60)}  | ${asciiPreview(bytesFromHex(i.hex))}  ${i.note || ""}`
    );
    const blob = new Blob([lines.join("\n") + "\n"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tankwagen-stream-${new Date().toISOString().replace(/:/g, "-")}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onPiChange = (val) => {
    setPiId(val === "_all_" ? "" : val);
    sinceRef.current = 0;
    itemsRef.current = [];
    setItems([]);
  };

  const filteredItems = useMemo(() => {
    if (filter === "all") return items;
    return items.filter((i) => i.direction === filter);
  }, [items, filter]);

  const stats = useMemo(() => {
    let rx = 0, tx = 0, rxBytes = 0, txBytes = 0;
    for (const it of items) {
      const len = (it.hex || "").length / 2;
      if (it.direction === "rx") { rx++; rxBytes += len; } else { tx++; txBytes += len; }
    }
    return { rx, tx, rxBytes, txBytes };
  }, [items]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)} data-testid="back-btn">
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Logo className="h-8" />
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Activity className="h-6 w-6 text-blue-600" />
                Tankwagen Live-Stream
              </h1>
              <p className="text-sm text-muted-foreground">Roh-Bytes vom Sening MultiFlow in Echtzeit</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={paused ? "secondary" : "default"} className="gap-1" data-testid="status-badge">
              <span className={`w-2 h-2 rounded-full ${paused ? "bg-slate-400" : "bg-emerald-500 animate-pulse"}`} />
              {paused ? "Pausiert" : "Live"}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => setPaused((p) => !p)} data-testid="pause-btn">
              {paused ? <Play className="h-4 w-4 mr-1" /> : <Pause className="h-4 w-4 mr-1" />}
              {paused ? "Fortsetzen" : "Pause"}
            </Button>
            <Button variant="outline" size="sm" onClick={onExport} data-testid="export-btn" disabled={items.length === 0}>
              <Download className="h-4 w-4 mr-1" /> Export
            </Button>
            <Button variant="outline" size="sm" onClick={onClear} data-testid="clear-btn">
              <Trash2 className="h-4 w-4 mr-1" /> Leeren
            </Button>
          </div>
        </div>

        {/* Controls */}
        <Card className="p-4 mb-4 flex flex-wrap items-center gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Pi auswaehlen</span>
            <Select value={piId || "_all_"} onValueChange={onPiChange}>
              <SelectTrigger className="w-[280px]" data-testid="pi-select">
                <SelectValue placeholder="Alle Pis" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all_">Alle Pis</SelectItem>
                {pis.map((p) => (
                  <SelectItem key={p.pi_id} value={p.pi_id}>
                    {p.hostname || "(unbenannt)"} — {p.pi_id.slice(0, 8)}… ({p.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Richtung</span>
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-[160px]" data-testid="dir-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">RX + TX</SelectItem>
                <SelectItem value="rx">Nur RX (Sening → Pi)</SelectItem>
                <SelectItem value="tx">Nur TX (Pi → Sening)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">Auto-Scroll</span>
            <Button
              variant={autoScroll ? "default" : "outline"}
              size="sm"
              onClick={() => setAutoScroll((a) => !a)}
              data-testid="autoscroll-btn"
              className="w-[110px]"
            >
              {autoScroll ? "An" : "Aus"}
            </Button>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1" data-testid="stat-rx">
              <ArrowDown className="h-4 w-4 text-emerald-600" />
              <span className="font-mono">{stats.rx}</span>
              <span className="text-muted-foreground">RX</span>
              <span className="text-xs text-muted-foreground">({stats.rxBytes} B)</span>
            </div>
            <div className="flex items-center gap-1" data-testid="stat-tx">
              <ArrowUp className="h-4 w-4 text-blue-600" />
              <span className="font-mono">{stats.tx}</span>
              <span className="text-muted-foreground">TX</span>
              <span className="text-xs text-muted-foreground">({stats.txBytes} B)</span>
            </div>
          </div>
        </Card>

        {/* Stream */}
        <Card className="overflow-hidden" data-testid="stream-card">
          <div className="bg-slate-900 text-slate-100 font-mono text-xs">
            <div className="grid grid-cols-[110px_50px_1fr_240px] gap-2 px-3 py-2 bg-slate-800 border-b border-slate-700 sticky top-0 text-slate-400 uppercase text-[10px] tracking-wider">
              <div>Zeit</div>
              <div>Dir</div>
              <div>Hex / ASCII</div>
              <div>Annotation</div>
            </div>
            <div className="max-h-[60vh] overflow-y-auto" data-testid="stream-list">
              {filteredItems.length === 0 ? (
                <div className="p-8 text-center text-slate-500">
                  Noch keine Daten. {paused ? "Stream ist pausiert." : "Warte auf den Tankwagen-Pi…"}
                </div>
              ) : (
                filteredItems.map((it, idx) => {
                  const bytes = bytesFromHex(it.hex);
                  const isRx = it.direction === "rx";
                  const note = it.note || annotate(it.hex, it.direction);
                  return (
                    <div
                      key={`${it.ts}-${idx}`}
                      className={`grid grid-cols-[110px_50px_1fr_240px] gap-2 px-3 py-1.5 border-b border-slate-800 hover:bg-slate-800/50 ${
                        isRx ? "" : "bg-blue-950/30"
                      }`}
                      data-testid={`stream-row-${idx}`}
                    >
                      <div className="text-slate-400">{fmtTime(it.ts)}</div>
                      <div className={isRx ? "text-emerald-400" : "text-blue-400"}>
                        {isRx ? "← RX" : "→ TX"}
                      </div>
                      <div className="overflow-hidden">
                        <div className="text-amber-300 break-all">{fmtHex(it.hex)}</div>
                        <div className="text-slate-500 break-all">{asciiPreview(bytes)}</div>
                      </div>
                      <div className="text-slate-300 text-[11px]">{note}</div>
                    </div>
                  );
                })
              )}
              <div ref={listEndRef} />
            </div>
          </div>
        </Card>

        {/* Help */}
        <div className="mt-4 text-xs text-muted-foreground space-y-1">
          <p><strong>Tipp:</strong> Auf dem Test-Pi <code className="font-mono bg-slate-200 dark:bg-slate-700 px-1 rounded">raw_stream_enabled = true</code> in <code className="font-mono">/etc/tankbeleg_pi.conf</code> setzen, dann <code className="font-mono">sudo systemctl restart tankbeleg_pi</code>.</p>
          <p><strong>Annotation:</strong> Bekannte Sening-Polls (ESC B3 …) und Epson-Status-Queries (DLE EOT, ESC v, GS r) werden automatisch beschriftet. Unbekannte Sequenzen erscheinen ohne Annotation — bitte hier melden, dann erweitere ich den Decoder.</p>
        </div>
      </div>
    </div>
  );
}
