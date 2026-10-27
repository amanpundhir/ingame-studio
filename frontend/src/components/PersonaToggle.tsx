/**
 * InGame Studio - 1-Click 4-Way Audience Persona Switcher
 * Features:
 * - Partisan Club Switcher (Northbridge Lions #EF0107 vs Harbourside City #6CABDD) for Club Loyalist
 * - Dynamic Player-Lock Connection with live telemetry bar, ratings & scouting notes for Fantasy Scout
 * Strictly conforms to ingame-ui-design design system.
 */

import React, { useEffect, useRef } from 'react';
import {
  VerifiedInsight,
  MatchEvent,
  ViewerPersona,
  LanguageCode,
  ClubPerspective,
  PlayerAnalytics,
} from '../types';
import { PERSONA_COLORS } from '../constants/tokens';

interface PersonaToggleProps {
  insight: VerifiedInsight | null;
  activeEvent?: MatchEvent | null;
  activePersona: ViewerPersona;
  onSelectPersona: (persona: ViewerPersona) => void;
  language: LanguageCode;
  favoriteClub?: ClubPerspective;
  onSelectClub?: (club: ClubPerspective) => void;
  selectedPlayerId?: string | null;
  players?: PlayerAnalytics[];
  onClearSelectedPlayer?: () => void;
  onSelectPlayer?: (playerId: string) => void;
}

