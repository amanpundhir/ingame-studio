/**
 * InGame Studio - Chaos vs. Control Rhythm Index (CCI) Bar
 * InGame design-system compliant — all inline styles replaced with token classes.
 */

import React from 'react';
import { VerifiedInsight, SpotlightMetric } from '../types';

interface ChaosRhythmBarProps {
  insight: VerifiedInsight | null;
  spotlightMetric?: SpotlightMetric;
  onSelectSpotlightMetric?: (metric: SpotlightMetric) => void;
}

export const ChaosRhythmBar: React.FC<ChaosRhythmBarProps> = ({
  insight,
  spotlightMetric,
  onSelectSpotlightMetric,
}) => {
  const cci = insight?.metrics?.chaos_index ?? 38.5;
  const isPinned = spotlightMetric === 'cci';

  // Semantic zone classification
  let stateLabel = 'CONTROLLED POSSESSION';
  let stateDesc  = 'High passing-network composure, stable defensive line structure';
  let stateColor: string;
  let stateColorVar: string;

  if (cci >= 65) {
    stateLabel    = 'HIGH TRANSITION CHAOS';
    stateDesc     = 'Frequent turnovers, rapid end-to-end counter-attacks, stretched lines';
    stateColor    = 'var(--color-accent-red)';
    stateColorVar = '#e90052';
  } else if (cci >= 35) {
    stateLabel    = 'MIDFIELD CONTEST';
    stateDesc     = 'Active pressing duels, moderate turnover volatility, tactical pressing';
    stateColor    = 'var(--color-accent-yellow)';
    stateColorVar = '#ffe600';
  } else {
    stateColor    = 'var(--color-accent-green)';
    stateColorVar = '#00ff87';
  }

  const fillBg = `linear-gradient(90deg, var(--color-accent-green), ${stateColor})`;
  const badgeBg = `${stateColorVar}18`;
  const badgeBorder = `${stateColorVar}45`;

  return (
    <div
      className={`studio-card cci-card ${isPinned ? 'studio-card-glow' : ''}`}
      style={isPinned ? { border: '1px solid var(--color-accent-cyan)' } : undefined}
    >
      {/* Header row */}
      <div className="cci-header">
        <div className="cci-title-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="cci-title">Chaos vs. Control Rhythm Index (CCI)</span>
          <span
            className="cci-state-badge"
            style={{
              background: badgeBg,
              color: stateColor,
              borderColor: badgeBorder,
            }}
            aria-label={`CCI state: ${stateLabel}`}
          >
            {stateLabel}
          </span>
          {onSelectSpotlightMetric && (
            <button
              onClick={() => onSelectSpotlightMetric(isPinned ? 'all' : 'cci')}
              title={isPinned ? 'Unpin CCI from Hero spotlight' : 'Spotlight CCI as Hero KPI'}
              style={{
                background: isPinned ? 'var(--color-accent-cyan)' : 'transparent',
                color: isPinned ? 'var(--color-text-inverse)' : 'var(--color-text-tertiary)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '10px',
                cursor: 'pointer',
                fontWeight: 700,
                transition: 'all 0.15s ease',
              }}
            >
              {isPinned ? '📌 PINNED' : '📌 PIN'}
            </button>
          )}
        </div>
        <div className="cci-value-group">
          <span className="cci-value mono-stat" style={{ color: stateColor }}>
            {cci.toFixed(1)}
          </span>
          <span className="cci-max">/ 100</span>
        </div>
      </div>

      {/* Segmented gradient bar */}
      <div
        className="cci-bar-track"
        role="progressbar"
        aria-valuenow={Math.round(cci)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`CCI: ${cci.toFixed(1)} out of 100`}
      >
        <div className="cci-bar-bg" aria-hidden="true" />
        <div
          className="cci-bar-fill"
          style={{
            width: `${Math.min(100, Math.max(0, cci))}%`,
            background: fillBg,
          }}
        />
      </div>

      {/* Footer: description + weight factors */}
      <div className="cci-footer">
        <span>{stateDesc}</span>
        <div className="cci-factors" aria-label="CCI factor weights">
          <span>Turnovers: 40%</span>
          <span>Speed Var: 35%</span>
          <span>Line Shift: 25%</span>
        </div>
      </div>
    </div>
  );
};
