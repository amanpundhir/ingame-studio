/**
 * InGame Studio - Replay clip player.
 *
 * Plays the real tracking data recorded 10 seconds before and after a match event as a
 * short video: every player and the ball move on a 2D pitch, the key action is
 * highlighted, and the viewer can pause, scrub and change speed.
 *
 * The clip data comes from GET /api/clips/{event_id} (see backend/clips.py).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

export interface ClipRosterEntry {
  id: string;
  team: 'home' | 'away';
  num: number;
  name: string;
  role: string;
}

export interface ClipEvent {
  id: string;
  t: number;
  type: string;
  sub_type?: string | null;
  outcome?: string | null;
  team: string;
  player_id?: string | null;
  player?: string | null;
  secondary_id?: string | null;
  secondary?: string | null;
  x?: number | null;
  y?: number | null;
  end_x?: number | null;
  end_y?: number | null;
}

export interface ClipFrame {
  t: number;
  ball: [number, number, number];
  p: Array<[number, number] | null>;
}

export interface ClipData {
  event_id: string;
  status: string;
  period: number;
  clock: string;
  event_type: string;
  team: string;
  player: string;
  fps: number;
  pre_s: number;
  post_s: number;
  score_before: [number, number];
  score_after: [number, number];
  roster: ClipRosterEntry[];
  frames: ClipFrame[];
  events: ClipEvent[];
}

export interface ClipPlayerProps {
  eventId: string | null;
  /** Start playing as soon as the clip is ready. */
  autoPlay?: boolean;
  loop?: boolean;
  /** Play only part of the clip, in seconds relative to the event (default -10 to +10). */
  trim?: { start: number; end: number };
  /** Large lower-third title shown for the first moments of playback. */
  title?: string;
  /** Caption shown along the bottom while playing. */
  caption?: string;
  /** Label shown in the corner badge. */
  badge?: string;
  /** Called when playback reaches the end of the (trimmed) clip. */
  onEnded?: () => void;
  /** Hides the scrubber and buttons (used by the auto-playing reel). */
  hideControls?: boolean;
  /** External play/pause control (used by the highlight reel). */
  paused?: boolean;
  /** External speed control (used by the highlight reel). */
  playbackSpeed?: number;
  className?: string;
}

const HOME_COLOR = '#EF0107';
const AWAY_COLOR = '#6CABDD';
const PITCH_L = 105;
const PITCH_W = 68;
const clipCache = new Map<string, ClipData>();

function clockToSeconds(clock: string): number {
  const [m, s] = (clock || '0:0').split(':').map((v) => parseInt(v, 10));
  return (m || 0) * 60 + (s || 0);
}

function formatClock(totalSeconds: number): string {
  const t = Math.max(0, Math.round(totalSeconds));
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
}

function isHomeTeam(team: string): boolean {
  const t = (team || '').toLowerCase();
  return t === 'home' || t.includes('northbridge');
}

