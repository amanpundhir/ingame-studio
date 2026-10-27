/**
 * InGame Studio - WebSocket Streaming Client Service
 */

import { TelemetryFrame, MatchEvent, VerifiedInsight, MetricAlert } from '../types';
import { getSessionId } from './session';

export type MessageHandler = {
  onTelemetry?: (frame: TelemetryFrame) => void;
  onEvent?: (event: MatchEvent) => void;
  onInsight?: (insight: VerifiedInsight) => void;
  onMetricAlert?: (alert: MetricAlert) => void;
  onControl?: (control: { action: string; clock?: string }) => void;
  onLatencyUpdate?: (latencyMs: number) => void;
  onStatusChange?: (connected: boolean) => void;
};

export class StudioStreamService {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: MessageHandler = {};
  private reconnectTimeout: number | null = null;
  private pingInterval: number | null = null;
  private isExplicitlyClosed = false;

  constructor(url?: string) {
    if (url) {
      this.url = url;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || 'localhost:8000';
      // The session id gives this viewer their own match on the server.
      this.url = `${protocol}//${host}/ws/match-stream?session=${encodeURIComponent(getSessionId())}`;
    }
  }

  public setHandlers(handlers: MessageHandler) {
    this.handlers = handlers;
  }

  public connect() {
    this.isExplicitlyClosed = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.handlers.onStatusChange?.(true);
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type = payload.type;

          if (type === 'telemetry') {
            this.handlers.onTelemetry?.(payload.data);
          } else if (type === 'event') {
            this.handlers.onEvent?.(payload.data);
          } else if (type === 'insight') {
            this.handlers.onInsight?.(payload.data);
          } else if (type === 'metric_alert') {
            this.handlers.onMetricAlert?.(payload.data);
          } else if (type === 'control') {
            this.handlers.onControl?.(payload.data);
          } else if (type === 'pong') {
            const clientTime = payload.client_time;
            if (clientTime) {
              const latency = Math.max(1, Date.now() - clientTime);
              this.handlers.onLatencyUpdate?.(latency);
            }
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };

      this.ws.onclose = () => {
        this.handlers.onStatusChange?.(false);
        this.stopPing();
        if (!this.isExplicitlyClosed) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket stream error', err);
      };
    } catch (err) {
      console.error('WebSocket connection failed', err);
      this.scheduleReconnect();
    }
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    this.stopPing();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  public sendControl(action: 'play' | 'pause' | 'reset') {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'control', action }));
    }
  }

  private startPing() {
    this.stopPing();
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping', client_time: Date.now() }));
      }
    }, 1000);
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) return;
    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, 2000);
  }
}
