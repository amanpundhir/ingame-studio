/**
 * InGame Studio - Tactical Pitch Canvas
 * Central interactive pitch canvas rendering freeze-frame 22-player coordinates,
 * player squad numbers, ball position, movement velocity vectors, and 5 tactical layer overlays:
 * 1. Heatmap overlay (territory density contours)
 * 2. Passing Lanes (directed passing channels with threat gradients)
 * 3. Low Block Shape (compactness polygon connecting defensive shape)
 * 4. Defensive Line Depth & Offside Line (line across pitch at last defender with distance annotation)
 * 5. Pressing Zones (high-press trap zones in attacking/middle thirds)
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { TacticalMoment, TacticalLayerState, PlayerTracking } from '../types';
import { CANONICAL_COLORS, PITCH_TOKENS } from '../constants/tokens';

export interface TacticalPitchCanvasProps {
  moment: TacticalMoment | null;
  layerState: TacticalLayerState;
  selectedPlayerId?: string | null;
  onSelectPlayer?: (playerId: string) => void;
  className?: string;
  isVisible?: boolean;
}

interface HoveredPlayerInfo {
  player: PlayerTracking;
  canvasX: number;
  canvasY: number;
}

export const TacticalPitchCanvas: React.FC<TacticalPitchCanvasProps> = ({
  moment,
  layerState,
  selectedPlayerId,
  onSelectPlayer,
  className = '',
  isVisible = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hoveredPlayer, setHoveredPlayer] = useState<HoveredPlayerInfo | null>(null);

  // Pitch standard dimensions (105m x 68m)
  const pitchLength = PITCH_TOKENS.length;
  const pitchWidth = PITCH_TOKENS.width;

  // Master Pitch Drawing Routine
  const drawPitch = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Measure against container to handle display:none -> block transitions cleanly
    const rect = container.getBoundingClientRect();
    if (rect.width <= 10 || rect.height <= 10) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const width = rect.width;
    const height = rect.height;

    // Sync canvas buffer dimensions with device pixel ratio
    const targetW = Math.floor(width * dpr);
    const targetH = Math.floor(height * dpr);
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }

    ctx.save();
    try {
      ctx.scale(dpr, dpr);

      // Pitch padding & aspect ratio scaling (105m x 68m = 1.5441)
      const pad = 24;
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

      // 0. Base Stadium Background
      ctx.fillStyle = CANONICAL_COLORS.bgBase;
      ctx.fillRect(0, 0, width, height);

      // 1. Turf Grass Alternating Mower Bands
      const bands = 15;
      const bandWidth = drawWidth / bands;
      for (let i = 0; i < bands; i++) {
        ctx.fillStyle = i % 2 === 0 ? PITCH_TOKENS.grassDark : PITCH_TOKENS.grassLight;
        ctx.fillRect(originX + i * bandWidth, originY, bandWidth, drawHeight);
      }

      // Outer pitch bezel border
      ctx.strokeStyle = PITCH_TOKENS.bezelColor;
      ctx.lineWidth = 1;
      ctx.strokeRect(originX - 1, originY - 1, drawWidth + 2, drawHeight + 2);

      // 2. IFAB Standard Pitch Markings
      ctx.strokeStyle = PITCH_TOKENS.lineColor;
      ctx.lineWidth = 1.5;

      // Boundary Touchlines
      ctx.strokeRect(originX, originY, drawWidth, drawHeight);

      // Halfway line
      const midX = toCanvasX(pitchLength / 2);
      ctx.beginPath();
      ctx.moveTo(midX, originY);
      ctx.lineTo(midX, originY + drawHeight);
      ctx.stroke();

      // Center circle & spot
      const centerCircleRadius = toCanvasDist(PITCH_TOKENS.centerCircleRadius);
      const centerSpotY = toCanvasY(pitchWidth / 2);
      ctx.beginPath();
      ctx.arc(midX, centerSpotY, centerCircleRadius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(midX, centerSpotY, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
      ctx.fill();

      // Penalty Boxes & Goal Areas
      const pBoxDepth = toCanvasDist(PITCH_TOKENS.penaltyBoxDepth);
      const pBoxWidth = toCanvasDist(PITCH_TOKENS.penaltyBoxWidth);
      const pBoxY = toCanvasY((pitchWidth - PITCH_TOKENS.penaltyBoxWidth) / 2);

      const gAreaDepth = toCanvasDist(PITCH_TOKENS.goalAreaDepth);
      const gAreaWidth = toCanvasDist(PITCH_TOKENS.goalAreaWidth);
      const gAreaY = toCanvasY((pitchWidth - PITCH_TOKENS.goalAreaWidth) / 2);

      // Left Penalty Box & Goal Area
      ctx.strokeRect(originX, pBoxY, pBoxDepth, pBoxWidth);
      ctx.strokeRect(originX, gAreaY, gAreaDepth, gAreaWidth);

      // Left Penalty Spot
      const leftPenSpotX = toCanvasX(PITCH_TOKENS.penaltySpotDistance);
      ctx.beginPath();
      ctx.arc(leftPenSpotX, centerSpotY, 2, 0, Math.PI * 2);
      ctx.fill();

      // Left Penalty Arc
      ctx.beginPath();
      ctx.arc(leftPenSpotX, centerSpotY, centerCircleRadius, -0.65, 0.65);
      ctx.stroke();

      // Right Penalty Box & Goal Area
      const rightPBoxX = originX + drawWidth - pBoxDepth;
      const rightGAreaX = originX + drawWidth - gAreaDepth;
      ctx.strokeRect(rightPBoxX, pBoxY, pBoxDepth, pBoxWidth);
      ctx.strokeRect(rightGAreaX, gAreaY, gAreaDepth, gAreaWidth);

      // Right Penalty Spot
      const rightPenSpotX = toCanvasX(pitchLength - PITCH_TOKENS.penaltySpotDistance);
      ctx.beginPath();
      ctx.arc(rightPenSpotX, centerSpotY, 2, 0, Math.PI * 2);
      ctx.fill();

      // Right Penalty Arc
      ctx.beginPath();
      ctx.arc(rightPenSpotX, centerSpotY, centerCircleRadius, Math.PI - 0.65, Math.PI + 0.65);
      ctx.stroke();

      // Corner Arcs
      const cornerR = toCanvasDist(PITCH_TOKENS.cornerArcRadius);
      ctx.beginPath(); ctx.arc(originX, originY, cornerR, 0, Math.PI / 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(originX, originY + drawHeight, cornerR, -Math.PI / 2, 0); ctx.stroke();
      ctx.beginPath(); ctx.arc(originX + drawWidth, originY, cornerR, Math.PI / 2, Math.PI); ctx.stroke();
      ctx.beginPath(); ctx.arc(originX + drawWidth, originY + drawHeight, cornerR, Math.PI, Math.PI * 1.5); ctx.stroke();

      // ─────────────────────────────────────────────────────────────
      // TACTICAL LAYER 1: HEATMAP OVERLAY (Territory Density Contours)
      // ─────────────────────────────────────────────────────────────
      if (layerState.heatmap && moment) {
        ctx.save();
        const isNorthbridgeMoment =
          moment.id === 'high_press_turnover' ||
          moment.id === 'goal_buildup' ||
          moment.id === 'low_block_shape';

        const heatNodes: Array<{ x: number; y: number; r: number; color: string; maxAlpha: number }> = [];

        if (moment.id === 'high_press_turnover') {
          heatNodes.push(
            { x: 74, y: 34, r: 22, color: '239, 1, 7', maxAlpha: 0.32 },
            { x: 70, y: 24, r: 16, color: '239, 1, 7', maxAlpha: 0.25 },
            { x: 78, y: 42, r: 18, color: '239, 1, 7', maxAlpha: 0.24 },
            { x: 86, y: 34, r: 15, color: '108, 171, 221', maxAlpha: 0.18 }
          );
        } else if (moment.id === 'goal_buildup') {
          heatNodes.push(
            { x: 88, y: 22, r: 20, color: '239, 1, 7', maxAlpha: 0.38 },
            { x: 96, y: 34, r: 18, color: '239, 1, 7', maxAlpha: 0.35 },
            { x: 92, y: 44, r: 14, color: '239, 1, 7', maxAlpha: 0.22 },
            { x: 75, y: 34, r: 24, color: '239, 1, 7', maxAlpha: 0.18 }
          );
        } else if (moment.id === 'counter_attack') {
          heatNodes.push(
            { x: 55, y: 34, r: 22, color: '108, 171, 221', maxAlpha: 0.35 },
            { x: 76, y: 32, r: 20, color: '108, 171, 221', maxAlpha: 0.32 },
            { x: 62, y: 18, r: 16, color: '108, 171, 221', maxAlpha: 0.22 },
            { x: 38, y: 34, r: 20, color: '108, 171, 221', maxAlpha: 0.15 }
          );
        } else {
          heatNodes.push(
            { x: 20, y: 34, r: 26, color: '239, 1, 7', maxAlpha: 0.34 },
            { x: 38, y: 34, r: 28, color: '108, 171, 221', maxAlpha: 0.28 },
            { x: 42, y: 20, r: 18, color: '108, 171, 221', maxAlpha: 0.22 },
            { x: 42, y: 48, r: 18, color: '108, 171, 221', maxAlpha: 0.22 }
          );
        }

        heatNodes.forEach((node) => {
          const cx = toCanvasX(node.x);
          const cy = toCanvasY(node.y);
          const cr = toCanvasDist(node.r);

          const radGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, cr);
          radGrad.addColorStop(0, `rgba(${node.color}, ${node.maxAlpha})`);
          radGrad.addColorStop(0.5, `rgba(${node.color}, ${node.maxAlpha * 0.5})`);
          radGrad.addColorStop(1, `rgba(${node.color}, 0)`);

          ctx.fillStyle = radGrad;
          ctx.beginPath();
          ctx.arc(cx, cy, cr, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = `rgba(${node.color}, ${node.maxAlpha * 0.4})`;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 4]);
          ctx.beginPath();
          ctx.arc(cx, cy, cr * 0.55, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        });

        // Layer Watermark
        ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
        ctx.font = '600 10px "Outfit", sans-serif';
        ctx.fillText(
          `● HEATMAP OVERLAY · ${isNorthbridgeMoment ? 'NORTHBRIDGE' : 'HARBOURSIDE CITY'} TERRITORIAL DENSITY`,
          originX + 10,
          originY + drawHeight - 12
        );
        ctx.restore();
      }

      // ─────────────────────────────────────────────────────────────
      // TACTICAL LAYER 5: PRESSING ZONES (High-Press Trap Zones)
      // ─────────────────────────────────────────────────────────────
      if (layerState.pressing_zones && moment && moment.pressing_zones) {
        ctx.save();
        moment.pressing_zones.forEach((pz, idx) => {
          const cx = toCanvasX(pz.x);
          const cy = toCanvasY(pz.y);
          const radiusM = pz.radius || 12;
          const cr = toCanvasDist(radiusM);

          const rawIntensity = (pz as any).intensity;
          const isHigh = rawIntensity === 'high' || rawIntensity === 'extreme' || (typeof rawIntensity === 'number' && rawIntensity > 0.7);
          const zoneColor = isHigh ? '233, 0, 82' : '255, 230, 0';

          const trapGrad = ctx.createRadialGradient(cx, cy, cr * 0.2, cx, cy, cr);
          trapGrad.addColorStop(0, `rgba(${zoneColor}, 0.28)`);
          trapGrad.addColorStop(0.7, `rgba(${zoneColor}, 0.12)`);
          trapGrad.addColorStop(1, `rgba(${zoneColor}, 0.0)`);

          ctx.fillStyle = trapGrad;
          ctx.beginPath();
          ctx.arc(cx, cy, cr, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = `rgba(${zoneColor}, 0.85)`;
          ctx.lineWidth = 2;
          ctx.setLineDash([6, 4]);
          ctx.beginPath();
          ctx.arc(cx, cy, cr, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);

          const arrowDist = cr * 0.8;
          const innerDist = cr * 0.35;
          const angles = [0, Math.PI / 2, Math.PI, (Math.PI * 3) / 2];
          ctx.strokeStyle = `rgba(${zoneColor}, 0.9)`;
          ctx.fillStyle = `rgba(${zoneColor}, 0.9)`;
          ctx.lineWidth = 1.5;

          angles.forEach((ang) => {
            const sx = cx + Math.cos(ang) * arrowDist;
            const sy = cy + Math.sin(ang) * arrowDist;
            const ex = cx + Math.cos(ang) * innerDist;
            const ey = cy + Math.sin(ang) * innerDist;

            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(ex, ey);
            ctx.stroke();

            const hLen = 6;
            const hAng = ang + Math.PI;
            ctx.beginPath();
            ctx.moveTo(ex, ey);
            ctx.lineTo(ex - hLen * Math.cos(hAng - Math.PI / 6), ey - hLen * Math.sin(hAng - Math.PI / 6));
            ctx.lineTo(ex - hLen * Math.cos(hAng + Math.PI / 6), ey - hLen * Math.sin(hAng + Math.PI / 6));
            ctx.closePath();
            ctx.fill();
          });

          const labelText = (pz as any).label || `PRESS TRAP #${idx + 1}`;
          const subLabel = (pz as any).turnover_prob
            ? `${Math.round((pz as any).turnover_prob * 100)}% TURNOVER PROB`
            : 'HIGH PRESS TRAP';

          ctx.font = '700 9px "Roboto Mono", monospace';
          const labelW = Math.max(ctx.measureText(labelText).width, ctx.measureText(subLabel).width) + 14;
          const labelH = 26;

          ctx.fillStyle = 'rgba(8, 11, 15, 0.88)';
          ctx.strokeStyle = `rgba(${zoneColor}, 0.7)`;
          ctx.lineWidth = 1;
          ctx.fillRect(cx - labelW / 2, cy - cr - labelH - 4, labelW, labelH);
          ctx.strokeRect(cx - labelW / 2, cy - cr - labelH - 4, labelW, labelH);

          ctx.fillStyle = `rgb(${zoneColor})`;
          ctx.textAlign = 'center';
          ctx.fillText(labelText, cx, cy - cr - 17);
          ctx.fillStyle = '#f0f4f8';
          ctx.font = '600 8px "Outfit", sans-serif';
          ctx.fillText(subLabel, cx, cy - cr - 7);
        });
        ctx.restore();
      }

      // ─────────────────────────────────────────────────────────────
      // TACTICAL LAYER 3: LOW BLOCK SHAPE (Compactness Polygon)
      // ─────────────────────────────────────────────────────────────
      if (layerState.low_block && moment && moment.low_block_polygon && moment.low_block_polygon.length > 2) {
        ctx.save();
        const poly = moment.low_block_polygon;

        ctx.beginPath();
        ctx.moveTo(toCanvasX(poly[0].x), toCanvasY(poly[0].y));
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(toCanvasX(poly[i].x), toCanvasY(poly[i].y));
        }
        ctx.closePath();

        const isNorthbridgeBlock = moment.id === 'low_block_shape' || moment.id === 'goal_buildup';
        ctx.fillStyle = isNorthbridgeBlock ? 'rgba(239, 1, 7, 0.16)' : 'rgba(108, 171, 221, 0.16)';
        ctx.fill();

        ctx.strokeStyle = CANONICAL_COLORS.accentCyan;
        ctx.lineWidth = 2.2;
        ctx.shadowColor = CANONICAL_COLORS.accentCyan;
        ctx.shadowBlur = 6;
        ctx.stroke();
        ctx.shadowBlur = 0;

        poly.forEach((pt) => {
          const vx = toCanvasX(pt.x);
          const vy = toCanvasY(pt.y);
          ctx.beginPath();
          ctx.arc(vx, vy, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#080b0f';
          ctx.fill();
          ctx.strokeStyle = CANONICAL_COLORS.accentCyan;
          ctx.lineWidth = 2;
          ctx.stroke();
        });

        let centroidX = 0;
        let centroidY = 0;
        poly.forEach((pt) => {
          centroidX += pt.x;
          centroidY += pt.y;
        });
        centroidX /= poly.length;
        centroidY /= poly.length;

        const badgeX = toCanvasX(centroidX);
        const badgeY = toCanvasY(centroidY);
        const compactnessArea = (moment as any).metrics?.compactness_m2 || 318;

        ctx.font = '700 9px "Roboto Mono", monospace';
        const badgeText = `DEFENSIVE COMPACTNESS: ${compactnessArea} m²`;
        const bw = ctx.measureText(badgeText).width + 16;
        const bh = 18;

        ctx.fillStyle = 'rgba(13, 17, 23, 0.92)';
        ctx.strokeStyle = CANONICAL_COLORS.accentCyan;
        ctx.lineWidth = 1;
        ctx.fillRect(badgeX - bw / 2, badgeY - bh / 2, bw, bh);
        ctx.strokeRect(badgeX - bw / 2, badgeY - bh / 2, bw, bh);

        ctx.fillStyle = CANONICAL_COLORS.accentCyan;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(badgeText, badgeX, badgeY);
        ctx.restore();
      }

      // ─────────────────────────────────────────────────────────────
      // TACTICAL LAYER 4: DEFENSIVE LINE DEPTH & OFFSIDE LINE
      // ─────────────────────────────────────────────────────────────
      if (layerState.defensive_line && moment && moment.offside_line_x !== undefined) {
        ctx.save();
        const offsideX = toCanvasX(moment.offside_line_x);
        const depthM = moment.defensive_line_depth_m || 24.5;

        const isDefendingLeftGoal = moment.offside_line_x < 52.5;
        const goalLineX = isDefendingLeftGoal ? originX : originX + drawWidth;

        const offsideRectX = isDefendingLeftGoal ? originX : offsideX;
        const offsideRectW = Math.abs(offsideX - goalLineX);
        ctx.fillStyle = 'rgba(233, 0, 82, 0.08)';
        ctx.fillRect(offsideRectX, originY, offsideRectW, drawHeight);

        ctx.strokeStyle = CANONICAL_COLORS.accentYellow;
        ctx.lineWidth = 2.4;
        ctx.setLineDash([6, 4]);
        ctx.shadowColor = CANONICAL_COLORS.accentYellow;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.moveTo(offsideX, originY);
        ctx.lineTo(offsideX, originY + drawHeight);
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.setLineDash([]);

        const annotY = originY + drawHeight * 0.22;
        ctx.strokeStyle = CANONICAL_COLORS.accentYellow;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(goalLineX, annotY);
        ctx.lineTo(offsideX, annotY);
        ctx.stroke();

        const arrowSize = 6;
        if (isDefendingLeftGoal) {
          ctx.beginPath();
          ctx.moveTo(goalLineX, annotY);
          ctx.lineTo(goalLineX + arrowSize, annotY - arrowSize);
          ctx.lineTo(goalLineX + arrowSize, annotY + arrowSize);
          ctx.closePath();
          ctx.fillStyle = CANONICAL_COLORS.accentYellow;
          ctx.fill();

          ctx.beginPath();
          ctx.moveTo(offsideX, annotY);
          ctx.lineTo(offsideX - arrowSize, annotY - arrowSize);
          ctx.lineTo(offsideX - arrowSize, annotY + arrowSize);
          ctx.closePath();
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.moveTo(offsideX, annotY);
          ctx.lineTo(offsideX + arrowSize, annotY - arrowSize);
          ctx.lineTo(offsideX + arrowSize, annotY + arrowSize);
          ctx.closePath();
          ctx.fillStyle = CANONICAL_COLORS.accentYellow;
          ctx.fill();

          ctx.beginPath();
          ctx.moveTo(goalLineX, annotY);
          ctx.lineTo(goalLineX - arrowSize, annotY - arrowSize);
          ctx.lineTo(goalLineX - arrowSize, annotY + arrowSize);
          ctx.closePath();
          ctx.fill();
        }

        const midDepthX = (goalLineX + offsideX) / 2;
        const depthBadgeText = `LINE DEPTH: ${depthM.toFixed(1)}m`;
        ctx.font = '700 9px "Roboto Mono", monospace';
        const dbw = ctx.measureText(depthBadgeText).width + 12;
        const dbh = 17;

        ctx.fillStyle = 'rgba(8, 11, 15, 0.9)';
        ctx.strokeStyle = CANONICAL_COLORS.accentYellow;
        ctx.lineWidth = 1;
        ctx.fillRect(midDepthX - dbw / 2, annotY - dbh / 2, dbw, dbh);
        ctx.strokeRect(midDepthX - dbw / 2, annotY - dbh / 2, dbw, dbh);

        ctx.fillStyle = CANONICAL_COLORS.accentYellow;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(depthBadgeText, midDepthX, annotY);

        const lineTagText = `LAST DEFENDER OFFSIDE LINE`;
        ctx.font = '700 8px "Roboto Mono", monospace';
        const ltw = ctx.measureText(lineTagText).width + 10;
        ctx.fillStyle = CANONICAL_COLORS.accentYellow;
        ctx.fillRect(offsideX - ltw / 2, originY + 4, ltw, 14);
        ctx.fillStyle = '#080b0f';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(lineTagText, offsideX, originY + 11);

        ctx.restore();
      }

      // ─────────────────────────────────────────────────────────────
      // TACTICAL LAYER 2: PASSING LANES (Threat Gradients & Corridors)
      // ─────────────────────────────────────────────────────────────
      if (layerState.passing_lanes && moment && moment.passing_lanes) {
        ctx.save();
        moment.passing_lanes.forEach((lane) => {
          const sx = toCanvasX((lane as any).startX ?? (lane as any).start?.x ?? 50);
          const sy = toCanvasY((lane as any).startY ?? (lane as any).start?.y ?? 34);
          const ex = toCanvasX((lane as any).endX ?? (lane as any).end?.x ?? 60);
          const ey = toCanvasY((lane as any).endY ?? (lane as any).end?.y ?? 34);

          const risk = (lane as any).risk ?? 0.5;
          const isActive = (lane as any).active ?? true;

          let laneColor: string = CANONICAL_COLORS.accentGreen;
          let laneLabel = 'VIABLE';
          if (risk > 0.65) {
            laneColor = CANONICAL_COLORS.accentRed;
            laneLabel = 'HIGH RISK';
          } else if (risk > 0.35) {
            laneColor = CANONICAL_COLORS.accentYellow;
            laneLabel = 'CONTESTED';
          }

          const corridorWidthM = 3.5;
          const corridorDist = toCanvasDist(corridorWidthM / 2);
          const angle = Math.atan2(ey - sy, ex - sx);
          const perpAngle = angle + Math.PI / 2;

          const dxPerp = Math.cos(perpAngle) * corridorDist;
          const dyPerp = Math.sin(perpAngle) * corridorDist;

          ctx.beginPath();
          ctx.moveTo(sx + dxPerp, sy + dyPerp);
          ctx.lineTo(ex + dxPerp, ey + dyPerp);
          ctx.lineTo(ex - dxPerp, ey - dyPerp);
          ctx.lineTo(sx - dxPerp, sy - dyPerp);
          ctx.closePath();
          ctx.fillStyle = `${laneColor}15`;
          ctx.fill();
          ctx.strokeStyle = `${laneColor}50`;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(ex, ey);
          ctx.strokeStyle = laneColor;
          ctx.lineWidth = isActive ? 2.8 : 1.8;
          ctx.shadowColor = laneColor;
          ctx.shadowBlur = isActive ? 5 : 2;
          ctx.stroke();
          ctx.shadowBlur = 0;

          const headLen = 10;
          ctx.beginPath();
          ctx.moveTo(ex, ey);
          ctx.lineTo(ex - headLen * Math.cos(angle - Math.PI / 6), ey - headLen * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(ex - headLen * Math.cos(angle + Math.PI / 6), ey - headLen * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fillStyle = laneColor;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(ex, ey, 6, 0, Math.PI * 2);
          ctx.strokeStyle = laneColor;
          ctx.lineWidth = 1.5;
          ctx.stroke();

          const midLX = (sx + ex) / 2;
          const midLY = (sy + ey) / 2;
          const pdrVal = (lane as any).pdr ?? Math.round(risk * 100);
          const badgeMsg = `PDR: ${pdrVal}% · ${laneLabel}`;

          ctx.font = '700 8px "Roboto Mono", monospace';
          const bWidth = ctx.measureText(badgeMsg).width + 8;
          ctx.fillStyle = 'rgba(8, 11, 15, 0.88)';
          ctx.strokeStyle = laneColor;
          ctx.lineWidth = 0.8;
          ctx.fillRect(midLX - bWidth / 2, midLY - 7, bWidth, 14);
          ctx.strokeRect(midLX - bWidth / 2, midLY - 7, bWidth, 14);

          ctx.fillStyle = laneColor;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(badgeMsg, midLX, midLY);
        });
        ctx.restore();
      }

      // ─────────────────────────────────────────────────────────────
      // 3. RENDER 22 FROZEN PLAYERS (Authentic Kits, Numbers, Vectors)
      // ─────────────────────────────────────────────────────────────
      const players = moment?.frame?.players || [];
      players.forEach((p) => {
        const px = toCanvasX(p.x);
        const py = toCanvasY(p.y);
        const isSelected = selectedPlayerId === p.player_id;
        const isHovered = hoveredPlayer?.player.player_id === p.player_id;

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
            kitBodyColor = CANONICAL_COLORS.gkHome;
            kitTrimColor = '#0A2E16';
            numberColor = '#0A2E16';
          } else {
            kitBodyColor = CANONICAL_COLORS.gkAway;
            kitTrimColor = CANONICAL_COLORS.harboursideNavy;
            numberColor = '#FFFFFF';
          }
        }

        // Drop shadow
        ctx.beginPath();
        ctx.ellipse(px, py + 2.5, 9, 4.5, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
        ctx.fill();

        // Movement Velocity Vector
        const speed = p.speed_kmh || Math.hypot(p.vx, p.vy) * 3.6;
        if (speed > 2.0) {
          const velLen = Math.min(22, Math.max(8, speed * 0.7));
          const velAngle = Math.atan2(p.vy, p.vx);
          const vxEnd = px + Math.cos(velAngle) * velLen;
          const vyEnd = py + Math.sin(velAngle) * velLen;

          ctx.strokeStyle = 'rgba(255, 255, 255, 0.75)';
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(vxEnd, vyEnd);
          ctx.stroke();

          const arrowL = 4.5;
          ctx.beginPath();
          ctx.moveTo(vxEnd, vyEnd);
          ctx.lineTo(vxEnd - arrowL * Math.cos(velAngle - Math.PI / 6), vyEnd - arrowL * Math.sin(velAngle - Math.PI / 6));
          ctx.lineTo(vxEnd - arrowL * Math.cos(velAngle + Math.PI / 6), vyEnd - arrowL * Math.sin(velAngle + Math.PI / 6));
          ctx.closePath();
          ctx.fillStyle = '#ffffff';
          ctx.fill();
        }

        // Selection / Hover Ring
        if (isSelected || isHovered) {
          ctx.beginPath();
          ctx.arc(px, py, PITCH_TOKENS.selectedPlayerRadius, 0, Math.PI * 2);
          ctx.strokeStyle = isSelected ? CANONICAL_COLORS.accentGreen : CANONICAL_COLORS.accentYellow;
          ctx.lineWidth = 2.2;
          ctx.shadowColor = isSelected ? CANONICAL_COLORS.accentGreen : CANONICAL_COLORS.accentYellow;
          ctx.shadowBlur = 6;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }

        // Player Circular Body
        ctx.beginPath();
        ctx.arc(px, py, PITCH_TOKENS.playerRadius, 0, Math.PI * 2);
        ctx.fillStyle = kitBodyColor;
        ctx.fill();
        ctx.lineWidth = 2.0;
        ctx.strokeStyle = kitTrimColor;
        ctx.stroke();

        // Northbridge Lions White Sleeves Detail
        if (isNorthbridge && !isGK) {
          ctx.fillStyle = '#FFFFFF';
          ctx.beginPath(); ctx.arc(px - 7.5, py, 3.2, 0, Math.PI * 2); ctx.fill();
          ctx.beginPath(); ctx.arc(px + 7.5, py, 3.2, 0, Math.PI * 2); ctx.fill();
        }

        // Squad Jersey Number
        ctx.fillStyle = numberColor;
        ctx.font = 'bold 9px "Roboto Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(p.jersey_number), px, py + 0.5);

        // Surname Label Tag
        const surname = p.name.split(' ').pop() || p.name;
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '700 9px "Outfit", sans-serif';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
        ctx.shadowBlur = 4;
        ctx.fillText(surname, px, py - 13);
        ctx.shadowBlur = 0;
      });

      // ─────────────────────────────────────────────────────────────
      // 4. RENDER FROZEN BALL (Coordinates & Drop Shadow)
      // ─────────────────────────────────────────────────────────────
      if (moment?.frame?.ball) {
        const b = moment.frame.ball;
        const bx = toCanvasX(b.x);
        const by = toCanvasY(b.y);
        const bz = b.z || 0.0;

        const shadowOffset = Math.min(10, bz * 2.2 + 2);
        ctx.beginPath();
        ctx.ellipse(bx, by + shadowOffset, 5 + bz * 0.5, 2.5 + bz * 0.3, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(bx, by - bz * 1.5, PITCH_TOKENS.ballRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.fill();
        ctx.strokeStyle = '#080b0f';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(bx, by - bz * 1.5, PITCH_TOKENS.ballRadius + 2, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // ─────────────────────────────────────────────────────────────
      // 5. TELSTRATOR HEADER HUD & COMPASS
      // ─────────────────────────────────────────────────────────────
      const clockText = moment?.clock || moment?.timestamp || '00:00';
      const momentTitle = moment?.name?.toUpperCase() || 'MOMENT FREEZE-FRAME';
      ctx.fillStyle = 'rgba(8, 11, 15, 0.85)';
      ctx.strokeStyle = CANONICAL_COLORS.borderSubtle;
      ctx.lineWidth = 1;
      ctx.fillRect(originX + 10, originY + 10, 230, 26);
      ctx.strokeRect(originX + 10, originY + 10, 230, 26);

      ctx.fillStyle = CANONICAL_COLORS.accentGreen;
      ctx.font = '700 9px "Roboto Mono", monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(`⏱ ${clockText}`, originX + 18, originY + 23);

      ctx.fillStyle = '#f0f4f8';
      ctx.font = '700 10px "Outfit", sans-serif';
      ctx.fillText(momentTitle, originX + 70, originY + 23);

      // Direction of Attack Compass (Top-Right)
      const compassW = 160;
      ctx.fillStyle = 'rgba(8, 11, 15, 0.85)';
      ctx.strokeStyle = CANONICAL_COLORS.borderSubtle;
      ctx.fillRect(originX + drawWidth - compassW - 10, originY + 10, compassW, 26);
      ctx.strokeRect(originX + drawWidth - compassW - 10, originY + 10, compassW, 26);

      ctx.fillStyle = CANONICAL_COLORS.northbridgeRed;
      ctx.font = '700 9px "Outfit", sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('NBL ➔', originX + drawWidth - compassW - 2, originY + 23);

      ctx.fillStyle = CANONICAL_COLORS.textSecondary;
      ctx.fillText(' | ', originX + drawWidth - compassW + 42, originY + 23);

      ctx.fillStyle = CANONICAL_COLORS.harboursideBlue;
      ctx.fillText('◀ HSC', originX + drawWidth - compassW + 62, originY + 23);
    } finally {
      ctx.restore();
    }
  }, [moment, layerState, selectedPlayerId, hoveredPlayer, pitchLength, pitchWidth]);

  // Redraw when moment, layers, or selection change, or when container resizes
  useEffect(() => {
    let animId: number;

    const render = () => {
      drawPitch();
    };

    // Immediate draw
    render();
    // Second draw pass on next frame to guarantee correct dimensions if DOM is mounting
    animId = requestAnimationFrame(render);

    const container = containerRef.current;
    let ro: ResizeObserver | null = null;
    if (container && typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => {
        render();
      });
      ro.observe(container);
    }

    window.addEventListener('resize', render);
    return () => {
      cancelAnimationFrame(animId);
      if (ro) ro.disconnect();
      window.removeEventListener('resize', render);
    };
  }, [drawPitch, isVisible]);

  // Handle player click and hover
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !moment?.frame?.players) return;

    const rect = container.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const pad = 24;
    const availW = Math.max(10, rect.width - pad * 2);
    const availH = Math.max(10, rect.height - pad * 2);
    const scale = Math.min(availW / pitchLength, availH / pitchWidth);
    const drawWidth = pitchLength * scale;
    const drawHeight = pitchWidth * scale;
    const originX = (rect.width - drawWidth) / 2;
    const originY = (rect.height - drawHeight) / 2;

    const toCanvasX = (x: number) => originX + x * scale;
    const toCanvasY = (y: number) => originY + y * scale;

    let found: HoveredPlayerInfo | null = null;
    for (const p of moment.frame.players) {
      const px = toCanvasX(p.x);
      const py = toCanvasY(p.y);
      const dist = Math.hypot(mouseX - px, mouseY - py);
      if (dist <= PITCH_TOKENS.playerRadius + 4) {
        found = { player: p, canvasX: px, canvasY: py };
        break;
      }
    }
    setHoveredPlayer(found);
  };

  const handleCanvasClick = () => {
    if (hoveredPlayer && onSelectPlayer) {
      onSelectPlayer(hoveredPlayer.player.player_id);
    }
  };

  const handleCanvasMouseLeave = () => {
    setHoveredPlayer(null);
  };

  return (
    <div
      ref={containerRef}
      className={`tactical-pitch-canvas-wrapper ${className}`}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: '440px',
        backgroundColor: 'var(--color-bg-base, #080b0f)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseMove={handleCanvasMouseMove}
        onClick={handleCanvasClick}
        onMouseLeave={handleCanvasMouseLeave}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          cursor: hoveredPlayer ? 'pointer' : 'crosshair',
        }}
        aria-label="Tactical Freeze-Frame Pitch Telestrator"
        role="img"
      />

      {/* Floating Hover Player Tooltip */}
      {hoveredPlayer && (
        <div
          className="tactical-player-tooltip"
          style={{
            position: 'absolute',
            pointerEvents: 'none',
            zIndex: 30,
            padding: '8px 12px',
            borderRadius: '6px',
            border: `1px solid ${CANONICAL_COLORS.borderEmphasis}`,
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(8px)',
            left: `${hoveredPlayer.canvasX + 16}px`,
            top: `${hoveredPlayer.canvasY - 24}px`,
            backgroundColor: 'rgba(13, 17, 23, 0.95)',
            minWidth: '150px',
            transform: 'translateY(-50%)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px',
              borderBottom: '1px solid #1e2a3a',
              paddingBottom: '4px',
              marginBottom: '4px',
            }}
          >
            <span style={{ fontWeight: 700, fontSize: '12px', color: '#f0f4f8' }}>
              {hoveredPlayer.player.name}
            </span>
            <span
              style={{
                padding: '2px 6px',
                borderRadius: '4px',
                fontSize: '10px',
                fontFamily: 'monospace',
                fontWeight: 700,
                backgroundColor:
                  hoveredPlayer.player.team === 'home' || hoveredPlayer.player.player_id.startsWith('NBL')
                    ? 'rgba(239, 1, 7, 0.2)'
                    : 'rgba(108, 171, 221, 0.2)',
                color:
                  hoveredPlayer.player.team === 'home' || hoveredPlayer.player.player_id.startsWith('NBL')
                    ? '#EF0107'
                    : '#6CABDD',
              }}
            >
              #{hoveredPlayer.player.jersey_number} · {hoveredPlayer.player.role}
            </span>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '2px 8px',
              fontSize: '10px',
              color: '#8b9bb4',
            }}
          >
            <div>Speed:</div>
            <div style={{ textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: '#f0f4f8' }}>
              {hoveredPlayer.player.speed_kmh?.toFixed(1) || '0.0'} km/h
            </div>
            <div>Coords:</div>
            <div style={{ textAlign: 'right', fontFamily: 'monospace', color: '#8b9bb4' }}>
              {hoveredPlayer.player.x.toFixed(1)}m, {hoveredPlayer.player.y.toFixed(1)}m
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
