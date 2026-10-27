/**
 * InGame Studio - InGame KPI Strip
 * 5 prominent match metric cards: Possession %, Expected Goals (xG),
 * Shots on Target, Pass Accuracy %, and Field Tilt / Territory.
 * Dual home/away comparison bars with --color-team-home and --color-team-away.
 */

import React from 'react';
import { MatchStatsData, AnalyticsResponse } from '../types';

export interface InGameKpiStripProps {
  matchStats?: MatchStatsData | null;
  analytics?: AnalyticsResponse | null;
  homeTeamName?: string;
  awayTeamName?: string;
}

interface KpiCardConfig {
  id: string;
  title: string;
  icon: React.ReactNode;
  homeValue: string;
  awayValue: string;
  homePct: number;
  awayPct: number;
  sublabel: string;
}

export const InGameKpiStrip: React.FC<InGameKpiStripProps> = ({
  matchStats,
  analytics,
  homeTeamName = 'NBL',
  awayTeamName = 'HSC',
}) => {
  // Extract or fall back to statistics
  const stats = matchStats || analytics?.match_stats;

  // 1. Possession %
  const rawHomePoss = stats?.possession_pct?.home ?? 53;
  const rawAwayPoss = stats?.possession_pct?.away ?? 47;
  const totalPoss = rawHomePoss + rawAwayPoss || 100;
  const homePoss = Math.round((rawHomePoss / totalPoss) * 100);
  const awayPoss = 100 - homePoss;

  // 2. Expected Goals (xG)
  const homeXg = stats?.xg?.home ?? 1.62;
  const awayXg = stats?.xg?.away ?? 1.18;
  const totalXg = homeXg + awayXg || 1;
  const homeXgPct = Math.round((homeXg / totalXg) * 100);
  const awayXgPct = 100 - homeXgPct;

  // 3. Shots on Target
  const homeOnTarget = stats?.shots?.home?.on_target ?? 5;
  const homeTotalShots = stats?.shots?.home?.total ?? 12;
  const awayOnTarget = stats?.shots?.away?.on_target ?? 3;
  const awayTotalShots = stats?.shots?.away?.total ?? 8;
  const totalShotsOT = homeOnTarget + awayOnTarget || 1;
  const homeShotsPct = Math.round((homeOnTarget / totalShotsOT) * 100);
  const awayShotsPct = 100 - homeShotsPct;

  // 4. Pass Accuracy %
  const homePassAcc = Math.round(stats?.passes?.home?.accuracy_pct ?? 88);
  const awayPassAcc = Math.round(stats?.passes?.away?.accuracy_pct ?? 84);
  const totalAcc = homePassAcc + awayPassAcc || 100;
  const homeAccPct = Math.round((homePassAcc / totalAcc) * 100);
  const awayAccPct = 100 - homeAccPct;

  // 5. Field Tilt / Territory
  const rawHomeTilt = stats?.field_tilt?.home ?? 57;
  const rawAwayTilt = stats?.field_tilt?.away ?? 43;
  const totalTilt = rawHomeTilt + rawAwayTilt || 100;
  const homeTilt = Math.round((rawHomeTilt / totalTilt) * 100);
  const awayTilt = 100 - homeTilt;

  const cards: KpiCardConfig[] = [
    {
      id: 'possession',
      title: 'POSSESSION',
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a10 10 0 0 0 0 20" fill="currentColor" fillOpacity="0.2" />
        </svg>
      ),
      homeValue: `${homePoss}%`,
      awayValue: `${awayPoss}%`,
      homePct: homePoss,
      awayPct: awayPoss,
      sublabel: 'Ball Control Dominance',
    },
    {
      id: 'xg',
      title: 'EXPECTED GOALS (xG)',
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m19 11-4-7-4 7h8Z" />
          <circle cx="12" cy="18" r="3" />
        </svg>
      ),
      homeValue: homeXg.toFixed(2),
      awayValue: awayXg.toFixed(2),
      homePct: homeXgPct,
      awayPct: awayXgPct,
      sublabel: 'Chance Quality Created',
    },
    {
      id: 'shots',
      title: 'SHOTS ON TARGET',
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="3" />
          <line x1="12" y1="2" x2="12" y2="5" />
          <line x1="12" y1="19" x2="12" y2="22" />
          <line x1="2" y1="12" x2="5" y2="12" />
          <line x1="19" y1="12" x2="22" y2="12" />
        </svg>
      ),
      homeValue: `${homeOnTarget} (${homeTotalShots})`,
      awayValue: `${awayOnTarget} (${awayTotalShots})`,
      homePct: homeShotsPct,
      awayPct: awayShotsPct,
      sublabel: 'On Target / Total Attempts',
    },
    {
      id: 'pass_acc',
      title: 'PASS ACCURACY',
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
      homeValue: `${homePassAcc}%`,
      awayValue: `${awayPassAcc}%`,
      homePct: homeAccPct,
      awayPct: awayAccPct,
      sublabel: 'Completed Distribution %',
    },
    {
      id: 'field_tilt',
      title: 'FIELD TILT / TERRITORY',
      icon: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      ),
      homeValue: `${homeTilt}%`,
      awayValue: `${awayTilt}%`,
      homePct: homeTilt,
      awayPct: awayTilt,
      sublabel: 'Final Third Possession Share',
    },
  ];

  return (
    <div
      className="ingame-kpi-strip"
      aria-label="Match KPI Strip"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--spacing-sm)',
        width: '100%',
      }}
    >
      {cards.map((card) => (
        <div
          key={card.id}
          className="studio-card"
          style={{
            padding: '10px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            background: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--spacing-sm)',
            transition: 'border-color 0.15s ease',
          }}
        >
          {/* Card Header: Icon & Metric Title */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              color: 'var(--color-text-secondary)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: 'var(--color-accent-cyan)' }}>{card.icon}</span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                {card.title}
              </span>
            </div>
            <span
              style={{
                fontSize: '10px',
                color: 'var(--color-text-tertiary)',
                fontWeight: 600,
              }}
            >
              H / A
            </span>
          </div>

          {/* Value Row: Home vs Away */}
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: '6px',
            }}
          >
            {/* Home Side Value */}
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
              <span
                style={{
                  fontSize: '9px',
                  fontWeight: 800,
                  color: 'var(--color-team-home)',
                  textTransform: 'uppercase',
                }}
              >
                {homeTeamName}
              </span>
              <span
                className="mono-stat"
                style={{
                  fontSize: '18px',
                  fontWeight: 800,
                  color: 'var(--color-team-home)',
                  lineHeight: 1,
                }}
              >
                {card.homeValue}
              </span>
            </div>

            <span
              style={{
                fontSize: '10px',
                color: 'var(--color-text-tertiary)',
                fontWeight: 700,
              }}
            >
              vs
            </span>

            {/* Away Side Value */}
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
              <span
                className="mono-stat"
                style={{
                  fontSize: '18px',
                  fontWeight: 800,
                  color: 'var(--color-team-away)',
                  lineHeight: 1,
                }}
              >
                {card.awayValue}
              </span>
              <span
                style={{
                  fontSize: '9px',
                  fontWeight: 800,
                  color: 'var(--color-team-away)',
                  textTransform: 'uppercase',
                }}
              >
                {awayTeamName}
              </span>
            </div>
          </div>

          {/* Dual Home / Away Comparison Bar */}
          <div
            style={{
              width: '100%',
              height: '5px',
              background: 'rgba(255, 255, 255, 0.06)',
              borderRadius: '3px',
              overflow: 'hidden',
              display: 'flex',
            }}
            role="progressbar"
            aria-label={`${card.title} comparison: ${homeTeamName} ${card.homePct}%, ${awayTeamName} ${card.awayPct}%`}
            aria-valuenow={card.homePct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              style={{
                width: `${card.homePct}%`,
                background: 'var(--color-team-home)',
                transition: 'width 0.3s ease',
              }}
            />
            <div
              style={{
                width: `${card.awayPct}%`,
                background: 'var(--color-team-away)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>

          {/* Card Subtitle */}
          <div
            style={{
              fontSize: '10px',
              color: 'var(--color-text-tertiary)',
              letterSpacing: '0.01em',
              lineHeight: 1.2,
            }}
          >
            {card.sublabel}
          </div>
        </div>
      ))}
    </div>
  );
};

export default InGameKpiStrip;
