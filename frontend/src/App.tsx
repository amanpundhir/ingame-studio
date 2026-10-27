/**
 * InGame Studio - Master Broadcast Studio Dashboard
 * AI Match Intelligence Engine
 * 5-Tab Unified Application Integration
 * Navigation Rail, InGame, Players Stats, Tactical Insights, Persona & Recap
 */

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { StudioStreamService } from './services/websocket';

// ── 11 Existing Studio Components (Maintained Intact for Test Invariants) ──
import { PitchVisualizer } from './components/PitchVisualizer';
import { BroadcastOverlay } from './components/BroadcastOverlay';
import { PersonaToggle } from './components/PersonaToggle';
import { MetricsStrip } from './components/MetricsStrip';
import { ChaosRhythmBar } from './components/ChaosRhythmBar';
import { PersonaSwitcher } from './components/PersonaSwitcher';
import { AnalystChat } from './components/AnalystChat';
import { LanguageSelector } from './components/LanguageSelector';
import { ProgressiveTimeline } from './components/ProgressiveTimeline';
import { MatchStatsOverview } from './components/MatchStatsOverview';
import { PlayerPerformanceTable } from './components/PlayerPerformanceTable';
import { PlayerRatingsFantasy } from './components/PlayerRatingsFantasy';
import { MatchRecapModal } from './components/MatchRecapModal';

// ── Newly Built 5-Tab Architecture Components ──
import { NavigationRail } from './components/NavigationRail';
import { InGameTab } from './components/InGameTab';
import { InGameKpiStrip } from './components/InGameKpiStrip';
import { PlayersStatsTab } from './components/PlayersStatsTab';
import { PlayerRadarChart } from './components/PlayerRadarChart';
import { PlayerHeatmapCanvas } from './components/PlayerHeatmapCanvas';
import { TacticalInsightsTab } from './components/TacticalInsightsTab';
import { TacticalPitchCanvas } from './components/TacticalPitchCanvas';
import { PersonaTab } from './components/PersonaTab';
import { RecapTab } from './components/RecapTab';

import {
  TabId,
  TelemetryFrame,
  MatchEvent,
  VerifiedInsight,
  ViewerPersona,
  LanguageCode,
  AnalyticsResponse,
  SpotlightMetric,
  ClubPerspective,
  TeamAllegiance,
  MatchRecapData,
  MetricAlert,
} from './types';

