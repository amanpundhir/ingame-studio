/**
 * InGame Studio - Progressive Event Timeline & Interactive Replay Jump
 * InGame design-system compliant — all inline styles replaced with token classes.
 */

import React, { useMemo } from 'react';
import { MatchEvent, ClubPerspective, SpotlightMetric } from '../types';

interface ProgressiveTimelineProps {
  events: MatchEvent[];
  currentClock: string;
  currentFrameIndex?: number;
  activeEventId?: string | null;
  onJumpToEvent: (eventId: string) => void;
  onSimulateFull?: () => void;
  isSimulatingFull?: boolean;
  favoriteClub?: ClubPerspective;
  clubModeActive?: boolean;
  spotlightMetric?: SpotlightMetric;
}

export const ProgressiveTimeline: React.FC<ProgressiveTimelineProps> = React.memo(({
  events,
  currentClock,
  currentFrameIndex,
  activeEventId,
  onJumpToEvent,
  onSimulateFull,
  isSimulatingFull = false,
  favoriteClub = 'Northbridge Lions',
  clubModeActive = false,
  spotlightMetric = 'all',
}) => {
  const parseClockToSeconds = (clk: string): number => {
    if (!clk) return 0;
    const parts = clk.split(':');
    if (parts.length === 2) {
      return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    }
    return 0;
  };

  const currentSeconds = parseClockToSeconds(currentClock || '00:00');

  const revealedEvents = useMemo(() => {
    return events.filter((ev) => {
      const evSec = parseClockToSeconds(ev.clock);
      if (evSec <= currentSeconds) return true;
      if (
        currentFrameIndex !== undefined &&
        ev.frame_index !== undefined &&
        ev.frame_index <= currentFrameIndex
      ) {
        return true;
      }
      return false;
    });
  }, [events, currentClock, currentFrameIndex, currentSeconds]);

  const hiddenCount = Math.max(0, events.length - revealedEvents.length);
  const metricLabel: Record<Exclude<SpotlightMetric, 'all'>, string> = { pdr: 'PDR', speed: 'SPEED', xt: 'xT', cci: 'CCI' };
  const isFavoriteClubEvent = (ev: MatchEvent): boolean => {
    const team = (ev.team || '').toLowerCase();
    const home = team === 'home' || team.includes('northbridge');
    const away = team === 'away' || team.includes('city');
    return favoriteClub === 'Northbridge Lions' ? home : away;
  };
  const getSpotlightValue = (ev: MatchEvent): number | undefined => {
    const metrics = ev.tactical_metrics || {};
    const key = spotlightMetric === 'pdr' ? 'pass_difficulty'
      : spotlightMetric === 'speed' ? 'ball_speed_kmh'
        : spotlightMetric === 'xt' ? 'xt_gained'
          : spotlightMetric === 'cci' ? 'chaos_index' : '';
    const value = metrics[key];
    return typeof value === 'number' ? value : undefined;
  };

  const getEventIcon = (type: string, subType?: string): string => {
    const t  = (type    || '').toLowerCase();
    const st = (subType || '').toLowerCase();
    if (t.includes('goal') || st.includes('goal')) return '⚽';
    if (t.includes('shot'))                         return '🎯';
    if (t.includes('pass'))                         return '↗';
    if (t.includes('tackle'))                       return '🛡';
    if (t.includes('turnover') || t.includes('interception')) return '🔄';
    if (t.includes('foul'))                         return '⚠';
    if (t.includes('substitution'))                 return '⇄';
    if (t.includes('card'))                         return st.includes('yellow_card') ? '🟨' : '🟥';
    if (t.includes('save'))                         return '🧤';
    return '◉';
  };

  return (
    <div className="studio-card timeline-card" aria-label="Match timeline">
      {/* Header */}
      <div className="timeline-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)' }}>
            <span className="timeline-title">Match Timeline</span>
            <span className="timeline-count" aria-live="polite">
              {revealedEvents.length}/{events.length}
            </span>
          </div>
          <div className="timeline-sub">Chronological revelation · Click to replay</div>
        </div>

        {onSimulateFull && (
          <button
            className="timeline-sim-btn"
            onClick={onSimulateFull}
            disabled={isSimulatingFull}
            title="Fast-forward simulation to 90'+ full-time and reveal all match analytics"
            aria-label={isSimulatingFull ? 'Simulation in progress' : 'Simulate full match'}
          >
            <span aria-hidden="true">⚡</span>
            <span>{isSimulatingFull ? 'SIMULATING…' : 'SIMULATE FULL MATCH'}</span>
          </button>
        )}
      </div>

      {(clubModeActive || spotlightMetric !== 'all') && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', padding: '0 12px 8px' }} aria-live="polite">
          {clubModeActive && (
            <span style={{ color: favoriteClub === 'Northbridge Lions' ? 'var(--color-team-home)' : 'var(--color-team-away)', fontSize: '10px', fontWeight: 900 }}>
              ★ YOUR CLUB: {favoriteClub} events highlighted
            </span>
          )}
          {spotlightMetric !== 'all' && (
            <span style={{ color: 'var(--color-accent-cyan)', fontSize: '10px', fontWeight: 900 }}>
              TRACKING {metricLabel[spotlightMetric]} across event metrics
            </span>
          )}
        </div>
      )}

      {/* Scrollable event list */}
      <div className="timeline-list" role="feed" aria-label="Match events">
        {revealedEvents.length === 0 ? (
          <div className="timeline-empty" role="status">
            Waiting for match kickoff… Events reveal as time advances.
          </div>
        ) : (
          revealedEvents.map((ev) => {
            const isActive  = activeEventId === ev.event_id;
            const isFavorite = clubModeActive && isFavoriteClubEvent(ev);
            const metricValue = getSpotlightValue(ev);
            const isNorthbridge = (ev.team || '').toLowerCase().includes('northbridge') || ev.team === 'home' || ev.team === 'Northbridge Lions';
            const teamColor = isNorthbridge ? 'var(--color-team-home)' : 'var(--color-team-away)';
            const teamName  = isNorthbridge ? 'Northbridge Lions' : 'Harbourside';
            const isGoal    =
              (ev.event_type || '').toLowerCase().includes('goal') ||
              (ev.outcome    || '').toLowerCase().includes('goal');
            const clockColor = isGoal ? 'var(--color-accent-yellow)' : 'var(--color-accent-cyan)';

            return (
              <button
                key={ev.event_id}
                className={`timeline-event-btn${isActive ? ' active' : ''}${isGoal ? ' goal' : ''}`}
                style={isFavorite ? {
                  borderLeft: `3px solid ${favoriteClub === 'Northbridge Lions' ? 'var(--color-team-home)' : 'var(--color-team-away)'}`,
                  background: favoriteClub === 'Northbridge Lions' ? 'rgba(239, 1, 7, 0.09)' : 'rgba(108, 171, 221, 0.09)',
                } : undefined}
                onClick={() => onJumpToEvent(ev.event_id)}
                aria-label={`${ev.player_name || 'Match action'} — ${ev.event_type} at ${ev.clock}`}
                aria-current={isActive ? 'true' : undefined}
              >
                <div className="timeline-event-left">
                  <span className="timeline-event-icon" aria-hidden="true">
                    {getEventIcon(ev.event_type, ev.sub_type)}
                  </span>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)' }}>
                      <span
                        className="timeline-event-dot"
                        style={{ background: teamColor }}
                        aria-hidden="true"
                      />
                      <span className={`timeline-event-name${isActive ? ' active' : ''}`}>
                        {ev.player_name || 'Match Action'}
                      </span>
                    </div>
                    <div className="timeline-event-desc">
                      {teamName} · {ev.event_type.replace(/_/g, ' ')}
                      {ev.sub_type ? ` (${ev.sub_type})` : ''}
                      {isFavorite && <span style={{ marginLeft: '6px', color: favoriteClub === 'Northbridge Lions' ? 'var(--color-team-home)' : 'var(--color-team-away)', fontWeight: 900 }}>YOUR CLUB</span>}
                    </div>
                  </div>
                </div>

                <div className="timeline-event-right">
                  <span className="timeline-event-clock mono-stat" style={{ color: clockColor }}>
                    {ev.clock}
                  </span>
                  {spotlightMetric !== 'all' && (
                    <span className="mono-stat" style={{ fontSize: '9px', color: 'var(--color-accent-cyan)' }}>
                      {metricValue === undefined ? '—' : `${metricValue.toFixed(1)}${spotlightMetric === 'pdr' ? '%' : spotlightMetric === 'speed' ? ' km/h' : ''}`}
                    </span>
                  )}
                  {isActive && (
                    <span className="timeline-replay-tag" aria-live="polite">REPLAY ACTIVE</span>
                  )}
                </div>
              </button>
            );
          })
        )}

        {hiddenCount > 0 && (
          <div className="timeline-hidden-banner" aria-live="polite">
            <span aria-hidden="true">🔒</span>
            <span>
              <strong>{hiddenCount} future event{hiddenCount !== 1 ? 's' : ''} hidden</strong> until match clock advances
            </span>
          </div>
        )}
      </div>
    </div>
  );
});
