/**
 * InGame Studio - Tactical Insights Tab (Milestone 4 / Tab 3)
 * Spatial Freeze-Frames, 5-Layer Interactive Telestration & AI Tactical Breakdown.
 *
 * Requirements (as per hand-drawn wireframe):
 * 1. Left Column: Main & Important Events List (4 critical match turning points)
 * 2. Center/Right Top: Opens match pitch screen with exact moment & all 22 player data points
 * 3. Bottom Left: Toggles for tactics on the Pitch (Heatmap, Passing lanes, Low block, Defensive line, Pressing zones)
 * 4. Bottom Right: AI explaining as per persona (Causal reasoning, quantitative KPIs & structural breakdown)
 */

import React, { useState, useEffect, useMemo } from 'react';
import { TacticalMoment, TacticalLayerState, ViewerPersona, LanguageCode, MomentBreakdown } from '../types';
import { TacticalPitchCanvas } from './TacticalPitchCanvas';
import { ClipPlayer } from './ClipPlayer';
import { CANONICAL_COLORS } from '../constants/tokens';

// Shown until the backend has derived key moments from the match events.
const EMPTY_BREAKDOWN: MomentBreakdown = {
  structural_weaknesses: 'Key moments appear here as the match is played or simulated.',
  player_decisions: '—',
  team_shape: '—',
  key_takeaway: 'No moment selected yet.',
  grounding_score: 0,
  pdr: 0,
  depth_m: 0,
  compactness_m2: 0,
  press_pct: 0,
  persona_notes: { tactical: '—', casual: '—', club: '—', fantasy: '—' },
};

export interface TacticalInsightsTabProps {
  className?: string;
  activePersona?: ViewerPersona;
  isVisible?: boolean;
  language?: LanguageCode;
  eventCount?: number;
}

