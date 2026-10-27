/**
 * InGame Studio - 22-Player Performance Table
 * InGame design-system compliant — all inline styles replaced with token classes.
 * Team colours use CSS custom properties (--color-team-home / --color-team-away) per skill §2.2.
 */

import React, { useState, useMemo } from 'react';
import { PlayerAnalytics } from '../types';

interface PlayerPerformanceTableProps {
  players: PlayerAnalytics[];
  selectedPlayerId?: string | null;
  onSelectPlayer?: (playerId: string) => void;
}

type SortField =
  | 'rating'
  | 'distance_km'
  | 'top_speed_kmh'
  | 'passes'
  | 'pdr'
  | 'xt_created'
  | 'defensive_interventions'
  | 'goals';


const SORT_HEADERS: { field: SortField; label: string }[] = [
  { field: 'rating',                   label: 'Rating'    },
  { field: 'distance_km',              label: 'Distance'  },
  { field: 'top_speed_kmh',            label: 'Top Speed' },
  { field: 'passes',                   label: 'Passes'    },
  { field: 'pdr',                      label: 'PDR'       },
  { field: 'xt_created',               label: 'xT'        },
  { field: 'defensive_interventions',  label: 'Def Interv'},
  { field: 'goals',                    label: 'G / A'     },
];

const getRatingColor = (r: number): string => {
  if (r >= 8.0) return 'var(--color-accent-green)';
  if (r >= 7.0) return 'var(--color-accent-cyan)';
  if (r >= 6.0) return 'var(--color-text-primary)';
  return 'var(--color-accent-red)';
};

