/**
 * InGame Studio - Match Stats Overview
 * InGame design-system compliant — all inline styles replaced with token classes.
 * Team colours use CSS custom properties (--color-team-home / --color-team-away) per skill §2.2.
 */

import React from 'react';
import { MatchStatsData } from '../types';

interface MatchStatsOverviewProps {
  stats: MatchStatsData | null;
}

const EMPTY_STATS: MatchStatsData = {
  possession_pct: { home: 0, away: 0 },
  xg: { home: 0, away: 0 },
  shots: { home: { total: 0, on_target: 0 }, away: { total: 0, on_target: 0 } },
  passes: { home: { total: 0, completed: 0, accuracy_pct: 0 }, away: { total: 0, completed: 0, accuracy_pct: 0 } },
  tackles: { home: { total: 0, won: 0, won_pct: 0 }, away: { total: 0, won: 0, won_pct: 0 } },
  interceptions: { home: 0, away: 0 },
  fouls: { home: 0, away: 0 },
  cards: { home: { yellow: 0, red: 0 }, away: { yellow: 0, red: 0 } },
  corners: { home: 0, away: 0 },
  chaos_index: 0,
  score: { home: 0, away: 0 },
};

interface StatRowProps {
  homeVal: React.ReactNode;
  label: string;
  awayVal: React.ReactNode;
  homeWidth: number;
  awayWidth: number;
}

const StatRow: React.FC<StatRowProps> = ({ homeVal, label, awayVal, homeWidth, awayWidth }) => (
  <div className="mso-stat-card">
    <div className="mso-stat-row">
      <span className="mso-stat-val" style={{ color: 'var(--color-team-home)' }}>{homeVal}</span>
      <span className="mso-stat-label">{label}</span>
      <span className="mso-stat-val" style={{ color: 'var(--color-team-away)', textAlign: 'right' }}>{awayVal}</span>
    </div>
    <div className="mso-dual-bar" role="img" aria-label={`${label}: home ${homeWidth.toFixed(0)}%, away ${awayWidth.toFixed(0)}%`}>
      <div className="mso-dual-bar-seg" style={{ width: `${homeWidth}%`, background: 'var(--color-team-home)' }} />
      <div className="mso-dual-bar-seg" style={{ width: `${awayWidth}%`, background: 'var(--color-team-away)' }} />
    </div>
  </div>
);

