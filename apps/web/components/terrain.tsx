"use client";
import { useEffect, useRef } from "react";

// Each polyline follows an elevation slice of the same terrain. The quiet
// center leaves room for the headline at both phone and desktop widths.
export function Terrain() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    function draw() {
      if (!el) return;
      const { width: w, height: h } = el.getBoundingClientRect();
      const d = Math.min(window.devicePixelRatio || 1, 2);
      el.width = Math.round(w * d);
      el.height = Math.round(h * d);
      const ctx = el.getContext("2d");
      if (!ctx) return;
      ctx.scale(d, d);
      for (const side of [-1, 1]) {
        for (let n = 0; n < 94; n++) {
          const depth = n / 93;
          ctx.beginPath();
          for (let p = 0; p <= 180; p++) {
            const t = p / 180;
            const x = side < 0 ? t * w * 0.57 : w - t * w * 0.57;
            const phase = side < 0 ? 0 : 1.5;
            const peak = Math.exp(
              -Math.pow(
                (t - (side < 0 ? 0.12 : 0.21) - 0.04 * Math.sin(depth * 4)) /
                  0.23,
                2,
              ),
            );
            const ridge =
              peak * (0.21 + 0.095 * Math.sin(6 * t + depth * 5 + phase)) +
              Math.sin(t * 10 + depth * 2 + phase) * 0.048 +
              Math.sin(t * 22 - depth * 2) * 0.014;
            const y =
              h *
                (0.68 + depth * 0.34 - ridge * (1 - depth * 0.23) + t * 0.12) +
              Math.sin(t * 40 + depth * 3) * 2;
            if (!p) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          const g = ctx.createLinearGradient(
            side < 0 ? 0 : w,
            0,
            side < 0 ? w * 0.55 : w * 0.45,
            0,
          );
          g.addColorStop(
            0,
            `rgba(225,158,90,${0.33 + 0.19 * Math.sin(depth * 2.5)})`,
          );
          g.addColorStop(0.56, "rgba(207,149,90,.35)");
          g.addColorStop(1, "rgba(207,149,90,0)");
          ctx.strokeStyle = g;
          ctx.lineWidth = 0.85;
          ctx.stroke();
        }
      }
    }
    const resize = new ResizeObserver(draw);
    resize.observe(el);
    draw();
    return () => resize.disconnect();
  }, []);
  return <canvas ref={ref} className="terrain" aria-hidden="true" />;
}
