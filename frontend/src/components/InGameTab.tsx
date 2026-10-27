/**
 * InGame Studio - Tab 1: InGame (Live Match Dashboard)
 * Broadcast Intelligence Tab
 *
 * Hosts:
 * - Top Match Bar: Scoreline banner with team crests/names, live match clock,
 *   play/pause, reset, speed controls (1x, 2x, 5x, 10x, 20x), and "Simulate to End" button.
 * - InGameKpiStrip: 5 prominent match KPI metric cards with dual comparison bars.
 * - Central Pitch Visualizer (2D IFAB canvas) + BroadcastOverlay.
 * - Right Panel: Live Events Feed (ProgressiveTimeline) + AI Persona Commentary (PersonaToggle).
 */

import React from 'react';
import { PitchVisualizer } from './PitchVisualizer';
import { BroadcastOverlay } from './BroadcastOverlay';
import { PersonaToggle } from './PersonaToggle';
import { MetricsStrip } from './MetricsStrip';
import { ChaosRhythmBar } from './ChaosRhythmBar';
import { ProgressiveTimeline } from './ProgressiveTimeline';
import { InGameKpiStrip } from './InGameKpiStrip';
import {
  TelemetryFrame,
  MatchEvent,
  VerifiedInsight,
  ViewerPersona,
  LanguageCode,
  AnalyticsResponse,
  SpotlightMetric,
  ClubPerspective,
  MetricAlert,
} from '../types';

export interface InGameTabProps {
  frame: TelemetryFrame | null;
  insight: VerifiedInsight | null;
  activeEvent: MatchEvent | null;
  eventsList: MatchEvent[];
  analytics: AnalyticsResponse | null;
  liveScore: { home: number; away: number };
  isPaused: boolean;
  speedMultiplier: number;
  isSimulatingFull: boolean;
  persona: ViewerPersona;
  language: LanguageCode;
  favoriteClub: ClubPerspective;
  selectedPlayerId: string | null;
  activeReplayEventId: string | null;
  metricAlert: MetricAlert | null;
  spotlightMetric: SpotlightMetric;
  latencyMs?: number;
  isConnected?: boolean;
  onPlayPause: () => void;
  onReset: () => void;
  onSpeedChange: (mult: number) => void;
  onSimulateFull: () => void;
  onJumpToEvent: (eventId: string) => void;
  onSelectPlayer: (id: string | null) => void;
  onSelectPersona: (p: ViewerPersona) => void;
  onSelectClub: (c: ClubPerspective) => void;
  onSelectSpotlightMetric: (m: SpotlightMetric) => void;
  onDismissAlert: () => void;
  onOpenRecapModal?: () => void;
}

