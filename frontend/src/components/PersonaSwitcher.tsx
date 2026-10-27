/**
 * InGame Studio - Global audience persona switcher.
 *
 * The one place where the viewer picks a persona (and, for the Club Loyalist, a club).
 * Every tab reads the choice from the app state, so no tab needs its own selector.
 */

import React from 'react';
import { ViewerPersona, ClubPerspective } from '../types';
import { PERSONA_COLORS } from '../constants/tokens';

export interface PersonaSwitcherProps {
  persona: ViewerPersona;
  favoriteClub: ClubPerspective;
  onSelectPersona: (persona: ViewerPersona) => void;
  onSelectClub: (club: ClubPerspective) => void;
}

const OPTIONS: { id: ViewerPersona; label: string; icon: string; color: string; title: string }[] = [
  { id: 'casual', label: 'Casual', icon: '📺', color: PERSONA_COLORS.casual, title: 'Casual Fan: high energy, accessible thrills' },
  { id: 'tactical', label: 'Tactical', icon: '⚽', color: PERSONA_COLORS.tactical, title: 'Tactical Purist: space, pressing lines, xT and PDR' },
  { id: 'club', label: 'Club', icon: '🔵', color: PERSONA_COLORS.club, title: 'Club Loyalist: passionate, partisan commentary' },
  { id: 'fantasy', label: 'Fantasy', icon: '📊', color: PERSONA_COLORS.fantasy, title: 'Fantasy Scout: fantasy points, BPS and assists' },
];

export const PersonaSwitcher: React.FC<PersonaSwitcherProps> = ({ persona, favoriteClub, onSelectPersona, onSelectClub }) => (
  <div className="persona-switcher" role="group" aria-label="Audience persona for every tab">
    <style>{`
      .persona-switcher { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
      .persona-switcher .ps-label { font: 800 9px var(--font-mono, monospace); letter-spacing: 0.1em; color: var(--color-text-secondary, #8b9bb4); text-transform: uppercase; }
      .persona-switcher .ps-pills { display: flex; gap: 2px; padding: 2px; border-radius: 8px; background: rgba(0,0,0,0.4); border: 1px solid var(--color-border-subtle, #1e2a3a); }
      .persona-switcher .ps-pill { display: flex; align-items: center; gap: 4px; border: none; border-radius: 6px; padding: 4px 9px; cursor: pointer;
        font: 700 11px var(--font-display, sans-serif); background: transparent; color: var(--color-text-secondary, #8b9bb4); }
      .persona-switcher .ps-pill:hover { color: var(--color-text-primary, #f0f4f8); }
      .persona-switcher .ps-club { display: flex; gap: 2px; }
      .persona-switcher .ps-club button { border-radius: 12px; padding: 3px 8px; font: 800 10px var(--font-display, sans-serif); cursor: pointer; }
    `}</style>
    <span className="ps-label">Persona</span>
    <div className="ps-pills" role="tablist">
      {OPTIONS.map((o) => {
        const selected = persona === o.id;
        const color =
          o.id === 'club' && selected
            ? favoriteClub === 'Northbridge Lions'
              ? 'var(--color-team-home)'
              : 'var(--color-team-away)'
            : o.color;
        return (
          <button
            key={o.id}
            role="tab"
            aria-selected={selected}
            title={o.title}
            className="ps-pill"
            onClick={() => onSelectPersona(o.id)}
            style={selected ? { background: color, color: 'var(--color-text-inverse, #080b0f)', boxShadow: `0 0 10px ${color}55` } : undefined}
          >
            <span aria-hidden="true">{o.icon}</span>
            <span>{o.label}</span>
          </button>
        );
      })}
    </div>
    {persona === 'club' && (
      <div className="ps-club" aria-label="Club allegiance">
        <button
          onClick={() => onSelectClub('Northbridge Lions')}
          style={{
            background: favoriteClub === 'Northbridge Lions' ? 'var(--color-team-home)' : 'rgba(239,1,7,0.1)',
            color: favoriteClub === 'Northbridge Lions' ? '#fff' : 'var(--color-team-home)',
            border: '1px solid var(--color-team-home)',
          }}
        >
          Northbridge Lions
        </button>
        <button
          onClick={() => onSelectClub('Harbourside City')}
          style={{
            background: favoriteClub === 'Harbourside City' ? 'var(--color-team-away)' : 'rgba(108,171,221,0.1)',
            color: favoriteClub === 'Harbourside City' ? '#080b0f' : 'var(--color-team-away)',
            border: '1px solid var(--color-team-away)',
          }}
        >
          Harbourside
        </button>
      </div>
    )}
  </div>
);
