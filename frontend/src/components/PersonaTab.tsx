/**
 * InGame Studio - Tab 4: AI Broadcast Persona Selector
 * 
 * Features:
 * 1. Team Allegiance Bar (Neutral, Northbridge Lions Home, Harbourside City Away)
 * 2. 4 Interactive Persona Cards Grid:
 *    - Tactical Purist (analytical, deep data, passing networks, xG)
 *    - Casual Fan (accessible, entertaining, simplified rules, excitement)
 *    - Club Loyalist (partisan, emotional, fan-focused narrative adapting to allegiance)
 *    - Fantasy Scout (fantasy football points, bonus point predictors, transfer advice)
 *    - Each card displays icon, badge, core focus, audience, and sample commentary excerpt.
 * 3. Persona Explanation Box: Detailed breakdown explaining how commentary, metrics prominence,
 *    and telestrator visuals adapt to the chosen persona.
 * 4. Action Button: "Apply Persona Settings" confirming and persisting selection to localStorage
 *    and notifying parent callback.
 * 
 * Conforms strictly to ingame-ui-design tokens and broadcast visual standards.
 */

import React, { useState, useEffect } from 'react';
import {
  ViewerPersona,
  LanguageCode,
  ClubPerspective,
  TeamAllegiance,
  VerifiedInsight,
  AnalyticsResponse,
} from '../types';
import { PERSONA_COLORS, CANONICAL_COLORS } from '../constants/tokens';

export interface PersonaTabProps {
  activePersona?: ViewerPersona;
  onSelectPersona?: (persona: ViewerPersona) => void;
  teamAllegiance?: TeamAllegiance;
  onSelectAllegiance?: (allegiance: TeamAllegiance) => void;
  favoriteClub?: ClubPerspective;
  onSelectClub?: (club: ClubPerspective) => void;
  language?: LanguageCode;
  onApplySettings?: (persona: ViewerPersona, allegiance: TeamAllegiance, club: ClubPerspective) => void;
  insight?: VerifiedInsight | null;
  analytics?: AnalyticsResponse | null;
  activeEventClock?: string;
}

interface PersonaCardDefinition {
  id: ViewerPersona;
  name: string;
  badge: string;
  icon: string;
  accentColor: string;
  tagline: string;
  targetAudience: string;
  coreFocus: string[];
  telestratorStyle: string;
}

const PERSONA_DEFINITIONS: PersonaCardDefinition[] = [
  {
    id: 'tactical',
    name: 'Tactical Purist',
    badge: 'TACTICAL PURIST',
    icon: '⚽',
    accentColor: PERSONA_COLORS.tactical,
    tagline: 'Deep spatial data, pressing networks & expected threat modeling',
    targetAudience: 'Coaches, match analysts, tactical bloggers & football purists',
    coreFocus: [
      'Pass Difficulty Rating (PDR) & corridor congestion',
      'Expected Threat (xT) & field tilt progression',
      'Compactness polygons & defensive line height',
      'Chaos vs Control Index (CCI) match momentum',
    ],
    telestratorStyle:
      'Passing lane vectors with intercept cones, 8m defender threat radii, low-block convex hulls, and offside line depth annotations.',
  },
  {
    id: 'casual',
    name: 'Casual Fan',
    badge: 'CASUAL FAN',
    icon: '📺',
    accentColor: PERSONA_COLORS.casual,
    tagline: 'High-energy storytelling, match thrills & accessible rules',
    targetAudience: 'Weekend supporters, neutral viewers & newcomers to the game',
    coreFocus: [
      'Goalmouth excitement & shot thunder velocity',
      'Decisive match turning points explained simply',
      'Clear momentum shifts without statistical overload',
      'Hero players, star matchups & stadium atmosphere',
    ],
    telestratorStyle:
      'High-impact shot trajectory arcs, bold goal celebration rings, player speed callouts, and clean highlight spotlights.',
  },
  {
    id: 'club',
    name: 'Club Loyalist',
    badge: 'CLUB LOYALIST',
    icon: '🔵',
    accentColor: PERSONA_COLORS.loyalist,
    tagline: 'Passionate partisan commentary, referee scrutiny & club heritage',
    targetAudience: 'Season ticket holders, club ultras & passionate fans with allegiances',
    coreFocus: [
      'Partisan pride and emotional narrative framing',
      'Key referee decisions, fouls, and penalty appeals',
      'Historical rivalry context and bragging rights',
      'Defending the badge with fearless grit and passion',
    ],
    telestratorStyle:
      'Club-colored territory dominance zones (Red for Northbridge Lions, Sky Blue for City), tackle impact markers, and tactical wall shields.',
  },
  {
    id: 'fantasy',
    name: 'Fantasy Scout',
    badge: 'Fantasy SCOUT',
    icon: '📊',
    accentColor: PERSONA_COLORS.fantasy,
    tagline: 'Bonus Points System (BPS), xGI, captaincy radar & price predictors',
    targetAudience: 'fantasy football managers, mini-league leaders & stat strategists',
    coreFocus: [
      'Fantasy Bonus Points System (BPS) live podium tracker',
      'Expected Goal Involvement (xGI) & key chance creation',
      'Clean sheet probabilities & defensive returns',
      'Upcoming Gameweek fixture swings & transfer targets',
    ],
    telestratorStyle:
      'Player-lock highlight rings, BPS point accumulation tags, shot quality cones, and bonus point podium indicators.',
  },
];