export const TacticalInsightsTab: React.FC<TacticalInsightsTabProps> = ({
  className = '',
  activePersona = 'tactical',
  isVisible = true,
  language = 'en',
  eventCount = 0,
}) => {
  const [moments, setMoments] = useState<TacticalMoment[]>([]);
  const [isLoadingMoments, setIsLoadingMoments] = useState<boolean>(false);
  const [selectedMomentId, setSelectedMomentId] = useState<string>('');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);

  // 5 Interactive Tactical Layer Switches State
  const [layerState, setLayerState] = useState<TacticalLayerState>({
    heatmap: true,
    passing_lanes: true,
    low_block: true,
    defensive_line: true,
    pressing_zones: true,
  });

  // Key moments are derived by the backend from the events played so far.
  useEffect(() => {
    if (!isVisible) return;
    let isMounted = true;
    setIsLoadingMoments(true);
    fetch(`/api/tactical?language=${language}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data || !Array.isArray(data.moments)) return;
        setMoments(data.moments);
        setSelectedMomentId((prev) =>
          data.moments.some((m: TacticalMoment) => m.id === prev) ? prev : data.moments[0]?.id ?? ''
        );
      })
      .catch(() => undefined)
      .finally(() => {
        if (isMounted) setIsLoadingMoments(false);
      });
    return () => {
      isMounted = false;
    };
  }, [isVisible, language, eventCount > 0]);

  const currentMoment = useMemo(() => {
    return moments.find((m) => m.id === selectedMomentId) || moments[0] || null;
  }, [moments, selectedMomentId]);

  const currentAi: MomentBreakdown = currentMoment?.breakdown ?? EMPTY_BREAKDOWN;

  const toggleLayer = (layerKey: keyof TacticalLayerState) => {
    setLayerState((prev) => ({
      ...prev,
      [layerKey]: !prev[layerKey],
    }));
  };

  const toggleAllLayers = (enable: boolean) => {
    setLayerState({
      heatmap: enable,
      passing_lanes: enable,
      low_block: enable,
      defensive_line: enable,
      pressing_zones: enable,
    });
  };

  return (
    <div className={`tactical-tab-container ${className}`}>
      {/* ── Component-Scoped CSS ────────────────────────────────────────── */}
      <style>{`
        .tactical-tab-container {
          display: flex;
          flex-direction: column;
          gap: 16px;
          width: 100%;
          padding: 16px;
          box-sizing: border-box;
          background-color: var(--color-bg-base, #080b0f);
          color: var(--color-text-primary, #f0f4f8);
          font-family: var(--font-display, sans-serif);
        }

        /* Top Header Bar */
        .tactical-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          padding-bottom: 14px;
          border-bottom: 1px solid var(--color-border-subtle, #1e2a3a);
        }
        .tactical-title-box {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .tactical-title-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .tactical-title {
          font-size: 20px;
          font-weight: 800;
          letter-spacing: -0.02em;
          color: var(--color-text-primary, #f0f4f8);
          margin: 0;
        }
        .tactical-badge {
          padding: 3px 8px;
          border-radius: 4px;
          font-family: var(--font-mono, monospace);
          font-size: 10px;
          font-weight: 700;
          background: rgba(0, 255, 135, 0.15);
          color: var(--color-accent-green, #00ff87);
          border: 1px solid rgba(0, 255, 135, 0.35);
        }
        .tactical-subtitle {
          font-size: 12px;
          color: var(--color-text-secondary, #8b9bb4);
          margin: 0;
        }
        .tactical-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .tactical-quick-btn {
          background: var(--color-bg-elevated, #0d1117);
          color: var(--color-text-secondary, #8b9bb4);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 6px;
          padding: 6px 14px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: border-color 0.15s, color 0.15s, background-color 0.15s;
        }
        .tactical-quick-btn:hover {
          border-color: var(--color-accent-green, #00ff87);
          color: var(--color-accent-green, #00ff87);
          background: rgba(0, 255, 135, 0.08);
        }
        .tactical-quick-btn.danger:hover {
          border-color: var(--color-accent-red, #e90052);
          color: var(--color-accent-red, #e90052);
          background: rgba(233, 0, 82, 0.08);
        }

        /* ── Master Workspace 2-Column Layout (Wireframe Alignment) ── */
        .tactical-workspace {
          display: grid;
          grid-template-columns: 310px 1fr;
          gap: 16px;
          align-items: start;
          width: 100%;
        }
        @media (max-width: 1080px) {
          .tactical-workspace {
            grid-template-columns: 1fr;
          }
        }

        /* ── Left Column: Main & Important Events List ── */
        .tactical-events-rail {
          display: flex;
          flex-direction: column;
          gap: 10px;
          background: var(--color-bg-elevated, #0d1117);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 10px;
          padding: 14px;
        }
        .tactical-rail-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--color-border-subtle, #1e2a3a);
          margin-bottom: 4px;
        }
        .tactical-rail-title {
          font-size: 11px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--color-accent-cyan, #04f0ff);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .tactical-pulse-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: var(--color-accent-green, #00ff87);
          box-shadow: 0 0 6px var(--color-accent-green, #00ff87);
        }
        .tactical-event-cards {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .tactical-event-card {
          background: var(--color-bg-base, #080b0f);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 8px;
          padding: 12px;
          text-align: left;
          cursor: pointer;
          transition: all 0.15s ease-out;
          display: flex;
          flex-direction: column;
          gap: 6px;
          position: relative;
        }
        .tactical-event-card:hover {
          border-color: var(--color-border-emphasis, #2d3f55);
          background: rgba(20, 28, 38, 0.6);
        }
        .tactical-event-card.selected {
          background: var(--color-bg-overlay, #141c26);
          border-color: var(--color-accent-cyan, #04f0ff);
          box-shadow: 0 0 14px rgba(4, 240, 255, 0.22);
        }
        .tactical-event-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
        }
        .tactical-time-badge {
          font-family: var(--font-mono, monospace);
          font-size: 11px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 4px;
          background: rgba(4, 240, 255, 0.15);
          color: var(--color-accent-cyan, #04f0ff);
          border: 1px solid rgba(4, 240, 255, 0.3);
        }
        .tactical-event-card.selected .tactical-time-badge {
          background: var(--color-accent-cyan, #04f0ff);
          color: #080b0f;
        }
        .tactical-grounded-tag {
          font-family: var(--font-mono, monospace);
          font-size: 10px;
          color: var(--color-text-secondary, #8b9bb4);
        }
        .tactical-event-name {
          font-size: 13px;
          font-weight: 700;
          color: var(--color-text-primary, #f0f4f8);
          line-height: 1.3;
          margin: 0;
        }
        .tactical-event-desc {
          font-size: 11px;
          color: var(--color-text-secondary, #8b9bb4);
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          margin: 0;
        }
        .tactical-event-stats {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 8px;
          margin-top: 2px;
          border-top: 1px solid var(--color-border-subtle, #1e2a3a);
          font-family: var(--font-mono, monospace);
          font-size: 10px;
          color: var(--color-text-secondary, #8b9bb4);
        }
        .tactical-event-stats strong {
          color: var(--color-text-primary, #f0f4f8);
        }
        .tactical-active-indicator {
          position: absolute;
          top: -3px;
          right: -3px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--color-accent-cyan, #04f0ff);
          box-shadow: 0 0 8px var(--color-accent-cyan, #04f0ff);
        }

        /* ── Right Main Workspace ── */
        .tactical-main-stage {
          display: flex;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }

        /* Replay clip (10 s before and after the moment) */
        .tactical-replay-box {
          background: var(--color-bg-elevated, #0d1117);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 12px;
          padding: 12px;
          box-shadow: 0 16px 36px rgba(0, 0, 0, 0.45);
        }
        .tactical-replay-head {
          display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;
          margin-bottom: 10px; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em;
          color: var(--color-accent-cyan, #04f0ff);
        }
        .tactical-replay-head span:last-child { color: var(--color-text-secondary, #8b9bb4); font-weight: 600; text-transform: none; letter-spacing: 0; }

        /* Pitch Canvas Container */
        .tactical-pitch-box {
          background: var(--color-bg-base, #080b0f);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
          position: relative;
          width: 100%;
          height: 480px;
        }

        /* Bottom Controls & AI Breakdown Grid */
        .tactical-bottom-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
          align-items: start;
        }
        @media (max-width: 1200px) {
          .tactical-bottom-grid {
            grid-template-columns: 1fr;
          }
        }

        /* ── Sub-card 1: Tactical Layer Overlays (Telestrator Controls) ── */
        .tactical-controls-card {
          background: var(--color-bg-elevated, #0d1117);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 10px;
          padding: 14px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .tactical-controls-title {
          font-size: 11px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--color-text-secondary, #8b9bb4);
          margin-bottom: 2px;
        }
        .tactical-toggle-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .tactical-pill-btn {
          background: var(--color-bg-overlay, #141c26);
          color: var(--color-text-secondary, #8b9bb4);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 20px;
          padding: 6px 14px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: all 0.15s ease-out;
        }
        .tactical-pill-btn:hover {
          border-color: var(--color-border-emphasis, #2d3f55);
          color: var(--color-text-primary, #f0f4f8);
        }
        .tactical-pill-btn.active-heatmap {
          background: rgba(233, 0, 82, 0.15);
          color: var(--color-accent-red, #e90052);
          border-color: var(--color-accent-red, #e90052);
          box-shadow: 0 0 10px rgba(233, 0, 82, 0.25);
        }
        .tactical-pill-btn.active-passing {
          background: rgba(0, 255, 135, 0.15);
          color: var(--color-accent-green, #00ff87);
          border-color: var(--color-accent-green, #00ff87);
          box-shadow: 0 0 10px rgba(0, 255, 135, 0.25);
        }
        .tactical-pill-btn.active-lowblock {
          background: rgba(4, 240, 255, 0.15);
          color: var(--color-accent-cyan, #04f0ff);
          border-color: var(--color-accent-cyan, #04f0ff);
          box-shadow: 0 0 10px rgba(4, 240, 255, 0.25);
        }
        .tactical-pill-btn.active-defline {
          background: rgba(255, 230, 0, 0.15);
          color: var(--color-accent-yellow, #ffe600);
          border-color: var(--color-accent-yellow, #ffe600);
          box-shadow: 0 0 10px rgba(255, 230, 0, 0.25);
        }
        .tactical-pill-btn.active-press {
          background: rgba(168, 85, 247, 0.15);
          color: #a855f7;
          border-color: #a855f7;
          box-shadow: 0 0 10px rgba(168, 85, 247, 0.25);
        }
        .tactical-status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--color-text-tertiary, #4a5568);
        }
        .active-heatmap .tactical-status-dot { background: var(--color-accent-red, #e90052); }
        .active-passing .tactical-status-dot { background: var(--color-accent-green, #00ff87); }
        .active-lowblock .tactical-status-dot { background: var(--color-accent-cyan, #04f0ff); }
        .active-defline .tactical-status-dot { background: var(--color-accent-yellow, #ffe600); }
        .active-press .tactical-status-dot { background: #a855f7; }

        /* Pitch Legend */
        .tactical-legend-box {
          border-top: 1px solid var(--color-border-subtle, #1e2a3a);
          padding-top: 10px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .tactical-legend-items {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 12px;
          font-size: 11px;
          color: var(--color-text-secondary, #8b9bb4);
        }
        .tactical-legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .tactical-legend-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .tactical-legend-line {
          width: 14px;
          height: 2px;
        }

        /* ── Sub-card 2: AI Tactical Breakdown ── */
        .tactical-ai-card {
          background: var(--color-bg-elevated, #0d1117);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 10px;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          box-shadow: 0 12px 28px rgba(0, 0, 0, 0.4);
        }
        .tactical-ai-header {
          border-bottom: 1px solid var(--color-border-subtle, #1e2a3a);
          padding-bottom: 10px;
        }
        .tactical-ai-stamp-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 4px;
        }
        .tactical-ai-stamp {
          font-size: 10px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--color-accent-cyan, #04f0ff);
        }
        .tactical-ai-verified {
          padding: 2px 6px;
          border-radius: 4px;
          font-family: var(--font-mono, monospace);
          font-size: 10px;
          font-weight: 700;
          background: rgba(0, 255, 135, 0.15);
          color: var(--color-accent-green, #00ff87);
          border: 1px solid rgba(0, 255, 135, 0.35);
        }
        .tactical-ai-title {
          font-size: 16px;
          font-weight: 800;
          color: var(--color-text-primary, #f0f4f8);
          margin: 0;
        }
        .tactical-ai-moment-sub {
          font-size: 11px;
          color: var(--color-text-secondary, #8b9bb4);
          margin-top: 2px;
        }

        /* 4 Quantitative KPI Tiles */
        .tactical-kpi-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
        }
        .tactical-kpi-box {
          background: var(--color-bg-overlay, #141c26);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 6px;
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .tactical-kpi-label {
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-secondary, #8b9bb4);
        }
        .tactical-kpi-val {
          font-family: var(--font-mono, monospace);
          font-size: 16px;
          font-weight: 800;
          color: var(--color-text-primary, #f0f4f8);
        }
        .tactical-kpi-bar {
          width: 100%;
          height: 3px;
          border-radius: 2px;
          background: var(--color-border-subtle, #1e2a3a);
          overflow: hidden;
          margin-top: 4px;
        }
        .tactical-kpi-bar-fill {
          height: 100%;
          border-radius: 2px;
        }

        /* Narrative blocks */
        .tactical-narrative-block {
          background: var(--color-bg-overlay, #141c26);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 6px;
          padding: 10px;
        }
        .tactical-narrative-title {
          font-size: 11px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 4px;
        }
        .tactical-narrative-text {
          font-size: 11px;
          color: var(--color-text-secondary, #8b9bb4);
          line-height: 1.5;
          margin: 0;
        }

        /* Key Takeaway Box */
        .tactical-takeaway-box {
          background: linear-gradient(135deg, var(--color-pl-purple-dark, #1c0020) 0%, var(--color-bg-overlay, #141c26) 100%);
          border: 1px solid rgba(0, 255, 135, 0.25);
          border-radius: 6px;
          padding: 10px;
        }
        .tactical-takeaway-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.04em;
          color: var(--color-accent-green, #00ff87);
          margin-bottom: 4px;
        }
        .tactical-takeaway-text {
          font-size: 11px;
          font-style: italic;
          color: var(--color-text-primary, #f0f4f8);
          line-height: 1.4;
          margin: 0;
        }

        /* Persona Switcher row */
        .tactical-persona-row {
          border-top: 1px solid var(--color-border-subtle, #1e2a3a);
          padding-top: 10px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .tactical-persona-tabs {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .tactical-persona-btns {
          display: flex;
          gap: 4px;
        }
        .tactical-persona-btn {
          background: var(--color-bg-overlay, #141c26);
          color: var(--color-text-secondary, #8b9bb4);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 4px;
          padding: 3px 8px;
          font-size: 10px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.15s;
        }
        .tactical-persona-btn.active {
          background: var(--color-pl-purple, #38003c);
          color: var(--color-accent-green, #00ff87);
          border-color: var(--color-accent-green, #00ff87);
        }
        .tactical-persona-quote {
          background: var(--color-bg-overlay, #141c26);
          border: 1px solid var(--color-border-subtle, #1e2a3a);
          border-radius: 6px;
          padding: 8px 10px;
          font-size: 11px;
          line-height: 1.4;
          color: var(--color-text-primary, #f0f4f8);
        }
      `}</style>

      {/* ──────────────────────────────────────────────────────────
          1. TAB TOP HEADER BAR
      ────────────────────────────────────────────────────────── */}
      <header className="tactical-header">
        <div className="tactical-title-box">
          <div className="tactical-title-row">
            <span style={{ fontSize: '18px' }}>📐</span>
            <h1 className="tactical-title">TACTICAL INSIGHTS STUDIO</h1>
            <span className="tactical-badge">FREEZE-FRAME TELSTRATOR</span>
          </div>
          <p className="tactical-subtitle">
            Spatial Freeze-Frames, 5-Layer Telestration & Multi-Agent Tactical Breakdown
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div className="tactical-actions">
          <button
            onClick={() => toggleAllLayers(true)}
            className="tactical-quick-btn"
            title="Enable all 5 tactical overlay layers"
          >
            All Layers On
          </button>
          <button
            onClick={() => toggleAllLayers(false)}
            className="tactical-quick-btn danger"
            title="Disable all tactical overlays"
          >
            Clear Overlays
          </button>
        </div>
      </header>

      {/* ──────────────────────────────────────────────────────────
          2. MASTER WORKSPACE (2-COLUMN WIREFRAME LAYOUT)
      ────────────────────────────────────────────────────────── */}
      <div className="tactical-workspace">
        {/* ── Left Column: Main & Important Events List ── */}
        <aside className="tactical-events-rail" aria-label="Main & Important Events List">
          <div className="tactical-rail-header">
            <div className="tactical-rail-title">
              <span className="tactical-pulse-dot" />
              <span>Key Moments</span>
            </div>
            <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>
              {moments.length} Moments
            </span>
          </div>

          <div className="tactical-event-cards" role="listbox">
            {moments.length === 0 && (
              <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', padding: '12px' }}>
                {isLoadingMoments
                  ? 'Analysing the match moments…'
                  : 'Turning points appear here once the match has produced events. Press play or Simulate to End.'}
              </p>
            )}
            {moments.map((mom) => {
              const isSelected = mom.id === selectedMomentId;
              const meta = mom.breakdown;

              return (
                <button
                  key={mom.id}
                  onClick={() => {
                    setSelectedMomentId(mom.id);
                    setSelectedPlayerId(null);
                  }}
                  className={`tactical-event-card ${isSelected ? 'selected' : ''}`}
                  role="option"
                  aria-selected={isSelected}
                >
                  <div className="tactical-event-meta">
                    <span className="tactical-time-badge">
                      ⏱ {mom.clock || mom.timestamp}
                    </span>
                    <span className="tactical-grounded-tag">
                      {meta?.grounding_score}% Grounded
                    </span>
                  </div>

                  <h3 className="tactical-event-name">{mom.name}</h3>
                  <p className="tactical-event-desc">{mom.description}</p>

                  <div className="tactical-event-stats">
                    <span>PDR: <strong>{meta?.pdr}%</strong></span>
                    <span>Line: <strong>{meta?.depth_m}m</strong></span>
                    <span>Area: <strong style={{ color: 'var(--color-accent-green)' }}>{meta?.compactness_m2}m²</strong></span>
                  </div>

                  {isSelected && <span className="tactical-active-indicator" />}
                </button>
              );
            })}
          </div>
        </aside>

        {/* ── Right Main Workspace (Pitch + Bottom Controls & AI) ── */}
        <main className="tactical-main-stage">
          {/* Replay: the moment as a short clip, 10 s before and after */}
          <div className="tactical-replay-box">
            <div className="tactical-replay-head">
              <span>▶ Moment replay · 10 s before and after</span>
              <span>
                {currentMoment?.turning_point ? `${currentMoment.turning_point} · ` : ''}
                {currentMoment?.clock}
                {currentMoment?.score_after ? ` · score ${currentMoment.score_after}` : ''}
              </span>
            </div>
            <ClipPlayer
              key={currentMoment?.event_id || 'none'}
              eventId={currentMoment?.event_id ?? null}
              autoPlay
              title={currentMoment?.name}
              caption={currentMoment?.description}
            />
          </div>

          {/* Freeze-frame: 2D Interactive Pitch Canvas with tactical overlays */}
          <div className="tactical-pitch-box">
            <TacticalPitchCanvas
              moment={currentMoment}
              layerState={layerState}
              selectedPlayerId={selectedPlayerId}
              onSelectPlayer={(id) => setSelectedPlayerId(id)}
              isVisible={isVisible}
            />
          </div>

          {/* Bottom Grid: Overlays Controls (Left) + AI Tactical Breakdown (Right) */}
          <div className="tactical-bottom-grid">
            {/* Sub-card 1: Tactical Layer Overlays (Telestrator Controls) */}
            <div className="tactical-controls-card">
              <div className="tactical-controls-title">
                Tactical Overlays (Telestrator Layers):
              </div>

              <div className="tactical-toggle-pills" role="toolbar" aria-label="Tactical Overlays">
                {/* 1. Heatmap */}
                <button
                  onClick={() => toggleLayer('heatmap')}
                  className={`tactical-pill-btn ${layerState.heatmap ? 'active-heatmap' : ''}`}
                  aria-pressed={layerState.heatmap}
                >
                  <span>🌡️</span>
                  <span>Heatmap</span>
                  <span className="tactical-status-dot" />
                </button>

                {/* 2. Passing Lanes */}
                <button
                  onClick={() => toggleLayer('passing_lanes')}
                  className={`tactical-pill-btn ${layerState.passing_lanes ? 'active-passing' : ''}`}
                  aria-pressed={layerState.passing_lanes}
                >
                  <span>↗️</span>
                  <span>Passing Lanes</span>
                  <span className="tactical-status-dot" />
                </button>

                {/* 3. Low Block Shape */}
                <button
                  onClick={() => toggleLayer('low_block')}
                  className={`tactical-pill-btn ${layerState.low_block ? 'active-lowblock' : ''}`}
                  aria-pressed={layerState.low_block}
                >
                  <span>🛡️</span>
                  <span>Low Block Shape</span>
                  <span className="tactical-status-dot" />
                </button>

                {/* 4. Defensive Depth & Offside */}
                <button
                  onClick={() => toggleLayer('defensive_line')}
                  className={`tactical-pill-btn ${layerState.defensive_line ? 'active-defline' : ''}`}
                  aria-pressed={layerState.defensive_line}
                >
                  <span>📏</span>
                  <span>Defensive Line & Offside</span>
                  <span className="tactical-status-dot" />
                </button>

                {/* 5. Pressing Zones */}
                <button
                  onClick={() => toggleLayer('pressing_zones')}
                  className={`tactical-pill-btn ${layerState.pressing_zones ? 'active-press' : ''}`}
                  aria-pressed={layerState.pressing_zones}
                >
                  <span>⚡</span>
                  <span>Pressing Zones</span>
                  <span className="tactical-status-dot" />
                </button>
              </div>

              {/* Pitch Legend */}
              <div className="tactical-legend-box">
                <div className="tactical-legend-items">
                  <span className="tactical-legend-item">
                    <span className="tactical-legend-dot" style={{ background: '#EF0107' }} />
                    <span>Northbridge Lions</span>
                  </span>
                  <span className="tactical-legend-item">
                    <span className="tactical-legend-dot" style={{ background: '#6CABDD' }} />
                    <span>Harbourside</span>
                  </span>
                  <span className="tactical-legend-item">
                    <span className="tactical-legend-line" style={{ background: 'var(--color-accent-green)' }} />
                    <span>Viable Lane</span>
                  </span>
                  <span className="tactical-legend-item">
                    <span className="tactical-legend-line" style={{ background: 'var(--color-accent-red)' }} />
                    <span>High Risk</span>
                  </span>
                  <span className="tactical-legend-item">
                    <span className="tactical-legend-line" style={{ borderTop: '2px dashed var(--color-accent-yellow)' }} />
                    <span>Offside Line</span>
                  </span>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
                  Click any player node on the pitch to inspect tracking vectors & speed.
                </div>
              </div>
            </div>

            {/* Sub-card 2: AI Tactical Breakdown */}
            <div className="tactical-ai-card">
              <div className="tactical-ai-header">
                <div className="tactical-ai-stamp-row">
                  <span className="tactical-ai-stamp">MULTI-AGENT CAUSAL REASONING</span>
                  <span className="tactical-ai-verified">✓ VERIFIED REF & TACTICIAN</span>
                </div>
                <h2 className="tactical-ai-title">AI Tactical Breakdown</h2>
                <div className="tactical-ai-moment-sub">
                  Moment: <strong style={{ color: 'var(--color-text-primary)' }}>{currentMoment?.name}</strong> at{' '}
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-green)' }}>
                    {currentMoment?.clock}
                  </span>
                </div>
              </div>

              {/* 4 Quantitative KPI Tiles */}
              <div className="tactical-kpi-grid">
                <div className="tactical-kpi-box">
                  <span className="tactical-kpi-label">Pass Difficulty (PDR)</span>
                  <span className="tactical-kpi-val">{currentAi.pdr}%</span>
                  <div className="tactical-kpi-bar">
                    <div
                      className="tactical-kpi-bar-fill"
                      style={{
                        width: `${currentAi.pdr}%`,
                        background: 'var(--color-accent-green)',
                      }}
                    />
                  </div>
                </div>

                <div className="tactical-kpi-box">
                  <span className="tactical-kpi-label">Defensive Line Depth</span>
                  <span className="tactical-kpi-val" style={{ color: 'var(--color-accent-yellow)' }}>
                    {currentAi.depth_m}m
                  </span>
                  <div className="tactical-kpi-bar">
                    <div
                      className="tactical-kpi-bar-fill"
                      style={{
                        width: `${Math.min(100, (currentAi.depth_m / 40) * 100)}%`,
                        background: 'var(--color-accent-yellow)',
                      }}
                    />
                  </div>
                </div>

                <div className="tactical-kpi-box">
                  <span className="tactical-kpi-label">Block Compactness</span>
                  <span className="tactical-kpi-val" style={{ color: 'var(--color-accent-cyan)' }}>
                    {currentAi.compactness_m2} m²
                  </span>
                  <div className="tactical-kpi-bar">
                    <div
                      className="tactical-kpi-bar-fill"
                      style={{
                        width: `${Math.min(100, (currentAi.compactness_m2 / 500) * 100)}%`,
                        background: 'var(--color-accent-cyan)',
                      }}
                    />
                  </div>
                </div>

                <div className="tactical-kpi-box">
                  <span className="tactical-kpi-label">Press Trap Intensity</span>
                  <span className="tactical-kpi-val" style={{ color: 'var(--color-accent-red)' }}>
                    {currentAi.press_pct}%
                  </span>
                  <div className="tactical-kpi-bar">
                    <div
                      className="tactical-kpi-bar-fill"
                      style={{
                        width: `${currentAi.press_pct}%`,
                        background: 'var(--color-accent-red)',
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Narrative: Structural Weaknesses */}
              <div className="tactical-narrative-block">
                <div className="tactical-narrative-title" style={{ color: 'var(--color-accent-yellow)' }}>
                  <span>⚠️</span>
                  <span>Structural Weaknesses & Spatial Flaws</span>
                </div>
                <p className="tactical-narrative-text">
                  {currentAi.structural_weaknesses}
                </p>
              </div>

              {/* Narrative: Player Decisions */}
              <div className="tactical-narrative-block">
                <div className="tactical-narrative-title" style={{ color: 'var(--color-accent-cyan)' }}>
                  <span>🎯</span>
                  <span>Player Decisions & Execution</span>
                </div>
                <p className="tactical-narrative-text">
                  {currentAi.player_decisions}
                </p>
              </div>

              {/* Key Takeaway Box */}
              <div className="tactical-takeaway-box">
                <div className="tactical-takeaway-header">
                  <span>TACTICAL KEY TAKEAWAY</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--color-text-secondary)' }}>
                    CONFIDENCE: {currentAi.grounding_score}%
                  </span>
                </div>
                <p className="tactical-takeaway-text">
                  "{currentAi.key_takeaway}"
                </p>
              </div>

              {/* Persona Voice Note: follows the persona chosen in the app header */}
              <div className="tactical-persona-row">
                <div className="tactical-persona-tabs">
                  <span style={{ fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
                    Persona Perspective: {activePersona === 'tactical' ? 'Purist' : activePersona === 'casual' ? 'Casual' : activePersona === 'club' ? 'Loyalist' : 'Fantasy'}
                  </span>
                </div>

                <div className="tactical-persona-quote">
                  {currentAi.persona_notes[activePersona] || currentAi.persona_notes.tactical}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};
