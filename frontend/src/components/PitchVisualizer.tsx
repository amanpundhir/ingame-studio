/**
 * InGame Studio - 2D Canvas Pitch Visualizer & Telestrator
 * Renders IFAB 105m x 68m pitch, authentic Northbridge Lions/Harbourside kits,
 * continuous 60fps LERP-smoothed player/ball animation with glowing ball trail,
 * and broadcast telestrator overlays.
 */

import React, { useRef, useEffect, useState } from 'react';
import { TelemetryFrame, VerifiedInsight } from '../types';
import { CANONICAL_COLORS, PITCH_TOKENS } from '../constants/tokens';

// Canonical kit colors conforming to ingame-ui-design & broadcast test contract
const NORTHBRIDGE_RED = CANONICAL_COLORS.northbridgeRed || '#EF0107';
const NORTHBRIDGE_WHITE = CANONICAL_COLORS.northbridgeWhite || '#FFFFFF';
const MANCITY_BLUE = CANONICAL_COLORS.harboursideBlue || '#6CABDD';
const MANCITY_NAVY = CANONICAL_COLORS.harboursideNavy || '#1C2C5B';
const GK_ROARK = CANONICAL_COLORS.gkHome || '#CCFF00';
const GK_AWAY = CANONICAL_COLORS.gkAway || '#FF5500';

interface PitchVisualizerProps {
  frame: TelemetryFrame | null;
  insight: VerifiedInsight | null;
  selectedPlayerId?: string | null;
  onSelectPlayer?: (playerId: string) => void;
}

interface TrailPoint {
  x: number;
  y: number;
  z: number;
  time: number;
}

