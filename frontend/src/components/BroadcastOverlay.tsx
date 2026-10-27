/**
 * InGame Studio - Broadcast Overlay & TV Lower-Third Ticker
 * Features:
 * - English/Spanish localized lower-third ticker
 * - Physical Threshold & Milestone Alert Banner (`metric_alert`) with auto-dismiss
 * Strictly conforms to ingame-ui-design tokens and broadcast aesthetic.
 */

import React from 'react';
import { VerifiedInsight, MatchEvent, LanguageCode, MetricAlert, SpotlightMetric } from '../types';

interface BroadcastOverlayProps {
  insight: VerifiedInsight | null;
  activeEvent?: MatchEvent | null;
  clock?: string;
  language?: LanguageCode;
  metricAlert?: MetricAlert | null;
  onDismissAlert?: () => void;
  spotlightMetric?: SpotlightMetric;
}

const DEFAULT_TICKERS: Record<LanguageCode, string> = {
  en: 'INGAME LIVE STREAM • AI INSIGHTS ENGINE ACTIVE • 25HZ TELEMETRY SYNCED',
  es: 'TRANSMISIÓN EN VIVO INGAME • MOTOR DE IA ACTIVO • TELEMETRÍA 25HZ SINCRONIZADA',
};

export const BroadcastOverlay: React.FC<BroadcastOverlayProps> = ({
  insight,
  activeEvent,
  clock = '00:00',
  language = 'en',
  metricAlert,
  onDismissAlert,
  spotlightMetric = 'all',
}) => {
  // Resolve localized ticker
  const localizedTicker =
    insight?.translations?.[language]?.ticker ||
    insight?.lower_third_ticker ||
    DEFAULT_TICKERS[language] ||
    DEFAULT_TICKERS.en;

  const isRtl = false;
  const isVerified = insight?.verification_status === 'VERIFIED';
  const groundingPct = Math.round((insight?.grounding_score ?? 1.0) * 100);

  // Alert color & icon resolution
  const getAlertStyle = (type: string) => {
    switch (type) {
      case 'sprint_threshold':
        return {
          bg: 'linear-gradient(90deg, rgba(4, 240, 255, 0.2) 0%, rgba(0, 255, 135, 0.15) 100%)',
          border: 'var(--color-accent-cyan)',
          tag: '⚡ PHYSICAL THRESHOLD ALERT',
          tagColor: 'var(--color-accent-cyan)',
        };
      case 'shot_threshold':
        return {
          bg: 'linear-gradient(90deg, rgba(233, 0, 82, 0.25) 0%, rgba(255, 230, 0, 0.15) 100%)',
          border: 'var(--color-accent-red)',
          tag: '🚀 SHOT VELOCITY ALERT',
          tagColor: 'var(--color-accent-red)',
        };
      case 'milestone':
        return {
          bg: 'linear-gradient(90deg, rgba(255, 230, 0, 0.2) 0%, rgba(56, 0, 60, 0.4) 100%)',
          border: 'var(--color-accent-yellow)',
          tag: '🏅 MATCH MILESTONE',
          tagColor: 'var(--color-accent-yellow)',
        };
      default:
        return {
          bg: 'linear-gradient(90deg, rgba(0, 255, 135, 0.2) 0%, rgba(20, 28, 38, 0.8) 100%)',
          border: 'var(--color-accent-green)',
          tag: 'TACTICAL ALERT',
          tagColor: 'var(--color-accent-green)',
        };
    }
  };

  const alertStyle = metricAlert ? getAlertStyle(metricAlert.alert_type) : null;

  const alertCopy: Record<LanguageCode, { threshold: string; sprint: string; shot: string; distance: string; milestone: string }> = {
    en: { threshold: 'Threshold', sprint: 'Sprint threshold reached', shot: 'High shot speed recorded', distance: 'Distance milestone reached', milestone: 'Match milestone' },
    es: { threshold: 'Umbral', sprint: 'Umbral de velocidad alcanzado', shot: 'Velocidad de tiro alta', distance: 'Hito de distancia alcanzado', milestone: 'Hito del partido' },
  };
  const copy = alertCopy[language] || alertCopy.en;
  const alertTags: Record<LanguageCode, { physical: string; shot: string; milestone: string; tactical: string }> = {
    en: { physical: '⚡ PHYSICAL THRESHOLD ALERT', shot: '🚀 SHOT VELOCITY ALERT', milestone: '🏅 MATCH MILESTONE', tactical: 'TACTICAL ALERT' },
    es: { physical: '⚡ UMBRAL FÍSICO', shot: '🚀 VELOCIDAD DE TIRO', milestone: '🏅 HITO DEL PARTIDO', tactical: 'ALERTA TÁCTICA' },
  };
  const tagCopy = alertTags[language] || alertTags.en;
  const localizedAlertTag = metricAlert?.alert_type === 'sprint_threshold' ? tagCopy.physical
    : metricAlert?.alert_type === 'shot_threshold' ? tagCopy.shot
      : metricAlert?.alert_type === 'milestone' || metricAlert?.alert_type === 'distance_mark' ? tagCopy.milestone : tagCopy.tactical;
  const alertHeadline = metricAlert
    ? metricAlert.alert_type === 'sprint_threshold' ? copy.sprint
      : metricAlert.alert_type === 'shot_threshold' ? copy.shot
        : metricAlert.alert_type === 'distance_mark' ? copy.distance
          : metricAlert.alert_type === 'milestone' ? `${copy.milestone}: ${metricAlert.headline}`
            : metricAlert.headline
    : '';
  const alertDescription = metricAlert
    ? `${metricAlert.player_name ? `${metricAlert.player_name} · ` : ''}${metricAlert.metric_name}: ${metricAlert.metric_value.toFixed(1)} ${metricAlert.unit}`
    : '';

  const narrativeSource = insight?.narrative_source;
  const sourceLabel = narrativeSource === 'azure_foundry_cache' ? 'AZURE FOUNDRY · CACHED · VERIFIED'
    : narrativeSource === 'azure_foundry_live' ? 'AZURE FOUNDRY · LIVE · VERIFIED'
      : 'LOCAL ENGINE · VERIFIED';

  const spotlightLabels: Record<LanguageCode, { tag: string; pdr: string; speed: string; shot: string; xt: string; cci: string }> = {
    en: { tag: 'TRACKING', pdr: 'Pass difficulty', speed: 'Ball speed', shot: 'Shot speed', xt: 'Expected threat', cci: 'Control vs chaos' },
    es: { tag: 'SEGUIMIENTO', pdr: 'Dificultad del pase', speed: 'Velocidad del balón', shot: 'Velocidad del tiro', xt: 'Amenaza esperada', cci: 'Control vs caos' },
  };
  const spotlightCopy = spotlightLabels[language] || spotlightLabels.en;
  const isShotEvent = ['shot', 'goal'].includes((activeEvent?.event_type || '').toLowerCase());
  const spotlightValue = spotlightMetric === 'pdr' ? insight?.metrics?.pass_difficulty
    : spotlightMetric === 'speed' ? (activeEvent?.tactical_metrics?.ball_speed_kmh ?? insight?.metrics?.ball_speed_kmh)
      : spotlightMetric === 'xt' ? insight?.metrics?.xt_gained
        : spotlightMetric === 'cci' ? insight?.metrics?.chaos_index
          : undefined;
  const spotlightName = spotlightMetric === 'pdr' ? spotlightCopy.pdr
    : spotlightMetric === 'speed' ? (isShotEvent ? spotlightCopy.shot : spotlightCopy.speed)
      : spotlightMetric === 'xt' ? spotlightCopy.xt
        : spotlightMetric === 'cci' ? spotlightCopy.cci : '';
  const spotlightUnit = spotlightMetric === 'pdr' ? '%' : spotlightMetric === 'speed' ? 'km/h' : spotlightMetric === 'xt' ? 'xT' : '/100';

  return (
    <div className="broadcast-overlay" role="region" aria-label="Broadcast lower-third overlay">
      {/* Top Banner Bar */}
      <div className="broadcast-top">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          <span className="broadcast-badge">
            INGAME
          </span>
          <span className="broadcast-label">STUDIO INTELLIGENCE</span>
          <span className="broadcast-divider" aria-hidden="true">|</span>
          <span className="broadcast-clock mono-stat">
            ⏱ {clock}
          </span>
          <span
            style={{
              fontSize: '10px',
              color: 'var(--color-text-tertiary)',
              borderLeft: '1px solid var(--color-border-subtle)',
              paddingLeft: '8px',
              fontFamily: 'var(--font-mono)',
            }}
          >
            LANG: {language.toUpperCase()}
          </span>
        </div>

        {/* Verification Status & Live Event Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          {insight && (
            <span
              className={`verification-badge ${isVerified ? 'verified' : 'fallback'}`}
              aria-label={`Insight verification: ${isVerified ? `Verified ${groundingPct}%` : 'Fallback applied'}`}
            >
              <span
                className="verification-dot"
                style={{
                  background: isVerified ? 'var(--color-accent-green)' : 'var(--color-accent-yellow)',
                  boxShadow: `0 0 6px ${isVerified ? 'var(--color-accent-green)' : 'var(--color-accent-yellow)'}`,
                }}
                aria-hidden="true"
              />
              {isVerified ? `${sourceLabel} (${groundingPct}%)` : 'FALLBACK APPLIED'}
            </span>
          )}

          {activeEvent && (
            <span className="event-badge" role="alert" aria-live="assertive">
              LIVE: {activeEvent.event_type.replace(/_/g, ' ')}
            </span>
          )}
        </div>
      </div>

      {/* Physical Threshold & Milestone Alert Banner (transient banner) */}
      {metricAlert && alertStyle && (
        <div
          role="alert"
          aria-live="assertive"
          dir={isRtl ? 'rtl' : 'ltr'}
          style={{
            background: alertStyle.bg,
            borderTop: `1px solid ${alertStyle.border}`,
            borderBottom: `1px solid ${alertStyle.border}`,
            padding: '6px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            animation: 'slideInDown 0.2s var(--ease-out-expo)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '9.5px',
                fontWeight: 900,
                color: '#080b0f',
                background: alertStyle.tagColor,
                padding: '2px 7px',
                borderRadius: '4px',
                letterSpacing: '0.05em',
              }}
            >
              {localizedAlertTag}
            </span>
            <span style={{ fontSize: '12px', fontWeight: 800, color: '#ffffff' }}>
              {alertHeadline}
            </span>
            <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              {alertDescription}
            </span>
            <span
              className="mono-stat"
              style={{
                fontSize: '11px',
                color: alertStyle.tagColor,
                fontWeight: 700,
                background: 'rgba(0,0,0,0.4)',
                padding: '1px 6px',
                borderRadius: '4px',
              }}
            >
              {metricAlert.metric_value.toFixed(1)} {metricAlert.unit} ({copy.threshold}: {metricAlert.threshold_value} {metricAlert.unit})
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="mono-stat" style={{ fontSize: '10.5px', color: 'var(--color-text-tertiary)' }}>
              ⏱ {metricAlert.clock}
            </span>
            {onDismissAlert && (
              <button
                onClick={onDismissAlert}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-text-tertiary)',
                  cursor: 'pointer',
                  fontSize: '14px',
                  lineHeight: 1,
                  padding: '2px 4px',
                }}
                aria-label="Dismiss alert"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

      {spotlightMetric !== 'all' && (
        <div
          className="ticker-bar"
          dir={isRtl ? 'rtl' : 'ltr'}
          aria-live="polite"
          style={{ borderTop: '1px solid var(--color-accent-cyan)', borderBottom: '1px solid var(--color-accent-cyan)', justifyContent: 'space-between', padding: '7px 14px' }}
        >
          <strong style={{ color: 'var(--color-accent-cyan)', fontSize: '10px', letterSpacing: '0.06em' }}>
            {spotlightCopy.tag}: {spotlightName}
          </strong>
          <span className="mono-stat" style={{ fontSize: '16px', fontWeight: 900, color: 'var(--color-text-primary)' }}>
            {spotlightValue === undefined ? '—' : spotlightValue.toFixed(1)} {spotlightUnit}
          </span>
        </div>
      )}

      {/* Television Broadcast Lower-Third Banner with RTL support */}
      <div
        className="ticker-bar"
        dir={isRtl ? 'rtl' : 'ltr'}
        style={isRtl ? { textAlign: 'right' } : undefined}
      >
        <span
          className="ticker-label"
          style={isRtl ? { borderRight: 'none', borderLeft: '1px solid rgba(255, 255, 255, 0.12)' } : undefined}
        >
          {isRtl ? 'الأخبار' : 'BROADCAST'}
        </span>
        <div
          className="ticker-text"
          aria-live="polite"
          style={isRtl ? { fontFamily: 'var(--font-arabic, sans-serif)' } : undefined}
        >
          <span className="ticker-text-inner">
            {localizedTicker} &nbsp;&bull;&nbsp; {localizedTicker}
          </span>
        </div>
      </div>
    </div>
  );
};
