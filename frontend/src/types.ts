/**
 * InGame Studio - Frontend TypeScript Type Definitions
 */

export interface PitchDimensions {
  length: number;
  width: number;
}

export interface BallTracking {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  speed_kmh: number;
  possession_team: string;
  status: string;
}

export interface PlayerTracking {
  player_id: string;
  team: string;
  jersey_number: number;
  name: string;
  role: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  speed_kmh: number;
}

export interface TelemetryFrame {
  frame_id: number;
  match_id: string;
  data_provenance?: 'synthetic_simulation' | string;
  synthetic_data_notice?: string;
  timestamp: string;
  period: number;
  clock: string;
  pitch_dimensions: PitchDimensions;
  ball: BallTracking;
  players: PlayerTracking[];
  active_event_id: string | null;
}

export interface MatchEvent {
  event_id: string;
  match_id: string;
  event_type: string;
  sub_type?: string;
  period: number;
  clock: string;
  frame_index: number;
  team: string;
  player_id?: string;
  player_name?: string;
  secondary_player_name?: string;
  location_x?: number;
  location_y?: number;
  end_x?: number | null;
  end_y?: number | null;
  outcome?: string;
  tactical_metrics?: Record<string, any>;
  context?: string;
}

export interface TelestratorVectors {
  pass_vector?: {
    start_x: number;
    start_y: number;
    end_x: number;
    end_y: number;
    distance_m: number;
  };
  corridor?: {
    width_m: number;
    defenders_count: number;
  };
  intercept_cone?: {
    angle_deg: number;
    defenders_count: number;
  };
  target_ring?: {
    x: number;
    y: number;
    radius_m: number;
  };
  style?: {
    color_hex: string;
    pulse: boolean;
    line_breaking: boolean;
  };
}

export interface VerifiedInsight {
  event_id: string;
  grounding_score: number;
  verification_status: 'VERIFIED' | 'FALLBACK_APPLIED' | string;
  retries_attempted: number;
  casual_story: string;
  tactical_analysis: string;
  club_loyalist_story: string;
  player_lock_story: string;
  lower_third_ticker: string;
  metrics: {
    pass_difficulty?: number;
    ball_speed_kmh?: number;
    chaos_index?: number;
    xt_gained?: number;
    pass_distance_m?: number;
    defenders_in_corridor?: number;
    defenders_in_cone?: number;
    [key: string]: number | undefined;
  };
  telestrator_vectors?: TelestratorVectors;
  translations?: Record<string, Record<string, string>>;
  narrative_source?: 'azure_foundry_live' | 'azure_foundry_cache' | 'local_template' | 'fallback_template' | string | null;
}

export type ViewerPersona = 'casual' | 'tactical' | 'club' | 'fantasy';

export type LanguageCode = 'en' | 'es';

export interface TeamMatchStats {
  total?: number;
  completed?: number;
  accuracy_pct?: number;
  won?: number;
  won_pct?: number;
  on_target?: number;
  blocked?: number;
  off_target?: number;
  yellow?: number;
  red?: number;
}

export interface MatchStatsData {
  possession_pct: { home: number; away: number };
  xg: { home: number; away: number };
  shots: { home: TeamMatchStats; away: TeamMatchStats };
  passes: { home: TeamMatchStats; away: TeamMatchStats };
  tackles: { home: TeamMatchStats; away: TeamMatchStats };
  interceptions: { home: number; away: number };
  fouls: { home: number; away: number };
  cards: { home: TeamMatchStats; away: TeamMatchStats };
  corners: { home: number; away: number };
  chaos_index: number;
  score: { home: number; away: number };
  field_tilt?: { home: number; away: number };
}

export interface PlayerAnalytics {
  /** Six radar axes, each ranked against every player in the match (0-100 percentile). */
  radar?: Array<{ key: string; label: string; value: number; displayValue: string }>;
  sprint_seconds?: number;
  /** Tracked position density, 12 columns (own goal to opposing goal) by 8 rows, in the team's attacking direction. */
  heatmap?: number[][];
  player_id: string;
  name: string;
  team: 'home' | 'away' | string;
  jersey_number: number;
  role: string;
  minutes_played: number;
  distance_km: number;
  top_speed_kmh: number;
  passes: {
    total: number;
    completed: number;
    accuracy_pct: number;
    avg_pdr: number;
  };
  xt_created: number;
  xg: number;
  shots: number;
  shots_on_target: number;
  goals: number;
  assists: number;
  key_passes: number;
  defensive_interventions: number;
  tackles_won: number;
  interceptions: number;
  rating: number;
  is_motm: boolean;
  bps: number;
  fantasy_bonus_points: number;
}

