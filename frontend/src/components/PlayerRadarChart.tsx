/**
 * InGame Studio — 6-Axis Tactical Radar Chart
 * Broadcast-grade SVG radar chart visualizing player attribute profile across:
 * Pace, Shooting, Passing, Defending, Threat, and Work Rate.
 * Conforms strictly to the InGame UI Design System.
 */

import React, { useMemo } from 'react';
import { PlayerAnalytics } from '../types';

export interface RadarMetric {
  key: string;
  label: string;
  value: number; // 0 to 100
  displayValue?: string;
  subtext?: string;
}

export interface PlayerRadarChartProps {
  player?: PlayerAnalytics | null;
  customMetrics?: RadarMetric[];
  size?: number; // default 340
  teamColor?: string;
  showLabels?: boolean;
  className?: string;
}

/**
 * Computes calibrated 6-axis tactical attributes from a player's analytical profile.
 * Produces authentic broadcast metrics across all positions.
 */
export const computePlayerRadarMetrics = (p: PlayerAnalytics | null | undefined): RadarMetric[] => {
  if (!p) {
    return [
      { key: 'pace', label: 'Pace', value: 75, displayValue: '31.2 km/h', subtext: 'Sprint Speed' },
      { key: 'shooting', label: 'Shooting', value: 70, displayValue: '0.45 xG', subtext: 'Finishing & Power' },
      { key: 'threat', label: 'Threat', value: 78, displayValue: '+0.32 xT', subtext: 'Expected Threat' },
      { key: 'workrate', label: 'Work Rate', value: 82, displayValue: '9.4 km', subtext: 'Stamina & Coverage' },
      { key: 'defending', label: 'Defending', value: 65, displayValue: '6 Interv', subtext: 'Tackles & Duels' },
      { key: 'passing', label: 'Passing', value: 80, displayValue: '85.4%', subtext: 'Vision & Delivery' },
    ];
  }

  // The backend ranks each axis against every player in the match (percentile, counts per 90).
  if (Array.isArray(p.radar) && p.radar.length === 6) {
    return p.radar.map((axis) => ({
      key: axis.key,
      label: axis.label,
      value: axis.value,
      displayValue: axis.displayValue,
      subtext: `Better than ${Math.round(axis.value)}% of players`,
    }));
  }

  const role = (p.role || 'MF').toUpperCase();
  const isGk = role === 'GK';
  const isDf = role === 'DF';
  const isMf = role === 'MF';
  const isFw = role === 'FW';

  // 1. Pace: based on top_speed_kmh (calibrated across 20 - 36 km/h)
  const topSpeed = p.top_speed_kmh || (isFw ? 33.5 : isMf ? 31.0 : isDf ? 32.5 : 26.0);
  const paceScore = Math.min(99, Math.max(30, Math.round(((topSpeed - 20) / (36.0 - 20)) * 65 + 32)));

  // 2. Shooting: goals, shots on target, shots, xg, role
  let shootingBase = isFw ? 74 : isMf ? 58 : isDf ? 38 : 18;
  const goalBonus = (p.goals || 0) * 12;
  const shotBonus = (p.shots_on_target || 0) * 4 + (p.shots || 0) * 2;
  const xgBonus = Math.min(16, Math.round((p.xg || 0) * 14));
  const shootingScore = Math.min(99, Math.max(20, shootingBase + goalBonus + shotBonus + xgBonus));

  // 3. Passing: pass accuracy %, completed volume, key passes
  const passAcc = p.passes?.accuracy_pct || (isMf ? 88.5 : isDf ? 86.0 : isGk ? 74.0 : 79.0);
  const completed = p.passes?.completed || (isMf ? 54 : isDf ? 48 : 28);
  const keyPasses = p.key_passes || 0;
  const passingScore = Math.min(
    99,
    Math.max(30, Math.round(passAcc * 0.58 + Math.min(22, completed / 2.6) + keyPasses * 4.5))
  );

  // 4. Defending: interventions, tackles won, interceptions, role
  let defBase = isDf ? 78 : isGk ? 75 : isMf ? 62 : 36;
  const defInterv = (p.defensive_interventions || 0) * 4;
  const tackles = (p.tackles_won || 0) * 5;
  const interc = (p.interceptions || 0) * 4;
  const defendingScore = Math.min(99, Math.max(20, defBase + defInterv + tackles + interc));

  // 5. Threat: xT created, xg, key passes
  let threatBase = isFw ? 68 : isMf ? 56 : isDf ? 36 : 15;
  const xtVal = p.xt_created || (isFw ? 0.38 : isMf ? 0.28 : 0.08);
  const xtScore = Math.min(25, Math.round(xtVal * 42));
  const threatScore = Math.min(99, Math.max(20, threatBase + xtScore + (p.goals * 5) + keyPasses * 4));

  // 6. Work Rate: distance covered, minutes, energy
  const dist = p.distance_km || (isMf ? 10.8 : isFw ? 9.5 : isDf ? 9.8 : 5.2);
  const mins = p.minutes_played || 90;
  const normalizedDist = mins > 0 ? (dist / mins) * 90 : dist;
  const workRateScore = Math.min(99, Math.max(35, Math.round((normalizedDist / 12.5) * 58 + 38)));

  return [
    {
      key: 'pace',
      label: 'Pace',
      value: paceScore,
      displayValue: `${topSpeed.toFixed(1)} km/h`,
      subtext: 'Sprint Velocity',
    },
    {
      key: 'shooting',
      label: 'Shooting',
      value: shootingScore,
      displayValue: `${p.goals}G · ${(p.xg || 0).toFixed(2)} xG`,
      subtext: 'Goal Conversion',
    },
    {
      key: 'threat',
      label: 'Threat',
      value: threatScore,
      displayValue: `+${(p.xt_created || 0).toFixed(2)} xT`,
      subtext: 'Offensive Impact',
    },
    {
      key: 'workrate',
      label: 'Work Rate',
      value: workRateScore,
      displayValue: `${dist.toFixed(1)} km`,
      subtext: 'Ground Coverage',
    },
    {
      key: 'defending',
      label: 'Defending',
      value: defendingScore,
      displayValue: `${p.defensive_interventions} Interv`,
      subtext: 'Defensive Actions',
    },
    {
      key: 'passing',
      label: 'Passing',
      value: passingScore,
      displayValue: `${passAcc.toFixed(0)}% (${completed})`,
      subtext: 'Distribution',
    },
  ];
};

