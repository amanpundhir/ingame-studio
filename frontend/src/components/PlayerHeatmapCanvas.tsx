/**
 * InGame Studio - Pitch Action Heatmap, Shot Map and Passing Lanes
 *
 * Everything drawn here is the real match data of the selected player:
 * - Heatmap: the player's tracked position density (12 x 8 grid from the analytics tracker).
 * - Shots: the player's shots and goals from the match events.
 * - Passing lanes: the player's passes from the match events (completed and not completed).
 *
 * The teams change ends at half-time, so every position is shown in the player's own
 * attacking direction: his team always attacks from left to right on this map.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { PlayerAnalytics, MatchEvent } from '../types';

export interface PlayerHeatmapCanvasProps {
  player?: PlayerAnalytics | null;
  events?: MatchEvent[];
  width?: number;
  height?: number;
  className?: string;
}

interface ShotPoint {
  x: number;
  y: number;
  outcome: 'goal' | 'on_target' | 'off_target';
  clock: string;
  xt: number;
  description: string;
}

interface PassLane {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  completed: boolean;
  clock: string;
  xt: number;
}

const L = 105;
const W = 68;

function isHomePlayer(player: PlayerAnalytics): boolean {
  return player.team.toLowerCase().includes('northbridge') || player.team === 'home' || player.player_id.startsWith('NBL');
}

/** Rotates a point into the player's attacking direction (second half is played the other way). */
function toAttackFrame(x: number, y: number, home: boolean, period: number): [number, number] {
  const attacksRight = period === 2 ? !home : home;
  return attacksRight ? [x, y] : [L - x, W - y];
}

export function derivePlayerMaps(player: PlayerAnalytics | null | undefined, events: MatchEvent[]) {
  const shots: ShotPoint[] = [];
  const passes: PassLane[] = [];
  if (!player) return { shots, passes, grid: null as number[][] | null };
  const home = isHomePlayer(player);
  for (const e of events) {
    if (e.player_id !== player.player_id) continue;
    if (typeof e.location_x !== 'number' || typeof e.location_y !== 'number') continue;
    const [x, y] = toAttackFrame(e.location_x, e.location_y, home, e.period);
    if (e.event_type === 'shot' || e.event_type === 'goal') {
      const goal = e.event_type === 'goal' || e.outcome === 'goal';
      shots.push({
        x,
        y,
        outcome: goal ? 'goal' : e.outcome === 'saved' ? 'on_target' : 'off_target',
        clock: e.clock,
        xt: Number(e.tactical_metrics?.xt_gained ?? 0),
        description: e.context || (goal ? `Goal by ${player.name}` : `Shot by ${player.name}`),
      });
    } else if (e.event_type === 'pass' && typeof e.end_x === 'number' && typeof e.end_y === 'number') {
      const [x2, y2] = toAttackFrame(e.end_x, e.end_y, home, e.period);
      passes.push({
        x1: x,
        y1: y,
        x2,
        y2,
        completed: e.outcome === 'complete',
        clock: e.clock,
        xt: Number(e.tactical_metrics?.xt_gained ?? 0),
      });
    }
  }
  const raw = player.heatmap;
  const hasTracked = Array.isArray(raw) && raw.some((col) => col.some((v) => v > 0));
  return { shots, passes, grid: hasTracked ? raw : null };
}

function heatColor(t: number): [number, number, number, number] {
  // transparent -> cyan -> yellow -> red
  const stops: Array<[number, number, number, number]> = [
    [4, 240, 255, 0],
    [4, 240, 255, 0.35],
    [255, 230, 0, 0.6],
    [233, 0, 82, 0.9],
  ];
  const p = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(p));
  const f = p - i;
  const a = stops[i];
  const b = stops[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f];
}

