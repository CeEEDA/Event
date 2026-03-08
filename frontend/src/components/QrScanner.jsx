import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";

export default function QrScanner({ onScan, onError, onClose }) {
  const containerRef = useRef(null);
  const scannerRef = useRef(null);
  const startedRef = useRef(false);
  const [camError, setCamError] = useState(null);

  useEffect(() => {
    const regionId = "qr-reader-" + Math.random().toString(36).slice(2, 8);
    if (containerRef.current) {
      containerRef.current.id = regionId;
    }

    let cancelled = false;
    const scanner = new Html5Qrcode(regionId);
    scannerRef.current = scanner;

    scanner
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        (text) => {
          if (!cancelled) {
            startedRef.current = false;
            scanner.stop().catch(() => {});
            onScan(text);
          }
        },
        () => {}
      )
      .then(() => {
        if (!cancelled) startedRef.current = true;
      })
      .catch((err) => {
        if (!cancelled) {
          setCamError(err?.message || "Kamera konnte nicht gestartet werden");
          if (onError) onError(err);
        }
      });

    return () => {
      cancelled = true;
      if (startedRef.current) {
        startedRef.current = false;
        scanner.stop().catch(() => {});
      }
      try { scanner.clear(); } catch { /* ignore */ }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    if (startedRef.current) {
      startedRef.current = false;
      scannerRef.current?.stop().catch(() => {});
    }
    if (onClose) onClose();
  };

  return (
    <div className="relative rounded-lg overflow-hidden bg-black" data-testid="qr-scanner">
      <div ref={containerRef} style={{ width: "100%", minHeight: 260 }} />
      {camError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/90 text-white p-4 text-center">
          <p className="text-sm mb-2">Kamera-Fehler</p>
          <p className="text-xs text-gray-300">{camError}</p>
        </div>
      )}
      {onClose && (
        <button
          onClick={handleClose}
          className="absolute top-2 right-2 bg-black/60 text-white rounded-full w-7 h-7 flex items-center justify-center text-sm hover:bg-black/80"
          data-testid="qr-scanner-close"
        >
          ✕
        </button>
      )}
    </div>
  );
}
