/**
 * InGame Studio - Tab 5: Condensed Match Story & Post-Game Recap
 * 
 * Features:
 * 1. Match Outcome Header:
 *    - Final scoreline (Northbridge Lions 1 - 1 Harbourside City) with team crests and high-contrast kits
 *    - Match result summary headline
 *    - Player of the Match (MOTM) badge and key performance metrics
 *    - Match stats summary (Possession, xG, Shots on target)
 * 2. Condensed 5-Minute Pitch Player:
 *    - Pitch view playing condensed match highlight sequences
 *    - Canvas-based IFAB pitch visualization (turf shading, 22 players with squad numbers, ball altitude & shadow)
 *    - Video-style timeline scrubber (00:00 to 90:00) with draggable slider and key moment markers
 *    - Play / Pause controls with keyboard support
 *    - Speed controls: 1x, 2x, 4x
 *    - Telestrator shot & pass vectors during highlight sequences
 * 3. Highlights Sequence:
 *    - Chronological list of key highlight moments (goals, cards, big chances, saves, turnovers)
 *    - Clickable items to seek the pitch player directly to that moment
 *    - Highlight badges with semantic colors and icons
 * 4. AI Match Story Recap:
 *    - Full match narrative synthesizing both halves tailored to active persona and language
 *    - Tactical entropy and rhythm breakdown (Chaos vs Control phases)
 * 
 * Strictly conforms to ingame-ui-design design system.
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  MatchRecapData,
  MatchStatsData,
  PlayerAnalytics,
  MatchEvent,
  ViewerPersona,
  LanguageCode,
  ClubPerspective,
  TeamAllegiance,
  HighlightMilestone,
} from '../types';
import {
  CANONICAL_COLORS,
  PITCH_TOKENS,
  PERSONA_COLORS,
} from '../constants/tokens';

import { HighlightReel, ReelHighlight } from './HighlightReel';

export interface RecapTabProps {
  recapData?: MatchRecapData | null;
  stats?: MatchStatsData | null;
  players?: PlayerAnalytics[];
  events?: MatchEvent[];
  activePersona?: ViewerPersona;
  language?: LanguageCode;
  favoriteClub?: ClubPerspective;
  teamAllegiance?: TeamAllegiance;
  onSeekMoment?: (minute: number) => void;
  onExploreAnalytics?: () => void;
}

// Highlight moments are derived by the backend from the events that actually happened,
// together with the 22-player positions at each moment.
interface HighlightPlayer {
  id: string;
  name: string;
  num: number;
  role: string;
  team: 'home' | 'away' | string;
  x: number;
  y: number;
}

interface PitchHighlightMoment {
  id: string;
  second: number; // match second (0 to 5670)
  clock: string;
  minute: string;
  title: string;
  subtitle: string;
  type: 'goal' | 'chance' | 'tackle' | 'turnover' | 'card';
  team: string;
  score: string;
  description: string;
  shooterId?: string | null;
  ballPos: { x: number; y: number; z: number };
  vector?: { startX: number; startY: number; endX: number; endY: number };
  players: HighlightPlayer[];
}

const TOTAL_MATCH_SECONDS = 5670; // 94:30

export const RecapTab: React.FC<RecapTabProps> = ({
  recapData,
  stats,
  players = [],
  events = [],
  activePersona = 'tactical',
  language = 'en',
  favoriteClub = 'Northbridge Lions',
  teamAllegiance = 'neutral',
  onSeekMoment,
  onExploreAnalytics,
}) => {
  // Scrubber & pitch player state
  const highlights = useMemo<PitchHighlightMoment[]>(
    () => ((recapData?.highlights as PitchHighlightMoment[] | undefined) ?? []),
    [recapData]
  );
  const [currentSecond, setCurrentSecond] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 2 | 4>(1);
  const [activeHighlightId, setActiveHighlightId] = useState<string>('');
  const [reelJump, setReelJump] = useState<{ id: string; n: number } | null>(null);
  const [hoverScrubberTime, setHoverScrubberTime] = useState<number | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastTickTimeRef = useRef<number>(performance.now());

  // Find the highlight closest to the scrubber position
  const currentHighlight = useMemo<PitchHighlightMoment | null>(() => {
    if (highlights.length === 0) return null;
    let closest = highlights[0];
    let minDiff = Math.abs(currentSecond - closest.second);
    for (const h of highlights) {
      const diff = Math.abs(currentSecond - h.second);
      if (diff < minDiff) {
        minDiff = diff;
        closest = h;
      }
    }
    return closest;
  }, [currentSecond, highlights]);

  // Keep active highlight in sync
  useEffect(() => {
    if (currentHighlight && currentHighlight.id !== activeHighlightId) {
      setActiveHighlightId(currentHighlight.id);
    }
  }, [currentHighlight, activeHighlightId]);

  // Start on the first goal (or first highlight) once highlights arrive
  useEffect(() => {
    if (highlights.length === 0) {
      setCurrentSecond(0);
      return;
    }
    setCurrentSecond((prev) => (prev === 0 ? (highlights.find((h) => h.type === 'goal') ?? highlights[0]).second : prev));
  }, [highlights]);

  // Format seconds to MM:SS
  const formatTime = (secs: number): string => {
    const clamped = Math.max(0, Math.min(TOTAL_MATCH_SECONDS, Math.floor(secs)));
    const m = Math.floor(clamped / 60);
    const s = clamped % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Seek pitch player to a specific second
  const seekToSecond = useCallback(
    (second: number) => {
      const clamped = Math.max(0, Math.min(TOTAL_MATCH_SECONDS, second));
      setCurrentSecond(clamped);
      if (onSeekMoment) {
        onSeekMoment(Math.floor(clamped / 60));
      }
    },
    [onSeekMoment]
  );

  // Seek to specific highlight moment
  const seekToHighlight = (moment: PitchHighlightMoment) => {
    setReelJump((prev) => ({ id: moment.id, n: (prev?.n ?? 0) + 1 }));
    seekToSecond(moment.second);
    setActiveHighlightId(moment.id);
    setIsPlaying(false);
  };

  // Keyboard shortcut: Spacebar toggles playback
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && (e.target as HTMLElement)?.tagName !== 'INPUT') {
        e.preventDefault();
        setIsPlaying((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Main playback loop
  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      return;
    }

    lastTickTimeRef.current = performance.now();

    const loop = (time: number) => {
      const deltaMs = time - lastTickTimeRef.current;
      lastTickTimeRef.current = time;

      // Realtime progression scaled by playbackSpeed
      // 5-minute condensed match: 94 minutes condensed into 300 real seconds (~19x base)
      // Multiplied by playbackSpeed (1x, 2x, 4x)
      const baseCompressionRate = 18.9; // 5670s / 300s
      const incrementSeconds = (deltaMs / 1000) * baseCompressionRate * playbackSpeed;

      setCurrentSecond((prev) => {
        const next = prev + incrementSeconds;
        if (next >= TOTAL_MATCH_SECONDS) {
          setIsPlaying(false);
          return TOTAL_MATCH_SECONDS;
        }
        return next;
      });

      animationFrameRef.current = requestAnimationFrame(loop);
    };

    animationFrameRef.current = requestAnimationFrame(loop);
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, playbackSpeed]);

  // Pitch canvas drawing logic
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const pitchLen = PITCH_TOKENS.length; // 105m
    const pitchWid = PITCH_TOKENS.width; // 68m

    const scaleX = (xMeters: number) => (xMeters / pitchLen) * width;
    const scaleY = (yMeters: number) => (yMeters / pitchWid) * height;

    // 1. Clear background
    ctx.clearRect(0, 0, width, height);

    // 2. Alternating grass stripes (turf bands)
    const stripeCount = 10;
    const stripeWidth = width / stripeCount;
    for (let i = 0; i < stripeCount; i++) {
      ctx.fillStyle = i % 2 === 0 ? PITCH_TOKENS.grassDark : PITCH_TOKENS.grassLight;
      ctx.fillRect(i * stripeWidth, 0, stripeWidth, height);
    }

    // 3. Pitch lines & markings
    ctx.strokeStyle = PITCH_TOKENS.lineColor;
    ctx.lineWidth = 1.5;

    // Touchlines & Goal lines boundary
    ctx.strokeRect(0, 0, width, height);

    // Halfway line
    ctx.beginPath();
    ctx.moveTo(width / 2, 0);
    ctx.lineTo(width / 2, height);
    ctx.stroke();

    // Center circle
    ctx.beginPath();
    ctx.arc(width / 2, height / 2, scaleX(PITCH_TOKENS.centerCircleRadius), 0, Math.PI * 2);
    ctx.stroke();

    // Center spot
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(width / 2, height / 2, 2.5, 0, Math.PI * 2);
    ctx.fill();

    // Penalty Areas (16.5m x 40.32m)
    const penBoxDepthPx = scaleX(PITCH_TOKENS.penaltyBoxDepth);
    const penBoxWidPx = scaleY(PITCH_TOKENS.penaltyBoxWidth);
    const penBoxY = (height - penBoxWidPx) / 2;

    // Home (Left) Box
    ctx.strokeRect(0, penBoxY, penBoxDepthPx, penBoxWidPx);
    // Away (Right) Box
    ctx.strokeRect(width - penBoxDepthPx, penBoxY, penBoxDepthPx, penBoxWidPx);

    // Goal Areas (5.5m x 18.32m)
    const goalAreaDepthPx = scaleX(PITCH_TOKENS.goalAreaDepth);
    const goalAreaWidPx = scaleY(PITCH_TOKENS.goalAreaWidth);
    const goalAreaY = (height - goalAreaWidPx) / 2;

    ctx.strokeRect(0, goalAreaY, goalAreaDepthPx, goalAreaWidPx);
    ctx.strokeRect(width - goalAreaDepthPx, goalAreaY, goalAreaDepthPx, goalAreaWidPx);

    // Penalty spots (11m)
    const penSpotXPx = scaleX(PITCH_TOKENS.penaltySpotDistance);
    ctx.beginPath();
    ctx.arc(penSpotXPx, height / 2, 2.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(width - penSpotXPx, height / 2, 2.5, 0, Math.PI * 2);
    ctx.fill();

    // Goal Nets (exterior)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.strokeRect(-8, goalAreaY + 10, 8, goalAreaWidPx - 20);
    ctx.strokeRect(width, goalAreaY + 10, 8, goalAreaWidPx - 20);

    // 4. Real player positions at the active highlight moment
    const active = currentHighlight;
    if (!active) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
      ctx.font = '14px "Outfit", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Highlights appear here as the match is played or simulated.', width / 2, height / 2);
      return;
    }
    const isGoalMoment = active.type === 'goal';

    // 5. Draw Telestrator Vectors
    if (active.vector) {
      const v = active.vector;
      const vStartX = scaleX(v.startX);
      const vStartY = scaleY(v.startY);
      const vEndX = scaleX(v.endX);
      const vEndY = scaleY(v.endY);

      const grad = ctx.createLinearGradient(vStartX, vStartY, vEndX, vEndY);
      grad.addColorStop(0, 'rgba(0, 255, 135, 0.2)');
      grad.addColorStop(1, isGoalMoment ? '#00ff87' : '#04f0ff');

      ctx.save();
      ctx.strokeStyle = grad;
      ctx.lineWidth = 3;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(vStartX, vStartY);
      ctx.lineTo(vEndX, vEndY);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.strokeStyle = isGoalMoment ? '#00ff87' : '#04f0ff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(vEndX, vEndY, 12, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // 6. Draw both teams from the reconstructed frame
    active.players.forEach((p) => {
      const isHome = p.team === 'home';
      const px = scaleX(p.x);
      const py = scaleY(p.y);
      const isShooter = p.id === active.shooterId;

      ctx.save();
      if (isShooter) {
        ctx.strokeStyle = '#00ff87';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(px, py, 14, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.fillStyle = p.role === 'GK'
        ? (isHome ? CANONICAL_COLORS.gkHome : CANONICAL_COLORS.gkAway)
        : (isHome ? CANONICAL_COLORS.northbridgeRed : CANONICAL_COLORS.harboursideBlue);
      ctx.beginPath();
      ctx.arc(px, py, PITCH_TOKENS.playerRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = isHome ? '#FFFFFF' : CANONICAL_COLORS.harboursideNavy;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.fillStyle = isHome ? (p.role === 'GK' ? '#000000' : '#FFFFFF') : '#1C2C5B';
      ctx.font = 'bold 9px "Roboto Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(p.num ?? ''), px, py);

      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
      ctx.font = '9px "Outfit", sans-serif';
      ctx.fillText(p.name, px, py + 15);
      ctx.restore();
    });

    // 8. Draw Ball with 3D Altitude & Shadow
    const bx = scaleX(active.ballPos.x);
    const by = scaleY(active.ballPos.y);
    const bz = active.ballPos.z;

    ctx.save();
    // Drop shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    ctx.beginPath();
    ctx.ellipse(bx + bz * 4, by + bz * 4, 5, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    // Ball glow
    ctx.shadowColor = '#FFFFFF';
    ctx.shadowBlur = isGoalMoment ? 12 : 6;

    // White ball circle
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(bx, by - bz * 6, PITCH_TOKENS.ballRadius + bz * 0.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 0.5;
    ctx.stroke();
    ctx.restore();

    // 9. Overlay Banner for Active Highlight
    ctx.save();
    ctx.fillStyle = 'rgba(8, 11, 15, 0.82)';
    ctx.fillRect(12, 12, 340, 48);
    ctx.strokeStyle = isGoalMoment ? '#00ff87' : 'rgba(255, 255, 255, 0.15)';
    ctx.lineWidth = 1;
    ctx.strokeRect(12, 12, 340, 48);

    ctx.fillStyle = isGoalMoment ? '#00ff87' : '#04f0ff';
    ctx.font = 'bold 11px "Outfit", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`${active.minute} • ${active.title.toUpperCase()}`, 24, 28);

    ctx.fillStyle = '#f0f4f8';
    ctx.font = '11px "Outfit", sans-serif';
    ctx.fillText(active.subtitle, 24, 46);
    ctx.restore();
  }, [currentHighlight]);

  // AI match story: written by the Foundry model on the server (cached per persona and language)
  const [storyNarrative, setStoryNarrative] = useState<string>('');
  const [storySource, setStorySource] = useState<string>('');
  const storyClub = teamAllegiance === 'away' ? 'Harbourside City' : teamAllegiance === 'home' ? 'Northbridge Lions' : favoriteClub;
  const matchStatus = recapData?.status;
  const eventCount = events.length;

  useEffect(() => {
    if (!recapData || eventCount === 0) {
      setStoryNarrative('');
      setStorySource('');
      return;
    }
    let cancelled = false;
    setStorySource('loading');
    const query = new URLSearchParams({ persona: activePersona, language, club: storyClub });
    fetch(`/api/story?${query.toString()}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setStoryNarrative(data.text || '');
        setStorySource(data.source || '');
      })
      .catch(() => {
        if (!cancelled) setStorySource('');
      });
    return () => {
      cancelled = true;
    };
  }, [activePersona, language, storyClub, matchStatus, eventCount, recapData?.headline]);

  // Resolved MOTM player (only when the backend has one)
  const motm = useMemo(
    () => (recapData?.man_of_the_match?.name ? recapData.man_of_the_match : null),
    [recapData]
  );

  const finalScore = recapData?.final_score ?? { home: 0, away: 0, home_team: 'Northbridge Lions', away_team: 'Harbourside City' };
  const scorersFor = (team: string): string =>
    (recapData?.turning_points ?? [])
      .filter((tp) => tp.type === 'goal' && tp.team === team)
      .map((tp) => `${tp.player} ${tp.minute} ⚽`)
      .join('  ');
  const totals = recapData?.team_totals;
  const possessionText = totals ? `${Math.round(totals.possession_pct.home)}% - ${Math.round(totals.possession_pct.away)}%` : '—';
  const xgText = recapData ? `${recapData.xg_balance.home_xg.toFixed(2)} - ${recapData.xg_balance.away_xg.toFixed(2)}` : '—';
  const shotsText = totals
    ? `${totals.shots.home} (${totals.shots_on_target.home}) - ${totals.shots.away} (${totals.shots_on_target.away})`
    : '—';
  const resultLabel = recapData?.status === 'FT'
    ? `FT ${recapData.clock} • ${finalScore.home === finalScore.away ? 'POINTS SHARED' : `${finalScore.home > finalScore.away ? finalScore.home_team : finalScore.away_team} WIN`}`
    : `${recapData?.status === 'LIVE' ? 'LIVE' : 'NOT STARTED'} ${recapData?.clock ?? ''}`;

  const isRtl = false;

  return (
    <div
      className="recap-tab-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--spacing-xl)',
        padding: 'var(--spacing-xl)',
        maxWidth: '1440px',
        margin: '0 auto',
        width: '100%',
        color: 'var(--color-text-primary)',
      }}
    >
      {/* ── SECTION 1: MATCH OUTCOME HEADER ──────────────────────────────── */}
      <header
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: 'var(--spacing-xl)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Top subtle glow banner */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            background: 'linear-gradient(90deg, #EF0107 0%, var(--color-accent-green) 50%, #6CABDD 100%)',
          }}
        />

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--spacing-lg)',
          }}
        >
          {/* Left: Scoreline & Teams */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xl)' }}>
            {/* Team Home: Northbridge Lions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: '#EF0107',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '18px',
                  boxShadow: '0 0 16px rgba(239, 1, 7, 0.4)',
                }}
              >
                NBL
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-h2)', fontWeight: 700, color: '#FFFFFF' }}>
                  Northbridge Lions
                </div>
                <div style={{ fontSize: 'var(--text-caption)', color: 'var(--color-text-secondary)' }}>
                  {scorersFor(finalScore.home_team)}
                </div>
              </div>
            </div>

            {/* Final Scoreboard Center */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '0 var(--spacing-lg)',
              }}
            >
              <div
                className="mono-stat"
                style={{
                  fontSize: 'var(--text-hero)',
                  fontWeight: 800,
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.04em',
                  color: 'var(--color-text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--spacing-md)',
                }}
              >
                <span>{finalScore.home}</span>
                <span style={{ color: 'var(--color-text-tertiary)', fontSize: '24px' }}>-</span>
                <span>{finalScore.away}</span>
              </div>
              <div
                style={{
                  fontSize: 'var(--text-micro)',
                  fontWeight: 700,
                  backgroundColor: 'rgba(0, 255, 135, 0.16)',
                  color: 'var(--color-accent-green)',
                  border: '1px solid var(--color-accent-green)',
                  borderRadius: '12px',
                  padding: '2px 10px',
                  marginTop: '4px',
                  letterSpacing: '0.06em',
                }}
              >
                {resultLabel}
              </div>
            </div>

            {/* Team Away: Harbourside City */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-h2)', fontWeight: 700, color: '#FFFFFF', textAlign: 'right' }}>
                  Harbourside City
                </div>
                <div style={{ fontSize: 'var(--text-caption)', color: 'var(--color-text-secondary)', textAlign: 'right' }}>
                  {scorersFor(finalScore.away_team)}
                </div>
              </div>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: '#6CABDD',
                  color: '#1C2C5B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '18px',
                  boxShadow: '0 0 16px rgba(108, 171, 221, 0.4)',
                }}
              >
                HSC
              </div>
            </div>
          </div>

          {/* Right: MOTM Badge Card */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-base)',
              border: '1px solid var(--color-accent-green)',
              borderRadius: '8px',
              padding: 'var(--spacing-md) var(--spacing-lg)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-md)',
              boxShadow: '0 4px 16px rgba(0, 255, 135, 0.12)',
            }}
          >
            <div
              style={{
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                backgroundColor: 'rgba(0, 255, 135, 0.16)',
                border: '2px solid var(--color-accent-green)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '20px',
              }}
            >
              ⭐
            </div>
            <div>
              <div
                style={{
                  fontSize: 'var(--text-micro)',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  color: 'var(--color-accent-green)',
                  letterSpacing: '0.06em',
                }}
              >
                Player of the Match
              </div>
              <div style={{ fontSize: 'var(--text-h3)', fontWeight: 700, color: '#FFFFFF' }}>
                {motm ? `${motm.name} (${motm.team})` : '—'}
              </div>
              <div
                className="mono-stat"
                style={{
                  fontSize: 'var(--text-caption)',
                  color: 'var(--color-text-secondary)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                Rating: <strong style={{ color: 'var(--color-accent-green)' }}>{motm?.rating ?? '—'}</strong> • {motm?.bps ?? 0} BPS • {motm?.goals ?? 0} {(motm?.goals ?? 0) === 1 ? 'Goal' : 'Goals'}
              </div>
            </div>
          </div>
        </div>

        {/* Quick Match Outcome Summary */}
        <div
          style={{
            marginTop: 'var(--spacing-lg)',
            paddingTop: 'var(--spacing-md)',
            borderTop: '1px solid var(--color-border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--spacing-md)',
          }}
        >
          <div style={{ fontSize: 'var(--text-body)', color: 'var(--color-text-secondary)', maxWidth: '820px' }}>
            {recapData?.match_story || recapData?.headline || 'The summary appears once the match is under way.'}
          </div>

          {/* Stat Pillars */}
          <div style={{ display: 'flex', gap: 'var(--spacing-lg)' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-micro)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase' }}>
                Possession
              </div>
              <div className="mono-stat" style={{ fontSize: 'var(--text-h3)', fontWeight: 700 }}>
                {possessionText}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-micro)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase' }}>
                Expected Goals (xG)
              </div>
              <div className="mono-stat" style={{ fontSize: 'var(--text-h3)', fontWeight: 700, color: 'var(--color-accent-cyan)' }}>
                {xgText}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-micro)', color: 'var(--color-text-tertiary)', textTransform: 'uppercase' }}>
                Shots (On Target)
              </div>
              <div className="mono-stat" style={{ fontSize: 'var(--text-h3)', fontWeight: 700 }}>
                {shotsText}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ── SECTION 2 & 3: CONDENSED PITCH PLAYER + HIGHLIGHTS REEL ──────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(320px, 1fr)',
          gap: 'var(--spacing-xl)',
        }}
      >
        {/* LEFT: MATCH HIGHLIGHT REEL (video-style recap cut from real tracking data) */}
        <section
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: 'var(--spacing-lg)',
          }}
        >
          <HighlightReel
            highlights={highlights as unknown as ReelHighlight[]}
            recap={recapData}
            jumpTo={reelJump}
            onActiveChange={setActiveHighlightId}
          />
        </section>

        {/* RIGHT: CHRONOLOGICAL HIGHLIGHTS SEQUENCE REEL */}
        <section
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: 'var(--spacing-lg)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ marginBottom: 'var(--spacing-md)' }}>
            <div
              style={{
                fontSize: 'var(--text-micro)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-accent-green)',
                letterSpacing: '0.06em',
              }}
            >
              Key Match Moments
            </div>
            <h3
              style={{
                fontSize: 'var(--text-h2)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                margin: '2px 0 0 0',
              }}
            >
              Highlights Sequence
            </h3>
            <p
              style={{
                fontSize: 'var(--text-caption)',
                color: 'var(--color-text-secondary)',
                margin: '2px 0 0 0',
              }}
            >
              Click any moment below to jump the pitch player and examine the action.
            </p>
          </div>

          {/* Scrollable Highlight Moments List */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--spacing-sm)',
              maxHeight: '480px',
              overflowY: 'auto',
              paddingRight: '4px',
            }}
          >
            {highlights.map((moment) => {
              const isSelected = activeHighlightId === moment.id;
              const isGoal = moment.type === 'goal';

              return (
                <div
                  key={moment.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => seekToHighlight(moment)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      seekToHighlight(moment);
                    }
                  }}
                  style={{
                    backgroundColor: isSelected
                      ? 'rgba(0, 255, 135, 0.08)'
                      : 'var(--color-bg-base)',
                    border: isSelected
                      ? '1px solid var(--color-accent-green)'
                      : '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    padding: 'var(--spacing-sm) var(--spacing-md)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--spacing-md)',
                    transition: 'background-color 0.15s ease, border-color 0.15s ease',
                  }}
                >
                  {/* Minute / Icon Badge */}
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minWidth: '40px',
                    }}
                  >
                    <span
                      className="mono-stat"
                      style={{
                        fontSize: 'var(--text-caption)',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        color: isGoal ? 'var(--color-accent-green)' : 'var(--color-accent-cyan)',
                      }}
                    >
                      {moment.minute}
                    </span>
                    <span style={{ fontSize: '16px', marginTop: '2px' }}>
                      {isGoal ? '⚽' : moment.type === 'chance' ? '🎯' : moment.type === 'tackle' ? '🛡️' : '⚡'}
                    </span>
                  </div>

                  {/* Moment Details */}
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '2px',
                      }}
                    >
                      <span
                        style={{
                          fontSize: 'var(--text-body)',
                          fontWeight: 700,
                          color: isSelected ? '#FFFFFF' : 'var(--color-text-primary)',
                        }}
                      >
                        {moment.title}
                      </span>
                      <span
                        style={{
                          fontSize: 'var(--text-micro)',
                          fontWeight: 700,
                          backgroundColor:
                            moment.team === 'Northbridge Lions' ? 'rgba(239, 1, 7, 0.2)' : 'rgba(108, 171, 221, 0.2)',
                          color: moment.team === 'Northbridge Lions' ? '#EF0107' : '#6CABDD',
                          padding: '1px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        {moment.team}
                      </span>
                    </div>

                    <p
                      style={{
                        margin: 0,
                        fontSize: 'var(--text-caption)',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.4,
                      }}
                    >
                      {moment.subtitle}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* ── SECTION 4: AI MATCH STORY RECAP PANEL ────────────────────────── */}
      <section
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: 'var(--spacing-xl)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--spacing-md)',
            marginBottom: 'var(--spacing-md)',
            borderBottom: '1px solid var(--color-border-subtle)',
            paddingBottom: 'var(--spacing-sm)',
          }}
        >
          <div>
            <div
              style={{
                fontSize: 'var(--text-micro)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-accent-green)',
                letterSpacing: '0.06em',
              }}
            >
              AI Broadcast Narrative • Multi-Agent Synthesis
            </div>
            <h3
              style={{
                fontSize: 'var(--text-h2)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                margin: '2px 0 0 0',
              }}
            >
              Full Match Story Recap
            </h3>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
            <span
              style={{
                fontSize: 'var(--text-caption)',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
                padding: '4px 10px',
                borderRadius: '16px',
                color: 'var(--color-text-secondary)',
              }}
            >
              Perspective: <strong>{activePersona.toUpperCase()}</strong>
            </span>
            <span
              style={{
                fontSize: 'var(--text-caption)',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
                padding: '4px 10px',
                borderRadius: '16px',
                color: 'var(--color-text-secondary)',
              }}
            >
              Language: <strong>{language.toUpperCase()}</strong>
            </span>
          </div>
        </div>

        {/* Narrative Box */}
        <div
          style={{
            backgroundColor: 'var(--color-bg-base)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '6px',
            padding: 'var(--spacing-lg)',
            marginBottom: 'var(--spacing-lg)',
            direction: isRtl ? 'rtl' : 'ltr',
          }}
        >
          <p
            style={{
              fontSize: 'var(--text-body)',
              color: 'var(--color-text-primary)',
              lineHeight: 1.6,
              margin: 0,
            }}
          >
            {storySource === 'loading' && !storyNarrative ? 'Writing the story…' : storyNarrative || 'The story is written once there are match events to describe.'}
          </p>
          {storySource.startsWith('azure_foundry') && (
            <div style={{ marginTop: 'var(--spacing-sm)', fontSize: 'var(--text-micro)', color: 'var(--color-text-tertiary)' }}>
              {storySource === 'azure_foundry_cache' ? 'Azure Foundry · served from cache' : 'Azure Foundry · generated live'}
            </div>
          )}
        </div>

        {/* Tactical Entropy & Match Rhythm Phases */}
        <div>
          <div
            style={{
              fontSize: 'var(--text-micro)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-text-tertiary)',
              letterSpacing: '0.04em',
              marginBottom: 'var(--spacing-sm)',
            }}
          >
            Tactical Entropy & Chaos Rhythm (CCI) Progression
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 'var(--spacing-md)',
            }}
          >
            {(recapData?.tactical_entropy_shifts ?? []).map((phase) => (
              <div
                key={phase.phase}
                style={{
                  backgroundColor: 'var(--color-bg-base)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '6px',
                  padding: 'var(--spacing-md)',
                }}
              >
                <div style={{ fontSize: 'var(--text-micro)', color: 'var(--color-text-tertiary)' }}>
                  {phase.phase}
                </div>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: 'var(--text-body)',
                    color:
                      phase.character === 'High Control'
                        ? 'var(--color-accent-green)'
                        : phase.character === 'High Transition Chaos'
                        ? 'var(--color-accent-yellow)'
                        : 'var(--color-accent-cyan)',
                  }}
                >
                  {phase.character} (CCI {phase.avg_cci.toFixed(1)})
                </div>
                <p style={{ margin: '4px 0 0 0', fontSize: 'var(--text-caption)', color: 'var(--color-text-secondary)' }}>
                  {phase.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};