export const PitchVisualizer: React.FC<PitchVisualizerProps> = ({
  frame,
  insight,
  selectedPlayerId,
  onSelectPlayer,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoveredPlayer, setHoveredPlayer] = useState<any | null>(null);

  // Keep refs for 60fps requestAnimationFrame loop
  const frameRef = useRef<TelemetryFrame | null>(frame);
  const insightRef = useRef<VerifiedInsight | null>(insight);
  const selectedPlayerIdRef = useRef<string | null>(selectedPlayerId || null);
  const hoveredPlayerRef = useRef<any | null>(hoveredPlayer);

  frameRef.current = frame;
  insightRef.current = insight;
  selectedPlayerIdRef.current = selectedPlayerId || null;
  hoveredPlayerRef.current = hoveredPlayer;

  // LERP animation state
  const currentBallRef = useRef({ x: 52.5, y: 34.0, z: 0.0, speed: 0.0 });
  const ballTrailRef = useRef<TrailPoint[]>([]);
  const currentPlayersRef = useRef<Map<string, { x: number; y: number; vx: number; vy: number; speed_kmh: number }>>(
    new Map()
  );

  // IFAB pitch dimensions from canonical tokens
  const pitchLength = PITCH_TOKENS.length;
  const pitchWidth = PITCH_TOKENS.width;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    const render = () => {
      const currentFrame = frameRef.current;
      const currentInsight = insightRef.current;
      const currentSelected = selectedPlayerIdRef.current;
      const currentHovered = hoveredPlayerRef.current;

      // High-DPI retina display handling
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = rect.width;
      const height = rect.height;

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);

      // Pitch Margins and Aspect Ratio Lock (105m x 68m = 1.5441)
      const pad = 20;
      const availW = Math.max(10, width - pad * 2);
      const availH = Math.max(10, height - pad * 2);
      const scale = Math.min(availW / pitchLength, availH / pitchWidth);
      const drawWidth = pitchLength * scale;
      const drawHeight = pitchWidth * scale;

      const originX = (width - drawWidth) / 2;
      const originY = (height - drawHeight) / 2;

      const toCanvasX = (x: number) => originX + x * scale;
      const toCanvasY = (y: number) => originY + y * scale;
      const toCanvasDist = (m: number) => m * scale;

      // Clear Canvas Background (Studio Dark)
      ctx.fillStyle = CANONICAL_COLORS.bgBase;
      ctx.fillRect(0, 0, width, height);

      // 1. Draw Pitch Grass Turf Bands
      const bands = 15;
      const bandWidth = drawWidth / bands;
      for (let i = 0; i < bands; i++) {
        ctx.fillStyle = i % 2 === 0 ? PITCH_TOKENS.grassDark : PITCH_TOKENS.grassLight;
        ctx.fillRect(originX + i * bandWidth, originY, bandWidth, drawHeight);
      }

      // Outer Pitch Bezel
      ctx.strokeStyle = PITCH_TOKENS.bezelColor;
      ctx.lineWidth = 1;
      ctx.strokeRect(originX - 1, originY - 1, drawWidth + 2, drawHeight + 2);

      // 2. Draw IFAB Pitch Markings
      ctx.strokeStyle = PITCH_TOKENS.lineColor;
      ctx.lineWidth = 1.5;

      // Touchline boundary
      ctx.strokeRect(originX, originY, drawWidth, drawHeight);

      // Halfway line
      const midX = toCanvasX(pitchLength / 2);
      ctx.beginPath();
      ctx.moveTo(midX, originY);
      ctx.lineTo(midX, originY + drawHeight);
      ctx.stroke();

      // Center circle (9.15m radius) & Center spot
      const centerCircleRadius = toCanvasDist(PITCH_TOKENS.centerCircleRadius);
      const centerY = toCanvasY(pitchWidth / 2);

      ctx.beginPath();
      ctx.arc(midX, centerY, centerCircleRadius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(midX, centerY, 3.5, 0, Math.PI * 2);
      ctx.fill();

      // Penalty Boxes (16.5m deep, 40.32m wide)
      const penBoxDepth = toCanvasDist(PITCH_TOKENS.penaltyBoxDepth);
      const penBoxHeight = toCanvasDist(PITCH_TOKENS.penaltyBoxWidth);
      const penBoxY = toCanvasY((pitchWidth - PITCH_TOKENS.penaltyBoxWidth) / 2);

      // Left Penalty Box (Northbridge Lions Goal Area end)
      ctx.strokeRect(originX, penBoxY, penBoxDepth, penBoxHeight);

      // Right Penalty Box (Harbourside Goal Area end)
      ctx.strokeRect(originX + drawWidth - penBoxDepth, penBoxY, penBoxDepth, penBoxHeight);

      // 6-Yard Goal Areas (5.5m deep, 18.32m wide)
      const goalAreaDepth = toCanvasDist(PITCH_TOKENS.goalAreaDepth);
      const goalAreaHeight = toCanvasDist(PITCH_TOKENS.goalAreaWidth);
      const goalAreaY = toCanvasY((pitchWidth - PITCH_TOKENS.goalAreaWidth) / 2);

      // Left Goal Area
      ctx.strokeRect(originX, goalAreaY, goalAreaDepth, goalAreaHeight);

      // Right Goal Area
      ctx.strokeRect(originX + drawWidth - goalAreaDepth, goalAreaY, goalAreaDepth, goalAreaHeight);

      // Penalty Spots (11m from goal lines)
      const leftPenSpotX = toCanvasX(PITCH_TOKENS.penaltySpotDistance);
      const rightPenSpotX = toCanvasX(pitchLength - PITCH_TOKENS.penaltySpotDistance);

      ctx.beginPath();
      ctx.arc(leftPenSpotX, centerY, 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(rightPenSpotX, centerY, 3, 0, Math.PI * 2);
      ctx.fill();

      // Penalty D-Arcs (9.15m radius from penalty spot outside box)
      const dArcAngle = Math.acos(PITCH_TOKENS.goalAreaDepth / PITCH_TOKENS.centerCircleRadius);
      // Left D-Arc
      ctx.beginPath();
      ctx.arc(leftPenSpotX, centerY, centerCircleRadius, -dArcAngle, dArcAngle, false);
      ctx.stroke();

      // Right D-Arc
      ctx.beginPath();
      ctx.arc(rightPenSpotX, centerY, centerCircleRadius, Math.PI - dArcAngle, Math.PI + dArcAngle, false);
      ctx.stroke();

      // Corner Arcs (1.0m radius)
      const cornerR = toCanvasDist(PITCH_TOKENS.cornerArcRadius);
      // Top-Left
      ctx.beginPath(); ctx.arc(originX, originY, cornerR, 0, Math.PI / 2); ctx.stroke();
      // Bottom-Left
      ctx.beginPath(); ctx.arc(originX, originY + drawHeight, cornerR, -Math.PI / 2, 0); ctx.stroke();
      // Top-Right
      ctx.beginPath(); ctx.arc(originX + drawWidth, originY, cornerR, Math.PI / 2, Math.PI); ctx.stroke();
      // Bottom-Right
      ctx.beginPath(); ctx.arc(originX + drawWidth, originY + drawHeight, cornerR, Math.PI, Math.PI * 1.5); ctx.stroke();

      // Goal Nets (Visual extension outside touchline)
      const goalWidth = toCanvasDist(PITCH_TOKENS.goalWidth);
      const goalDepth = toCanvasDist(PITCH_TOKENS.goalDepth);
      const goalY = toCanvasY((pitchWidth - PITCH_TOKENS.goalWidth) / 2);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
      ctx.lineWidth = 1.0;
      // Left Goal Net
      ctx.strokeRect(originX - goalDepth, goalY, goalDepth, goalWidth);
      // Right Goal Net
      ctx.strokeRect(originX + drawWidth, goalY, goalDepth, goalWidth);

      // 3. Draw Dynamic Telestrator Vectors (from verified insight)
      if (currentInsight && currentInsight.telestrator_vectors) {
        const tv = currentInsight.telestrator_vectors;

        if (tv.pass_vector) {
          const sx = toCanvasX(tv.pass_vector.start_x);
          const sy = toCanvasY(tv.pass_vector.start_y);
          const ex = toCanvasX(tv.pass_vector.end_x);
          const ey = toCanvasY(tv.pass_vector.end_y);

          // Draw Intercept Cone (20 degree cone)
          if (tv.intercept_cone) {
            const angle = Math.atan2(ey - sy, ex - sx);
            const coneHalfAngle = (tv.intercept_cone.angle_deg * Math.PI) / 360;
            const dist = Math.hypot(ex - sx, ey - sy) * 1.1;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.arc(sx, sy, dist, angle - coneHalfAngle, angle + coneHalfAngle);
            ctx.closePath();
            ctx.fillStyle = 'rgba(255, 230, 0, 0.08)';
            ctx.strokeStyle = 'rgba(255, 230, 0, 0.35)';
            ctx.lineWidth = 1;
            ctx.fill();
            ctx.stroke();
            ctx.restore();
          }

          // Draw Passing Corridor (4m lateral envelope)
          if (tv.corridor) {
            const corridorDist = toCanvasDist(tv.corridor.width_m / 2);
            const angle = Math.atan2(ey - sy, ex - sx);
            const perpAngle = angle + Math.PI / 2;

            const dxPerp = Math.cos(perpAngle) * corridorDist;
            const dyPerp = Math.sin(perpAngle) * corridorDist;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(sx + dxPerp, sy + dyPerp);
            ctx.lineTo(ex + dxPerp, ey + dyPerp);
            ctx.lineTo(ex - dxPerp, ey - dyPerp);
            ctx.lineTo(sx - dxPerp, sy - dyPerp);
            ctx.closePath();
            ctx.fillStyle = 'rgba(0, 255, 135, 0.09)';
            ctx.strokeStyle = 'rgba(0, 255, 135, 0.4)';
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1.5;
            ctx.fill();
            ctx.stroke();
            ctx.restore();
          }

          // Animated Passing Vector Line with Arrowhead
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(ex, ey);
          ctx.strokeStyle = CANONICAL_COLORS.accentGreen;
          ctx.lineWidth = 3.0;
          ctx.shadowColor = CANONICAL_COLORS.accentGreen;
          ctx.shadowBlur = 4;
          ctx.stroke();

          // Arrowhead
          const headLen = 9;
          const arrowAngle = Math.atan2(ey - sy, ex - sx);
          ctx.beginPath();
          ctx.moveTo(ex, ey);
          ctx.lineTo(ex - headLen * Math.cos(arrowAngle - Math.PI / 6), ey - headLen * Math.sin(arrowAngle - Math.PI / 6));
          ctx.lineTo(ex - headLen * Math.cos(arrowAngle + Math.PI / 6), ey - headLen * Math.sin(arrowAngle + Math.PI / 6));
          ctx.closePath();
          ctx.fillStyle = CANONICAL_COLORS.accentGreen;
          ctx.fill();
          ctx.restore();

          // Target Destination Ring (with pulse)
          if (tv.target_ring) {
            const trRadius = toCanvasDist(tv.target_ring.radius_m);
            ctx.save();
            ctx.beginPath();
            ctx.arc(ex, ey, trRadius, 0, Math.PI * 2);
            ctx.strokeStyle = CANONICAL_COLORS.accentGreen;
            ctx.lineWidth = 2.0;
            ctx.shadowColor = CANONICAL_COLORS.accentGreen;
            ctx.shadowBlur = 4;
            ctx.stroke();

            // Inner crosshair
            ctx.beginPath();
            ctx.moveTo(ex - 5, ey); ctx.lineTo(ex + 5, ey);
            ctx.moveTo(ex, ey - 5); ctx.lineTo(ex, ey + 5);
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.2;
            ctx.stroke();
            ctx.restore();
          }
        }
      }

      // 4. LERP Players & Draw with High-Contrast Authentic Kits
      if (currentFrame && currentFrame.players) {
        currentFrame.players.forEach((p) => {
          let curr = currentPlayersRef.current.get(p.player_id);
          if (!curr) {
            curr = { x: p.x, y: p.y, vx: p.vx, vy: p.vy, speed_kmh: p.speed_kmh };
            currentPlayersRef.current.set(p.player_id, curr);
          } else {
            // Smooth 60fps interpolation factor
            curr.x += (p.x - curr.x) * 0.35;
            curr.y += (p.y - curr.y) * 0.35;
            curr.vx = p.vx;
            curr.vy = p.vy;
            curr.speed_kmh = p.speed_kmh;
          }

          const px = toCanvasX(curr.x);
          const py = toCanvasY(curr.y);
          const isSelected = currentSelected === p.player_id;
          const isHovered = currentHovered?.player_id === p.player_id;

          // Team & Goalkeeper Kit Differentiation (Robust Check)
          const isNorthbridge =
            p.team === 'home' ||
            p.team.toLowerCase().includes('northbridge') ||
            p.player_id.startsWith('NBL');

          const isGK =
            p.role === 'GK' ||
            p.jersey_number === 1 ||
            p.jersey_number === 31 ||
            p.name.includes('Roark') ||
            p.name.includes('Enzo Barreto');

          let kitBodyColor: string = isNorthbridge ? CANONICAL_COLORS.northbridgeRed : CANONICAL_COLORS.harboursideBlue;
          let kitTrimColor: string = isNorthbridge ? CANONICAL_COLORS.northbridgeWhite : CANONICAL_COLORS.harboursideNavy;
          let numberColor = '#FFFFFF';

          if (isGK) {
            if (isNorthbridge) {
              // Daniel Roark: Vibrant Neon Lime Yellow
              kitBodyColor = CANONICAL_COLORS.gkHome;
              kitTrimColor = '#0A2E16';
              numberColor = '#0A2E16';
            } else {
              // Enzo Barreto: Vibrant Neon Tangerine Orange
              kitBodyColor = CANONICAL_COLORS.gkAway;
              kitTrimColor = CANONICAL_COLORS.harboursideNavy;
              numberColor = '#FFFFFF';
            }
          }

          // (a) Ground Drop Shadow
          ctx.beginPath();
          ctx.ellipse(px, py + 2.5, 9, 4.5, 0, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
          ctx.fill();

          // (b) Velocity Vector Pointer (when running)
          if (curr.speed_kmh > 3.0) {
            const velLength = Math.min(20, curr.speed_kmh * 0.7);
            const velAngle = Math.atan2(curr.vy, curr.vx);
            ctx.beginPath();
            ctx.moveTo(px, py);
            ctx.lineTo(px + Math.cos(velAngle) * velLength, py + Math.sin(velAngle) * velLength);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
            ctx.lineWidth = 1.6;
            ctx.stroke();
          }

          // (c) Selection / Hover Highlight Ring (restrained halo)
          if (isSelected || isHovered) {
            ctx.beginPath();
            ctx.arc(px, py, PITCH_TOKENS.selectedPlayerRadius, 0, Math.PI * 2);
            ctx.strokeStyle = isSelected ? CANONICAL_COLORS.accentGreen : CANONICAL_COLORS.accentYellow;
            ctx.lineWidth = 2.0;
            ctx.shadowColor = isSelected ? CANONICAL_COLORS.accentGreen : CANONICAL_COLORS.accentYellow;
            ctx.shadowBlur = 5;
            ctx.stroke();
            ctx.shadowBlur = 0;
          }

          // (d) Player Circular Body
          ctx.beginPath();
          ctx.arc(px, py, PITCH_TOKENS.playerRadius, 0, Math.PI * 2);
          ctx.fillStyle = kitBodyColor;
          ctx.fill();
          ctx.lineWidth = 2.0;
          ctx.strokeStyle = kitTrimColor;
          ctx.stroke();

          // (e) Northbridge Lions Authentic White Sleeves Detail
          if (isNorthbridge && !isGK) {
            ctx.fillStyle = '#FFFFFF';
            ctx.beginPath();
            ctx.arc(px - 7.5, py, 3.4, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(px + 7.5, py, 3.4, 0, Math.PI * 2);
            ctx.fill();
          }

          // (f) Jersey Squad Number
          ctx.fillStyle = numberColor;
          ctx.font = 'bold 9px "Roboto Mono", monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(String(p.jersey_number), px, py + 0.5);

          // (g) Surname Label Tag
          const surname = p.name.split(' ').pop() || p.name;
          ctx.fillStyle = '#FFFFFF';
          ctx.font = '700 9px "Outfit", sans-serif';
          ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
          ctx.shadowBlur = 4;
          ctx.fillText(surname, px, py - 13);
          ctx.shadowBlur = 0;
        });
      }

      // 5. LERP Ball & Render 3D Kinematics with Glowing Trail
      if (currentFrame && currentFrame.ball) {
        const targetBall = currentFrame.ball;
        const b = currentBallRef.current;

        // Smooth 60fps interpolation
        b.x += (targetBall.x - b.x) * 0.35;
        b.y += (targetBall.y - b.y) * 0.35;
        b.z += (targetBall.z - b.z) * 0.35;
        b.speed = targetBall.speed_kmh;

        // Record position in ball motion trail
        const now = Date.now();
        ballTrailRef.current.push({ x: b.x, y: b.y, z: b.z, time: now });

        // Keep last 12 points within 600ms
        ballTrailRef.current = ballTrailRef.current.filter((pt) => now - pt.time <= 600).slice(-12);

        const bx = toCanvasX(b.x);
        const by = toCanvasY(b.y);
        const bz = Math.max(0.0, b.z);

        // (a) Glowing Motion Trail Behind Ball
        if (ballTrailRef.current.length > 2 && b.speed > 5.0) {
          ctx.save();
          for (let i = 1; i < ballTrailRef.current.length; i++) {
            const p1 = ballTrailRef.current[i - 1];
            const p2 = ballTrailRef.current[i];
            const progress = i / ballTrailRef.current.length;
            const alpha = progress * 0.6;

            const t1x = toCanvasX(p1.x);
            const t1y = toCanvasY(p1.y) - p1.z * scale * 1.5;
            const t2x = toCanvasX(p2.x);
            const t2y = toCanvasY(p2.y) - p2.z * scale * 1.5;

            ctx.beginPath();
            ctx.moveTo(t1x, t1y);
            ctx.lineTo(t2x, t2y);
            ctx.strokeStyle = `rgba(0, 255, 135, ${alpha})`;
            ctx.lineWidth = 2.5 * progress;
            ctx.stroke();
          }
          ctx.restore();
        }

        // (b) Turf-Anchored Ground Shadow at (bx, by)
        const shadowAlpha = Math.max(0.12, 0.6 - 0.08 * bz);
        const shadowRadiusX = 5.5 + bz * 0.7;
        const shadowRadiusY = 3.2 + bz * 0.4;

        ctx.beginPath();
        ctx.ellipse(bx, by, shadowRadiusX, shadowRadiusY, 0, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 0, 0, ${shadowAlpha})`;
        ctx.fill();

        // (c) 3D Ball Visual Altitude Displacement
        const altitudeScale = 8.5;
        const altitudeOffset = bz * altitudeScale;
        const ballVisualX = bx;
        const ballVisualY = by - altitudeOffset;

        // (d) Dashed Altitude Tether Line when elevated (z > 0.3m)
        if (bz > 0.3) {
          ctx.save();
          ctx.beginPath();
          ctx.setLineDash([2, 3]);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
          ctx.lineWidth = 1.2;
          ctx.moveTo(bx, by);
          ctx.lineTo(ballVisualX, ballVisualY);
          ctx.stroke();
          ctx.restore();
        }

        // (e) 3D Ball Sphere with Shading
        const ballRadius = 4.8 * (1.0 + 0.12 * Math.min(5.0, bz));

        // High-velocity Aura Glow (>35 km/h) — restrained per skill §5.5
        if (b.speed > PITCH_TOKENS.ballGlowThresholdSpeed) {
          ctx.save();
          ctx.beginPath();
          ctx.arc(ballVisualX, ballVisualY, ballRadius + 3, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(0, 255, 135, 0.6)';
          ctx.lineWidth = 1.5;
          ctx.shadowColor = CANONICAL_COLORS.accentGreen;
          ctx.shadowBlur = 5;
          ctx.stroke();
          ctx.restore();
        }

        const ballGrad = ctx.createRadialGradient(
          ballVisualX - ballRadius * 0.35,
          ballVisualY - ballRadius * 0.35,
          1,
          ballVisualX,
          ballVisualY,
          ballRadius
        );
        ballGrad.addColorStop(0, '#FFFFFF');
        ballGrad.addColorStop(0.7, '#E2E8F0');
        ballGrad.addColorStop(1, '#64748B');

        ctx.beginPath();
        ctx.arc(ballVisualX, ballVisualY, ballRadius, 0, Math.PI * 2);
        ctx.fillStyle = ballGrad;
        ctx.fill();
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = '#0F172A';
        ctx.stroke();
      }

      ctx.restore();
      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  // Handle canvas mouse hover for player tooltips
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const frameData = frameRef.current;
    if (!frameData || !frameData.players) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const pad = 20;
    const availW = Math.max(10, width - pad * 2);
    const availH = Math.max(10, height - pad * 2);
    const scale = Math.min(availW / pitchLength, availH / pitchWidth);
    const drawWidth = pitchLength * scale;
    const drawHeight = pitchWidth * scale;
    const originX = (width - drawWidth) / 2;
    const originY = (height - drawHeight) / 2;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    let found: any = null;
    for (const p of frameData.players) {
      const px = originX + p.x * scale;
      const py = originY + p.y * scale;
      const dist = Math.hypot(mouseX - px, mouseY - py);
      if (dist < 16) {
        found = p;
        break;
      }
    }
    setHoveredPlayer(found);
  };

  const handleClick = () => {
    if (hoveredPlayer && onSelectPlayer) {
      onSelectPlayer(hoveredPlayer.player_id);
    }
  };

  return (
    <div className="pitch-wrapper" role="region" aria-label="Live tactical pitch radar">
      <canvas
        ref={canvasRef}
        className="pitch-canvas"
        style={{ cursor: hoveredPlayer ? 'pointer' : 'default' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredPlayer(null)}
        onClick={handleClick}
        role="img"
        aria-label="2D Tactical pitch showing 22 players and ball trajectory"
      />

      {/* Floating Tactical Camera Pill */}
      <div className="pitch-pill" aria-hidden="true">
        <span className="pitch-pill-dot" />
        <span>TACTICAL RADAR 2D • 105m × 68m</span>
      </div>

      {/* Hover Player HUD Tooltip */}
      {hoveredPlayer && (
        <div className="pitch-tooltip" role="tooltip" aria-live="polite">
          <span
            className="pitch-tooltip-dot"
            style={{
              background: hoveredPlayer.player_id.startsWith('NBL')
                ? 'var(--color-team-home, #EF0107)'
                : 'var(--color-team-away, #6CABDD)',
            }}
            aria-hidden="true"
          />
          <div>
            <div className="pitch-tooltip-name">
              {hoveredPlayer.name} #{hoveredPlayer.jersey_number} ({hoveredPlayer.role})
            </div>
            <div className="pitch-tooltip-meta">
              Speed: <span className="pitch-tooltip-speed">{hoveredPlayer.speed_kmh.toFixed(1)} km/h</span> &bull; Pos: [{hoveredPlayer.x.toFixed(1)}m, {hoveredPlayer.y.toFixed(1)}m]
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