export const MatchStatsOverview: React.FC<MatchStatsOverviewProps> = React.memo(({ stats }) => {
  const d = stats || EMPTY_STATS;

  const homePoss    = d.possession_pct?.home ?? 0;
  const awayPoss    = d.possession_pct?.away ?? 0;
  const homeXG      = d.xg?.home ?? 0;
  const awayXG      = d.xg?.away ?? 0;
  const totalXG     = Math.max(0.1, homeXG + awayXG);
  const homeXGPct   = (homeXG / totalXG) * 100;

  const homeShots   = d.shots?.home?.total ?? 0;
  const awayShots   = d.shots?.away?.total ?? 0;
  const homeShotsOT = d.shots?.home?.on_target ?? 0;
  const awayShotsOT = d.shots?.away?.on_target ?? 0;
  const totalShots  = Math.max(1, homeShots + awayShots);

  const homePasses  = d.passes?.home?.total ?? 0;
  const awayPasses  = d.passes?.away?.total ?? 0;
  const homePassAcc = d.passes?.home?.accuracy_pct ?? 0;
  const awayPassAcc = d.passes?.away?.accuracy_pct ?? 0;
  const totalPasses = Math.max(1, homePasses + awayPasses);

  const homeTackleWon  = d.tackles?.home?.won    ?? 0;
  const homeTackleTotal= d.tackles?.home?.total  ?? 0;
  const awayTackleWon  = d.tackles?.away?.won    ?? 0;
  const awayTackleTotal= d.tackles?.away?.total  ?? 0;
  const homeTacklePct  = d.tackles?.home?.won_pct ?? Math.round((homeTackleWon / Math.max(1, homeTackleTotal)) * 100);
  const awayTacklePct  = d.tackles?.away?.won_pct ?? Math.round((awayTackleWon / Math.max(1, awayTackleTotal)) * 100);
  const totalTackle    = Math.max(1, homeTacklePct + awayTacklePct);

  const chaosIndex = d.chaos_index ?? 0;

  return (
    <div className="studio-card mso-card" aria-label="Match statistics overview">
      {/* Section header */}
      <div className="mso-header">
        <div className="mso-title-group">
          <svg className="mso-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <rect x="2" y="10" width="3" height="8" rx="1" fill="currentColor" opacity=".5" />
            <rect x="7" y="6"  width="3" height="12" rx="1" fill="currentColor" opacity=".75" />
            <rect x="12" y="2" width="3" height="16" rx="1" fill="currentColor" />
            <rect x="17" y="8" width="1" height="1" rx=".5" fill="none" />
          </svg>
          <div>
            <div className="mso-title">Match Stats Overview</div>
            <div className="mso-subtitle">Live synthetic match statistics</div>
          </div>
        </div>

        {/* Team legend */}
        <div className="mso-legend" aria-label="Team colour legend">
          <div className="mso-legend-team">
            <span className="mso-legend-dot" style={{ background: 'var(--color-team-home)' }} aria-hidden="true" />
            <span style={{ color: 'var(--color-team-home)', fontWeight: 800 }}>NORTHBRIDGE</span>
          </div>
          <span className="mso-legend-sep">VS</span>
          <div className="mso-legend-team">
            <span className="mso-legend-dot" style={{ background: 'var(--color-team-away)' }} aria-hidden="true" />
            <span style={{ color: 'var(--color-team-away)', fontWeight: 800 }}>HARBOURSIDE</span>
          </div>
        </div>
      </div>

      {/* Metric cards grid */}
      <div className="mso-grid">
        <StatRow
          homeVal={`${homePoss.toFixed(1)}%`}
          label="Possession %"
          awayVal={`${awayPoss.toFixed(1)}%`}
          homeWidth={homePoss}
          awayWidth={awayPoss}
        />
        <StatRow
          homeVal={homeXG.toFixed(2)}
          label="Expected Goals (xG)"
          awayVal={awayXG.toFixed(2)}
          homeWidth={homeXGPct}
          awayWidth={100 - homeXGPct}
        />
        <div className="mso-stat-card">
          <div className="mso-stat-row">
            <div>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-home)' }}>{homeShots}</span>
              <span className="mso-stat-label" style={{ marginLeft: 4 }}>({homeShotsOT})</span>
            </div>
            <span className="mso-stat-label">Shots (On Target)</span>
            <div style={{ textAlign: 'right' }}>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-away)' }}>{awayShots}</span>
              <span className="mso-stat-label" style={{ marginLeft: 4 }}>({awayShotsOT})</span>
            </div>
          </div>
          <div className="mso-dual-bar" role="img" aria-label={`Shots — home ${homeShots}, away ${awayShots}`}>
            <div className="mso-dual-bar-seg" style={{ width: `${(homeShots / totalShots) * 100}%`, background: 'var(--color-team-home)' }} />
            <div className="mso-dual-bar-seg" style={{ width: `${(awayShots / totalShots) * 100}%`, background: 'var(--color-team-away)' }} />
          </div>
        </div>
        <div className="mso-stat-card">
          <div className="mso-stat-row">
            <div>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-home)' }}>{homePasses}</span>
              <span style={{ fontSize: 'var(--text-micro)', color: 'var(--color-accent-green)', marginLeft: 4 }}>[{homePassAcc.toFixed(1)}%]</span>
            </div>
            <span className="mso-stat-label">Passes (Acc %)</span>
            <div style={{ textAlign: 'right' }}>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-away)' }}>{awayPasses}</span>
              <span style={{ fontSize: 'var(--text-micro)', color: 'var(--color-accent-green)', marginLeft: 4 }}>[{awayPassAcc.toFixed(1)}%]</span>
            </div>
          </div>
          <div className="mso-dual-bar" role="img" aria-label={`Passes — home ${homePasses}, away ${awayPasses}`}>
            <div className="mso-dual-bar-seg" style={{ width: `${(homePasses / totalPasses) * 100}%`, background: 'var(--color-team-home)' }} />
            <div className="mso-dual-bar-seg" style={{ width: `${(awayPasses / totalPasses) * 100}%`, background: 'var(--color-team-away)' }} />
          </div>
        </div>
        <div className="mso-stat-card">
          <div className="mso-stat-row">
            <div>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-home)' }}>{homeTacklePct}%</span>
              <span className="mso-stat-label" style={{ marginLeft: 4 }}>({homeTackleWon}/{homeTackleTotal})</span>
            </div>
            <span className="mso-stat-label">Tackles Won %</span>
            <div style={{ textAlign: 'right' }}>
              <span className="mso-stat-val" style={{ color: 'var(--color-team-away)' }}>{awayTacklePct}%</span>
              <span className="mso-stat-label" style={{ marginLeft: 4 }}>({awayTackleWon}/{awayTackleTotal})</span>
            </div>
          </div>
          <div className="mso-dual-bar" role="img" aria-label={`Tackles won — home ${homeTacklePct}%, away ${awayTacklePct}%`}>
            <div className="mso-dual-bar-seg" style={{ width: `${(homeTacklePct / totalTackle) * 100}%`, background: 'var(--color-team-home)' }} />
            <div className="mso-dual-bar-seg" style={{ width: `${(awayTacklePct / totalTackle) * 100}%`, background: 'var(--color-team-away)' }} />
          </div>
        </div>

        {/* Chaos Index mini-card */}
        <div className="mso-stat-card">
          <div className="mso-stat-row">
            <span className="mso-stat-label" style={{ color: 'var(--color-accent-green)' }}>CONTROL</span>
            <span className="mso-stat-label">
              Chaos Index:{' '}
              <strong className="mono-stat" style={{ color: 'var(--color-accent-cyan)' }}>
                {chaosIndex.toFixed(1)}
              </strong>
            </span>
            <span className="mso-stat-label" style={{ color: 'var(--color-accent-red)' }}>CHAOS</span>
          </div>
          <div
            className="progress-bar"
            role="progressbar"
            aria-valuenow={Math.round(chaosIndex)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Chaos index: ${chaosIndex.toFixed(1)}`}
          >
            <div
              className="progress-fill"
              style={{
                width: `${Math.min(100, Math.max(0, chaosIndex))}%`,
                background: 'linear-gradient(90deg, var(--color-accent-green) 0%, var(--color-accent-yellow) 50%, var(--color-accent-red) 100%)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Disciplinary & set-pieces strip */}
      <div className="mso-secondary-strip">
        <div className="mso-sec-item">
          <span className="mono-stat" style={{ color: 'var(--color-team-home)', fontWeight: 700 }}>{d.corners?.home ?? 6}</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>Corners</span>
          <span className="mono-stat" style={{ color: 'var(--color-team-away)', fontWeight: 700 }}>{d.corners?.away ?? 5}</span>
        </div>
        <span className="mso-sec-sep" aria-hidden="true">·</span>
        <div className="mso-sec-item">
          <span className="mono-stat" style={{ color: 'var(--color-team-home)', fontWeight: 700 }}>{d.fouls?.home ?? 10}</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>Fouls</span>
          <span className="mono-stat" style={{ color: 'var(--color-team-away)', fontWeight: 700 }}>{d.fouls?.away ?? 12}</span>
        </div>
        <span className="mso-sec-sep" aria-hidden="true">·</span>
        <div className="mso-sec-item">
          <span className="mono-stat" style={{ color: 'var(--color-team-home)', fontWeight: 700 }}>
            🟨 {d.cards?.home?.yellow ?? 2}
          </span>
          <span style={{ color: 'var(--color-text-secondary)' }}>Yellow Cards</span>
          <span className="mono-stat" style={{ color: 'var(--color-team-away)', fontWeight: 700 }}>
            🟨 {d.cards?.away?.yellow ?? 3}
          </span>
        </div>
        <span className="mso-sec-sep" aria-hidden="true">·</span>
        <div className="mso-sec-item">
          <span className="mono-stat" style={{ color: 'var(--color-team-home)', fontWeight: 700 }}>{d.interceptions?.home ?? 11}</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>Interceptions</span>
          <span className="mono-stat" style={{ color: 'var(--color-team-away)', fontWeight: 700 }}>{d.interceptions?.away ?? 9}</span>
        </div>
      </div>
    </div>
  );
});