export const PlayerHeatmapCanvas: React.FC<PlayerHeatmapCanvasProps> = ({
  player,
  events = [],
  width = 540,
  height = 350,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [showHeat, setShowHeat] = useState(true);
  const [showShots, setShowShots] = useState(true);
  const [showPasses, setShowPasses] = useState(true);
  const [hoveredShot, setHoveredShot] = useState<ShotPoint | null>(null);

  const { shots, passes, grid } = useMemo(() => derivePlayerMaps(player, events), [player, events]);
  const home = player ? isHomePlayer(player) : true;
  const completed = passes.filter((p) => p.completed).length;

  const geometry = () => {
    const padX = 14;
    const padY = 14;
    const pw = width - padX * 2;
    const ph = height - padY * 2;
    return { padX, padY, pw, ph, X: (x: number) => padX + (x / L) * pw, Y: (y: number) => padY + (y / W) * ph };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const { padX, padY, pw, ph, X, Y } = geometry();

    // Pitch
    ctx.fillStyle = '#184724';
    ctx.fillRect(0, 0, width, height);
    const bands = 12;
    for (let b = 0; b < bands; b++) {
      ctx.fillStyle = b % 2 === 0 ? '#1a5c1a' : '#1d641f';
      ctx.fillRect(padX + (pw / bands) * b, padY, pw / bands + 0.5, ph);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.8)';
    ctx.lineWidth = 1.3;
    ctx.strokeRect(padX, padY, pw, ph);
    ctx.beginPath();
    ctx.moveTo(X(L / 2), Y(0));
    ctx.lineTo(X(L / 2), Y(W));
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(X(L / 2), Y(W / 2), (9.15 / L) * pw, 0, Math.PI * 2);
    ctx.stroke();
    for (const side of [0, 1]) {
      const gx = side === 0 ? 0 : L;
      const box = (depth: number, span: number) =>
        ctx.strokeRect(side === 0 ? X(gx) : X(gx - depth), Y((W - span) / 2), (depth / L) * pw, (span / W) * ph);
      box(16.5, 40.32);
      box(5.5, 18.32);
    }

    // Heatmap (tracked positions, smoothly scaled up from the 12 x 8 grid)
    if (showHeat && grid) {
      const cols = grid.length;
      const rows = grid[0].length;
      const max = Math.max(1, ...grid.map((c) => Math.max(...c)));
      const small = document.createElement('canvas');
      small.width = cols;
      small.height = rows;
      const sctx = small.getContext('2d');
      if (sctx) {
        const img = sctx.createImageData(cols, rows);
        for (let cx = 0; cx < cols; cx++) {
          for (let ry = 0; ry < rows; ry++) {
            const t = Math.sqrt(grid[cx][ry] / max);
            const [r, g, b, a] = heatColor(t);
            const idx = (ry * cols + cx) * 4;
            img.data[idx] = r;
            img.data[idx + 1] = g;
            img.data[idx + 2] = b;
            img.data[idx + 3] = Math.round(a * 255);
          }
        }
        sctx.putImageData(img, 0, 0);
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.filter = 'blur(6px)';
        ctx.drawImage(small, padX, padY, pw, ph);
        ctx.restore();
      }
    }

    // Passing lanes
    if (showPasses) {
      for (const p of passes) {
        const color = p.completed ? 'rgba(4,240,255,0.55)' : 'rgba(233,0,82,0.7)';
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = p.completed ? 1.4 : 1.2;
        ctx.setLineDash(p.completed ? [] : [4, 3]);
        const x1 = X(p.x1);
        const y1 = Y(p.y1);
        const x2 = X(p.x2);
        const y2 = Y(p.y2);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.setLineDash([]);
        const ang = Math.atan2(y2 - y1, x2 - x1);
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - 6 * Math.cos(ang - 0.4), y2 - 6 * Math.sin(ang - 0.4));
        ctx.lineTo(x2 - 6 * Math.cos(ang + 0.4), y2 - 6 * Math.sin(ang + 0.4));
        ctx.closePath();
        ctx.fill();
      }
    }

    // Shots
    if (showShots) {
      for (const s of shots) {
        const cx = X(s.x);
        const cy = Y(s.y);
        if (s.outcome === 'goal') {
          ctx.fillStyle = '#ffe600';
          ctx.strokeStyle = '#080b0f';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          for (let k = 0; k < 10; k++) {
            const r = k % 2 === 0 ? 9 : 4;
            const a = (Math.PI / 5) * k - Math.PI / 2;
            ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
          }
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        } else if (s.outcome === 'on_target') {
          ctx.strokeStyle = '#00ff87';
          ctx.fillStyle = 'rgba(0,255,135,0.3)';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        } else {
          ctx.strokeStyle = '#e90052';
          ctx.lineWidth = 2.2;
          ctx.beginPath();
          ctx.moveTo(cx - 5, cy - 5);
          ctx.lineTo(cx + 5, cy + 5);
          ctx.moveTo(cx + 5, cy - 5);
          ctx.lineTo(cx - 5, cy + 5);
          ctx.stroke();
        }
      }
    }

    // Direction of play
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.font = '700 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${home ? 'Northbridge Lions' : 'Harbourside'} attack  →`, X(L / 2), padY + ph - 5);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grid, shots, passes, showHeat, showShots, showPasses, width, height, home]);

  const handleMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const { X, Y } = geometry();
    const mx = ((e.clientX - rect.left) / rect.width) * width;
    const my = ((e.clientY - rect.top) / rect.height) * height;
    const hit = showShots ? shots.find((s) => Math.hypot(X(s.x) - mx, Y(s.y) - my) < 10) : undefined;
    setHoveredShot(hit ?? null);
  };

  const chip = (label: string, on: boolean, toggle: () => void, color: string) => (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      style={{
        background: on ? color : 'transparent',
        color: on ? '#080b0f' : 'var(--color-text-secondary, #8b9bb4)',
        border: `1px solid ${on ? color : 'var(--color-border-subtle, #1e2a3a)'}`,
        borderRadius: '16px',
        padding: '3px 10px',
        fontSize: '10px',
        fontWeight: 800,
        cursor: 'pointer',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </button>
  );

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', maxWidth: `${width}px` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-text-secondary, #8b9bb4)' }}>
          {player?.name ?? 'Player'} · attacking left to right
        </span>
        <div style={{ display: 'flex', gap: '4px' }} role="group" aria-label="Map layers">
          {chip('Heatmap', showHeat, () => setShowHeat((v) => !v), '#04f0ff')}
          {chip('Shots', showShots, () => setShowShots((v) => !v), '#ffe600')}
          {chip('Passing lanes', showPasses, () => setShowPasses((v) => !v), '#00ff87')}
        </div>
      </div>

      <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--color-border-subtle, #1e2a3a)', backgroundColor: '#184724' }}>
        <canvas
          ref={canvasRef}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoveredShot(null)}
          style={{ display: 'block', width: '100%', height: 'auto', aspectRatio: `${width} / ${height}` }}
          aria-label={`Heatmap, shot map and passing lanes for ${player?.name ?? 'the selected player'}`}
          role="img"
        />
        {hoveredShot && (
          <div
            style={{
              position: 'absolute', top: '10px', right: '10px', background: 'var(--color-bg-overlay, #141c26)',
              border: '1px solid var(--color-accent-cyan, #04f0ff)', borderRadius: '6px', padding: '6px 10px',
              fontSize: '11px', color: 'var(--color-text-primary, #f0f4f8)', pointerEvents: 'none', maxWidth: '70%',
            }}
          >
            <div style={{ fontWeight: 800 }}>{hoveredShot.description}</div>
            <div style={{ color: 'var(--color-accent-cyan, #04f0ff)', fontSize: '10px' }}>
              {hoveredShot.clock} · xT {hoveredShot.xt.toFixed(2)}
            </div>
          </div>
        )}
        {showHeat && !grid && (
          <div style={{ position: 'absolute', left: 8, bottom: 8, fontSize: '10px', color: '#fff', background: 'rgba(8,11,15,0.7)', padding: '2px 6px', borderRadius: 4 }}>
            No tracked positions yet
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', fontSize: '10px', color: 'var(--color-text-secondary, #8b9bb4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>Low</span>
          <div style={{ width: 56, height: 6, borderRadius: 3, background: 'linear-gradient(90deg, rgba(4,240,255,0.4), rgba(255,230,0,0.6), rgba(233,0,82,0.9))' }} />
          <span>High time on ball position</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span><span style={{ color: '#ffe600' }}>★</span> Goal ({shots.filter((s) => s.outcome === 'goal').length})</span>
          <span><span style={{ color: '#00ff87' }}>●</span> On target ({shots.filter((s) => s.outcome === 'on_target').length})</span>
          <span><span style={{ color: '#e90052', fontWeight: 800 }}>×</span> Off target ({shots.filter((s) => s.outcome === 'off_target').length})</span>
          <span><span style={{ color: '#04f0ff' }}>→</span> Completed pass ({completed})</span>
          <span><span style={{ color: '#e90052' }}>⇢</span> Not completed ({passes.length - completed})</span>
        </div>
      </div>
    </div>
  );
};

export default PlayerHeatmapCanvas;
