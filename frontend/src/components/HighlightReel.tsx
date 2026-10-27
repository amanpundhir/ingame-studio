/**
 * InGame Studio - Match highlight reel.
 *
 * A short "video" recap of the match, built the way broadcasters cut one: an opening
 * title card, then the key moments one after another (a few seconds of replay each, with
 * the score bug and a caption), and a full-time card. Every clip is real tracking data
 * from the match; see ClipPlayer.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { ClipPlayer } from './ClipPlayer';
import type { MatchRecapData } from '../types';

export interface ReelHighlight {
  id: string;
  event_id?: string;
  minute: string;
  clock?: string;
  title: string;
  subtitle?: string;
  description?: string;
  type: string;
  team?: string;
  score?: string;
}

export interface HighlightReelProps {
  highlights: ReelHighlight[];
  recap?: MatchRecapData | null;
  /** Changes each time the viewer picks a moment from the list beside the reel. */
  jumpTo?: { id: string; n: number } | null;
  onActiveChange?: (id: string) => void;
}

const CLIP_TRIM = { start: -7, end: 5 };
const INTRO_MS = 3200;

export const HighlightReel: React.FC<HighlightReelProps> = ({ highlights, recap, jumpTo, onActiveChange }) => {
  const clips = useMemo(() => highlights.filter((h) => h.event_id), [highlights]);
  // Stages: 0 = opening card, 1..n = clips, n + 1 = full-time card
  const [stage, setStage] = useState<number>(0);
  const [started, setStarted] = useState<boolean>(false);
  const [playing, setPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1);
  const last = clips.length + 1;

  const score = recap?.final_score;
  const homeTeam = score?.home_team ?? 'Northbridge Lions';
  const awayTeam = score?.away_team ?? 'Harbourside City';
  const goals = clips.filter((h) => h.type === 'goal');
  const motm = recap?.man_of_the_match;

  // Jump to a clip chosen elsewhere on the page (the list beside the reel).
  useEffect(() => {
    if (!jumpTo) return;
    const idx = clips.findIndex((h) => h.id === jumpTo.id);
    if (idx >= 0) {
      setStage(idx + 1);
      setStarted(true);
      setPlaying(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpTo?.n]);

  const goTo = (next: number) => {
    const bounded = Math.max(0, Math.min(last, next));
    setStage(bounded);
    setPlaying(true);
    if (bounded >= 1 && bounded <= clips.length) onActiveChange?.(clips[bounded - 1].id);
  };

  // The opening card advances by itself
  useEffect(() => {
    if (!started || !playing || stage !== 0) return;
    const timer = window.setTimeout(() => goTo(1), INTRO_MS / speed);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [started, playing, stage, speed]);

  const current = stage >= 1 && stage <= clips.length ? clips[stage - 1] : null;

  const card = (children: React.ReactNode) => (
    <div className="reel-card">{children}</div>
  );

  return (
    <div className="reel">
      <style>{`
        .reel { display: flex; flex-direction: column; gap: 10px; }
        .reel-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
        .reel-kicker { font-size: 10px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-accent-green); }
        .reel-title { margin: 0; font-size: 18px; font-weight: 800; color: var(--color-text-primary); }
        .reel-meta { font: 700 11px var(--font-mono, monospace); color: var(--color-accent-cyan); }
        .reel-frame { position: relative; }
        .reel-card { position: relative; width: 100%; aspect-ratio: 1.62; border-radius: 10px; overflow: hidden;
          border: 1px solid var(--color-border-emphasis, #2d3f55); display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 10px; text-align: center; padding: 20px;
          background: radial-gradient(circle at 30% 20%, #4b0a52 0%, #1d0422 55%, #080b0f 100%); color: #fff; }
        .reel-card .tag { font: 800 11px var(--font-mono, monospace); letter-spacing: 0.18em; color: #00ff87; }
        .reel-card .big { font: 900 clamp(22px, 4.2vw, 44px) var(--font-display, sans-serif); letter-spacing: -0.02em; }
        .reel-card .score { font: 900 clamp(34px, 7vw, 72px) var(--font-mono, monospace); }
        .reel-card .sub { font-size: 13px; color: #cdd6e4; max-width: 560px; line-height: 1.5; }
        .reel-card .goal-list { display: flex; flex-wrap: wrap; gap: 6px 16px; justify-content: center; font: 700 12px var(--font-mono, monospace); color: #ffe600; }
        .reel-poster { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          background: rgba(8,11,15,0.55); border-radius: 10px; }
        .reel-play { background: #00ff87; color: #080b0f; border: none; border-radius: 999px; padding: 14px 28px;
          font: 900 15px var(--font-display, sans-serif); cursor: pointer; box-shadow: 0 8px 30px rgba(0,255,135,0.35); }
        .reel-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .reel-btn { background: var(--color-bg-overlay, #141c26); color: var(--color-text-primary, #f0f4f8);
          border: 1px solid var(--color-border-emphasis, #2d3f55); border-radius: 6px; padding: 5px 11px;
          font: 700 12px var(--font-display, sans-serif); cursor: pointer; }
        .reel-btn:hover { border-color: var(--color-accent-green, #00ff87); color: var(--color-accent-green, #00ff87); }
        .reel-btn.active { background: var(--color-pl-purple, #38003c); border-color: var(--color-accent-green, #00ff87); color: var(--color-accent-green, #00ff87); }
        .reel-chapters { display: flex; gap: 4px; flex: 1; min-width: 220px; }
        .reel-chapter { flex: 1; height: 26px; border-radius: 4px; border: 1px solid var(--color-border-subtle, #1e2a3a);
          background: var(--color-bg-base, #080b0f); color: var(--color-text-secondary, #8b9bb4); cursor: pointer;
          font: 700 10px var(--font-mono, monospace); padding: 0; }
        .reel-chapter.done { background: rgba(0,255,135,0.15); color: #fff; }
        .reel-chapter.now { background: #00ff87; color: #080b0f; border-color: #00ff87; }
        .reel-chapter.goal { border-color: #ffe600; }
      `}</style>

      <div className="reel-head">
        <div>
          <div className="reel-kicker">Match recap video</div>
          <h2 className="reel-title">Full-time highlights</h2>
        </div>
        <div className="reel-meta">
          {clips.length} moments · replays are cut from the real tracking data
        </div>
      </div>

      <div className="reel-frame">
        {stage === 0 &&
          card(
            <>
              <div className="tag">INGAME · MATCH HIGHLIGHTS</div>
              <div className="big">
                {homeTeam} v {awayTeam}
              </div>
              <div className="sub">{recap?.headline || 'The key moments of the match.'}</div>
            </>
          )}

        {current && (
          <ClipPlayer
            key={current.id}
            eventId={current.event_id ?? null}
            autoPlay
            hideControls
            paused={!playing}
            playbackSpeed={speed}
            trim={CLIP_TRIM}
            title={current.title}
            caption={current.description || current.subtitle}
            badge={`HIGHLIGHT ${stage}/${clips.length} · ${current.minute}`}
            onEnded={() => window.setTimeout(() => goTo(stage + 1), 500)}
          />
        )}

        {stage === last &&
          card(
            <>
              <div className="tag">FULL-TIME</div>
              <div className="score">
                {score ? `${score.home} - ${score.away}` : '— - —'}
              </div>
              <div className="big" style={{ fontSize: 'clamp(16px, 2.6vw, 26px)' }}>
                {homeTeam} v {awayTeam}
              </div>
              {goals.length > 0 && (
                <div className="goal-list">
                  {goals.map((g) => (
                    <span key={g.id}>
                      ⚽ {g.minute} {g.title.replace(/^GOAL!\s*/, '')}
                    </span>
                  ))}
                </div>
              )}
              {motm?.name && motm.name !== 'Not available' && (
                <div className="sub">
                  Player of the match: <strong>{motm.name}</strong> ({motm.team}), rated {motm.rating}
                </div>
              )}
              <button className="reel-btn" onClick={() => goTo(0)}>
                ↺ Watch again
              </button>
            </>
          )}

        {!started && (
          <div className="reel-poster">
            <button
              className="reel-play"
              onClick={() => {
                setStarted(true);
                setPlaying(true);
              }}
              aria-label="Play the match highlights video"
            >
              ▶ Play match highlights
            </button>
          </div>
        )}
      </div>

      <div className="reel-bar">
        <button className="reel-btn" onClick={() => goTo(stage - 1)} disabled={!started || stage === 0} aria-label="Previous">
          ⏮
        </button>
        <button
          className="reel-btn"
          onClick={() => {
            if (!started) setStarted(true);
            setPlaying((p) => (started ? !p : true));
          }}
          aria-label={playing && started ? 'Pause' : 'Play'}
        >
          {playing && started ? '❚❚ Pause' : '▶ Play'}
        </button>
        <button className="reel-btn" onClick={() => goTo(stage + 1)} disabled={!started || stage === last} aria-label="Next">
          ⏭
        </button>
        <div className="reel-chapters" role="tablist" aria-label="Highlights">
          {clips.map((h, i) => (
            <button
              key={h.id}
              role="tab"
              aria-selected={stage === i + 1}
              className={`reel-chapter ${stage === i + 1 ? 'now' : stage > i + 1 ? 'done' : ''} ${h.type === 'goal' ? 'goal' : ''}`}
              onClick={() => {
                setStarted(true);
                goTo(i + 1);
              }}
              title={h.title}
            >
              {h.type === 'goal' ? '⚽' : h.type === 'card' ? '🟥' : ''} {h.minute}
            </button>
          ))}
        </div>
        {[1, 2].map((s) => (
          <button key={s} className={`reel-btn ${speed === s ? 'active' : ''}`} onClick={() => setSpeed(s)}>
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
};
