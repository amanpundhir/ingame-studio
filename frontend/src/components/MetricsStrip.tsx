/**
 * InGame Studio - Real-Time Tactical HUD Metrics Strip
 * Supports Single Metric Tracking Mode (Hero KPI spotlighting & satellite strip)
 * Strictly conforms to ingame-ui-design tokens and type scales.
 */

import React from 'react';
import { VerifiedInsight, TelemetryFrame, SpotlightMetric, PlayerAnalytics, MatchEvent } from '../types';

interface MetricsStripProps {
  insight: VerifiedInsight | null;
  frame: TelemetryFrame | null;
  latencyMs: number;
  fps?: number;
  players?: PlayerAnalytics[];
  spotlightPlayerId?: string | null;
  activeEvent?: MatchEvent | null;
  spotlightMetric?: SpotlightMetric;
  onSelectSpotlightMetric?: (metric: SpotlightMetric) => void;
}

export const MetricsStrip: React.FC<MetricsStripProps> = ({
  insight,
  frame,
  latencyMs,
  fps = 25,
  players = [],
  spotlightPlayerId,
  activeEvent,
  spotlightMetric = 'all',
  onSelectSpotlightMetric,
}) => {
  const pdr = insight?.metrics?.pass_difficulty ?? 65.0;
  const isShotEvent = ['shot', 'goal'].includes((activeEvent?.event_type || '').toLowerCase());
  const ballSpeed = isShotEvent
    ? (activeEvent?.tactical_metrics?.shot_speed_kmh ?? activeEvent?.tactical_metrics?.ball_speed_kmh ?? insight?.metrics?.ball_speed_kmh ?? frame?.ball?.speed_kmh ?? 0.0)
    : (frame?.ball?.speed_kmh ?? insight?.metrics?.ball_speed_kmh ?? 0.0);
  const xt = insight?.metrics?.xt_gained ?? 0.12;
  const cci = insight?.metrics?.chaos_index ?? 38.5;
  const coneDefenders = insight?.metrics?.defenders_in_cone ?? 2;
  const corridorDefenders = insight?.metrics?.defenders_in_corridor ?? 1;
  const passDistance = insight?.metrics?.pass_distance_m ?? 22.4;

  // PDR color zoning
  const getPdrColor = (val: number) => {
    if (val < 50) return 'var(--color-accent-green)'; // favorable
    if (val < 75) return 'var(--color-accent-yellow)'; // contested
    return 'var(--color-accent-red)'; // extreme risk
  };

  const getPdrLabel = (val: number) => {
    if (val < 50) return 'FAVORABLE';
    if (val < 75) return 'CONTESTED';
    return 'HIGH RISK';
  };

  const setSpotlight = (metric: SpotlightMetric) => {
    onSelectSpotlightMetric?.(metric);
  };

  const isSpotlighted = spotlightMetric !== 'all';
  const currentPlayer = spotlightPlayerId ? players.find((player) => player.player_id === spotlightPlayerId) : undefined;
  const distanceLeaders = [...players].sort((a, b) => b.distance_km - a.distance_km).slice(0, 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      {/* Top Spotlight Control Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '2px 4px',
        }}
      >
        <span
          style={{
            fontSize: 'var(--text-micro)',
            fontWeight: 800,
            letterSpacing: '0.06em',
            color: 'var(--color-text-secondary)',
            textTransform: 'uppercase',
          }}
        >
          HUD Tactical Telemetry {isSpotlighted && <span style={{ color: 'var(--color-accent-cyan)' }}>&bull; Hero Mode</span>}
        </span>

        {/* Metric Selector Pills */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {(
            [
              { id: 'all', label: 'All', icon: '📊' },
              { id: 'pdr', label: 'PDR', icon: '🎯' },
              { id: 'speed', label: 'Velocity', icon: '⚡' },
              { id: 'xt', label: 'xT', icon: '📈' },
              { id: 'cci', label: 'CCI', icon: '🌊' },
            ] as const
          ).map((m) => {
            const active = spotlightMetric === m.id;
            return (
              <button
                key={m.id}
                onClick={() => setSpotlight(m.id)}
                style={{
                  background: active ? 'var(--color-accent-cyan)' : 'rgba(255, 255, 255, 0.05)',
                  color: active ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '12px',
                  padding: '2px 8px',
                  fontSize: '10px',
                  fontWeight: active ? 800 : 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>{m.icon}</span> {m.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Live physical indicators from player analytics */}
      {players.length > 0 && (
        <div
          className="studio-card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
            padding: '8px 12px',
            border: '1px solid var(--color-border-subtle)',
          }}
          aria-label="Player physical performance indicators"
        >
          <div style={{ fontSize: '10px', fontWeight: 900, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
            {currentPlayer ? `Last event player · ${currentPlayer.name}` : 'Distance covered leaders'}
          </div>
          {currentPlayer ? (
            <div style={{ display: 'flex', gap: '14px', fontSize: '11px' }}>
              <span>Distance <strong className="mono-stat">{currentPlayer.distance_km.toFixed(2)} km</strong></span>
              <span>Top speed <strong className="mono-stat">{currentPlayer.top_speed_kmh.toFixed(1)} km/h</strong></span>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '10px' }}>
              {distanceLeaders.map((player) => (
                <span key={player.player_id}>
                  <strong>{player.name}</strong> {player.distance_km.toFixed(2)} km · {player.top_speed_kmh.toFixed(1)} km/h
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Hero Spotlight Mode (when a single metric is pinned) */}
      {isSpotlighted && (
        <div
          className="studio-card studio-card-glow"
          style={{
            padding: '16px 20px',
            border: '1px solid var(--color-accent-cyan)',
            background: 'linear-gradient(135deg, rgba(20, 28, 38, 0.95) 0%, rgba(13, 17, 23, 0.98) 100%)',
          }}
        >
          {/* Hero Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 900,
                  background: 'var(--color-accent-cyan)',
                  color: 'var(--color-text-inverse)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  letterSpacing: '0.04em',
                }}
              >
                SPOTLIGHT HERO KPI
              </span>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
                {spotlightMetric === 'pdr' && 'Pass Difficulty Rating (PDR)'}
                {spotlightMetric === 'speed' && (isShotEvent ? 'Shot Speed · Current Shot' : 'Instantaneous Ball Speed')}
                {spotlightMetric === 'xt' && 'Expected Threat Gained (xT)'}
                {spotlightMetric === 'cci' && 'Chaos vs. Control Rhythm Index (CCI)'}
              </span>
            </div>

            <button
              onClick={() => setSpotlight('all')}
              style={{
                background: 'transparent',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text-tertiary)',
                borderRadius: '4px',
                padding: '2px 8px',
                fontSize: '10px',
                cursor: 'pointer',
                fontWeight: 700,
              }}
              title="Return to standard 4-card grid"
            >
              ✕ Unpin / View All
            </button>
          </div>

          {/* Hero Value Display */}
          <div style={{ margin: '14px 0 10px 0' }}>
            {spotlightMetric === 'pdr' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                  <span
                    className="mono-stat"
                    style={{ fontSize: 'var(--text-hero)', fontWeight: 900, color: getPdrColor(pdr) }}
                  >
                    {pdr.toFixed(1)}%
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: getPdrColor(pdr),
                      background: 'rgba(0, 0, 0, 0.4)',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    {getPdrLabel(pdr)}
                  </span>
                </div>
                {/* Gauge bar */}
                <div style={{ width: '100%', height: '8px', background: 'var(--color-bg-base)', borderRadius: '4px', overflow: 'hidden', margin: '8px 0' }}>
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, pdr))}%`,
                      height: '100%',
                      background: getPdrColor(pdr),
                      boxShadow: `0 0 10px ${getPdrColor(pdr)}`,
                      transition: 'width 0.25s ease',
                    }}
                  />
                </div>
                {/* Diagnostic telemetry breakdown */}
                <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                  <span>Pass Distance: <strong style={{ color: 'var(--color-text-primary)' }}>{passDistance.toFixed(1)}m</strong></span>
                  <span>Intercept Cone Defenders: <strong style={{ color: 'var(--color-accent-yellow)' }}>{coneDefenders}</strong></span>
                  <span>Corridor Defenders: <strong style={{ color: 'var(--color-accent-red)' }}>{corridorDefenders}</strong></span>
                </div>
              </div>
            )}

            {spotlightMetric === 'speed' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                  <span
                    className="mono-stat"
                    style={{ fontSize: 'var(--text-hero)', fontWeight: 900, color: 'var(--color-text-primary)' }}
                  >
                    {ballSpeed.toFixed(1)}
                  </span>
                  <span style={{ fontSize: '16px', color: 'var(--color-accent-cyan)', fontWeight: 800 }}>km/h</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: 'var(--color-accent-cyan)',
                      background: 'rgba(4, 240, 255, 0.1)',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    25Hz KINEMATICS
                  </span>
                </div>
                {/* Speedometer Bar (0 to 150 km/h) */}
                <div style={{ width: '100%', height: '8px', background: 'var(--color-bg-base)', borderRadius: '4px', overflow: 'hidden', margin: '8px 0' }}>
                  <div
                    style={{
                      width: `${Math.min(100, (ballSpeed / 150) * 100)}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--color-accent-cyan), var(--color-accent-green))',
                      boxShadow: '0 0 10px rgba(4, 240, 255, 0.5)',
                      transition: 'width 0.1s linear',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                  <span>{isShotEvent ? 'Shot speed event' : 'Ball status'}: <strong style={{ color: 'var(--color-accent-green)' }}>{isShotEvent ? (activeEvent?.player_name || 'Shot') : (frame?.ball?.status || 'In Play')}</strong></span>
                  <span>Elevation Z: <strong style={{ color: 'var(--color-text-primary)' }}>{(frame?.ball?.z ?? 0.0).toFixed(2)}m</strong></span>
                  <span>Max Scale: <strong style={{ color: 'var(--color-text-tertiary)' }}>150 km/h</strong></span>
                </div>
              </div>
            )}

            {spotlightMetric === 'xt' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                  <span
                    className="mono-stat"
                    style={{ fontSize: 'var(--text-hero)', fontWeight: 900, color: 'var(--color-accent-yellow)' }}
                  >
                    {xt >= 0 ? `+${xt.toFixed(2)}` : xt.toFixed(2)}
                  </span>
                  <span style={{ fontSize: '16px', color: 'var(--color-text-secondary)', fontWeight: 800 }}>&Delta;xT</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: 'var(--color-accent-yellow)',
                      background: 'rgba(255, 230, 0, 0.12)',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    TERRITORIAL PROGRESSION
                  </span>
                </div>
                <div style={{ width: '100%', height: '8px', background: 'var(--color-bg-base)', borderRadius: '4px', overflow: 'hidden', margin: '8px 0' }}>
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, (xt + 0.5) * 100))}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--color-accent-yellow), var(--color-accent-red))',
                      boxShadow: '0 0 10px rgba(255, 230, 0, 0.5)',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                  <span>Primary Target: <strong style={{ color: 'var(--color-text-primary)' }}>Zone 14 (Central Edge)</strong></span>
                  <span>Threat Gradient: <strong style={{ color: 'var(--color-accent-yellow)' }}>High Penetration</strong></span>
                </div>
              </div>
            )}

            {spotlightMetric === 'cci' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                  <span
                    className="mono-stat"
                    style={{ fontSize: 'var(--text-hero)', fontWeight: 900, color: 'var(--color-accent-cyan)' }}
                  >
                    {cci.toFixed(1)}
                  </span>
                  <span style={{ fontSize: '16px', color: 'var(--color-text-tertiary)', fontWeight: 700 }}>/ 100</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: 'var(--color-accent-cyan)',
                      background: 'rgba(4, 240, 255, 0.1)',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    TACTICAL ENTROPY
                  </span>
                </div>
                <div style={{ width: '100%', height: '8px', background: 'var(--color-bg-base)', borderRadius: '4px', overflow: 'hidden', margin: '8px 0' }}>
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, cci))}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--color-accent-green), var(--color-accent-cyan))',
                      boxShadow: '0 0 10px rgba(4, 240, 255, 0.5)',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                  <span>Turnovers: <strong style={{ color: 'var(--color-text-primary)' }}>40%</strong></span>
                  <span>Speed Var: <strong style={{ color: 'var(--color-text-primary)' }}>35%</strong></span>
                  <span>Defensive Line Shift: <strong style={{ color: 'var(--color-text-primary)' }}>25%</strong></span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Satellite Strip (if spotlighted) OR Standard 4-Tile Grid (if 'all') */}
      <div className="metrics-grid">
        {/* PDR Card */}
        {(!isSpotlighted || spotlightMetric !== 'pdr') && (
          <div
            className="studio-card"
            style={{
              padding: isSpotlighted ? '10px 14px' : '14px 16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
                PDR
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    color: getPdrColor(pdr),
                    background: 'rgba(0, 0, 0, 0.3)',
                    padding: '1px 5px',
                    borderRadius: '4px',
                    fontWeight: 700,
                  }}
                >
                  {getPdrLabel(pdr)}
                </span>
                <button
                  onClick={() => setSpotlight('pdr')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--color-text-tertiary)',
                    cursor: 'pointer',
                    fontSize: '11px',
                    padding: '1px 3px',
                  }}
                  title="Spotlight PDR as Hero KPI"
                >
                  📌
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', margin: isSpotlighted ? '4px 0' : '8px 0 6px 0' }}>
              <span style={{ fontSize: isSpotlighted ? '20px' : '26px', fontWeight: 900, color: getPdrColor(pdr) }} className="mono-stat">
                {pdr.toFixed(1)}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--color-text-tertiary)', fontWeight: 700 }}>%</span>
            </div>
            <div style={{ width: '100%', height: '4px', background: 'var(--color-bg-base)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, pdr))}%`,
                  height: '100%',
                  background: getPdrColor(pdr),
                  transition: 'width 0.25s ease',
                }}
              />
            </div>
          </div>
        )}

        {/* Ball Speed Card */}
        {(!isSpotlighted || spotlightMetric !== 'speed') && (
          <div
            className="studio-card"
            style={{
              padding: isSpotlighted ? '10px 14px' : '14px 16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
                {isShotEvent ? 'Shot Speed' : 'Ball Velocity'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: '9px', color: 'var(--color-accent-cyan)', background: 'rgba(4, 240, 255, 0.1)', padding: '1px 5px', borderRadius: '4px', fontWeight: 700 }}>
                  {isShotEvent ? 'SHOT' : 'SPEED'}
                </span>
                <button
                  onClick={() => setSpotlight('speed')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--color-text-tertiary)',
                    cursor: 'pointer',
                    fontSize: '11px',
                    padding: '1px 3px',
                  }}
                  title="Spotlight Ball Velocity as Hero KPI"
                >
                  📌
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', margin: isSpotlighted ? '4px 0' : '8px 0 6px 0' }}>
              <span style={{ fontSize: isSpotlighted ? '20px' : '26px', fontWeight: 900, color: 'var(--color-text-primary)' }} className="mono-stat">
                {ballSpeed.toFixed(1)}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--color-accent-cyan)', fontWeight: 700 }}>km/h</span>
            </div>
            <div style={{ width: '100%', height: '4px', background: 'var(--color-bg-base)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.min(100, (ballSpeed / 150) * 100)}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--color-accent-cyan), var(--color-accent-green))',
                  transition: 'width 0.1s linear',
                }}
              />
            </div>
          </div>
        )}

        {/* xT Card */}
        {(!isSpotlighted || spotlightMetric !== 'xt') && (
          <div
            className="studio-card"
            style={{
              padding: isSpotlighted ? '10px 14px' : '14px 16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
                Threat (xT)
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: '9px', color: 'var(--color-accent-yellow)', background: 'rgba(255, 230, 0, 0.1)', padding: '1px 5px', borderRadius: '4px', fontWeight: 700 }}>
                  ZONE 14
                </span>
                <button
                  onClick={() => setSpotlight('xt')}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--color-text-tertiary)',
                    cursor: 'pointer',
                    fontSize: '11px',
                    padding: '1px 3px',
                  }}
                  title="Spotlight Expected Threat as Hero KPI"
                >
                  📌
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', margin: isSpotlighted ? '4px 0' : '8px 0 6px 0' }}>
              <span style={{ fontSize: isSpotlighted ? '20px' : '26px', fontWeight: 900, color: 'var(--color-accent-yellow)' }} className="mono-stat">
                {xt >= 0 ? `+${xt.toFixed(2)}` : xt.toFixed(2)}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', fontWeight: 600 }}>&Delta;xT</span>
            </div>
            <div style={{ width: '100%', height: '4px', background: 'var(--color-bg-base)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, (xt + 0.5) * 100))}%`,
                  height: '100%',
                  background: 'var(--color-accent-yellow)',
                }}
              />
            </div>
          </div>
        )}

        {/* Stream Health Card */}
        <div
          className="studio-card"
          style={{
            padding: isSpotlighted ? '10px 14px' : '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>
              Stream Sync
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '10px',
                color: 'var(--color-accent-green)',
                fontWeight: 700,
              }}
            >
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--color-accent-green)' }} />
              25Hz
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', margin: isSpotlighted ? '2px 0' : '6px 0' }}>
            <div>
              <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>FPS</div>
              <div style={{ fontSize: isSpotlighted ? '14px' : '16px', fontWeight: 800, color: 'var(--color-text-primary)' }} className="mono-stat">
                {fps}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '9px', color: 'var(--color-text-tertiary)' }}>LATENCY</div>
              <div
                style={{
                  fontSize: isSpotlighted ? '14px' : '16px',
                  fontWeight: 800,
                  color: latencyMs < 50 ? 'var(--color-accent-green)' : 'var(--color-accent-yellow)',
                }}
                className="mono-stat"
              >
                {latencyMs}ms
              </div>
            </div>
          </div>

          <div style={{ fontSize: '9.5px', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            #{frame?.frame_id ?? 0} &bull; {frame?.clock ?? '00:00'}
          </div>
        </div>
      </div>
    </div>
  );
};
