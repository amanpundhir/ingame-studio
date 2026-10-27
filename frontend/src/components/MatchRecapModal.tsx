/**
 * InGame Studio - Post-Match Studio Recap Modal
 * Broadcast-grade post-match intelligence conforming to ingame-ui-design tokens.
 */

import React, { useState, useEffect } from 'react';
import {
  MatchRecapData,
  MatchStatsData,
  LanguageCode,
  PlayerAnalytics,
  ViewerPersona,
} from '../types';

export interface MatchRecapModalProps {
  isOpen: boolean;
  onClose: () => void;
  recapData: MatchRecapData | null;
  stats: MatchStatsData | null;
  players: PlayerAnalytics[];
  language: LanguageCode;
  persona?: ViewerPersona;
  club?: string;
  onExploreAnalytics?: () => void;
}

export const MatchRecapModal: React.FC<MatchRecapModalProps> = ({
  isOpen,
  onClose,
  recapData,
  stats,
  players,
  language,
  persona = 'tactical',
  club = 'Northbridge Lions',
  onExploreAnalytics,
}) => {
  const [activeTab, setActiveTab] = useState<'story' | 'tactical' | 'honours'>('story');
  const [aiStory, setAiStory] = useState<string>('');

  // Studio story written by the Foundry model (cached), in the viewer's language and persona
  useEffect(() => {
    if (!isOpen || !recapData) return;
    let cancelled = false;
    const query = new URLSearchParams({ persona, language, club });
    fetch(`/api/story?${query.toString()}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.text) setAiStory(data.text);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isOpen, recapData?.headline, persona, language, club]);

  // Handle Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;
  if (!recapData) {
    return (
      <div className="recap-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="recap-unavailable-title">
        <div className="recap-modal-container" style={{ padding: '28px', maxWidth: '520px' }}>
          <h2 id="recap-unavailable-title">Match recap unavailable</h2>
          <p>The recap could not be loaded. Try again after the match data is available.</p>
          <button type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  const effectiveRecap: MatchRecapData = recapData;
  const xgTotal = Math.max(0.01, effectiveRecap.xg_balance.home_xg + effectiveRecap.xg_balance.away_xg);
  const fantasyPodium = [...players]
    .filter((player) => player.minutes_played > 0 || player.distance_km > 0 || player.passes.total > 0 || player.shots > 0 || player.goals > 0 || player.assists > 0 || player.defensive_interventions > 0)
    .sort((a, b) => b.bps - a.bps)
    .slice(0, 3);

  // Localized story resolution
  const storyText =
    aiStory || effectiveRecap.translations?.[language]?.match_story || effectiveRecap.match_story;
  const headlineText = effectiveRecap.headline;

  const isRtl = false;

  return (
    <div
      className="recap-modal-backdrop"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        backgroundColor: 'rgba(8, 11, 15, 0.82)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--spacing-lg)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="recap-headline"
    >
      <div
        className="recap-modal-container"
        style={{
          width: '100%',
          maxWidth: '860px',
          maxHeight: '90vh',
          backgroundColor: 'var(--color-bg-overlay)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '12px',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.75), 0 0 30px rgba(56, 0, 60, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'slideInDown 0.22s var(--ease-out-expo)',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            padding: '16px 24px',
            background: 'linear-gradient(90deg, #1c0020 0%, #38003c 55%, #1c0020 100%)',
            borderBottom: '2px solid var(--color-accent-green)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'var(--color-accent-green)',
                color: 'var(--color-pl-purple)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 900,
                fontSize: '12px',
                letterSpacing: '0.05em',
              }}
            >
              PL
            </div>
            <div>
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  letterSpacing: '0.08em',
                  color: 'var(--color-accent-green)',
                  textTransform: 'uppercase',
                }}
              >
                Official Studio Recap
              </div>
              <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                Full-Time Match Intelligence
              </div>
            </div>
          </div>

          {/* Final Scoreboard */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'rgba(0, 0, 0, 0.5)',
              padding: '6px 14px',
              borderRadius: '20px',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <span style={{ color: 'var(--color-team-home)', fontWeight: 800, fontSize: '12px' }}>
              NBL
            </span>
            <span
              className="mono-stat"
              style={{ fontSize: '18px', fontWeight: 900, color: 'var(--color-text-primary)' }}
            >
              {effectiveRecap.final_score.home} - {effectiveRecap.final_score.away}
            </span>
            <span style={{ color: 'var(--color-team-away)', fontWeight: 800, fontSize: '12px' }}>
              HSC
            </span>
            <span
              style={{
                fontSize: '10px',
                background: 'var(--color-accent-green)',
                color: 'var(--color-text-inverse)',
                padding: '1px 6px',
                borderRadius: '4px',
                fontWeight: 800,
              }}
            >
              FT
            </span>
          </div>

          <button
            onClick={onClose}
            aria-label="Close match recap"
            style={{
              background: 'transparent',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text-secondary)',
              fontSize: '16px',
              cursor: 'pointer',
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
          >
            ✕
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div
          style={{
            display: 'flex',
            backgroundColor: 'var(--color-bg-elevated)',
            borderBottom: '1px solid var(--color-border-subtle)',
            padding: '0 24px',
            gap: '8px',
          }}
          role="tablist"
          aria-label="Match recap sections"
        >
          <button
            role="tab"
            aria-selected={activeTab === 'story'}
            onClick={() => setActiveTab('story')}
            style={{
              padding: '12px 16px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'story' ? '2px solid var(--color-accent-cyan)' : '2px solid transparent',
              color: activeTab === 'story' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontSize: '13px',
              fontWeight: activeTab === 'story' ? 700 : 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>📖</span>
            <span>Match Story &amp; Turning Points</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'tactical'}
            onClick={() => setActiveTab('tactical')}
            style={{
              padding: '12px 16px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'tactical' ? '2px solid var(--color-accent-yellow)' : '2px solid transparent',
              color: activeTab === 'tactical' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontSize: '13px',
              fontWeight: activeTab === 'tactical' ? 700 : 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>⚖️</span>
            <span>Tactical &amp; xG Balance</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'honours'}
            onClick={() => setActiveTab('honours')}
            style={{
              padding: '12px 16px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'honours' ? '2px solid var(--color-accent-green)' : '2px solid transparent',
              color: activeTab === 'honours' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontSize: '13px',
              fontWeight: activeTab === 'honours' ? 700 : 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🏆</span>
            <span>MOTM &amp; Fantasy Honours</span>
          </button>
        </div>

        {/* Modal Scrollable Content Area */}
        <div
          style={{
            padding: '24px',
            overflowY: 'auto',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {/* Tab 1: Match Story & Turning Points */}
          {activeTab === 'story' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }} dir={isRtl ? 'rtl' : 'ltr'}>
              <div>
                <h2
                  id="recap-headline"
                  style={{
                    fontSize: '18px',
                    fontWeight: 800,
                    color: 'var(--color-text-primary)',
                    lineHeight: 1.3,
                    marginBottom: '8px',
                  }}
                >
                  {headlineText}
                </h2>
                <p
                  style={{
                    fontSize: '14px',
                    lineHeight: 1.6,
                    color: 'var(--color-text-secondary)',
                    background: 'var(--color-bg-elevated)',
                    padding: '14px 16px',
                    borderRadius: '8px',
                    borderLeft: isRtl ? 'none' : '3px solid var(--color-accent-cyan)',
                    borderRight: isRtl ? '3px solid var(--color-accent-cyan)' : 'none',
                  }}
                >
                  {storyText}
                </p>
              </div>

              <div>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--color-text-secondary)',
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>⏱</span>
                  <span>Key Match Turning Points ({effectiveRecap.turning_points.length})</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {effectiveRecap.turning_points.map((tp, idx) => {
                    const isHome = tp.team.toLowerCase().includes('northbridge');
                    const teamColor = isHome ? 'var(--color-team-home)' : 'var(--color-team-away)';
                    return (
                      <div
                        key={idx}
                        className="studio-card"
                        style={{
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '14px',
                          borderLeft: isRtl ? '1px solid var(--color-border-subtle)' : `3px solid ${teamColor}`,
                          borderRight: isRtl ? `3px solid ${teamColor}` : '1px solid var(--color-border-subtle)',
                        }}
                      >
                        <div
                          className="mono-stat"
                          style={{
                            fontSize: '14px',
                            fontWeight: 900,
                            color: teamColor,
                            background: 'rgba(0, 0, 0, 0.4)',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            minWidth: '42px',
                            textAlign: 'center',
                          }}
                        >
                          {tp.minute}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                              {tp.title}
                            </span>
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                color: teamColor,
                                background: `${teamColor}18`,
                                padding: '1px 6px',
                                borderRadius: '4px',
                              }}
                            >
                              {tp.team}
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>
                            {tp.description}
                          </div>
                          <div
                            style={{
                              fontSize: '11px',
                              color: 'var(--color-accent-green)',
                              fontWeight: 600,
                              marginTop: '4px',
                            }}
                          >
                            &bull; {tp.impact}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Tactical & xG Balance */}
          {activeTab === 'tactical' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* xG Dual Comparison Card */}
              <div className="studio-card" style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)' }}>
                    Expected Goals (xG) Balance
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--color-accent-yellow)', fontWeight: 700 }}>
                    {effectiveRecap.xg_balance.dominance}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', margin: '10px 0' }}>
                  <div style={{ width: '80px', textAlign: 'left' }}>
                    <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-team-home)' }}>Northbridge Lions</div>
                    <div className="mono-stat" style={{ fontSize: '22px', fontWeight: 900, color: 'var(--color-team-home)' }}>
                      {effectiveRecap.xg_balance.home_xg.toFixed(2)}
                    </div>
                  </div>

                  {/* Dual Bar */}
                  <div style={{ flex: 1, height: '12px', background: 'var(--color-bg-base)', borderRadius: '6px', overflow: 'hidden', display: 'flex' }}>
                    <div
                      style={{
                        width: `${(effectiveRecap.xg_balance.home_xg / xgTotal) * 100}%`,
                        height: '100%',
                        background: 'var(--color-team-home)',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Northbridge Lions xG: ${effectiveRecap.xg_balance.home_xg}`}
                    />
                    <div
                      style={{
                        width: `${(effectiveRecap.xg_balance.away_xg / xgTotal) * 100}%`,
                        height: '100%',
                        background: 'var(--color-team-away)',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Harbourside xG: ${effectiveRecap.xg_balance.away_xg}`}
                    />
                  </div>

                  <div style={{ width: '80px', textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-team-away)' }}>Harbourside</div>
                    <div className="mono-stat" style={{ fontSize: '22px', fontWeight: 900, color: 'var(--color-team-away)' }}>
                      {effectiveRecap.xg_balance.away_xg.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--color-text-tertiary)', marginTop: '8px' }}>
                  <span>{effectiveRecap.xg_balance.home_shots} Shots ({stats?.shots?.home?.on_target ?? 0} on target)</span>
                  <span>{effectiveRecap.xg_balance.away_shots} Shots ({stats?.shots?.away?.on_target ?? 0} on target)</span>
                </div>
              </div>

              {/* Tactical Entropy & Chaos Rhythm Breakdown */}
              <div className="studio-card" style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)' }}>
                    Tactical Entropy &amp; Rhythm (CCI)
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--color-accent-cyan)', fontWeight: 700 }}>
                    {effectiveRecap.tactical_entropy.rhythm_label}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '8px 0' }}>
                  <span className="mono-stat" style={{ fontSize: '28px', fontWeight: 900, color: 'var(--color-accent-cyan)' }}>
                    {effectiveRecap.tactical_entropy.average_cci.toFixed(1)}
                  </span>
                  <span style={{ fontSize: '13px', color: 'var(--color-text-tertiary)', fontWeight: 600 }}>
                    / 100 Avg Match Index
                  </span>
                </div>

                <div style={{ width: '100%', height: '6px', background: 'var(--color-bg-base)', borderRadius: '3px', overflow: 'hidden', marginBottom: '12px' }}>
                  <div
                    style={{
                      width: `${effectiveRecap.tactical_entropy.average_cci}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--color-accent-cyan), var(--color-accent-yellow))',
                    }}
                  />
                </div>

                <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                  {effectiveRecap.tactical_entropy.summary}
                </p>
              </div>

              {/* Possession & Passing Distribution */}
              {stats && (
                <div className="studio-card" style={{ padding: '16px 20px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
                    Possession &amp; Territory Control
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ textAlign: 'left' }}>
                      <div className="mono-stat" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-team-home)' }}>
                        {stats.possession_pct.home}%
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>Northbridge Lions Possession</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div className="mono-stat" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-accent-green)' }}>
                        {stats.passes.home.completed} / {stats.passes.away.completed}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>Completed Passes</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="mono-stat" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-team-away)' }}>
                        {stats.possession_pct.away}%
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>Harbourside Possession</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: MOTM & Fantasy Honours */}
          {activeTab === 'honours' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Man of the Match Hero Card */}
              <div
                className="studio-card"
                style={{
                  padding: '20px',
                  background: 'linear-gradient(135deg, rgba(20, 28, 38, 0.95) 0%, rgba(56, 0, 60, 0.35) 100%)',
                  border: '1px solid var(--color-accent-yellow)',
                  boxShadow: '0 0 20px rgba(255, 230, 0, 0.15)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, var(--color-accent-yellow), #f59e0b)',
                        color: '#080b0f',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '22px',
                        boxShadow: '0 0 12px rgba(255, 230, 0, 0.4)',
                      }}
                    >
                      ★
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 900,
                            background: 'var(--color-accent-yellow)',
                            color: '#080b0f',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            letterSpacing: '0.05em',
                          }}
                        >
                          OFFICIAL MAN OF THE MATCH
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>
                          Broadcast Jury
                        </span>
                      </div>
                      <h3 style={{ fontSize: '20px', fontWeight: 900, color: 'var(--color-text-primary)', marginTop: '4px' }}>
                        {effectiveRecap.man_of_the_match.name}
                      </h3>
                      <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                        {effectiveRecap.man_of_the_match.team}
                      </div>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-tertiary)', fontWeight: 700 }}>
                      MATCH RATING
                    </div>
                    <div
                      className="mono-stat"
                      style={{ fontSize: '28px', fontWeight: 900, color: 'var(--color-accent-green)' }}
                    >
                      {effectiveRecap.man_of_the_match.rating.toFixed(1)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--color-accent-yellow)', fontWeight: 700 }}>
                      +{effectiveRecap.man_of_the_match.bps} Fantasy BPS
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    marginTop: '16px',
                    padding: '12px 14px',
                    background: 'rgba(0, 0, 0, 0.35)',
                    borderRadius: '6px',
                    fontSize: '12px',
                    color: 'var(--color-text-secondary)',
                    lineHeight: 1.5,
                  }}
                >
                  {effectiveRecap.man_of_the_match.summary}
                </div>
              </div>

              {/* Fantasy Bonus Points System (BPS) Podium */}
              <div>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--color-text-secondary)',
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>🏆</span>
                  <span>fantasy football (Fantasy) Bonus Points Allocation</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                  {fantasyPodium.map((p, idx) => {
                    const badgeLabels = ['🥇 3 BONUS PTS', '🥈 2 BONUS PTS', '🥉 1 BONUS PT'];
                    const badgeColors = ['#f59e0b', '#94a3b8', '#b45309'];
                    const teamColor =
                      p.team === 'home' || p.team === 'Northbridge Lions'
                        ? 'var(--color-team-home)'
                        : 'var(--color-team-away)';

                    return (
                      <div
                        key={p.player_id}
                        className="studio-card"
                        style={{
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          textAlign: 'center',
                          borderTop: `3px solid ${badgeColors[idx]}`,
                        }}
                      >
                        <div
                          style={{
                            fontSize: '10px',
                            fontWeight: 900,
                            color: badgeColors[idx],
                            marginBottom: '6px',
                          }}
                        >
                          {badgeLabels[idx]}
                        </div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--color-text-primary)' }}>
                          {p.name}
                        </div>
                        <div style={{ fontSize: '11px', color: teamColor, fontWeight: 700, margin: '2px 0 8px 0' }}>
                          #{p.jersey_number} &bull; {p.role}
                        </div>
                        <div
                          className="mono-stat"
                          style={{
                            fontSize: '16px',
                            fontWeight: 900,
                            color: 'var(--color-accent-green)',
                            background: 'rgba(0, 255, 135, 0.1)',
                            padding: '3px 10px',
                            borderRadius: '12px',
                          }}
                        >
                          {p.bps} BPS
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div
          style={{
            padding: '14px 24px',
            backgroundColor: 'var(--color-bg-elevated)',
            borderTop: '1px solid var(--color-border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>
            InGame AI Studio &bull; 4-Agent Verified Intelligence
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            {onExploreAnalytics && (
              <button
                onClick={onExploreAnalytics}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  color: 'var(--color-text-primary)',
                  border: '1px solid var(--color-border-subtle)',
                  padding: '8px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
              >
                📊 Explore 22-Player Analytics ↓
              </button>
            )}

            <button
              onClick={onClose}
              style={{
                background: 'linear-gradient(135deg, var(--color-accent-green) 0%, var(--color-accent-cyan) 100%)',
                color: 'var(--color-text-inverse)',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 900,
                cursor: 'pointer',
                boxShadow: '0 0 12px rgba(0, 255, 135, 0.3)',
              }}
            >
              Close Studio Recap
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