export const InGameTab: React.FC<InGameTabProps> = ({
  frame,
  insight,
  activeEvent,
  eventsList,
  analytics,
  liveScore,
  isPaused,
  speedMultiplier,
  isSimulatingFull,
  persona,
  language,
  favoriteClub,
  selectedPlayerId,
  activeReplayEventId,
  metricAlert,
  spotlightMetric,
  latencyMs = 12,
  isConnected = true,
  onPlayPause,
  onReset,
  onSpeedChange,
  onSimulateFull,
  onJumpToEvent,
  onSelectPlayer,
  onSelectPersona,
  onSelectClub,
  onSelectSpotlightMetric,
  onDismissAlert,
  onOpenRecapModal,
}) => {
  const speedOptions = [1.0, 2.0, 5.0, 10.0, 20.0];
  const isFullTime = frame?.clock === '94:30' || frame?.clock === '90:00';

  return (
    <div
      className="ingame-tab-view"
      role="tabpanel"
      id="panel-ingame"
      aria-labelledby="tab-ingame"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--spacing-md)',
        width: '100%',
        padding: 'var(--spacing-md)',
      }}
    >
      {/* 1. Top Match Bar: Scoreline banner, Clock, Speed Controls & Simulate to End */}
      <header
        className="studio-card studio-header"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          gap: 'var(--spacing-md)',
          background: 'linear-gradient(90deg, var(--color-pl-purple-dark) 0%, var(--color-bg-elevated) 50%, var(--color-pl-purple-dark) 100%)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: 'var(--spacing-sm)',
        }}
      >
        {/* Left: Team Crests & Scoreline Banner */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Home Crest: Northbridge Lions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: '#EF0107',
                border: '2px solid #FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 10px rgba(239, 1, 7, 0.4)',
              }}
              title="Northbridge Lions Football Club"
            >
              <span style={{ fontSize: '11px', fontWeight: 900, color: '#FFFFFF' }}>NBL</span>
            </div>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--color-team-home)', lineHeight: 1.1 }}>
                Northbridge Lions
              </div>
              <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>Home</div>
            </div>
          </div>

          {/* Central Live Score Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '4px 14px',
              background: 'rgba(8, 11, 15, 0.85)',
              borderRadius: '6px',
              border: '1px solid var(--color-border-emphasis)',
            }}
          >
            <span
              className="mono-stat"
              style={{
                fontSize: '22px',
                fontWeight: 900,
                color: 'var(--color-team-home)',
                lineHeight: 1,
              }}
            >
              {liveScore.home}
            </span>
            <span style={{ color: 'var(--color-text-tertiary)', fontWeight: 700, fontSize: '14px' }}>:</span>
            <span
              className="mono-stat"
              style={{
                fontSize: '22px',
                fontWeight: 900,
                color: 'var(--color-team-away)',
                lineHeight: 1,
              }}
            >
              {liveScore.away}
            </span>
          </div>

          {/* Away Crest: Harbourside City */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: '#6CABDD',
                border: '2px solid #1C2C5B',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 10px rgba(108, 171, 221, 0.4)',
              }}
              title="Harbourside City Football Club"
            >
              <span style={{ fontSize: '11px', fontWeight: 900, color: '#081028' }}>HSC</span>
            </div>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--color-team-away)', lineHeight: 1.1 }}>
                Harbourside City
              </div>
              <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>Away</div>
            </div>
          </div>

          {/* Match Clock with Status Indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              background: 'rgba(0, 0, 0, 0.4)',
              borderRadius: '6px',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: isFullTime ? 'var(--color-accent-yellow)' : 'var(--color-accent-green)',
                boxShadow: `0 0 8px ${isFullTime ? 'var(--color-accent-yellow)' : 'var(--color-accent-green)'}`,
              }}
            />
            <span
              className="mono-stat"
              style={{
                color: 'var(--color-accent-cyan)',
                fontWeight: 800,
                fontSize: '14px',
              }}
            >
              ⏱ {frame?.clock || '00:00'}
            </span>
            {isFullTime && (
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  color: 'var(--color-accent-yellow)',
                  letterSpacing: '0.04em',
                }}
              >
                FT
              </span>
            )}
          </div>
        </div>

        {/* Right: Simulation Controls (Play/Pause, Reset, Speed, Simulate to End) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Play / Pause Toggle Button */}
          <button
            type="button"
            className="action-btn"
            onClick={onPlayPause}
            aria-label={isPaused ? 'Resume Match Simulation' : 'Pause Match Simulation'}
            title={isPaused ? 'Resume Simulation' : 'Pause Simulation'}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: isPaused ? 'rgba(0, 255, 135, 0.15)' : 'rgba(255, 255, 255, 0.06)',
              border: `1px solid ${isPaused ? 'var(--color-accent-green)' : 'var(--color-border-emphasis)'}`,
              color: isPaused ? 'var(--color-accent-green)' : 'var(--color-text-primary)',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            <span>{isPaused ? '▶ Play' : '⏸ Pause'}</span>
          </button>

          {/* Reset Button */}
          <button
            type="button"
            className="action-btn"
            onClick={onReset}
            aria-label="Reset Match to Minute 00:00"
            title="Reset Simulation"
            style={{
              padding: '6px 10px',
              fontSize: '12px',
              fontWeight: 700,
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid var(--color-border-emphasis)',
              color: 'var(--color-text-secondary)',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            ↺ Reset
          </button>

          {/* Speed Multiplier Pill Selector (1x, 2x, 5x, 10x, 20x) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
              background: 'rgba(0, 0, 0, 0.5)',
              padding: '2px',
              borderRadius: '6px',
              border: '1px solid var(--color-border-subtle)',
            }}
            role="group"
            aria-label="Simulation Speed Multiplier"
          >
            {speedOptions.map((speed) => {
              const isSelected = speedMultiplier === speed;
              return (
                <button
                  key={speed}
                  type="button"
                  onClick={() => onSpeedChange(speed)}
                  className={`mono-stat ${isSelected ? 'active-speed' : ''}`}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    fontWeight: isSelected ? 800 : 500,
                    background: isSelected ? 'rgba(4, 240, 255, 0.2)' : 'transparent',
                    color: isSelected ? 'var(--color-accent-cyan)' : 'var(--color-text-secondary)',
                    border: isSelected ? '1px solid var(--color-accent-cyan)' : '1px solid transparent',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  title={`Run simulation at ${speed}x speed`}
                >
                  {speed}x
                </button>
              );
            })}
          </div>

          {/* "Simulate to End" Button */}
          <button
            type="button"
            onClick={onSimulateFull}
            disabled={isSimulatingFull}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, var(--color-pl-purple-mid) 0%, #200028 100%)',
              border: '1px solid rgba(0, 255, 135, 0.4)',
              color: 'var(--color-accent-green)',
              fontSize: '12px',
              fontWeight: 800,
              cursor: isSimulatingFull ? 'not-allowed' : 'pointer',
              opacity: isSimulatingFull ? 0.6 : 1,
              boxShadow: '0 0 10px rgba(0, 255, 135, 0.2)',
              transition: 'all 0.15s ease',
            }}
            title="Accelerate match simulation instantly to 90' full-time"
          >
            <span>⏩</span>
            <span>{isSimulatingFull ? 'Simulating...' : 'Simulate to End'}</span>
          </button>

          {/* Post-Match Studio Recap Modal Trigger if provided */}
          {onOpenRecapModal && (
            <button
              type="button"
              onClick={onOpenRecapModal}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: '6px',
                background: 'rgba(255, 230, 0, 0.12)',
                border: '1px solid rgba(255, 230, 0, 0.4)',
                color: 'var(--color-accent-yellow)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
              title="Open full-match tactical recap and turning points analysis"
            >
              <span>📋</span>
              <span>Studio Recap</span>
            </button>
          )}

          {/* WebSocket Latency / Sync Status */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '4px',
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid var(--color-border-subtle)',
              fontSize: '11px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: isConnected ? 'var(--color-accent-green)' : 'var(--color-accent-red)',
              }}
            />
            <span
              className="mono-stat"
              style={{
                color: isConnected ? 'var(--color-accent-green)' : 'var(--color-accent-red)',
                fontWeight: 700,
              }}
            >
              {isConnected ? `${latencyMs}ms` : 'OFFLINE'}
            </span>
          </div>
        </div>
      </header>

      {/* 2. InGame KPI Metric Strip: 5 Match KPI Cards */}
      <InGameKpiStrip
        matchStats={analytics?.match_stats}
        analytics={analytics}
        homeTeamName="NBL"
        awayTeamName="HSC"
      />

      {/* 3. Main Workspace Grid: Pitch Visualizer (Left) + Intelligence & Timeline (Right) */}
      <div className="studio-main-grid" style={{ width: '100%' }}>
        {/* Left Column: 2D Canvas Pitch + Broadcast Lower-Third Overlay */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div
            className="studio-card"
            style={{
              flex: '0 0 auto',
              position: 'relative',
              overflow: 'hidden',
              minHeight: '480px',
              display: 'block',
              background: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: 'var(--spacing-sm)',
            }}
          >
            <PitchVisualizer
              frame={frame}
              insight={insight}
              selectedPlayerId={selectedPlayerId}
              onSelectPlayer={onSelectPlayer}
            />
          </div>

          {/* Broadcast Lower-Third Banner with 5-Language Ticker & Metric Alerts */}
          <BroadcastOverlay
            insight={insight}
            activeEvent={activeEvent}
            clock={frame?.clock}
            language={language}
            metricAlert={metricAlert}
            spotlightMetric={spotlightMetric}
            onDismissAlert={onDismissAlert}
          />
        </section>

        {/* Right Column: AI Persona Commentary, Rhythm Bar, Metrics & Live Events Feed */}
        <aside
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            overflowY: 'auto',
            paddingRight: '2px',
          }}
        >
          {/* AI Persona Commentary & Switcher */}
          <PersonaToggle
            insight={insight}
            activePersona={persona}
            onSelectPersona={onSelectPersona}
            language={language}
            favoriteClub={favoriteClub}
            onSelectClub={onSelectClub}
            selectedPlayerId={selectedPlayerId}
            players={analytics?.player_stats || []}
            activeEvent={activeEvent}
            onClearSelectedPlayer={() => onSelectPlayer(null)}
            onSelectPlayer={onSelectPlayer}
          />

          {/* Chaos vs Control Rhythm Index (CCI) Bar */}
          <ChaosRhythmBar
            insight={insight}
            spotlightMetric={spotlightMetric}
            onSelectSpotlightMetric={onSelectSpotlightMetric}
          />

          {/* Real-time Tactical HUD Metrics Strip */}
          <MetricsStrip
            insight={insight}
            frame={frame}
            latencyMs={latencyMs}
            fps={25}
            players={analytics?.player_stats || []}
            spotlightPlayerId={selectedPlayerId || activeEvent?.player_id || null}
            activeEvent={activeEvent}
            spotlightMetric={spotlightMetric}
            onSelectSpotlightMetric={onSelectSpotlightMetric}
          />

          {/* Live Chronological Events Feed & Interactive Replay Jump */}
          <ProgressiveTimeline
            events={eventsList}
            currentClock={frame?.clock || '00:00'}
            currentFrameIndex={frame?.frame_id}
            activeEventId={activeReplayEventId || activeEvent?.event_id || insight?.event_id}
            onJumpToEvent={onJumpToEvent}
            onSimulateFull={onSimulateFull}
            isSimulatingFull={isSimulatingFull}
            favoriteClub={favoriteClub}
            clubModeActive={persona === 'club'}
            spotlightMetric={spotlightMetric}
          />
        </aside>
      </div>
    </div>
  );
};

export default InGameTab;
