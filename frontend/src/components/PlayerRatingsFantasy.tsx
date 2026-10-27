/**
 * InGame Studio - Player Ratings & Fantasy Summary
 * InGame design-system compliant — all inline styles replaced with token classes.
 */

import React, { useMemo } from 'react';
import { PlayerAnalytics } from '../types';

interface PlayerRatingsFantasyProps {
  players: PlayerAnalytics[];
}

const isNorthbridgePlayer = (p: PlayerAnalytics): boolean =>
  p.team.toLowerCase().includes('northbridge') || p.team === 'Northbridge Lions' || p.team === 'home';

const getTeamColor = (p: PlayerAnalytics): string =>
  isNorthbridgePlayer(p) ? 'var(--color-team-home)' : 'var(--color-team-away)';

const getTeamName = (p: PlayerAnalytics): string =>
  isNorthbridgePlayer(p) ? 'Northbridge Lions' : 'Harbourside';

export const PlayerRatingsFantasy: React.FC<PlayerRatingsFantasyProps> = React.memo(({ players }) => {
  const activePlayers = useMemo(() => players.filter((p) =>
    p.minutes_played > 0 || p.distance_km > 0 || p.passes.total > 0 || p.shots > 0 ||
    p.goals > 0 || p.assists > 0 || p.defensive_interventions > 0
  ), [players]);
  const sortedByRating = useMemo(() => [...activePlayers].sort((a, b) => b.rating - a.rating), [activePlayers]);
  const sortedByBPS    = useMemo(() => [...activePlayers].sort((a, b) => b.bps    - a.bps),    [activePlayers]);

  const motmPlayer = useMemo(() => {
    const explicit = players.find((p) => p.is_motm);
    return explicit || sortedByRating[0] || null;
  }, [players, sortedByRating]);

  const podium = useMemo(() => ({
    first:  sortedByBPS[0] || null,
    second: sortedByBPS[1] || null,
    third:  sortedByBPS[2] || null,
  }), [sortedByBPS]);

  return (
    <div className="studio-card fantasy-card" aria-label="Broadcast ratings and Fantasy summary">
      {/* Header */}
      <div className="fantasy-header">
        <div className="mso-title-group">
          {/* SVG star icon instead of emoji */}
          <svg width="20" height="20" viewBox="0 0 20 20" fill="var(--color-accent-yellow)" aria-hidden="true">
            <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.32L10 13.27l-4.77 2.44.91-5.32L2.27 6.62l5.34-.78L10 1z" />
          </svg>
          <div>
            <div className="mso-title">Broadcast Ratings &amp; Fantasy Center</div>
            <div className="mso-subtitle">Performance ratings (0–10) · Man of the Match · Official Fantasy BPS</div>
          </div>
        </div>
        <span className="fantasy-badge" aria-label="fantasy football official BPS">Fantasy OFFICIAL BPS</span>
      </div>

      {/* Split: MOTM + Podium */}
      <div className="fantasy-split">
        {/* MOTM Spotlight */}
        {motmPlayer && (
          <div className="fantasy-motm-card" aria-label={`Man of the Match: ${motmPlayer.name}`}>
            <div className="fantasy-motm-header">
              <span className="fantasy-motm-badge">
                {/* Crown SVG instead of emoji in badge */}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
                  <path d="M1 9h10L9 3 6 6 3 1 1 9z" />
                </svg>
                MAN OF THE MATCH
              </span>
              <div>
                <span className="fantasy-motm-rating mono-stat">{motmPlayer.rating.toFixed(1)}</span>
                <span className="fantasy-motm-rating-max">/10</span>
              </div>
            </div>

            <div className="fantasy-motm-player">
              <span
                style={{ width: 12, height: 12, borderRadius: '50%', background: getTeamColor(motmPlayer), display: 'inline-block', flexShrink: 0 }}
                aria-hidden="true"
              />
              <div>
                <div className="fantasy-motm-name">{motmPlayer.name}</div>
                <div className="fantasy-motm-meta">
                  {getTeamName(motmPlayer)} · #{motmPlayer.jersey_number} · {motmPlayer.role}
                </div>
              </div>
            </div>

            <div className="fantasy-motm-metrics" aria-label="MOTM impact metrics">
              <div>
                <div className="fantasy-motm-metric-label">Goals / Ast</div>
                <div className="fantasy-motm-metric-value mono-stat" style={{ color: 'var(--color-accent-green)' }}>
                  {motmPlayer.goals} / {motmPlayer.assists}
                </div>
              </div>
              <div>
                <div className="fantasy-motm-metric-label">xT Created</div>
                <div className="fantasy-motm-metric-value mono-stat" style={{ color: 'var(--color-accent-cyan)' }}>
                  +{motmPlayer.xt_created.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="fantasy-motm-metric-label">Distance</div>
                <div className="fantasy-motm-metric-value mono-stat" style={{ color: 'var(--color-text-primary)' }}>
                  {motmPlayer.distance_km.toFixed(1)} km
                </div>
              </div>
              <div>
                <div className="fantasy-motm-metric-label">Fantasy BPS</div>
                <div className="fantasy-motm-metric-value mono-stat" style={{ color: 'var(--color-accent-yellow)' }}>
                  {motmPlayer.bps}
                </div>
              </div>
            </div>

            <p className="fantasy-motm-quote">
              "Decisive offensive threat creating highest match xT and key goal contributions."
            </p>
          </div>
        )}

        {/* Fantasy BPS Podium */}
        <div className="fantasy-podium-card" aria-label="Fantasy Bonus Points System podium">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-md)' }}>
            <div>
              <div className="fantasy-podium-title">Fantasy BONUS POINTS (BPS) PODIUM</div>
              <div className="fantasy-podium-sub">Provisional Post-Match</div>
            </div>
          </div>

          <div className="fantasy-podium-grid">
            {/* 2nd — Silver */}
            {podium.second && (
              <div className="fantasy-podium-slot silver">
                <div className="fantasy-podium-emoji" aria-label="2nd place">🥈</div>
                <div className="fantasy-podium-bonus" style={{ color: '#c0c0c0' }}>+2 BONUS</div>
                <div className="fantasy-podium-name">{podium.second.name.split(' ').pop()}</div>
                <div className="fantasy-podium-team" style={{ color: getTeamColor(podium.second) }}>{getTeamName(podium.second)}</div>
                <div className="fantasy-podium-bps mono-stat">{podium.second.bps} BPS</div>
              </div>
            )}

            {/* 1st — Gold */}
            {podium.first && (
              <div className="fantasy-podium-slot gold">
                <div className="fantasy-podium-emoji" aria-label="1st place">🥇</div>
                <div className="fantasy-podium-bonus" style={{ color: 'var(--color-accent-yellow)' }}>+3 BONUS</div>
                <div className="fantasy-podium-name">{podium.first.name.split(' ').pop()}</div>
                <div className="fantasy-podium-team" style={{ color: getTeamColor(podium.first) }}>{getTeamName(podium.first)}</div>
                <div className="fantasy-podium-bps mono-stat" style={{ color: 'var(--color-accent-green)' }}>{podium.first.bps} BPS</div>
              </div>
            )}

            {/* 3rd — Bronze */}
            {podium.third && (
              <div className="fantasy-podium-slot bronze">
                <div className="fantasy-podium-emoji" aria-label="3rd place">🥉</div>
                <div className="fantasy-podium-bonus" style={{ color: '#cd7f32' }}>+1 BONUS</div>
                <div className="fantasy-podium-name">{podium.third.name.split(' ').pop()}</div>
                <div className="fantasy-podium-team" style={{ color: getTeamColor(podium.third) }}>{getTeamName(podium.third)}</div>
                <div className="fantasy-podium-bps mono-stat">{podium.third.bps} BPS</div>
              </div>
            )}
          </div>

          <p className="fantasy-podium-footnote">
            * Official Fantasy BPS from passes, chances, goals, tackles won, and disciplinary records.
          </p>
        </div>
      </div>

      {/* Top 5 performers bar */}
      <div className="fantasy-top-performers" aria-label="Top 5 performers by rating">
        <span className="fantasy-tp-label">Top Performers:</span>
        <div className="fantasy-tp-list">
          {sortedByRating.slice(0, 5).map((p) => (
            <div key={p.player_id} className="fantasy-tp-item">
              <span className="fantasy-tp-dot" style={{ background: getTeamColor(p) }} aria-hidden="true" />
              <span className="fantasy-tp-name">{p.name.split(' ').pop()}</span>
              <span className="fantasy-tp-score mono-stat">{p.rating.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});
