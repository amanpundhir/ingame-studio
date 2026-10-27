/**
 * InGame Studio - Global Navigation Rail
 * Persistent 72px vertical navigation rail adhering to broadcast design system.
 * Hosts 5 tabs: InGame, Players Stats, Tactical Insights, Persona, and Recap.
 */

import React, { useState } from 'react';
import { TabId } from '../types';

export interface NavigationRailProps {
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  isLive?: boolean;
}

interface NavItem {
  id: TabId;
  label: string;
  badge?: string;
  tooltip: string;
  icon: (active: boolean) => React.ReactNode;
}

export const NavigationRail: React.FC<NavigationRailProps> = ({
  activeTab,
  onSelectTab,
  isLive = true,
}) => {
  const [hoveredTab, setHoveredTab] = useState<TabId | null>(null);

  const navItems: NavItem[] = [
    {
      id: 'ingame',
      label: 'InGame',
      tooltip: 'Live Match Dashboard & 2D Tracking Pitch',
      icon: (active) => (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={active ? 'var(--color-accent-green)' : 'currentColor'}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
          <path d="M2 12h20" />
          <path d="M7 6.5c1.5 1.5 3 2.5 5 2.5s3.5-1 5-2.5" />
          <path d="M7 17.5c1.5-1.5 3-2.5 5-2.5s3.5 1 5 2.5" />
        </svg>
      ),
    },
    {
      id: 'players',
      label: 'Players',
      tooltip: 'Player Intelligence, Radar Charts & Heatmaps',
      icon: (active) => (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={active ? 'var(--color-accent-cyan)' : 'currentColor'}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 20V10" />
          <path d="M12 20V4" />
          <path d="M6 20v-6" />
          <circle cx="12" cy="4" r="1.5" fill={active ? 'var(--color-accent-cyan)' : 'none'} />
        </svg>
      ),
    },
    {
      id: 'tactical',
      label: 'Tactics',
      tooltip: 'Spatial Moments, Freeze-Frame & Layer Toggles',
      icon: (active) => (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={active ? 'var(--color-accent-cyan)' : 'currentColor'}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polygon points="12 2 2 22 22 22" />
          <line x1="12" y1="9" x2="12" y2="15" />
          <line x1="9" y1="18" x2="15" y2="18" />
        </svg>
      ),
    },
    {
      id: 'persona',
      label: 'Persona',
      tooltip: 'AI Broadcast Personas & Partisan Allegiance',
      icon: (active) => (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={active ? '#a855f7' : 'currentColor'}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M2 10s3-3 5-3 5 3 5 3-3 3-5 3-5-3-5-3Z" />
          <path d="M12 14s3-3 5-3 5 3 5 3-3 3-5 3-5-3-5-3Z" />
          <circle cx="7" cy="10" r="1" fill={active ? '#a855f7' : 'none'} />
          <circle cx="17" cy="14" r="1" fill={active ? '#a855f7' : 'none'} />
        </svg>
      ),
    },
    {
      id: 'recap',
      label: 'Recap',
      tooltip: '5-Minute Condensed Pitch Player & AI Story',
      icon: (active) => (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke={active ? 'var(--color-accent-yellow)' : 'currentColor'}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="2" y="4" width="20" height="16" rx="2" />
          <path d="M2 8h20" />
          <path d="m6 4 3 4" />
          <path d="m11 4 3 4" />
          <path d="m16 4 3 4" />
          <polygon points="10 11 15 14 10 17 10 11" fill={active ? 'var(--color-accent-yellow)' : 'none'} />
        </svg>
      ),
    },
  ];

  return (
    <aside
      className="ingame-nav-rail"
      role="navigation"
      aria-label="InGame Navigation Rail"
      style={{
        width: '72px',
        minWidth: '72px',
        maxWidth: '72px',
        height: '100vh',
        background: 'linear-gradient(180deg, var(--color-pl-purple) 0%, var(--color-pl-purple-dark) 40%, var(--color-bg-base) 100%)',
        borderRight: '1px solid var(--color-border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 'var(--spacing-md) 0 var(--spacing-lg) 0',
        userSelect: 'none',
        zIndex: 50,
        position: 'relative',
      }}
    >
      {/* InGame Emblem Brand Header */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '4px',
          marginBottom: 'var(--spacing-xl)',
          cursor: 'pointer',
        }}
        onClick={() => onSelectTab('ingame')}
        title="InGame Studio - Broadcast Engine"
      >
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, var(--color-pl-purple-mid) 0%, #200028 100%)',
            border: '1.5px solid rgba(0, 255, 135, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 14px rgba(0, 255, 135, 0.25)',
            position: 'relative',
          }}
        >
          {/* Stylized InGame Crown */}
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-label="InGame emblem">
            <path
              d="M12 2L15 8L21 6L18 12L22 17H2L6 12L3 6L9 8L12 2Z"
              fill="var(--color-accent-green)"
              fillOpacity="0.9"
            />
            <circle cx="12" cy="14" r="2.5" fill="#38003c" />
            <path d="M10 19h4v2h-4z" fill="var(--color-accent-green)" />
          </svg>
        </div>
        <span
          style={{
            fontSize: '9px',
            fontWeight: 800,
            letterSpacing: '0.08em',
            color: 'var(--color-accent-green)',
            textTransform: 'uppercase',
          }}
        >
          PL STUDIO
        </span>
      </div>

      {/* Navigation Tab Buttons */}
      <nav
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--spacing-sm)',
          width: '100%',
          alignItems: 'center',
          flex: 1,
        }}
        role="tablist"
        aria-orientation="vertical"
      >
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          const isHovered = hoveredTab === item.id;

          // Semantic glow indicator colors
          const accentColor =
            item.id === 'ingame'
              ? 'var(--color-accent-green)'
              : item.id === 'players' || item.id === 'tactical'
              ? 'var(--color-accent-cyan)'
              : item.id === 'persona'
              ? '#a855f7'
              : 'var(--color-accent-yellow)';

          return (
            <div
              key={item.id}
              style={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center' }}
              onMouseEnter={() => setHoveredTab(item.id)}
              onMouseLeave={() => setHoveredTab(null)}
            >
              {/* Active Tab Vertical Indicator Pill on Left Edge */}
              {isActive && (
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: '8px',
                    bottom: '8px',
                    width: '3.5px',
                    borderRadius: '0 4px 4px 0',
                    background: accentColor,
                    boxShadow: `0 0 10px ${accentColor}`,
                  }}
                  aria-hidden="true"
                />
              )}

              <button
                type="button"
                role="tab"
                id={`tab-${item.id}`}
                aria-selected={isActive}
                aria-controls={`panel-${item.id}`}
                aria-label={`${item.label}: ${item.tooltip}`}
                tabIndex={isActive ? 0 : -1}
                onClick={() => onSelectTab(item.id)}
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '8px',
                  background: isActive
                    ? 'rgba(255, 255, 255, 0.08)'
                    : isHovered
                    ? 'rgba(255, 255, 255, 0.04)'
                    : 'transparent',
                  border: isActive
                    ? `1px solid ${accentColor}44`
                    : '1px solid transparent',
                  color: isActive
                    ? 'var(--color-text-primary)'
                    : isHovered
                    ? 'var(--color-text-primary)'
                    : 'var(--color-text-secondary)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease, border-color 0.15s ease, color 0.15s ease',
                  outline: 'none',
                  padding: 0,
                  position: 'relative',
                }}
              >
                {/* Tab Icon */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {item.icon(isActive)}
                </div>

                {/* Tab Short Label */}
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: isActive ? 700 : 500,
                    letterSpacing: '0.02em',
                    lineHeight: 1,
                    color: isActive ? accentColor : 'inherit',
                  }}
                >
                  {item.label}
                </span>

                {/* Live Activity Pulse Dot for InGame when active */}
                {item.id === 'ingame' && isLive && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '6px',
                      right: '6px',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: 'var(--color-accent-green)',
                      boxShadow: '0 0 6px var(--color-accent-green)',
                    }}
                    title="Live Simulation Active"
                  />
                )}
              </button>

              {/* Broadcast Grade Hover Tooltip Floating to the Right */}
              {isHovered && (
                <div
                  role="tooltip"
                  id={`tooltip-${item.id}`}
                  style={{
                    position: 'absolute',
                    left: '74px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'var(--color-bg-overlay)',
                    border: '1px solid var(--color-border-emphasis)',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    whiteSpace: 'nowrap',
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
                    zIndex: 1000,
                    pointerEvents: 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        color: accentColor,
                      }}
                    >
                      {item.label}
                    </span>
                    {isActive && (
                      <span
                        style={{
                          fontSize: '9px',
                          fontWeight: 800,
                          padding: '1px 4px',
                          borderRadius: '3px',
                          background: `${accentColor}22`,
                          color: accentColor,
                          textTransform: 'uppercase',
                        }}
                      >
                        Active
                      </span>
                    )}
                  </div>
                  <span
                    style={{
                      fontSize: '11px',
                      color: 'var(--color-text-secondary)',
                      maxWidth: '220px',
                      whiteSpace: 'normal',
                      lineHeight: 1.3,
                    }}
                  >
                    {item.tooltip}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom Live Sync / Status Indicator */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '4px',
          paddingTop: 'var(--spacing-md)',
          borderTop: '1px solid var(--color-border-subtle)',
          width: '80%',
        }}
        title={isLive ? '25Hz Stream Active' : 'Disconnected'}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: isLive ? 'var(--color-accent-green)' : 'var(--color-accent-red)',
              boxShadow: isLive ? '0 0 6px var(--color-accent-green)' : 'none',
            }}
          />
          <span
            className="mono-stat"
            style={{
              fontSize: '9px',
              fontWeight: 800,
              color: isLive ? 'var(--color-accent-green)' : 'var(--color-text-tertiary)',
            }}
          >
            25Hz
          </span>
        </div>
        <span
          style={{
            fontSize: '8px',
            color: 'var(--color-text-tertiary)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          SYNC
        </span>
      </div>
    </aside>
  );
};

export default NavigationRail;