export const ClipPlayer: React.FC<ClipPlayerProps> = ({
  eventId,
  autoPlay = true,
  loop = false,
  trim,
  title,
  caption,
  badge,
  onEnded,
  hideControls = false,
  paused,
  playbackSpeed,
  className = '',
}) => {
  const [clip, setClip] = useState<ClipData | null>(null);
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'preparing' | 'error'>('idle');
  const [playing, setPlaying] = useState<boolean>(autoPlay);
  const [speed, setSpeed] = useState<number>(1);
  const [time, setTime] = useState<number>(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });
  const timeRef = useRef<number>(0);
  const playingRef = useRef<boolean>(autoPlay);
  const speedRef = useRef<number>(1);
  const clipRef = useRef<ClipData | null>(null);
  const endedRef = useRef<boolean>(false);
  const onEndedRef = useRef(onEnded);
  const loopRef = useRef(loop);
  const trimRef = useRef(trim);

  onEndedRef.current = onEnded;
  loopRef.current = loop;
  trimRef.current = trim;
  playingRef.current = playing;
  speedRef.current = speed;
  clipRef.current = clip;

  const startT = (): number => trimRef.current?.start ?? -(clipRef.current?.pre_s ?? 10);
  const endT = (): number => trimRef.current?.end ?? (clipRef.current?.post_s ?? 10);

  // ── Load the clip (poll while the backend is still recording it) ──────────
  useEffect(() => {
    if (!eventId) {
      setClip(null);
      setLoadState('idle');
      return;
    }
    const cached = clipCache.get(eventId);
    if (cached) {
      setClip(cached);
      setLoadState('idle');
      return;
    }
    let cancelled = false;
    let timer: number | undefined;
    setClip(null);
    setLoadState('loading');
    const fetchClip = () => {
      fetch(`/api/clips/${encodeURIComponent(eventId)}`)
        .then(async (res) => {
          if (cancelled) return;
          if (res.status === 200) {
            const data: ClipData = await res.json();
            clipCache.set(eventId, data);
            setClip(data);
            setLoadState('idle');
          } else if (res.status === 202) {
            setLoadState('preparing');
            timer = window.setTimeout(fetchClip, 2500);
          } else {
            setLoadState('error');
          }
        })
        .catch(() => {
          if (!cancelled) setLoadState('error');
        });
    };
    fetchClip();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [eventId]);

  // Restart from the beginning of the (trimmed) window whenever a new clip is shown.
  useEffect(() => {
    if (!clip) return;
    const t0 = trim?.start ?? -clip.pre_s;
    timeRef.current = t0;
    endedRef.current = false;
    setTime(t0);
    setPlaying(paused === undefined ? autoPlay : !paused);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip, trim?.start, trim?.end]);

  useEffect(() => {
    if (paused !== undefined) setPlaying(!paused);
  }, [paused]);

  useEffect(() => {
    if (playbackSpeed) setSpeed(playbackSpeed);
  }, [playbackSpeed]);

  // ── Drawing ───────────────────────────────────────────────────────────────
  const draw = useCallback((t: number) => {
    const canvas = canvasRef.current;
    const data = clipRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const { w, h, dpr } = sizeRef.current;
    if (w < 10 || h < 10) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const pad = 18;
    const scale = Math.min((w - pad * 2) / PITCH_L, (h - pad * 2) / PITCH_W);
    const ox = (w - PITCH_L * scale) / 2;
    const oy = (h - PITCH_W * scale) / 2;
    const X = (x: number) => ox + x * scale;
    const Y = (y: number) => oy + y * scale;

    // Pitch
    ctx.fillStyle = '#06130c';
    ctx.fillRect(0, 0, w, h);
    const stripes = 14;
    for (let i = 0; i < stripes; i++) {
      ctx.fillStyle = i % 2 === 0 ? '#1d5a2c' : '#216532';
      ctx.fillRect(X((PITCH_L / stripes) * i), Y(0), (PITCH_L / stripes) * scale + 0.5, PITCH_W * scale);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.78)';
    ctx.lineWidth = 1.4;
    ctx.strokeRect(X(0), Y(0), PITCH_L * scale, PITCH_W * scale);
    ctx.beginPath();
    ctx.moveTo(X(PITCH_L / 2), Y(0));
    ctx.lineTo(X(PITCH_L / 2), Y(PITCH_W));
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(X(PITCH_L / 2), Y(PITCH_W / 2), 9.15 * scale, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.beginPath();
    ctx.arc(X(PITCH_L / 2), Y(PITCH_W / 2), 2, 0, Math.PI * 2);
    ctx.fill();
    for (const side of [0, 1]) {
      const dir = side === 0 ? 1 : -1;
      const gx = side === 0 ? 0 : PITCH_L;
      const box = (depth: number, width: number) =>
        ctx.strokeRect(side === 0 ? X(gx) : X(gx - depth), Y((PITCH_W - width) / 2), depth * scale, width * scale);
      box(16.5, 40.32);
      box(5.5, 18.32);
      ctx.beginPath();
      ctx.arc(X(gx + dir * 11), Y(PITCH_W / 2), 1.6, 0, Math.PI * 2);
      ctx.fill();
      const a = Math.acos(5.5 / 9.15);
      ctx.beginPath();
      if (side === 0) ctx.arc(X(11), Y(PITCH_W / 2), 9.15 * scale, -a, a);
      else ctx.arc(X(PITCH_L - 11), Y(PITCH_W / 2), 9.15 * scale, Math.PI - a, Math.PI + a);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.95)';
      ctx.strokeRect(side === 0 ? X(-2) : X(PITCH_L), Y((PITCH_W - 7.32) / 2), 2 * scale, 7.32 * scale);
      ctx.strokeStyle = 'rgba(255,255,255,0.78)';
    }
    if (!data || data.frames.length === 0) return;

    // Interpolated state at time t
    const frames = data.frames;
    const first = frames[0].t;
    const pos = Math.max(0, Math.min(frames.length - 1, (t - first) * data.fps));
    const i0 = Math.floor(pos);
    const i1 = Math.min(frames.length - 1, i0 + 1);
    const a = pos - i0;
    const f0 = frames[i0];
    const f1 = frames[i1];
    const lerp = (p: number, q: number) => p + (q - p) * a;
    const ballX = lerp(f0.ball[0], f1.ball[0]);
    const ballY = lerp(f0.ball[1], f1.ball[1]);
    const ballZ = lerp(f0.ball[2], f1.ball[2]);

    const actorIds = new Set<string>();
    const labelled: Array<{ id: string; text: string }> = [];
    const active = data.events.filter((e) => e.t <= t && t - e.t <= 1.8);
    const playerPos = (rosterIndex: number): [number, number] | null => {
      const p0 = f0.p[rosterIndex];
      const p1 = f1.p[rosterIndex];
      if (p0 && p1) return [lerp(p0[0], p1[0]), lerp(p0[1], p1[1])];
      return p0 || p1;
    };
    const indexById = new Map<string, number>();
    data.roster.forEach((r, idx) => indexById.set(r.id, idx));

    // Action lines (passes, shots, goals) that fade out after they happen
    for (const e of active) {
      if (e.x == null || e.y == null || e.end_x == null || e.end_y == null) continue;
      if (!['pass', 'shot', 'goal'].includes(e.type)) continue;
      const fade = Math.max(0, 1 - (t - e.t) / 1.8);
      const isGoal = e.type === 'goal';
      ctx.strokeStyle = isGoal ? `rgba(255,230,0,${0.25 + fade * 0.75})` : e.type === 'shot' ? `rgba(255,120,60,${fade})` : `rgba(255,255,255,${fade * 0.7})`;
      ctx.lineWidth = isGoal ? 3 : 2;
      ctx.setLineDash(e.type === 'pass' ? [6, 5] : []);
      ctx.beginPath();
      ctx.moveTo(X(e.x), Y(e.y));
      ctx.lineTo(X(e.end_x), Y(e.end_y));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Highlight the actors of the clip's own event around the moment it happens
    const mainEvent = data.events.find((e) => e.id === data.event_id);
    if (mainEvent && t >= mainEvent.t - 1.2 && t <= mainEvent.t + 2.5) {
      if (mainEvent.player_id) actorIds.add(mainEvent.player_id);
      if (mainEvent.player_id && mainEvent.player) labelled.push({ id: mainEvent.player_id, text: mainEvent.player });
      if (mainEvent.secondary_id && mainEvent.secondary && mainEvent.type !== 'pass') {
        labelled.push({ id: mainEvent.secondary_id, text: mainEvent.secondary });
      }
    }

    // Players
    const radius = Math.max(6, Math.min(11, scale * 1.15));
    data.roster.forEach((r, idx) => {
      const p = playerPos(idx);
      if (!p) return;
      const cx = X(p[0]);
      const cy = Y(p[1]);
      const color = r.team === 'home' ? HOME_COLOR : AWAY_COLOR;
      if (actorIds.has(r.id)) {
        const pulse = 1 + 0.25 * Math.sin(t * 9);
        ctx.strokeStyle = '#ffe600';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(cx, cy, (radius + 5) * pulse, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.beginPath();
      ctx.ellipse(cx + 1.5, cy + 2.5, radius, radius * 0.7, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = r.role === 'GK' ? (r.team === 'home' ? '#ff9a3c' : '#3cf0b4') : color;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.font = `700 ${Math.round(radius * 1.05)}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(r.num), cx, cy + 0.5);
    });

    // Name labels for the actors
    ctx.font = '700 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    for (const item of labelled) {
      const idx = indexById.get(item.id);
      if (idx === undefined) continue;
      const p = playerPos(idx);
      if (!p) continue;
      const text = item.text;
      const tw = ctx.measureText(text).width + 12;
      const lx = Math.max(tw / 2 + 2, Math.min(w - tw / 2 - 2, X(p[0])));
      const ly = Y(p[1]) - radius - 8;
      ctx.fillStyle = 'rgba(8,11,15,0.85)';
      ctx.fillRect(lx - tw / 2, ly - 16, tw, 18);
      ctx.fillStyle = '#ffe600';
      ctx.fillText(text, lx, ly - 2);
    }

    // Ball with a short trail
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let k = 6; k >= 0; k--) {
      const fi = Math.max(0, Math.min(frames.length - 1, i0 - k));
      const fb = frames[fi].ball;
      if (k === 6) ctx.moveTo(X(fb[0]), Y(fb[1]));
      else ctx.lineTo(X(fb[0]), Y(fb[1]));
    }
    ctx.lineTo(X(ballX), Y(ballY));
    ctx.stroke();
    const lift = Math.min(14, ballZ * 3);
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.beginPath();
    ctx.ellipse(X(ballX), Y(ballY) + 2, 4.5, 3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#111111';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(X(ballX), Y(ballY) - lift, 5.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }, []);

  // ── Size handling ─────────────────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      sizeRef.current = { w: rect.width, h: rect.height, dpr };
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      draw(timeRef.current);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, [draw]);

  // ── Playback loop ─────────────────────────────────────────────────────────
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let shown = -999;
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const data = clipRef.current;
      if (data && playingRef.current) {
        let t = timeRef.current + dt * speedRef.current;
        const end = endT();
        if (t >= end) {
          if (loopRef.current) {
            t = startT();
          } else {
            t = end;
            if (!endedRef.current) {
              endedRef.current = true;
              setPlaying(false);
              onEndedRef.current?.();
            }
          }
        }
        timeRef.current = t;
      }
      draw(timeRef.current);
      if (Math.abs(timeRef.current - shown) > 0.05) {
        shown = timeRef.current;
        setTime(timeRef.current);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draw]);

  // ── Controls ──────────────────────────────────────────────────────────────
  const togglePlay = () => {
    if (!clip) return;
    if (!playing && timeRef.current >= endT() - 0.05) {
      timeRef.current = startT();
      endedRef.current = false;
    }
    endedRef.current = false;
    setPlaying((p) => !p);
  };
  const restart = () => {
    timeRef.current = startT();
    endedRef.current = false;
    setTime(startT());
    setPlaying(true);
  };
  const seek = (value: number) => {
    timeRef.current = value;
    endedRef.current = false;
    setTime(value);
    draw(value);
  };

  const rangeStart = trim?.start ?? -(clip?.pre_s ?? 10);
  const rangeEnd = trim?.end ?? (clip?.post_s ?? 10);
  const eventSeconds = clip ? clockToSeconds(clip.clock) : 0;
  const matchClock = formatClock(eventSeconds + time);
  const afterScore = time >= (clip?.event_type === 'goal' ? 1.2 : 0);
  const score = clip ? (afterScore ? clip.score_after : clip.score_before) : [0, 0];
  const showTitle = Boolean(title) && time - rangeStart < 2.2;
  const markers = clip ? clip.events.filter((e) => ['goal', 'shot', 'card', 'substitution'].includes(e.type) && e.t >= rangeStart && e.t <= rangeEnd) : [];
  const eventPct = ((0 - rangeStart) / Math.max(0.1, rangeEnd - rangeStart)) * 100;

  return (
    <div className={`clip-player ${className}`}>
      <style>{`
        .clip-player { display: flex; flex-direction: column; gap: 8px; width: 100%; }
        .clip-stage { position: relative; width: 100%; aspect-ratio: 1.62; background: #06130c; border-radius: 10px;
          overflow: hidden; border: 1px solid var(--color-border-emphasis, #2d3f55); }
        .clip-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
        .clip-badge { position: absolute; top: 10px; left: 10px; display: flex; gap: 6px; align-items: center;
          background: rgba(8,11,15,0.82); border: 1px solid rgba(233,0,82,0.7); color: #fff; border-radius: 4px;
          padding: 3px 8px; font: 800 10px var(--font-mono, monospace); letter-spacing: 0.08em; }
        .clip-badge i { width: 7px; height: 7px; border-radius: 50%; background: #e90052; animation: clipPulse 1s infinite; }
        @keyframes clipPulse { 50% { opacity: 0.25; } }
        .clip-score { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); display: flex; align-items: center;
          gap: 8px; background: rgba(8,11,15,0.88); border: 1px solid var(--color-border-emphasis, #2d3f55);
          border-radius: 6px; padding: 4px 12px; font: 800 14px var(--font-mono, monospace); color: #fff; white-space: nowrap; }
        .clip-score .h { color: ${HOME_COLOR}; } .clip-score .a { color: ${AWAY_COLOR}; }
        .clip-score .clock { color: #00ff87; font-size: 12px; }
        .clip-title { position: absolute; left: 0; bottom: 56px; max-width: 80%; background: linear-gradient(90deg, #38003c, rgba(56,0,60,0.92));
          border-left: 5px solid #00ff87; color: #fff; padding: 8px 16px; font: 800 18px var(--font-display, sans-serif);
          animation: clipSlide 0.35s ease-out; }
        @keyframes clipSlide { from { transform: translateX(-30px); opacity: 0; } }
        .clip-caption { position: absolute; left: 0; right: 0; bottom: 0; padding: 18px 14px 8px; color: #fff;
          display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
          background: linear-gradient(180deg, transparent, rgba(8,11,15,0.92)); font: 600 12px/1.4 var(--font-display, sans-serif); }
        .clip-empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 6px; color: var(--color-text-secondary, #8b9bb4); font-size: 12px; text-align: center; padding: 16px; }
        .clip-controls { display: flex; align-items: center; gap: 10px; }
        .clip-btn { background: var(--color-bg-overlay, #141c26); color: var(--color-text-primary, #f0f4f8);
          border: 1px solid var(--color-border-emphasis, #2d3f55); border-radius: 6px; padding: 5px 11px;
          font: 700 12px var(--font-display, sans-serif); cursor: pointer; }
        .clip-btn:hover { border-color: var(--color-accent-green, #00ff87); color: var(--color-accent-green, #00ff87); }
        .clip-btn.active { background: var(--color-pl-purple, #38003c); border-color: var(--color-accent-green, #00ff87); color: var(--color-accent-green, #00ff87); }
        .clip-scrub { position: relative; flex: 1; height: 26px; display: flex; align-items: center; }
        .clip-scrub input[type=range] { width: 100%; accent-color: #00ff87; margin: 0; }
        .clip-mark { position: absolute; top: 0; width: 2px; height: 8px; background: #ffe600; pointer-events: none; }
        .clip-mark.main { background: #e90052; height: 12px; width: 3px; }
        .clip-time { font: 700 11px var(--font-mono, monospace); color: var(--color-text-secondary, #8b9bb4); min-width: 150px; text-align: right; }
      `}</style>

      <div className="clip-stage" ref={containerRef}>
        <canvas ref={canvasRef} className="clip-canvas" role="img" aria-label="Replay of the match moment on a 2D pitch" />
        {clip && (
          <>
            <div className="clip-badge"><i />{badge || 'REPLAY · ±10 s'}</div>
            <div className="clip-score">
              <span className="h">NBL {score[0]}</span>
              <span>-</span>
              <span className="a">{score[1]} HSC</span>
              <span className="clock">{matchClock}</span>
            </div>
            {showTitle && <div className="clip-title">{title}</div>}
            {caption && <div className="clip-caption">{caption}</div>}
          </>
        )}
        {!clip && (
          <div className="clip-empty" role="status">
            {loadState === 'error' ? (
              <span>Replay unavailable for this moment.</span>
            ) : eventId ? (
              <>
                <strong style={{ color: '#fff' }}>{loadState === 'preparing' ? 'Recording this replay…' : 'Loading replay…'}</strong>
                <span>
                  {loadState === 'preparing'
                    ? 'The clip is cut from the match simulation; this takes about a minute the first time.'
                    : 'Fetching 20 seconds of tracking data.'}
                </span>
              </>
            ) : (
              <span>Select a moment to watch the replay.</span>
            )}
          </div>
        )}
      </div>

      {!hideControls && (
        <div className="clip-controls">
          <button className="clip-btn" onClick={togglePlay} disabled={!clip} aria-label={playing ? 'Pause replay' : 'Play replay'}>
            {playing ? '❚❚ Pause' : '▶ Play'}
          </button>
          <button className="clip-btn" onClick={restart} disabled={!clip} aria-label="Restart replay">
            ↺
          </button>
          <div className="clip-scrub">
            {markers.map((m) => (
              <span
                key={m.id}
                className={`clip-mark ${m.id === eventId ? 'main' : ''}`}
                style={{ left: `calc(${((m.t - rangeStart) / Math.max(0.1, rangeEnd - rangeStart)) * 100}% - 1px)` }}
                title={`${m.type} ${m.player ?? ''}`}
              />
            ))}
            <span className="clip-mark main" style={{ left: `${eventPct}%` }} />
            <input
              type="range"
              min={rangeStart}
              max={rangeEnd}
              step={0.04}
              value={Math.max(rangeStart, Math.min(rangeEnd, time))}
              onChange={(e) => seek(parseFloat(e.target.value))}
              disabled={!clip}
              aria-label="Replay position"
            />
          </div>
          {[0.5, 1, 2].map((s) => (
            <button key={s} className={`clip-btn ${speed === s ? 'active' : ''}`} onClick={() => setSpeed(s)}>
              {s}x
            </button>
          ))}
          <span className="clip-time">
            {time < 0 ? '−' : '+'}
            {Math.abs(time).toFixed(1)} s · {matchClock}
          </span>
        </div>
      )}
    </div>
  );
};
