import { useEffect, useRef } from "react";

// Flowing, amplitude-reactive "sound wave" field drawn on a 2D canvas.
// Layered translucent sine waves shift cyan -> blue -> purple -> pink to echo
// the neon voice-assistant look. Pure canvas (no WebGL) so it's crash-proof.

const LINES = 22; // number of stacked wave lines

function lineColor(t: number): [number, number, number] {
  // cyan -> blue -> purple -> pink
  const stops: [number, [number, number, number]][] = [
    [0, [34, 211, 238]],
    [0.34, [59, 130, 246]],
    [0.67, [168, 85, 247]],
    [1, [236, 72, 153]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i];
    const [b, cb] = stops[i + 1];
    if (t >= a && t <= b) {
      const k = (t - a) / (b - a || 1);
      return [
        Math.round(ca[0] + (cb[0] - ca[0]) * k),
        Math.round(ca[1] + (cb[1] - ca[1]) * k),
        Math.round(ca[2] + (cb[2] - ca[2]) * k),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

export default function VoiceWaves({
  amplitude = 0,
  active = false,
}: {
  amplitude?: number;
  active?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Keep latest props in refs so the animation loop reads fresh values.
  const ampProp = useRef(amplitude);
  const activeProp = useRef(active);
  ampProp.current = amplitude;
  activeProp.current = active;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;
    const smoothAmp = { v: 0 };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const start = performance.now();
    const draw = () => {
      const t = (performance.now() - start) / 1000;
      // Ease toward the live amplitude; gentle idle motion when not active.
      const target = activeProp.current ? ampProp.current : 0;
      smoothAmp.v += (target - smoothAmp.v) * 0.08;
      const amp = 0.12 + smoothAmp.v * 0.9; // 0..~1 base wave strength

      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter"; // additive glow where waves overlap

      const baseY = height * 0.62;
      const span = height * 0.34;

      for (let li = 0; li < LINES; li++) {
        const depth = li / (LINES - 1);
        const [r, g, b] = lineColor(depth);
        const phase = li * 0.5;
        const yOffset = baseY + (depth - 0.5) * span;
        const strength = (0.4 + (1 - depth) * 0.9) * amp;
        const alpha = 0.08 + (1 - depth) * 0.32;

        ctx.beginPath();
        const step = Math.max(2, Math.floor(width / 220));
        for (let x = 0; x <= width; x += step) {
          const nx = x / width; // 0..1
          const wave =
            Math.sin(nx * 7 + t * 1.6 + phase) * 0.55 +
            Math.sin(nx * 3.3 - t * 1.05 + phase) * 0.4 +
            Math.sin(nx * 12 + t * 0.7 - phase) * 0.18 * (1 - depth);
          // Taper the amplitude toward the edges for a centered "pinch".
          const envelope = Math.sin(Math.PI * nx);
          const y = yOffset - wave * strength * span * 0.9 * envelope;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.shadowBlur = 8;
        ctx.shadowColor = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        ctx.stroke();
      }

      ctx.globalCompositeOperation = "source-over";
      ctx.shadowBlur = 0;
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: "100%", display: "block" }}
    />
  );
}
