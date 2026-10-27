/**
 * InGame Studio — Production Design Tokens & Canvas Constants
 * Conforming strictly to the Broadcast Design System (`ingame-ui-design`).
 * Mirrors CSS custom properties defined in `frontend/src/index.css`.
 */

export const CANONICAL_COLORS = {
  // Brand Core
  plPurple: '#38003c',
  plPurpleMid: '#560044',
  plPurpleDark: '#1c0020',

  // Accent – ONE per visual zone
  accentGreen: '#00ff87',
  accentCyan: '#04f0ff',
  accentYellow: '#ffe600',
  accentRed: '#e90052',

  // Surfaces (Dark-mode only)
  bgBase: '#080b0f',
  bgElevated: '#0d1117',
  bgOverlay: '#141c26',
  bgInput: '#1a2233',

  // Borders
  borderSubtle: '#1e2a3a',
  borderEmphasis: '#2d3f55',
  borderActive: '#00ff87',

  // Text (WCAG AA Compliant)
  textPrimary: '#f0f4f8',
  textSecondary: '#8b9bb4',
  textTertiary: '#94a3b8', // >=4.5:1 on bgElevated (#0d1117)
  textInverse: '#080b0f',

  // Teams (Canonical kit differentiation)
  teamHome: '#EF0107', // Northbridge Lions Red
  teamAway: '#6CABDD', // Harbourside City Sky Blue
  northbridgeRed: '#EF0107',
  northbridgeWhite: '#FFFFFF',
  harboursideBlue: '#6CABDD',
  harboursideNavy: '#1C2C5B',
  gkHome: '#CCFF00', // Daniel Roark GK Kit
  gkAway: '#FF5500', // Enzo Barreto GK Kit

  // Data Visualisation
  xTHigh: '#ef4444',
  xTLow: '#22c55e',
  neutral: '#6b7280',
} as const;

export const PITCH_TOKENS = {
  // Grass & Turf Bands
  grassLight: '#1d542b',
  grassDark: '#184724',
  grassCanonical: '#1a5c1a',
  lineColor: 'rgba(255, 255, 255, 0.6)',
  bezelColor: 'rgba(255, 255, 255, 0.12)',

  // IFAB Standard Dimensions (meters)
  length: 105.0,
  width: 68.0,
  halfLength: 52.5,
  halfWidth: 34.0,
  penaltyBoxDepth: 16.5,
  penaltyBoxWidth: 40.32,
  goalAreaDepth: 5.5,
  goalAreaWidth: 18.32,
  centerCircleRadius: 9.15,
  penaltySpotDistance: 11.0,
  cornerArcRadius: 1.0,
  goalWidth: 7.32,
  goalDepth: 2.44,

  // Canvas Geometry & Radii (pixels)
  playerRadius: 9.5,
  selectedPlayerRadius: 14.0,
  ballRadius: 4.5,
  ballGlowThresholdSpeed: 35.0, // km/h
} as const;

export const PERSONA_COLORS = {
  tactical: '#04f0ff',
  casual: '#ffe600',
  loyalist: '#a855f7',
  club: '#a855f7', // Alias for backward compatibility
  fantasy: '#00ff87',
} as const;

export type CanonicalColors = typeof CANONICAL_COLORS;
export type CanonicalColorKey = keyof CanonicalColors;

export type PitchTokens = typeof PITCH_TOKENS;
export type PitchTokenKey = keyof PitchTokens;

export type PersonaColors = typeof PERSONA_COLORS;
export type PersonaColorKey = keyof PersonaColors;