export const App: React.FC = () => {
  // Master Active Tab State: 'ingame' | 'players' | 'tactical' | 'persona' | 'recap'
  const [activeTab, setActiveTab] = useState<TabId>('ingame');

  // Shared Master Telemetry, Event, and Intelligence State
  const [frame, setFrame] = useState<TelemetryFrame | null>(null);
  const [insight, setInsight] = useState<VerifiedInsight | null>(null);
  const [activeEvent, setActiveEvent] = useState<MatchEvent | null>(null);
  const [eventsList, setEventsList] = useState<MatchEvent[]>([]);
  const [latencyMs, setLatencyMs] = useState<number>(12);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [persona, setPersona] = useState<ViewerPersona>(() => {
    try {
      const saved = localStorage.getItem('ingame_persona');
      if (saved === 'tactical' || saved === 'casual' || saved === 'club' || saved === 'fantasy') {
        return saved;
      }
    } catch (_) {}
    return 'tactical';
  });
  const [language, setLanguage] = useState<LanguageCode>('en');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1.0);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [isSimulatingFull, setIsSimulatingFull] = useState<boolean>(false);
  const [activeReplayEventId, setActiveReplayEventId] = useState<string | null>(null);
  const [showRecapModal, setShowRecapModal] = useState<boolean>(false);
  const [recapData, setRecapData] = useState<MatchRecapData | null>(null);
  const [spotlightMetric, setSpotlightMetric] = useState<SpotlightMetric>('all');
  const [favoriteClub, setFavoriteClub] = useState<ClubPerspective>(() => {
    try {
      const saved = localStorage.getItem('ingame_club');
      if (saved === 'Northbridge Lions' || saved === 'Harbourside City') return saved;
    } catch (_) {}
    return 'Northbridge Lions';
  });
  const [teamAllegiance, setTeamAllegiance] = useState<TeamAllegiance>(() => {
    try {
      const saved = localStorage.getItem('ingame_allegiance');
      if (saved === 'neutral' || saved === 'home' || saved === 'away') return saved;
    } catch (_) {}
    return 'neutral';
  });
  const [metricAlert, setMetricAlert] = useState<MetricAlert | null>(null);
  const [liveScore, setLiveScore] = useState({ home: 0, away: 0 });
  const liveScoreRef = useRef({ home: 0, away: 0 });
  const goalEventsSeenRef = useRef(false);
  const processedGoalIdsRef = useRef<Set<string>>(new Set());

  // Initialize stream service (persists across all tab switches without disconnecting)
  const streamService = useMemo(() => new StudioStreamService(), []);

  // Fetch match and player analytics
  const fetchAnalytics = () => {
    fetch('/api/analytics')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.match_stats && data.player_stats) {
          setAnalytics(data);
          if (!goalEventsSeenRef.current) {
            const score = data.match_stats.score || { home: 0, away: 0 };
            liveScoreRef.current = { home: score.home || 0, away: score.away || 0 };
            setLiveScore(liveScoreRef.current);
          }
        }
      })
      .catch((err) => console.warn('Could not fetch analytics', err));
  };

  // Fetch automated post-match studio recap
  const fetchRecap = () => {
    fetch('/api/recap')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setRecapData(data);
        }
      })
      .catch((err) => console.warn('Could not fetch match recap', err));
  };

  // Event catalogue and latest insight are refreshed from the server after bulk changes
  // (full-match simulation), since those never arrive one-by-one over the socket.
  const refreshEvents = () => {
    fetch('/api/events')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setEventsList(data))
      .catch((err) => console.warn('Could not refresh events', err));
  };

  const refreshLatestInsight = () => {
    fetch('/api/insights/latest')
      .then((res) => (res.ok && res.status !== 204 ? res.json() : null))
      .then((data) => {
        if (data) setInsight(data);
      })
      .catch(() => undefined);
  };

  const lastStateUpdateTimeRef = useRef<number>(0);
  const alertTimeoutRef = useRef<number | null>(null);
  const hasAutoOpenedRecapRef = useRef<boolean>(false);
  const clearLocalMatchStateRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    streamService.setHandlers({
      onTelemetry: (newFrame) => {
        const now = performance.now();
        // Throttle React state frame updates to 20Hz max to guarantee 60fps canvas performance
        if (now - lastStateUpdateTimeRef.current >= 45) {
          lastStateUpdateTimeRef.current = now;
          setFrame(newFrame);

          // Detect match full-time (94:30 or 90:00) and auto-open recap modal
          if (
            (newFrame.clock === '94:30' || newFrame.clock === '90:00') &&
            !hasAutoOpenedRecapRef.current
          ) {
            hasAutoOpenedRecapRef.current = true;
            fetchRecap();
            setShowRecapModal(true);
          }
        }
      },
      onEvent: (event) => {
        setActiveEvent(event);
        setEventsList((prev) =>
          prev.some((existing) => existing.event_id === event.event_id) ? prev : [...prev, event]
        );
        const isGoal = event.event_type?.toLowerCase() === 'goal' || event.outcome?.toLowerCase() === 'goal';
        if (isGoal && event.event_id && !processedGoalIdsRef.current.has(event.event_id)) {
          processedGoalIdsRef.current.add(event.event_id);
          goalEventsSeenRef.current = true;
          const next = { ...liveScoreRef.current };
          const side = (event.team || '').toLowerCase();
          if (side === 'home' || side === 'northbridge') next.home += 1;
          else if (side === 'away' || side.includes('city')) next.away += 1;
          liveScoreRef.current = next;
          setLiveScore(next);
        }
        fetchAnalytics();
      },
      onInsight: (newInsight) => setInsight(newInsight),
      onMetricAlert: (alert) => {
        setMetricAlert(alert);
        if (alertTimeoutRef.current) {
          window.clearTimeout(alertTimeoutRef.current);
        }
        alertTimeoutRef.current = window.setTimeout(() => {
          setMetricAlert(null);
          alertTimeoutRef.current = null;
        }, 6000);
      },
      onControl: (control) => {
        if (control.action === 'full_time') {
          setIsPaused(true);
        } else if (control.action === 'reset') {
          clearLocalMatchStateRef.current();
        }
      },
      onLatencyUpdate: (lat) => setLatencyMs(lat),
      onStatusChange: (status) => setIsConnected(status),
    });

    streamService.connect();

    // Fetch initial event catalog, latest insight, and analytics via REST API
    fetch('/api/events')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setEventsList(data))
      .catch((err) => console.warn('Could not fetch events catalog', err));

    fetch('/api/insights/latest')
      .then((res) => (res.ok && res.status !== 204 ? res.json() : null))
      .then((data) => {
        if (data) setInsight(data);
      })
      .catch((err) => console.warn('Could not fetch initial insight', err));

    fetchAnalytics();

    // Restore the current match state (clock, pause state, speed) after a page reload
    fetch('/api/state')
      .then((res) => (res.ok ? res.json() : null))
      .then((state) => {
        if (!state) return;
        if (state.frame && state.frame.players) setFrame(state.frame);
        if (typeof state.is_paused === 'boolean') setIsPaused(state.is_paused);
        if (typeof state.speed_multiplier === 'number') setSpeedMultiplier(state.speed_multiplier);
      })
      .catch(() => undefined);

    return () => {
      if (alertTimeoutRef.current) {
        window.clearTimeout(alertTimeoutRef.current);
      }
      streamService.disconnect();
    };
  }, [streamService]);

  // Reflect the viewer's language on the document (screen readers, hyphenation, RTL-aware widgets).
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = 'ltr';
  }, [language]);

  // Opening the Recap tab pulls the latest recap, highlights and stats for the match so far.
  useEffect(() => {
    if (activeTab === 'recap') fetchRecap();
  }, [activeTab]);

  // The persona and club chosen in the header apply to every tab and are remembered.
  const handleSelectClub = (club: ClubPerspective) => {
    setFavoriteClub(club);
    setTeamAllegiance(club === 'Northbridge Lions' ? 'home' : 'away');
  };

  useEffect(() => {
    try {
      localStorage.setItem('ingame_persona', persona);
      localStorage.setItem('ingame_favorite_club', favoriteClub);
    } catch (_) {}
  }, [persona, favoriteClub]);

  const handlePlayPause = () => {
    const nextState = !isPaused;
    // After full time (94:30) Play starts the match again from kick-off.
    if (!nextState && frame?.clock === '94:30') clearLocalMatchState();
    setIsPaused(nextState);
    streamService.sendControl(nextState ? 'pause' : 'play');
    fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: nextState ? 'pause' : 'play' }),
    }).catch(console.error);
  };

  // Everything the viewer sees about the current run of the match, cleared for a fresh kick-off.
  const clearLocalMatchState = () => {
    setActiveReplayEventId(null);
    hasAutoOpenedRecapRef.current = false;
    setMetricAlert(null);
    setEventsList([]);
    setInsight(null);
    setActiveEvent(null);
    setRecapData(null);
    setIsPaused(false);
    goalEventsSeenRef.current = false;
    processedGoalIdsRef.current.clear();
    liveScoreRef.current = { home: 0, away: 0 };
    setLiveScore(liveScoreRef.current);
  };
  clearLocalMatchStateRef.current = clearLocalMatchState;

  const handleReset = () => {
    streamService.sendControl('reset');
    clearLocalMatchState();
    fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reset' }),
    }).catch(console.error);
  };

  // Variable Speed Multiplier Handler (1x, 2x, 5x, 10x, 20x)
  const handleSpeedChange = (mult: number) => {
    setSpeedMultiplier(mult);
    fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'speed', multiplier: mult }),
    }).catch((err) => console.error('Speed control failed', err));
  };

  // 1-Click Interactive Replay Jump Handler
  const handleJumpToEvent = (eventId: string) => {
    setActiveReplayEventId(eventId);
    fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'jump', event_id: eventId }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          if (data.insight) setInsight(data.insight);
          if (data.frame) setFrame(data.frame);
        }
      })
      .catch((err) => console.error('Replay jump failed', err));
  };

  // Instant Full Match Simulation Handler
  const handleSimulateFull = () => {
    setIsSimulatingFull(true);
    fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'simulate_full' }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setIsSimulatingFull(false);
        if (data) {
          if (data.match_stats && data.player_stats) {
            setAnalytics({ match_stats: data.match_stats, player_stats: data.player_stats });
            const score = data.match_stats.score || { home: 0, away: 0 };
            liveScoreRef.current = { home: score.home || 0, away: score.away || 0 };
            setLiveScore(liveScoreRef.current);
            goalEventsSeenRef.current = true;
          }
          if (data.insight) setInsight(data.insight);
          // Advance local clock view to full-time 94:30
          if (frame) {
            setFrame({
              ...frame,
              clock: '94:30',
              period: 2,
            });
          }
        }
        fetchAnalytics();
        fetchRecap();
        refreshEvents();
        refreshLatestInsight();
        hasAutoOpenedRecapRef.current = true;
        setShowRecapModal(true);
      })
      .catch((err) => {
        console.error('Simulate full match failed', err);
        setIsSimulatingFull(false);
        if (frame) {
          setFrame({ ...frame, clock: '94:30', period: 2 });
        }
        fetchRecap();
        hasAutoOpenedRecapRef.current = true;
        setShowRecapModal(true);
      });
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div
      className="ingame-app-layout"
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100vh',
        width: '100vw',
        background: 'var(--color-bg-base)',
        color: 'var(--color-text-primary)',
        overflow: 'hidden',
      }}
    >
      {/* 1. Persistent 72px Left Vertical Navigation Rail */}
      <NavigationRail
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isLive={isConnected}
      />

      {/* 2. Main Content Area (flex: 1) with Unified Scroll and Header */}
      <div
        className="ingame-content-area"
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {/* Global Master Header (56px) */}
        <header className="ingame-master-header">
          {/* Left: Branding & Active Tab Indicator */}
          <div className="ingame-master-brand">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '15px',
                  fontWeight: 900,
                  letterSpacing: '0.04em',
                  color: 'var(--color-text-primary)',
                }}
              >
                INGAME STUDIO
              </span>
              <span style={{ color: 'var(--color-text-tertiary)', fontSize: '12px' }}>|</span>
              <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                Northbridge Lions vs Harbourside City
              </span>
            </div>
            <div
              className="ingame-tab-indicator-badge"
              style={{
                background:
                  activeTab === 'ingame'
                    ? 'rgba(0, 255, 135, 0.12)'
                    : activeTab === 'players' || activeTab === 'tactical'
                    ? 'rgba(4, 240, 255, 0.12)'
                    : activeTab === 'persona'
                    ? 'rgba(168, 85, 247, 0.12)'
                    : 'rgba(255, 230, 0, 0.12)',
                border: `1px solid ${
                  activeTab === 'ingame'
                    ? 'var(--color-accent-green)'
                    : activeTab === 'players' || activeTab === 'tactical'
                    ? 'var(--color-accent-cyan)'
                    : activeTab === 'persona'
                    ? '#a855f7'
                    : 'var(--color-accent-yellow)'
                }`,
                color:
                  activeTab === 'ingame'
                    ? 'var(--color-accent-green)'
                    : activeTab === 'players' || activeTab === 'tactical'
                    ? 'var(--color-accent-cyan)'
                    : activeTab === 'persona'
                    ? '#a855f7'
                    : 'var(--color-accent-yellow)',
              }}
            >
              {activeTab === 'ingame' && '● LIVE DASHBOARD'}
              {activeTab === 'players' && '📊 PLAYER INTEL & RADAR'}
              {activeTab === 'tactical' && '🎯 TACTICAL MOMENTS & LAYERS'}
              {activeTab === 'persona' && '🎙 AI BROADCAST PERSONA'}
              {activeTab === 'recap' && '⏱ 5-MIN CONDENSED RECAP'}
            </div>
          </div>

          {/* Center: Live Scoreboard Pill */}
          <div className="ingame-scoreboard-pill">
            <span style={{ fontWeight: 800, fontSize: '12px', color: 'var(--color-team-home)' }}>NBL</span>
            <span className="mono-stat" style={{ fontSize: '15px', fontWeight: 900, color: 'var(--color-text-primary)' }}>
              {liveScore.home} - {liveScore.away}
            </span>
            <span style={{ fontWeight: 800, fontSize: '12px', color: 'var(--color-team-away)' }}>HSC</span>
            <span style={{ color: 'var(--color-border-emphasis)', margin: '0 2px' }}>•</span>
            <span className="mono-stat" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-accent-cyan)' }}>
              ⏱ {frame?.clock || '00:00'}
            </span>
          </div>

          {/* Right: Persona (applies to every tab), Language Selector & Live Latency */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)', flexWrap: 'wrap' }}>
            <PersonaSwitcher persona={persona} favoriteClub={favoriteClub} onSelectPersona={setPersona} onSelectClub={handleSelectClub} />
            <LanguageSelector currentLanguage={language} onSelectLanguage={setLanguage} />
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '4px',
                background: 'rgba(0, 0, 0, 0.4)',
                border: '1px solid var(--color-border-subtle)',
                fontSize: '11px',
                fontWeight: 700,
              }}
            >
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: isConnected ? 'var(--color-accent-green)' : 'var(--color-accent-red)',
                  boxShadow: `0 0 6px ${isConnected ? 'var(--color-accent-green)' : 'var(--color-accent-red)'}`,
                }}
              />
              <span style={{ color: isConnected ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
                {isConnected ? `${latencyMs}ms 25Hz` : 'OFFLINE'}
              </span>
            </div>
          </div>
        </header>

        {/* ── Tab 1: InGame Live Match Dashboard ── */}
        <div
          id="tab-panel-ingame"
          role="tabpanel"
          aria-labelledby="tab-ingame"
          className="ingame-tab-container"
          style={{
            display: activeTab === 'ingame' ? 'flex' : 'none',
            flexDirection: 'column',
            width: '100%',
          }}
        >
          <InGameTab
            frame={frame}
            insight={insight}
            activeEvent={activeEvent}
            eventsList={eventsList}
            analytics={analytics}
            liveScore={liveScore}
            isPaused={isPaused}
            speedMultiplier={speedMultiplier}
            isSimulatingFull={isSimulatingFull}
            persona={persona}
            language={language}
            favoriteClub={favoriteClub}
            selectedPlayerId={selectedPlayerId}
            activeReplayEventId={activeReplayEventId}
            metricAlert={metricAlert}
            spotlightMetric={spotlightMetric}
            latencyMs={latencyMs}
            isConnected={isConnected}
            onPlayPause={handlePlayPause}
            onReset={handleReset}
            onSpeedChange={handleSpeedChange}
            onSimulateFull={handleSimulateFull}
            onJumpToEvent={handleJumpToEvent}
            onSelectPlayer={setSelectedPlayerId}
            onSelectPersona={setPersona}
            onSelectClub={setFavoriteClub}
            onSelectSpotlightMetric={setSpotlightMetric}
            onDismissAlert={() => setMetricAlert(null)}
            onOpenRecapModal={() => {
              fetchRecap();
              setShowRecapModal(true);
            }}
          />

          {/* Downward Navigation Header & Anchor Bar */}
          <div className="studio-nav-bar" style={{ marginTop: 'var(--spacing-lg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '18px' }}>📊</span>
              <div>
                <div
                  style={{
                    fontSize: 'var(--text-micro)',
                    fontWeight: 900,
                    letterSpacing: '0.06em',
                    color: 'var(--color-text-primary)',
                    textTransform: 'uppercase',
                  }}
                >
                  Match &amp; Player Intelligence Center
                </div>
                <div style={{ fontSize: 'var(--text-micro)', color: 'var(--color-text-secondary)' }}>
                  Comprehensive 90-minute telemetry analytics &bull; 22-player tracking &bull; fantasy football (Fantasy) bonus points
                </div>
              </div>
            </div>

            {/* Quick-Jump Section Buttons */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => scrollToSection('section-match-stats')} className="studio-nav-btn">
                📊 Match Stats
              </button>
              <button onClick={() => scrollToSection('section-players-table')} className="studio-nav-btn">
                📋 22-Player Table
              </button>
              <button onClick={() => scrollToSection('section-ratings-fantasy')} className="studio-nav-btn">
                🏆 MOTM &amp; Fantasy Podium
              </button>
            </div>
          </div>

          {/* Extended Scrollable Analytics Dashboard */}
          <div className="studio-analytics-container">
            {/* Section 1: Comparative Match Stats Overview */}
            <div id="section-match-stats">
              <MatchStatsOverview stats={analytics?.match_stats || null} />
            </div>

            {/* Section 2: 22-Player Performance Table */}
            <div id="section-players-table">
              <PlayerPerformanceTable
                players={analytics?.player_stats || []}
                selectedPlayerId={selectedPlayerId}
                onSelectPlayer={setSelectedPlayerId}
              />
            </div>

            {/* Section 3: Broadcast Player Ratings, MOTM & Fantasy BPS Podium */}
            <div id="section-ratings-fantasy">
              <PlayerRatingsFantasy players={analytics?.player_stats || []} />
            </div>
          </div>
        </div>

        {/* ── Tab 2: Players Stats (Player Intelligence & Analytics) ── */}
        <div
          id="tab-panel-players"
          role="tabpanel"
          aria-labelledby="tab-players"
          className="ingame-tab-container"
          style={{
            display: activeTab === 'players' ? 'block' : 'none',
            width: '100%',
          }}
        >
          <PlayersStatsTab
            players={analytics?.player_stats || []}
            events={eventsList}
            selectedPlayerId={selectedPlayerId}
            onSelectPlayer={(id) => setSelectedPlayerId(id)}
            activePersona={persona}
            language={language}
          />
        </div>

        {/* ── Tab 3: Tactical Insights (Spatial Moments & Layer Toggles) ── */}
        <div
          id="tab-panel-tactical"
          role="tabpanel"
          aria-labelledby="tab-tactical"
          className="ingame-tab-container"
          style={{
            display: activeTab === 'tactical' ? 'block' : 'none',
            width: '100%',
          }}
        >
          <TacticalInsightsTab
            activePersona={persona}
            isVisible={activeTab === 'tactical'}
            language={language}
            eventCount={eventsList.length}
          />
        </div>

        {/* ── Tab 4: Persona Selector (AI Broadcast Personas & Allegiance) ── */}
        <div
          id="tab-panel-persona"
          role="tabpanel"
          aria-labelledby="tab-persona"
          className="ingame-tab-container"
          style={{
            display: activeTab === 'persona' ? 'block' : 'none',
            width: '100%',
          }}
        >
          <PersonaTab
            activePersona={persona}
            favoriteClub={favoriteClub}
            language={language}
            insight={insight}
            analytics={analytics}
            activeEventClock={activeEvent?.clock ?? eventsList.find((e) => e.event_id === insight?.event_id)?.clock}
          />
        </div>

        {/* ── Tab 5: Recap (5-Minute Condensed Match Story) ── */}
        <div
          id="tab-panel-recap"
          role="tabpanel"
          aria-labelledby="tab-recap"
          className="ingame-tab-container"
          style={{
            display: activeTab === 'recap' ? 'block' : 'none',
            width: '100%',
          }}
        >
          <RecapTab
            recapData={recapData}
            stats={analytics?.match_stats || null}
            players={analytics?.player_stats || []}
            events={eventsList}
            activePersona={persona}
            language={language}
            favoriteClub={favoriteClub}
            teamAllegiance={teamAllegiance}
            onSeekMoment={() => {}}
            onExploreAnalytics={() => {
              setActiveTab('ingame');
              setTimeout(() => scrollToSection('section-match-stats'), 100);
            }}
          />
        </div>

        {/* Post-Match Studio Recap Modal */}
        <MatchRecapModal
          isOpen={showRecapModal}
          onClose={() => setShowRecapModal(false)}
          recapData={recapData}
          stats={analytics?.match_stats || null}
          players={analytics?.player_stats || []}
          language={language}
          persona={persona}
          club={favoriteClub}
          onExploreAnalytics={() => {
            setShowRecapModal(false);
            setActiveTab('ingame');
            setTimeout(() => scrollToSection('section-match-stats'), 100);
          }}
        />

        {/* Match Analyst chat bubble: bottom-right of the main match tab */}
        <AnalystChat
          persona={persona}
          favoriteClub={favoriteClub}
          language={language}
          visible={activeTab === 'ingame'}
        />
      </div>
    </div>
  );
};

export default App;