export const PersonaTab: React.FC<PersonaTabProps> = ({
  activePersona: propPersona = 'tactical',
  onSelectPersona,
  teamAllegiance: propAllegiance = 'neutral',
  onSelectAllegiance,
  favoriteClub: propClub = 'Northbridge Lions',
  onSelectClub,
  language = 'en',
  onApplySettings,
  insight = null,
  analytics = null,
  activeEventClock,
}) => {
  // Local state initialized with fallback to localStorage then props
  const [selectedPersona, setSelectedPersona] = useState<ViewerPersona>(() => {
    const saved = localStorage.getItem('ingame_persona');
    if (saved && ['tactical', 'casual', 'club', 'fantasy'].includes(saved)) {
      return saved as ViewerPersona;
    }
    return propPersona;
  });

  const [selectedAllegiance, setSelectedAllegiance] = useState<TeamAllegiance>(() => {
    const saved = localStorage.getItem('ingame_allegiance');
    if (saved && ['neutral', 'home', 'away'].includes(saved)) {
      return saved as TeamAllegiance;
    }
    return propAllegiance;
  });

  const [selectedClub, setSelectedClub] = useState<ClubPerspective>(() => {
    const saved = localStorage.getItem('ingame_favorite_club');
    if (saved === 'Harbourside City' || saved === 'Northbridge Lions') {
      return saved;
    }
    return propClub;
  });

  const [isSavedFeedback, setIsSavedFeedback] = useState<boolean>(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string>('');

  // Sync state if external props change
  useEffect(() => {
    if (propPersona) setSelectedPersona(propPersona);
  }, [propPersona]);

  useEffect(() => {
    if (propAllegiance) setSelectedAllegiance(propAllegiance);
  }, [propAllegiance]);

  useEffect(() => {
    if (propClub) setSelectedClub(propClub);
  }, [propClub]);

  // Handle Team Allegiance Selection
  const handleAllegianceChange = (allegiance: TeamAllegiance) => {
    setSelectedAllegiance(allegiance);
    let resolvedClub: ClubPerspective = selectedClub;
    if (allegiance === 'home') {
      resolvedClub = 'Northbridge Lions';
    } else if (allegiance === 'away') {
      resolvedClub = 'Harbourside City';
    }
    setSelectedClub(resolvedClub);

    if (onSelectAllegiance) {
      onSelectAllegiance(allegiance);
    }
    if (onSelectClub) {
      onSelectClub(resolvedClub);
    }
  };

  // Handle Persona Selection
  const handlePersonaSelect = (personaId: ViewerPersona) => {
    setSelectedPersona(personaId);
    if (onSelectPersona) {
      onSelectPersona(personaId);
    }
  };

  // Handle Apply Persona Settings Action
  const handleApply = () => {
    // Persist to localStorage
    localStorage.setItem('ingame_persona', selectedPersona);
    localStorage.setItem('ingame_allegiance', selectedAllegiance);
    localStorage.setItem('ingame_favorite_club', selectedClub);

    // Notify callbacks
    if (onSelectPersona) {
      onSelectPersona(selectedPersona);
    }
    if (onSelectAllegiance) {
      onSelectAllegiance(selectedAllegiance);
    }
    if (onSelectClub) {
      onSelectClub(selectedClub);
    }
    if (onApplySettings) {
      onApplySettings(selectedPersona, selectedAllegiance, selectedClub);
    }

    const personaName = PERSONA_DEFINITIONS.find((p) => p.id === selectedPersona)?.name || 'Persona';
    const allegianceName =
      selectedAllegiance === 'neutral'
        ? 'Neutral Broadcast'
        : selectedAllegiance === 'home'
        ? 'Northbridge Lions (Lions)'
        : 'Harbourside City (Harbourers)';

    setFeedbackMessage(`✓ Applied: ${personaName} mode with ${allegianceName} perspective saved to broadcast studio.`);
    setIsSavedFeedback(true);

    // Auto-hide feedback toast after 4 seconds
    setTimeout(() => {
      setIsSavedFeedback(false);
    }, 4000);
  };

  const activeDef =
    PERSONA_DEFINITIONS.find((p) => p.id === selectedPersona) || PERSONA_DEFINITIONS[0];

  // Resolve commentary sample for current allegiance
  // Live commentary: the latest verified insight, in the viewer's language
  const getSampleText = (def: PersonaCardDefinition): string => {
    if (!insight) return '';
    const key = def.id === 'fantasy' ? 'player' : def.id;
    const translated = insight.translations?.[language]?.[key];
    if (translated) return translated;
    return def.id === 'tactical'
      ? insight.tactical_analysis
      : def.id === 'casual'
      ? insight.casual_story
      : def.id === 'club'
      ? insight.club_loyalist_story
      : insight.player_lock_story;
  };

  // Live metrics each persona puts first, from the current match state
  const getLiveMetrics = (def: PersonaCardDefinition): string[] => {
    const stats = analytics?.match_stats;
    const m = insight?.metrics ?? {};
    const fmt = (value: number | undefined, digits = 1, unit = '') =>
      value === undefined || value === null || Number.isNaN(value) ? '—' : `${value.toFixed(digits)}${unit}`;
    if (def.id === 'tactical') {
      return [
        `PDR: ${fmt(m.pass_difficulty, 1, '%')}`,
        `xT Gained: ${m.xt_gained === undefined ? '—' : `${m.xt_gained >= 0 ? '+' : ''}${m.xt_gained.toFixed(2)}`}`,
        `CCI: ${fmt(m.chaos_index)}`,
        `Field Tilt: ${stats?.field_tilt ? `${Math.round(stats.field_tilt.home)}% - ${Math.round(stats.field_tilt.away)}%` : '—'}`,
      ];
    }
    if (def.id === 'casual') {
      return [
        `Ball Speed: ${fmt(m.ball_speed_kmh, 1, ' km/h')}`,
        `Possession: ${stats ? `${Math.round(stats.possession_pct.home)}% - ${Math.round(stats.possession_pct.away)}%` : '—'}`,
        `Shots: ${stats ? `${stats.shots.home.total ?? 0} - ${stats.shots.away.total ?? 0}` : '—'}`,
        `Score: ${stats ? `${stats.score.home} - ${stats.score.away}` : '—'}`,
      ];
    }
    if (def.id === 'club') {
      return [
        `Tackles Won: ${stats ? `${Math.round(stats.tackles.home.won_pct ?? 0)}% - ${Math.round(stats.tackles.away.won_pct ?? 0)}%` : '—'}`,
        `Fouls: ${stats ? `${stats.fouls.home} - ${stats.fouls.away}` : '—'}`,
        `Corners: ${stats ? `${stats.corners.home} - ${stats.corners.away}` : '—'}`,
        `Interceptions: ${stats ? `${stats.interceptions.home} - ${stats.interceptions.away}` : '—'}`,
      ];
    }
    const top = [...(analytics?.player_stats ?? [])].sort((x, y) => y.bps - x.bps)[0];
    return [
      `BPS Leader: ${top && top.bps > 0 ? `${top.name} (${top.bps})` : '—'}`,
      `Bonus Points: ${top ? top.fantasy_bonus_points : '—'}`,
      `Top Rating: ${top ? top.rating.toFixed(1) : '—'}`,
      `Key Passes: ${top ? top.key_passes : '—'}`,
    ];
  };

  return (
    <div
      className="persona-tab-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--spacing-xl)',
        padding: 'var(--spacing-xl)',
        maxWidth: '1440px',
        margin: '0 auto',
        width: '100%',
        color: 'var(--color-text-primary)',
      }}
    >
      {/* ── HEADER SECTION ──────────────────────────────────────────────── */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          borderBottom: '1px solid var(--color-border-subtle)',
          paddingBottom: 'var(--spacing-lg)',
          flexWrap: 'wrap',
          gap: 'var(--spacing-md)',
        }}
      >
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--spacing-xs)',
              fontSize: 'var(--text-caption)',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--color-accent-green)',
              marginBottom: 'var(--spacing-xs)',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-accent-green)',
                boxShadow: '0 0 8px var(--color-accent-green)',
              }}
            />
            AI Broadcast Persona Engine • 4 Multi-Agent Personas
          </div>
          <h1
            style={{
              fontSize: 'var(--text-h1)',
              fontWeight: 700,
              color: 'var(--color-text-primary)',
              letterSpacing: '-0.02em',
              margin: 0,
            }}
          >
            Audience Persona
          </h1>
          <p
            style={{
              fontSize: 'var(--text-body)',
              color: 'var(--color-text-secondary)',
              marginTop: 'var(--spacing-xs)',
              maxWidth: '840px',
            }}
          >
            Personalize the live commentary narrative, metric prominence in the broadcast HUD,
            and 2D pitch telestrator overlays to match your preferred analytical depth and club allegiance.
          </p>
        </div>

        {/* Global Quick Status Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--spacing-md)',
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-emphasis)',
            borderRadius: '8px',
            padding: 'var(--spacing-sm) var(--spacing-lg)',
          }}
        >
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                fontSize: 'var(--text-micro)',
                textTransform: 'uppercase',
                color: 'var(--color-text-tertiary)',
                fontWeight: 600,
                letterSpacing: '0.04em',
              }}
            >
              Active Broadcast Profile
            </div>
            <div
              style={{
                fontSize: 'var(--text-h3)',
                fontWeight: 700,
                color: activeDef.accentColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '6px',
              }}
            >
              <span>{activeDef.icon}</span>
              <span>{activeDef.name}</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── TOAST NOTIFICATION FEEDBACK ──────────────────────────────────── */}
      {isSavedFeedback && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'rgba(0, 255, 135, 0.12)',
            border: '1px solid var(--color-accent-green)',
            borderRadius: '8px',
            padding: 'var(--spacing-md) var(--spacing-lg)',
            color: 'var(--color-accent-green)',
            fontSize: 'var(--text-body)',
            fontWeight: 600,
            boxShadow: '0 4px 16px rgba(0, 255, 135, 0.15)',
            animation: 'fadeIn 0.2s ease-out',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>{feedbackMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setIsSavedFeedback(false)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-accent-green)',
              cursor: 'pointer',
              fontSize: 'var(--text-body)',
              fontWeight: 700,
              padding: '0 var(--spacing-xs)',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── SECTION 2: 4 PERSONA CARDS GRID ──────────────────────────────── */}
      <section>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 'var(--spacing-md)',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 'var(--text-h2)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                margin: 0,
              }}
            >
              Broadcast Personas
            </h2>
            <p
              style={{
                fontSize: 'var(--text-caption)',
                color: 'var(--color-text-secondary)',
                marginTop: '2px',
              }}
            >
              The highlighted card is the persona chosen in the top bar; it is applied to every tab.
            </p>
          </div>
        </div>

        {/* 4 Cards Interactive Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--spacing-lg)',
          }}
        >
          {PERSONA_DEFINITIONS.map((def) => {
            const isSelected = selectedPersona === def.id;
            return (
              <div
                key={def.id}
                aria-current={isSelected ? 'true' : undefined}
                style={{
                  backgroundColor: 'var(--color-bg-elevated)',
                  border: isSelected
                    ? `2px solid ${def.accentColor}`
                    : '1px solid var(--color-border-subtle)',
                  borderRadius: '8px',
                  padding: 'var(--spacing-lg)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  cursor: 'default',
                  position: 'relative',
                  outline: 'none',
                  boxShadow: isSelected
                    ? `0 4px 20px rgba(0, 0, 0, 0.4), inset 0 0 0 1px ${def.accentColor}`
                    : '0 2px 8px rgba(0,0,0,0.2)',
                  transition: 'border-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease',
                  transform: isSelected ? 'translateY(-2px)' : 'none',
                }}
              >
                {/* Top Badge & Radio */}
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 'var(--spacing-md)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--spacing-xs)',
                        padding: '4px 10px',
                        borderRadius: '16px',
                        backgroundColor: `rgba(${def.accentColor === PERSONA_COLORS.tactical ? '4,240,255' : def.accentColor === PERSONA_COLORS.casual ? '255,230,0' : def.accentColor === PERSONA_COLORS.loyalist ? '168,85,247' : '0,255,135'}, 0.12)`,
                        color: def.accentColor,
                        fontSize: 'var(--text-caption)',
                        fontWeight: 700,
                        letterSpacing: '0.04em',
                      }}
                    >
                      <span>{def.icon}</span>
                      <span>{def.badge}</span>
                    </div>

                    {/* Radio Indicator */}
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        border: isSelected
                          ? `2px solid ${def.accentColor}`
                          : '2px solid var(--color-border-emphasis)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        backgroundColor: 'var(--color-bg-base)',
                      }}
                    >
                      {isSelected && (
                        <div
                          style={{
                            width: '10px',
                            height: '10px',
                            borderRadius: '50%',
                            backgroundColor: def.accentColor,
                          }}
                        />
                      )}
                    </div>
                  </div>

                  {/* Persona Title & Tagline */}
                  <h3
                    style={{
                      fontSize: 'var(--text-h2)',
                      fontWeight: 700,
                      color: isSelected ? '#FFFFFF' : 'var(--color-text-primary)',
                      marginBottom: 'var(--spacing-xs)',
                    }}
                  >
                    {def.name}
                  </h3>
                  <p
                    style={{
                      fontSize: 'var(--text-body)',
                      color: 'var(--color-text-secondary)',
                      lineHeight: 1.4,
                      marginBottom: 'var(--spacing-md)',
                    }}
                  >
                    {def.tagline}
                  </p>

                  {/* Target Audience Pill */}
                  <div
                    style={{
                      fontSize: 'var(--text-micro)',
                      color: 'var(--color-text-tertiary)',
                      marginBottom: 'var(--spacing-md)',
                    }}
                  >
                    <span style={{ fontWeight: 600, color: 'var(--color-text-secondary)' }}>Audience: </span>
                    {def.targetAudience}
                  </div>

                  {/* Core Focus List */}
                  <div
                    style={{
                      borderTop: '1px solid var(--color-border-subtle)',
                      paddingTop: 'var(--spacing-sm)',
                      marginBottom: 'var(--spacing-md)',
                    }}
                  >
                    <div
                      style={{
                        fontSize: 'var(--text-micro)',
                        textTransform: 'uppercase',
                        color: 'var(--color-text-tertiary)',
                        fontWeight: 700,
                        letterSpacing: '0.04em',
                        marginBottom: '6px',
                      }}
                    >
                      Core Focus
                    </div>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: '18px',
                        fontSize: 'var(--text-caption)',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.5,
                      }}
                    >
                      {def.coreFocus.map((focusItem, idx) => (
                        <li key={idx} style={{ marginBottom: '2px' }}>
                          {focusItem}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Metric Chips */}
                  <div style={{ marginBottom: 'var(--spacing-md)' }}>
                    <div
                      style={{
                        fontSize: 'var(--text-micro)',
                        textTransform: 'uppercase',
                        color: 'var(--color-text-tertiary)',
                        fontWeight: 700,
                        letterSpacing: '0.04em',
                        marginBottom: '6px',
                      }}
                    >
                      Priority Telemetry
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {getLiveMetrics(def).map((metric, idx) => (
                        <span
                          key={idx}
                          className="mono-stat"
                          style={{
                            fontSize: 'var(--text-micro)',
                            fontFamily: 'var(--font-mono)',
                            backgroundColor: 'var(--color-bg-base)',
                            border: '1px solid var(--color-border-subtle)',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            color: isSelected ? def.accentColor : 'var(--color-text-secondary)',
                            fontWeight: 600,
                          }}
                        >
                          {metric}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Sample Live Excerpt */}
                <div
                  style={{
                    backgroundColor: 'var(--color-bg-base)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    padding: 'var(--spacing-sm) var(--spacing-md)',
                    marginTop: 'var(--spacing-xs)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '4px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: 'var(--text-micro)',
                        textTransform: 'uppercase',
                        fontWeight: 700,
                        color: def.accentColor,
                        letterSpacing: '0.04em',
                      }}
                    >
                      Live Commentary Excerpt
                    </span>
                    <span
                      style={{
                        fontSize: 'var(--text-micro)',
                        color: 'var(--color-text-tertiary)',
                      }}
                    >
                      {activeEventClock ? `⏱ ${activeEventClock}` : '⏱ --:--'}
                    </span>
                  </div>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 'var(--text-caption)',
                      color: 'var(--color-text-primary)',
                      fontStyle: 'italic',
                      lineHeight: 1.45,
                    }}
                  >
                    {getSampleText(def)
                      ? `"${getSampleText(def)}"`
                      : 'Live commentary appears here as soon as the match produces its first event.'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── SECTION 3: DETAILED PERSONA EXPLANATION BOX ─────────────────── */}
      <section
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border-emphasis)',
          borderRadius: '8px',
          padding: 'var(--spacing-xl)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Accent Bar on top */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            backgroundColor: activeDef.accentColor,
          }}
        />

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: 'var(--spacing-md)',
            marginBottom: 'var(--spacing-lg)',
          }}
        >
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--spacing-xs)',
                fontSize: 'var(--text-caption)',
                fontWeight: 700,
                color: activeDef.accentColor,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginBottom: 'var(--spacing-xs)',
              }}
            >
              <span>{activeDef.icon}</span>
              <span>{activeDef.name} Multi-Agent Architecture Adaptation</span>
            </div>
            <h3
              style={{
                fontSize: 'var(--text-h2)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                margin: 0,
              }}
            >
              How InGame Studio Adapts to Your Selected Persona
            </h3>
          </div>

          <div
            style={{
              fontSize: 'var(--text-caption)',
              color: 'var(--color-text-tertiary)',
              backgroundColor: 'var(--color-bg-base)',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            Configured for: <strong>{activeDef.name}</strong> • Language: <strong>{language.toUpperCase()}</strong>
          </div>
        </div>

        {/* 3 Explanation Columns */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--spacing-lg)',
          }}
        >
          {/* Column 1: AI Commentary & Narrative */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              padding: 'var(--spacing-md)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-xs)',
                fontSize: 'var(--text-h3)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--spacing-xs)',
              }}
            >
              <span>🎙️</span>
              <span>Commentary & Narrative Tone</span>
            </div>
            <p
              style={{
                fontSize: 'var(--text-caption)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
                margin: 0,
              }}
            >
              {selectedPersona === 'tactical' &&
                'The Pundit and Studio Director agents formulate causal reasoning rooted in numerical telemetry: space opening, pass lane risk, and line breaking. Commentary prioritizes tactical terminology, defensive shape stability, and xT delta.'}
              {selectedPersona === 'casual' &&
                'Narrative models prioritize excitement, momentum swings, and the emotional story of the game. Statistical terms are translated into intuitive broadcast analogies (e.g. "thunderous blast" instead of "104 km/h with 0.12 PDR").'}
              {selectedPersona === 'club' &&
                `The agent adopts an unashamedly partisan narrative for ${
                  selectedAllegiance === 'home'
                    ? 'Northbridge Lions, cheering Northbridge dominance and celebrating every press and recovery'
                    : selectedAllegiance === 'away'
                    ? 'Harbourside City, lauding title-winning pedigree, Hagen’s ruthless finishing, and the manager’s masterclass'
                    : 'both clubs with fiery derby tension, tracking rivalry pride and contested referee decisions'
                }.`}
              {selectedPersona === 'fantasy' &&
                'Every pass, tackle, and shot is instantly converted into fantasy football scoring currency. Live updates report provisional Bonus Point System (BPS) rankings, clean sheet odds, assist eligibility, and Gameweek transfer targets.'}
            </p>
          </div>

          {/* Column 2: Metrics Prominence */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              padding: 'var(--spacing-md)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-xs)',
                fontSize: 'var(--text-h3)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--spacing-xs)',
              }}
            >
              <span>📈</span>
              <span>Broadcast HUD & Telemetry Priority</span>
            </div>
            <p
              style={{
                fontSize: 'var(--text-caption)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
                margin: 0,
              }}
            >
              {selectedPersona === 'tactical' &&
                'Spotlight tiles highlight Pass Difficulty Rating (PDR), Chaos vs Control Rhythm Index (CCI), Field Tilt %, and Expected Threat (xT) created per 90. Monospace stats appear with delta indicators.'}
              {selectedPersona === 'casual' &&
                'HUD simplifies the display to primary match pillars: Scoreline, Live Clock, Top Shot Speed (km/h), Possession %, and decisive Goal / Card callout banners.'}
              {selectedPersona === 'club' &&
                'Emphasizes territorial dominance in the attacking third, fouls drawn, tackle win percentage, and comparative discipline statistics between the two sides.'}
              {selectedPersona === 'fantasy' &&
                'Dynamic player lock surfaces BPS scores, Expected Goal Involvement (xGI), minutes played threshold for clean sheet points (60’), and live price change radar indicators.'}
            </p>
          </div>

          {/* Column 3: Pitch Telestrator Visuals */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              padding: 'var(--spacing-md)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-xs)',
                fontSize: 'var(--text-h3)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--spacing-xs)',
              }}
            >
              <span>📐</span>
              <span>2D Canvas Telestrator Graphics</span>
            </div>
            <p
              style={{
                fontSize: 'var(--text-caption)',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
                margin: 0,
              }}
            >
              {activeDef.telestratorStyle}
            </p>
          </div>
        </div>
      </section>

    </div>
  );
};
