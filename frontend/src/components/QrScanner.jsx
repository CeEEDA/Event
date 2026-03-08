import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";

export default function QrScanner({ onScan, onError, onClose }) {
  const containerRef = useRef(null);
  const scannerRef = useRef(null);
  const [camError, setCamError] = useState(null);

  useEffect(() => {
    const regionId = "qr-reader-" + Math.random().toString(36).slice(2, 8);
    if (containerRef.current) {
      containerRef.current.id = regionId;
    }

    let cancelled = false;
    const scanner = new Html5Qrcode(regionId);
    scannerRef.current = scanner;

    // Suppress media abort errors (expected when stopping camera)
    const suppressAbortError = (e) => {
      const msg = e?.message || e?.reason?.message || String(e?.reason || "");
      if (msg.includes("fetching process") || msg.includes("aborted")) {
        e.preventDefault?.();
        e.stopPropagation?.();
        return true;
      }
    };
    window.addEventListener("error", suppressAbortError, true);
    window.addEventListener("unhandledrejection", suppressAbortError, true);

    // Force-kill all camera tracks from the container
    const killCameraTracks = () => {
      try {
        const videos = containerRef.current?.querySelectorAll("video");
        videos?.forEach((v) => {
          const stream = v.srcObject;
          if (stream) {
            stream.getTracks().forEach((t) => t.stop());
            v.srcObject = null;
          }
        });
      } catch { /* ignore */ }
    };

    scanner
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        (text) => {
          if (!cancelled) {
            scanner.stop().catch(() => {}).finally(() => killCameraTracks());
            onScan(text);
          }
        },
        () => {}
      )
      .then(() => {
        if (cancelled) {
          scanner.stop().catch(() => {}).finally(() => killCameraTracks());
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setCamError(err?.message || "Kamera konnte nicht gestartet werden");
          if (onError) onError(err);
        }
      });

    return () => {
      cancelled = true;
      // Try library stop first, then force-kill tracks as fallback
      scanner.stop().catch(() => {}).finally(() => {
        killCameraTracks();
        try { scanner.clear(); } catch { /* ignore */ }
      });
      setTimeout(() => {
        killCameraTracks(); // Extra safety after async operations
        window.removeEventListener("error", suppressAbortError, true);
        window.removeEventListener("unhandledrejection", suppressAbortError, true);
      }, 500);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    // Force stop camera tracks immediately
    try {
      const videos = containerRef.current?.querySelectorAll("video");
      videos?.forEach((v) => {
        const stream = v.srcObject;
        if (stream) {
          stream.getTracks().forEach((t) => t.stop());
          v.srcObject = null;
        }
      });
    } catch { /* ignore */ }
    if (scannerRef.current) {
      scannerRef.current.stop().catch(() => {});
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