export interface AnalyticsResponse {
  match_stats: MatchStatsData;
  player_stats: PlayerAnalytics[];
}

export type SpotlightMetric = 'all' | 'pdr' | 'speed' | 'xt' | 'cci';

export type ClubPerspective = 'Northbridge Lions' | 'Harbourside City';

export interface TurningPoint {
  minute: string;
  title: string;
  description: string;
  impact: string;
  team: string;
  type?: string;
  player?: string;
  event_id?: string;
  score_after?: string;
}

export interface RecapPhase {
  phase: string;
  avg_cci: number;
  character: string;
  dominant_team: string;
  description: string;
}

export interface MatchRecapData {
  match_id: string;
  status?: 'FT' | 'LIVE' | 'NOT_STARTED' | string;
  clock?: string;
  highlights?: any[];
  tactical_entropy_shifts?: RecapPhase[];
  team_totals?: {
    possession_pct: { home: number; away: number };
    shots: { home: number; away: number };
    shots_on_target: { home: number; away: number };
    fouls?: { home: number; away: number };
    yellow_cards?: { home: number; away: number };
    red_cards?: { home: number; away: number };
    substitutions?: { home: number; away: number };
  };
  headline: string;
  final_score: {
    home: number;
    away: number;
    home_team: string;
    away_team: string;
  };
  match_story: string;
  turning_points: TurningPoint[];
  xg_balance: {
    home_xg: number;
    away_xg: number;
    dominance: string;
    home_shots: number;
    away_shots: number;
  };
  man_of_the_match: {
    player_id: string;
    name: string;
    team: string;
    rating: number;
    bps: number;
    goals?: number;
    summary: string;
  };
  tactical_entropy: {
    average_cci: number;
    rhythm_label: string;
    summary: string;
  };
  translations?: Record<LanguageCode, {
    headline: string;
    match_story: string;
  }>;
}

export interface MetricAlert {
  alert_id: string;
  alert_type: 'sprint_threshold' | 'shot_threshold' | 'milestone' | string;
  timestamp: string;
  clock: string;
  player_id?: string;
  player_name?: string;
  team?: string;
  metric_name: string;
  metric_value: number;
  threshold_value: number;
  unit: string;
  headline: string;
  description: string;
}

export type TabId = 'ingame' | 'players' | 'tactical' | 'persona' | 'recap';

export type TeamAllegiance = 'neutral' | 'home' | 'away';

export interface TacticalLayerState {
  heatmap: boolean;
  passing_lanes: boolean;
  low_block: boolean;
  defensive_line: boolean;
  pressing_zones: boolean;
}

export interface MomentBreakdown {
  structural_weaknesses: string;
  player_decisions: string;
  team_shape: string;
  key_takeaway: string;
  grounding_score: number;
  pdr: number;
  depth_m: number;
  compactness_m2: number;
  press_pct: number;
  persona_notes: Record<'tactical' | 'casual' | 'club' | 'fantasy', string>;
  source?: string;
}

export interface TacticalMoment {
  id: string;
  event_id?: string;
  event_type?: string;
  score_after?: string;
  period?: number;
  breakdown?: MomentBreakdown;
  name: string;
  timestamp: string;
  clock: string;
  frame?: TelemetryFrame;
  passing_lanes?: Array<{
    from_player_id: string;
    to_player_id: string;
    startX: number;
    startY: number;
    endX: number;
    endY: number;
    risk: number;
    active?: boolean;
  }>;
  low_block_polygon?: Array<{ x: number; y: number }>;
  defensive_line_depth_m?: number;
  offside_line_x?: number;
  pressing_zones?: Array<{
    x: number;
    y: number;
    radius: number;
    intensity: number;
    team: string;
  }>;
  ai_analysis?: string;
  description?: string;
  turning_point?: string;
}

export interface RadarMetric {
  axis: string;
  value: number;
  fullMark: number;
  formattedValue?: string;
}

export interface PlayerRadarData {
  player_id: string;
  player_name: string;
  metrics: RadarMetric[];
}

export interface HighlightMilestone {
  id: string;
  minute: string;
  title: string;
  start_frame?: number;
  end_frame?: number;
  duration_seconds?: number;
  event_type?: string;
  team?: string;
  score?: string;
  description?: string;
}