export const PlayerPerformanceTable: React.FC<PlayerPerformanceTableProps> = React.memo(({
  players,
  selectedPlayerId,
  onSelectPlayer,
}) => {
  const [teamFilter, setTeamFilter] = useState<'all' | 'Northbridge Lions' | 'Harbourside City'>('all');
  const [roleFilter, setRoleFilter] = useState<'all' | 'GK' | 'DF' | 'MF' | 'FW'>('all');
  const [sortField,  setSortField]  = useState<SortField>('rating');
  const [sortAsc,    setSortAsc]    = useState(false);

  const candidateList = players || [];

  const filteredPlayers = useMemo(() =>
    candidateList.filter((p) => {
      const isArs = p.team.toLowerCase().includes('northbridge') || p.team === 'home' || p.player_id.startsWith('NBL');
      if (teamFilter === 'Northbridge Lions'          && !isArs) return false;
      if (teamFilter === 'Harbourside City'  &&  isArs) return false;
      if (roleFilter !== 'all' && p.role !== roleFilter) return false;
      return true;
    }),
  [candidateList, teamFilter, roleFilter]);

  const sortedPlayers = useMemo(() =>
    [...filteredPlayers].sort((a, b) => {
      let va = 0, vb = 0;
      switch (sortField) {
        case 'rating':                  va = a.rating;                       vb = b.rating;                       break;
        case 'distance_km':             va = a.distance_km;                  vb = b.distance_km;                  break;
        case 'top_speed_kmh':           va = a.top_speed_kmh;                vb = b.top_speed_kmh;                break;
        case 'passes':                  va = a.passes?.completed || 0;       vb = b.passes?.completed || 0;       break;
        case 'pdr':                     va = a.passes?.avg_pdr   || 0;       vb = b.passes?.avg_pdr   || 0;       break;
        case 'xt_created':              va = a.xt_created;                   vb = b.xt_created;                   break;
        case 'defensive_interventions': va = a.defensive_interventions;      vb = b.defensive_interventions;      break;
        case 'goals':                   va = a.goals;                        vb = b.goals;                        break;
      }
      return sortAsc ? va - vb : vb - va;
    }),
  [filteredPlayers, sortField, sortAsc]);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortAsc((a) => !a);
    else { setSortField(field); setSortAsc(false); }
  };

  return (
    <div className="studio-card ppt-card" aria-label="Player performance table">
      {/* Header + filters */}
      <div className="ppt-header">
        <div>
          <div className="ppt-title">Player Performance Table</div>
          <div className="ppt-subtitle">Live synthetic player statistics · Click row to highlight on pitch</div>
        </div>
        <div className="ppt-filters">
          {/* Team filter */}
          <div className="ppt-filter-group" role="group" aria-label="Filter by team">
            {(['all', 'Northbridge Lions', 'Harbourside City'] as const).map((t) => {
              const activeClass =
                teamFilter === t
                  ? t === 'Northbridge Lions'         ? 'active-home'
                  : t === 'Harbourside City' ? 'active-away'
                  : 'active'
                  : '';
              return (
                <button
                  key={t}
                  className={`ppt-filter-btn${activeClass ? ` ${activeClass}` : ''}`}
                  onClick={() => setTeamFilter(t)}
                  aria-pressed={teamFilter === t}
                >
                  {t === 'all' ? 'All' : t}
                </button>
              );
            })}
          </div>

          {/* Position filter */}
          <div className="ppt-filter-group" role="group" aria-label="Filter by position">
            {(['all', 'GK', 'DF', 'MF', 'FW'] as const).map((r) => (
              <button
                key={r}
                className={`ppt-filter-btn${roleFilter === r ? ' active' : ''}`}
                onClick={() => setRoleFilter(r)}
                aria-pressed={roleFilter === r}
              >
                {r === 'all' ? 'All Pos' : r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="ppt-table-wrap">
        <table className="ppt-table" aria-label={`Player stats — ${sortedPlayers.length} players`}>
          <thead>
            <tr>
              <th className="ppt-th" scope="col">Player</th>
              <th className="ppt-th" scope="col">Team</th>
              <th className="ppt-th" scope="col">Pos</th>
              {SORT_HEADERS.map(({ field, label }) => (
                <th
                  key={field}
                  className={`ppt-th sortable${sortField === field ? ' active-sort' : ''}`}
                  scope="col"
                  onClick={() => handleSort(field)}
                  aria-sort={sortField === field ? (sortAsc ? 'ascending' : 'descending') : 'none'}
                >
                  {label} {sortField === field ? (sortAsc ? '▲' : '▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedPlayers.map((p) => {
              const isArs     = p.team.toLowerCase().includes('northbridge') || p.team === 'home' || p.player_id.startsWith('NBL');
              const teamColor = isArs ? 'var(--color-team-home)' : 'var(--color-team-away)';
              const isSelected = selectedPlayerId === p.player_id;

              return (
                <tr
                  key={p.player_id}
                  className={`ppt-tr${isSelected ? ' selected' : ''}`}
                  onClick={() => onSelectPlayer && onSelectPlayer(p.player_id)}
                  aria-selected={isSelected}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelectPlayer && onSelectPlayer(p.player_id)}
                >
                  {/* Player name cell */}
                  <td className="ppt-td" style={{ maxWidth: 140 }}>
                    <div className="ppt-player-cell">
                      <span className="ppt-team-dot" style={{ background: teamColor }} aria-hidden="true" />
                      <strong style={{ color: isSelected ? 'var(--color-accent-green)' : 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {p.name}
                      </strong>
                      <span className="mono-stat" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-micro)' }}>#{p.jersey_number}</span>
                      {p.is_motm && <span className="ppt-motm-badge">MOTM</span>}
                    </div>
                  </td>
                  <td className="ppt-td" style={{ color: teamColor, fontWeight: 700 }}>
                    {isArs ? 'NBL' : 'HSC'}
                  </td>
                  <td className="ppt-td" style={{ color: 'var(--color-text-secondary)' }}>{p.role}</td>
                  <td className="ppt-td ppt-td-mono" style={{ color: getRatingColor(p.rating), fontWeight: 800, textAlign: 'right' }}>
                    {p.rating.toFixed(1)}
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-text-primary)', textAlign: 'right' }}>
                    {p.distance_km.toFixed(2)}<span style={{ color: 'var(--color-text-tertiary)' }}>km</span>
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-text-primary)', textAlign: 'right' }}>
                    {p.top_speed_kmh.toFixed(1)}<span style={{ color: 'var(--color-text-tertiary)' }}>km/h</span>
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ textAlign: 'right' }}>
                    <span style={{ color: 'var(--color-text-primary)' }}>{p.passes?.completed ?? 0}</span>
                    <span style={{ color: 'var(--color-text-tertiary)' }}>/{p.passes?.total ?? 0}</span>
                    {' '}
                    <span style={{ color: 'var(--color-accent-green)', fontSize: 'var(--text-micro)' }}>
                      ({p.passes?.accuracy_pct?.toFixed(0) ?? 0}%)
                    </span>
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-accent-cyan)', textAlign: 'right' }}>
                    {p.passes?.avg_pdr?.toFixed(1) ?? '0.0'}
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-accent-yellow)', textAlign: 'right' }}>
                    +{p.xt_created.toFixed(2)}
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-text-primary)', textAlign: 'right' }}>
                    {p.defensive_interventions}
                  </td>
                  <td className="ppt-td ppt-td-mono" style={{ color: 'var(--color-text-primary)', fontWeight: 700, textAlign: 'right' }}>
                    {p.goals} / {p.assists}
                  </td>
                </tr>
              );
            })}
            {sortedPlayers.length === 0 && (
              <tr><td className="ppt-td" colSpan={11}>No player statistics available yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});
