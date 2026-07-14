import { useEffect, useRef } from "react";

// Lightweight 2D-canvas "sound wave" field — flowing cyan -> purple -> pink
// sine layers that react to mic amplitude. No WebGL, so it never hits the
// browser's WebGL-context limit or crashes the app.

const LAYERS = 14;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

// cyan -> blue -> purple -> pink across [0,1]
function layerColor(t: number): [number, number, number] {
  const stops: [number, number, number][] = [
    [34, 211, 238], // cyan
    [59, 130, 246], // blue
    [168, 85, 247], // purple
    [236, 72, 153], // pink
  ];
  const seg = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(seg));
  const f = seg - i;
  return [
    Math.round(lerp(stops[i][0], stops[i + 1][0], f)),
    Math.round(lerp(stops[i][1], stops[i + 1][1], f)),
    Math.round(lerp(stops[i][2], stops[i + 1][2], f)),
  ];
}

export default function VoiceWaveCanvas({
  amplitude = 0,
  active = false,
}: {
  amplitude?: number;
  active?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Keep the latest props in refs so the animation loop stays stable.
  const ampRef = useRef(0);
  const targetRef = useRef(0);
  const activeRef = useRef(active);

  useEffect(() => {
    targetRef.current = amplitude;
    activeRef.current = active;
  }, [amplitude, active]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let t = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // ease amplitude toward the target; gentle idle motion when not active
      const target = activeRef.current ? targetRef.current : 0;
      ampRef.current += (target - ampRef.current) * 0.08;
      const amp = (0.12 + ampRef.current * 1.4) * h;

      t += 0.02;
      const baseY = h * 0.62;

      for (let li = 0; li < LAYERS; li++) {
        const depth = li / (LAYERS - 1);
        const [r, g, b] = layerColor(depth);
        const yOffset = baseY + depth * h * 0.22;
        const phase = li * 0.5;
        const layerAmp = amp * (0.35 + (1 - depth) * 0.65);

        ctx.beginPath();
        for (let x = 0; x <= w; x += 6 * dpr) {
          const nx = x / w;
          const y =
            yOffset +
            Math.sin(nx * 7 + t * 1.6 + phase) * layerAmp * 0.5 +
            Math.sin(nx * 3.5 - t * 1.1 + phase) * layerAmp * 0.35 +
            Math.sin(nx * 13 + t * 0.7 - phase) * layerAmp * 0.15 * (1 - depth);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.14 + (1 - depth) * 0.4})`;
        ctx.lineWidth = dpr * (1 - depth * 0.4);
        ctx.stroke();
      }

      raf = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full"
      style={{ display: "block" }}
    />
  );
}
