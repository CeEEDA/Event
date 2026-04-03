import { useState, useRef, useCallback, useEffect } from "react";
import { Camera, X, RotateCcw, Check } from "lucide-react";
import { Button } from "./ui/button";

export default function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [photo, setPhoto] = useState(null);
  const [facingMode, setFacingMode] = useState("environment");
  const [error, setError] = useState(null);

  const startCamera = useCallback(async (facing) => {
    // Stop existing stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setError(null);
    } catch (err) {
      setError("Kamera-Zugriff nicht moeglich. Bitte Berechtigung erteilen.");
    }
  }, []);

  useEffect(() => {
    startCamera(facingMode);
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, [startCamera, facingMode]);

  const takePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    setPhoto(dataUrl);
  };

  const retake = () => {
    setPhoto(null);
  };

  const confirm = () => {
    if (!photo) return;
    // Convert data URL to File
    const arr = photo.split(",");
    const bstr = atob(arr[1]);
    const n = bstr.length;
    const u8arr = new Uint8Array(n);
    for (let i = 0; i < n; i++) u8arr[i] = bstr.charCodeAt(i);
    const filename = `Foto_${new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-")}.jpg`;
    const file = new File([u8arr], filename, { type: "image/jpeg" });
    onCapture(file);
  };

  const switchCamera = () => {
    setFacingMode(prev => prev === "environment" ? "user" : "environment");
  };

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col" data-testid="camera-modal">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4">
        <button onClick={onClose} className="p-2 bg-black/50 rounded-full text-white" data-testid="camera-close">
          <X className="w-6 h-6" />
        </button>
        <button onClick={switchCamera} className="p-2 bg-black/50 rounded-full text-white" data-testid="camera-switch">
          <RotateCcw className="w-5 h-5" />
        </button>
      </div>

      {/* Camera / Photo */}
      <div className="flex-1 flex items-center justify-center overflow-hidden">
        {error ? (
          <div className="text-white text-center p-8">
            <Camera className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <p className="text-sm">{error}</p>
          </div>
        ) : photo ? (
          <img src={photo} alt="Aufnahme" className="max-w-full max-h-full object-contain" />
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="max-w-full max-h-full object-contain" />
        )}
      </div>

      {/* Controls */}
      <div className="p-6 flex items-center justify-center gap-6">
        {!photo ? (
          <button onClick={takePhoto} disabled={!!error}
            className="w-16 h-16 rounded-full bg-white border-4 border-gray-300 hover:bg-gray-100 active:scale-95 transition-transform disabled:opacity-30"
            data-testid="camera-shutter" />
        ) : (
          <>
            <Button variant="outline" onClick={retake} className="bg-white/10 text-white border-white/30 hover:bg-white/20" data-testid="camera-retake">
              <RotateCcw className="w-4 h-4 mr-2" /> Nochmal
            </Button>
            <Button onClick={confirm} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="camera-confirm">
              <Check className="w-4 h-4 mr-2" /> Verwenden
            </Button>
          </>
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