export const PlayerRadarChart: React.FC<PlayerRadarChartProps> = ({
  player,
  customMetrics,
  size = 340,
  teamColor,
  showLabels = true,
  className = '',
}) => {
  const metrics = useMemo(() => {
    return customMetrics || computePlayerRadarMetrics(player);
  }, [player, customMetrics]);

  // Determine active visual color
  const isNorthbridge =
    player &&
    (player.team.toLowerCase().includes('northbridge') ||
      player.team === 'home' ||
      player.player_id.startsWith('NBL'));

  const activeColor =
    teamColor ||
    (isNorthbridge ? 'var(--color-team-home, #EF0107)' : 'var(--color-team-away, #6CABDD)');

  // Dimensions & geometry
  const center = size / 2;
  const radius = size * 0.36; // leaves comfortable border space for labels
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0];
  const axisCount = metrics.length;
  const angleStep = (Math.PI * 2) / axisCount;

  // Concentric polygon ring points
  const ringPolygons = useMemo(() => {
    return levels.map((lvl) => {
      const ringRadius = radius * lvl;
      const points = Array.from({ length: axisCount }, (_, i) => {
        const angle = -Math.PI / 2 + i * angleStep;
        const x = center + ringRadius * Math.cos(angle);
        const y = center + ringRadius * Math.sin(angle);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
      return { level: lvl, points };
    });
  }, [center, radius, axisCount, angleStep]);

  // Radial spoke lines
  const radialLines = useMemo(() => {
    return Array.from({ length: axisCount }, (_, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const x2 = center + radius * Math.cos(angle);
      const y2 = center + radius * Math.sin(angle);
      return { x1: center, y1: center, x2, y2 };
    });
  }, [center, radius, axisCount, angleStep]);

  // Data polygon points
  const dataPolygon = useMemo(() => {
    const pointsList = metrics.map((m, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const clampedVal = Math.min(100, Math.max(0, m.value));
      const r = (clampedVal / 100) * radius;
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      return { x, y, metric: m };
    });

    const pointsString = pointsList
      .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' ');

    return { pointsString, pointsList };
  }, [metrics, center, radius, angleStep]);

  // Axis label coordinates
  const labelPositions = useMemo(() => {
    const labelDistance = radius + 26;
    return metrics.map((m, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const x = center + labelDistance * Math.cos(angle);
      const y = center + labelDistance * Math.sin(angle);

      // Alignment adjustments based on angle
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      let textAnchor: 'middle' | 'start' | 'end' = 'middle';
      if (cos > 0.3) textAnchor = 'start';
      else if (cos < -0.3) textAnchor = 'end';

      let dominantBaseline: 'middle' | 'auto' | 'hanging' = 'middle';
      if (sin < -0.4) dominantBaseline = 'auto';
      else if (sin > 0.4) dominantBaseline = 'hanging';

      return { x, y, textAnchor, dominantBaseline, metric: m };
    });
  }, [metrics, center, radius, angleStep]);

  const gradientId = `radar-grad-${player?.player_id || 'default'}`;

  return (
    <div
      className={`player-radar-container ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        position: 'relative',
      }}
      aria-label={`Tactical radar chart for ${player?.name || 'Selected Player'}`}
      role="img"
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ overflow: 'visible', maxWidth: '100%', height: 'auto' }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={activeColor} stopOpacity={0.5} />
            <stop offset="100%" stopColor={activeColor} stopOpacity={0.15} />
          </linearGradient>
          <filter id="radar-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor={activeColor} floodOpacity="0.4" />
          </filter>
        </defs>

        {/* Concentric grid rings */}
        {ringPolygons.map(({ level, points }) => (
          <polygon
            key={level}
            points={points}
            fill={level === 1.0 ? 'rgba(255, 255, 255, 0.02)' : 'none'}
            stroke={level === 1.0 ? 'var(--color-border-emphasis, #2d3f55)' : 'rgba(255, 255, 255, 0.07)'}
            strokeWidth={level === 1.0 ? 1.5 : 1}
            strokeDasharray={level < 1.0 ? '3 3' : undefined}
          />
        ))}

        {/* Radial axis lines */}
        {radialLines.map((line, idx) => (
          <line
            key={idx}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke="rgba(255, 255, 255, 0.12)"
            strokeWidth="1"
          />
        ))}

        {/* Data polygon with gradient fill */}
        <polygon
          points={dataPolygon.pointsString}
          fill={`url(#${gradientId})`}
          stroke={activeColor}
          strokeWidth="2.5"
          filter="url(#radar-glow)"
          style={{ transition: 'all 0.3s ease-out' }}
        />

        {/* Data vertex point markers */}
        {dataPolygon.pointsList.map((pt, idx) => (
          <g key={idx}>
            <circle
              cx={pt.x}
              cy={pt.y}
              r="4.5"
              fill={activeColor}
              stroke="var(--color-bg-base, #080b0f)"
              strokeWidth="2"
            />
            <circle
              cx={pt.x}
              cy={pt.y}
              r="8"
              fill="transparent"
              stroke={activeColor}
              strokeWidth="1"
              strokeOpacity="0.3"
            />
          </g>
        ))}

        {/* Center dot */}
        <circle cx={center} cy={center} r="3" fill="rgba(255, 255, 255, 0.3)" />

        {/* Outer axis labels */}
        {showLabels &&
          labelPositions.map((pos, idx) => (
            <g key={idx} transform={`translate(${pos.x}, ${pos.y})`}>
              <text
                x="0"
                y="0"
                textAnchor={pos.textAnchor}
                dominantBaseline={pos.dominantBaseline}
                fill="var(--color-text-primary, #f0f4f8)"
                fontSize="11"
                fontWeight="700"
                letterSpacing="0.04em"
                fontFamily="var(--font-display, sans-serif)"
                style={{ textTransform: 'uppercase' }}
              >
                {pos.metric.label}
              </text>
              <text
                x="0"
                y={pos.dominantBaseline === 'hanging' ? 14 : -12}
                textAnchor={pos.textAnchor}
                dominantBaseline={pos.dominantBaseline}
                fill={activeColor}
                fontSize="12"
                fontWeight="800"
                fontFamily="var(--font-mono, monospace)"
                className="mono-stat"
              >
                {pos.metric.value}
              </text>
            </g>
          ))}
      </svg>
    </div>
  );
};

export default PlayerRadarChart;
