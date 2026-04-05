import { useState, useRef, useCallback, useEffect } from "react";
import { LogIn, LogOut } from "lucide-react";

export function SwipeClock({ clockedIn, onSwipeComplete, disabled }) {
  const trackRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [offset, setOffset] = useState(0);
  const startX = useRef(0);
  const trackWidth = useRef(0);
  const THUMB_SIZE = 52;
  const THRESHOLD = 0.75;

  const getTrackWidth = useCallback(() => {
    if (trackRef.current) return trackRef.current.offsetWidth - THUMB_SIZE;
    return 200;
  }, []);

  const handleStart = (clientX) => {
    if (disabled) return;
    setDragging(true);
    startX.current = clientX;
    trackWidth.current = getTrackWidth();
  };

  const handleMove = (clientX) => {
    if (!dragging) return;
    const delta = clientX - startX.current;
    const max = trackWidth.current;
    setOffset(Math.max(0, Math.min(delta, max)));
  };

  const handleEnd = () => {
    if (!dragging) return;
    setDragging(false);
    const max = trackWidth.current;
    if (offset >= max * THRESHOLD) {
      setOffset(max);
      setTimeout(() => {
        onSwipeComplete();
        setOffset(0);
      }, 200);
    } else {
      setOffset(0);
    }
  };

  // Mouse events
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e) => handleMove(e.clientX);
    const onUp = () => handleEnd();
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  });

  const progress = trackWidth.current > 0 ? offset / trackWidth.current : 0;

  return (
    <div
      ref={trackRef}
      className={`relative h-[52px] rounded-full select-none overflow-hidden transition-colors ${
        clockedIn
          ? "bg-gradient-to-r from-green-500 to-green-600"
          : "bg-gradient-to-r from-gray-200 to-gray-300"
      }`}
      style={{ minWidth: 220 }}
      data-testid="swipe-clock"
    >
      {/* Track label */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <span className={`text-xs font-semibold tracking-wide transition-opacity ${
          clockedIn ? "text-white/70" : "text-gray-500"
        } ${dragging ? "opacity-30" : "opacity-100"}`}>
          {clockedIn ? "Zum Ausstempeln schieben" : "Zum Einstempeln schieben"}
        </span>
      </div>

      {/* Thumb */}
      <div
        className={`absolute top-0 h-[52px] w-[52px] rounded-full flex items-center justify-center shadow-lg cursor-grab active:cursor-grabbing transition-transform ${
          dragging ? "" : "transition-all duration-300"
        } ${clockedIn
          ? "bg-white text-green-600"
          : "bg-white text-gray-600"
        }`}
        style={{
          left: offset,
          transform: `scale(${dragging ? 1.05 : 1})`,
        }}
        onMouseDown={(e) => { e.preventDefault(); handleStart(e.clientX); }}
        onTouchStart={(e) => handleStart(e.touches[0].clientX)}
        onTouchMove={(e) => handleMove(e.touches[0].clientX)}
        onTouchEnd={handleEnd}
        data-testid="swipe-thumb"
      >
        {clockedIn ? <LogOut className="w-5 h-5" /> : <LogIn className="w-5 h-5" />}
      </div>

      {/* Progress fill */}
      {!clockedIn && offset > 0 && (
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-green-400 to-green-500 transition-none"
          style={{ width: offset + THUMB_SIZE / 2 }}
        />
      )}
      {clockedIn && offset > 0 && (
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-red-400 to-red-500 transition-none"
          style={{ width: offset + THUMB_SIZE / 2 }}
        />
      )}
    </div>
  );
}