export const PersonaToggle: React.FC<PersonaToggleProps> = ({
  insight,
  activeEvent,
  activePersona,
  onSelectPersona,
  language,
  favoriteClub = 'Northbridge Lions',
  onSelectClub,
  selectedPlayerId,
  players = [],
  onClearSelectedPlayer,
  onSelectPlayer,
}) => {
  const lastLockedPlayerEventRef = useRef<MatchEvent | null>(null);
  const personas: { id: ViewerPersona; label: string; icon: string; color: string; desc: string }[] = [
    { id: 'casual', label: 'Casual Fan', icon: '📺', color: PERSONA_COLORS.casual, desc: 'High energy, accessible thrills & momentum' },
    { id: 'tactical', label: 'Tactical Purist', icon: '⚽', color: PERSONA_COLORS.tactical, desc: 'Space, pressing lines, xT & PDR analysis' },
    { id: 'club', label: 'Club Loyalist', icon: '🔵', color: PERSONA_COLORS.club, desc: 'Passionate commentary & club pride' },
    { id: 'fantasy', label: 'Fantasy Scout', icon: '📊', color: PERSONA_COLORS.fantasy, desc: 'Fantasy points, BPS & assist projections' },
  ];

  // Resolve locked player if any
  const lockedPlayer = selectedPlayerId
    ? players.find((p) => p.player_id === selectedPlayerId) || null
    : null;

  const eventMentionsLockedPlayer = (event: MatchEvent | null, player: PlayerAnalytics | null): boolean => {
    if (!event || !player) return false;
    return event.player_id === player.player_id || event.player_name === player.name || event.secondary_player_name === player.name;
  };

  useEffect(() => {
    const involvesLockedPlayer = !!activeEvent && !!lockedPlayer && (
      activeEvent.player_id === lockedPlayer.player_id ||
      activeEvent.player_name === lockedPlayer.name ||
      activeEvent.secondary_player_name === lockedPlayer.name
    );
    if (involvesLockedPlayer) {
      lastLockedPlayerEventRef.current = activeEvent || null;
    }
  }, [activeEvent, lockedPlayer]);

  // Star players for quick-select if no player selected
  const keyPlayers = [
    { id: 'p7', name: 'Sarpong', num: 7, team: 'Northbridge Lions' },
    { id: 'p9', name: 'Hagen', num: 9, team: 'Harbourside' },
    { id: 'p17', name: 'Devos', num: 17, team: 'Harbourside' },
    { id: 'p41', name: 'Rowe', num: 41, team: 'Northbridge Lions' },
    { id: 'p8', name: 'Olsvik', num: 8, team: 'Northbridge Lions' },
  ];

  // Resolve club loyalist partisan narrative
  const getClubLoyalistStory = (): string => {
    const raw = insight?.club_loyalist_story || 'Watching the tactical contest unfold with club pride...';
    const isNorthbridge = favoriteClub === 'Northbridge Lions';

    // Adapt narrative tone based on selected club perspective
    if (isNorthbridge) {
      if (raw.toLowerCase().includes('northbridge') || raw.toLowerCase().includes('sarpong') || raw.toLowerCase().includes('olsvik') || raw.toLowerCase().includes('rowe')) {
        return `[🔴 THE LIONS PERSPECTIVE] ${raw} Northbridge’s red army asserting Northbridge dominance with supreme tactical control and relentless pressure!`;
      }
      return `[🔴 NORTHBRIDGE DEFENSIVE VIGILANCE] The Lions holding firm against Harbourside City's advances. Gabriel, Sandoval, and Roark marshaling the backline with heroic discipline. COYG!`;
    } else {
      if (raw.toLowerCase().includes('city') || raw.toLowerCase().includes('hagen') || raw.toLowerCase().includes('devos') || raw.toLowerCase().includes('fenton')) {
        return `[🔵 HARBOURSIDE PERSPECTIVE] ${raw} Harbourside's title-winning side suffocating the opposition with trademark positional mastery and lethal precision!`;
      }
      return `[🔵 HARBOURSIDE DISCIPLINE] City absorbing Northbridge Lions' transitional flurry. Rodrigo Vale and Duarte controlling the defensive corridor before springing the counter-attack!`;
    }
  };

  // Resolve Player-Lock Fantasy Scouting Narrative
  const getFantasyScoutStory = (): string => {
    if (lockedPlayer) {
      const isHome = lockedPlayer.team === 'home' || lockedPlayer.team === 'Northbridge Lions';
      const teamName = isHome ? 'Northbridge Lions' : 'Harbourside';
      const motmStr = lockedPlayer.is_motm ? '★ Current MOTM Leader! ' : '';
      return `${motmStr}Scouting ${lockedPlayer.name} (#${lockedPlayer.jersey_number}, ${teamName}): Registering a match rating of ${lockedPlayer.rating.toFixed(1)} with ${lockedPlayer.bps} BPS accrued. Active threat index of ${lockedPlayer.xt_created >= 0 ? '+' : ''}${lockedPlayer.xt_created.toFixed(2)} xT, with ${lockedPlayer.passes.completed}/${lockedPlayer.passes.total} passes completed (${lockedPlayer.passes.accuracy_pct.toFixed(0)}% accuracy) and top sprint at ${lockedPlayer.top_speed_kmh.toFixed(1)} km/h. High upside for maximum Fantasy bonus points.`;
    }

    if (insight?.player_lock_story) {
      return insight.player_lock_story;
    }

    return 'Tracking ball-carrier micro-telemetry and live fantasy football BPS trajectories. Click any player on the pitch to lock dedicated performance tracking.';
  };

  // Resolve story text based on language and persona
  const getStory = (): string => {
    if (!insight) return 'Awaiting match event intelligence...';

    if (activePersona === 'fantasy' && lockedPlayer && activeEvent && !eventMentionsLockedPlayer(activeEvent, lockedPlayer)) {
      const lastEvent = lastLockedPlayerEventRef.current;
      const lastMoment = lastEvent ? ` Last involvement: ${lastEvent.event_type.replace(/_/g, ' ')} at ${lastEvent.clock}.` : '';
      const followText: Record<LanguageCode, string> = {
        en: `⏳ Monitoring ${lockedPlayer.name} (#${lockedPlayer.jersey_number}). Not directly involved in this action; tracking their next contribution.${lastMoment}`,
        es: `⏳ Siguiendo a ${lockedPlayer.name} (#${lockedPlayer.jersey_number}). No participa directamente en esta jugada; esperamos su próxima intervención.${lastMoment}`,
      };
      return followText[language];
    }

    // Check if multi-language translation exists
    if (language !== 'en' && insight.translations && insight.translations[language]) {
      const translated = insight.translations[language][activePersona];
      if (translated) return translated;
    }

    switch (activePersona) {
      case 'casual':
        return insight.casual_story;
      case 'tactical':
        return insight.tactical_analysis;
      case 'club':
        return getClubLoyalistStory();
      case 'fantasy':
        return getFantasyScoutStory();
      default:
        return insight.tactical_analysis;
    }
  };

  const activeMeta = personas.find((p) => p.id === activePersona) || personas[0];
  const isClubPersona = activePersona === 'club';
  const isFantasyPersona = activePersona === 'fantasy';

  // Dynamic accent color for Club Loyalist based on chosen club
  const activeColor =
    isClubPersona
      ? favoriteClub === 'Northbridge Lions'
        ? 'var(--color-team-home)'
        : 'var(--color-team-away)'
      : activeMeta.color;

  return (
    <div
      className="studio-card persona-card"
      data-persona={activePersona}
      role="region"
      aria-label="Audience persona switcher"
    >
      {/* The persona is chosen once, in the app header, and applies to every tab. */}
      <div className="persona-header">
        <div className="persona-title-group">
          <span className="persona-title">Commentary: {activeMeta.label}</span>
          <span className="persona-tag">Change persona in the top bar</span>
        </div>
      </div>

      {/* Dynamic Player-Lock Header & Micro-Metrics (Rendered for Fantasy Scout) */}
      {isFantasyPersona && (
        <div style={{ marginBottom: '10px' }}>
          {lockedPlayer ? (
            <div
              style={{
                background: 'var(--color-bg-base)',
                border: '1px solid var(--color-accent-green)',
                borderRadius: '8px',
                padding: '10px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      background: lockedPlayer.team === 'home' || lockedPlayer.team === 'Northbridge Lions' ? 'var(--color-team-home)' : 'var(--color-team-away)',
                      color: lockedPlayer.team === 'home' || lockedPlayer.team === 'Northbridge Lions' ? '#fff' : '#080b0f',
                      fontWeight: 900,
                      fontSize: '11px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    #{lockedPlayer.jersey_number}
                  </span>
                  <div>
                    <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--color-text-primary)' }}>
                      {lockedPlayer.name}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', marginLeft: '6px' }}>
                      ({lockedPlayer.role})
                    </span>
                  </div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '9px',
                      fontWeight: 800,
                      color: 'var(--color-accent-green)',
                      background: 'rgba(0, 255, 135, 0.1)',
                      padding: '1px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'var(--color-accent-green)' }} />
                    LOCKED
                  </span>
                </div>

                {onClearSelectedPlayer && (
                  <button
                    onClick={onClearSelectedPlayer}
                    style={{
                      background: 'transparent',
                      border: '1px solid var(--color-border-subtle)',
                      color: 'var(--color-text-tertiary)',
                      borderRadius: '4px',
                      padding: '2px 8px',
                      fontSize: '10px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                    title="Unlock player and resume general ball-carrier view"
                  >
                    ✕ Unlock
                  </button>
                )}
              </div>

              {/* Micro-metric telemetry bar */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, 1fr)',
                  gap: '6px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  padding: '6px 8px',
                  borderRadius: '6px',
                  textAlign: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>RATING</div>
                  <div className="mono-stat" style={{ fontSize: '13px', fontWeight: 900, color: 'var(--color-accent-green)' }}>
                    {lockedPlayer.rating.toFixed(1)} {lockedPlayer.is_motm ? '★' : ''}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>BPS</div>
                  <div className="mono-stat" style={{ fontSize: '13px', fontWeight: 900, color: 'var(--color-accent-yellow)' }}>
                    {lockedPlayer.bps}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>TOP SPEED</div>
                  <div className="mono-stat" style={{ fontSize: '13px', fontWeight: 900, color: 'var(--color-accent-cyan)' }}>
                    {lockedPlayer.top_speed_kmh.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>DIST (KM)</div>
                  <div className="mono-stat" style={{ fontSize: '13px', fontWeight: 900, color: 'var(--color-text-primary)' }}>
                    {lockedPlayer.distance_km.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>xT CREATED</div>
                  <div className="mono-stat" style={{ fontSize: '13px', fontWeight: 900, color: 'var(--color-accent-yellow)' }}>
                    {lockedPlayer.xt_created >= 0 ? '+' : ''}{lockedPlayer.xt_created.toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                background: 'var(--color-bg-base)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '8px',
                padding: '8px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                  Lock telemetry on star player:
                </span>
                <span style={{ fontSize: '10px', color: 'var(--color-text-tertiary)' }}>
                  or click pitch/table
                </span>
              </div>
              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                {keyPlayers.map((kp) => (
                  <button
                    key={kp.id}
                    onClick={() => onSelectPlayer?.(kp.id)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: kp.team === 'Northbridge Lions' ? 'var(--color-team-home)' : 'var(--color-team-away)',
                      border: '1px solid var(--color-border-subtle)',
                      borderRadius: '12px',
                      padding: '2px 8px',
                      fontSize: '10px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    #{kp.num} {kp.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Persona Story Display Card */}
      <div
        id={`persona-panel-${activePersona}`}
        role="tabpanel"
        aria-label={`${activeMeta.label} narrative`}
        className="persona-story-card"
        dir="ltr"
        style={{ borderLeft: `3px solid ${activeColor}`, textAlign: undefined }}
      >
        <div className="persona-story-header">
          <span className="persona-story-label" style={{ color: activeColor }}>
            {activeMeta.icon} {isClubPersona ? `${favoriteClub} Loyalist` : activeMeta.label} Narrative
          </span>
          <span className="persona-story-desc">
            {isClubPersona ? `Passionate viewpoint from the ${favoriteClub} dugout` : activeMeta.desc}
          </span>
        </div>

        <p className="persona-story-text">
          {getStory()}
        </p>

        {/* Key Moment Metric Chips */}
        {insight && insight.metrics && (
          <div className="persona-chips-row" aria-label="Key telemetry values">
            {insight.metrics.pass_difficulty !== undefined && (
              <span className="persona-chip" style={{ color: 'var(--color-accent-green)' }}>
                PDR: {insight.metrics.pass_difficulty.toFixed(1)}%
              </span>
            )}
            {insight.metrics.ball_speed_kmh !== undefined && (
              <span className="persona-chip" style={{ color: 'var(--color-accent-cyan)' }}>
                Speed: {insight.metrics.ball_speed_kmh.toFixed(1)} km/h
              </span>
            )}
            {insight.metrics.xt_gained !== undefined && (
              <span className="persona-chip" style={{ color: 'var(--color-accent-yellow)' }}>
                Threat: {insight.metrics.xt_gained >= 0 ? '+' : ''}{insight.metrics.xt_gained.toFixed(2)} xT
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
