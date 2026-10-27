/**
 * InGame Studio - the Match Analyst chat bubble.
 *
 * A round button in the bottom-right corner of the match view opens a small chat. The viewer
 * asks about the match; a Microsoft Agent Framework agent answers by calling the MCP analytics
 * tools. The answer describes the match as it stands at the current clock, follows the persona
 * chosen in the top bar (and the supported club for the Club persona), and is checked against
 * the tool results before it is shown.
 */

import React, { useEffect, useRef, useState } from 'react';
import { ClubPerspective, ViewerPersona } from '../types';

interface AnalystAnswer {
  answer: string;
  verified: boolean;
  source: string;
  tools_used: { tool: string; arguments: Record<string, unknown> }[];
  as_of_clock?: string;
  as_of_score?: string;
  match_status?: string;
}

interface ChatMessage {
  role: 'user' | 'analyst';
  text: string;
  meta?: AnalystAnswer;
}

export interface AnalystChatProps {
  persona: ViewerPersona;
  favoriteClub: ClubPerspective;
  language: string;
  /** Only shown on the main match tab; the chat keeps its history when hidden. */
  visible: boolean;
}

const SUGGESTIONS: Record<string, string[]> = {
  en: ['What is happening right now?', 'Who is playing best so far?', 'Which team is on top?'],
  es: ['¿Qué está pasando ahora?', '¿Quién juega mejor hasta ahora?', '¿Qué equipo domina?'],
};

const PERSONA_LABEL: Record<ViewerPersona, string> = {
  casual: 'Casual fan',
  tactical: 'Tactical purist',
  club: 'Club loyalist',
  fantasy: 'Fantasy scout',
};

export const AnalystChat: React.FC<AnalystChatProps> = ({ persona, favoriteClub, language, visible }) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, busy, open]);

  const voice =
    persona === 'club'
      ? `${favoriteClub} fan`
      : PERSONA_LABEL[persona];

  const ask = (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setInput('');
    setBusy(true);
    fetch('/api/analyst/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, language, persona, club: persona === 'club' ? favoriteClub : '' }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: AnalystAnswer) => setMessages((m) => [...m, { role: 'analyst', text: data.answer, meta: data }]))
      .catch(() => setMessages((m) => [...m, { role: 'analyst', text: 'The analyst could not be reached. Please try again.' }]))
      .finally(() => setBusy(false));
  };

  if (!visible) return null;

  return (
    <>
      <style>{`
        .ac-fab { position: fixed; right: 20px; bottom: 20px; z-index: 900; width: 58px; height: 58px; border-radius: 50%;
          border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 26px;
          background: radial-gradient(circle at 30% 30%, #4dffb0, #00c26a); color: #04130c;
          box-shadow: 0 6px 22px rgba(0,255,135,0.4), 0 0 0 4px rgba(0,255,135,0.12); transition: transform .15s; }
        .ac-fab:hover { transform: scale(1.07); }
        .ac-panel { position: fixed; right: 20px; bottom: 90px; z-index: 900; width: min(380px, calc(100vw - 24px));
          height: min(520px, calc(100vh - 120px)); display: flex; flex-direction: column; border-radius: 14px; overflow: hidden;
          background: var(--color-surface, #10161f); border: 1px solid var(--color-border-emphasis, #2d3f55);
          box-shadow: 0 16px 48px rgba(0,0,0,0.55); }
        .ac-head { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: rgba(0,255,135,0.08);
          border-bottom: 1px solid var(--color-border-subtle, #1e2a3a); }
        .ac-head b { font-size: 13px; letter-spacing: .03em; }
        .ac-head small { display: block; font-size: 10px; color: var(--color-text-secondary, #8b9bb4); }
        .ac-close { margin-left: auto; background: none; border: none; color: inherit; font-size: 18px; cursor: pointer; }
        .ac-body { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
        .ac-msg { max-width: 88%; padding: 8px 11px; border-radius: 12px; font-size: 13px; line-height: 1.5; }
        .ac-user { align-self: flex-end; background: #00c26a; color: #04130c; border-bottom-right-radius: 3px; font-weight: 600; }
        .ac-bot { align-self: flex-start; background: rgba(255,255,255,0.06); border-bottom-left-radius: 3px; }
        .ac-meta { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; font-size: 9px; font-family: var(--font-mono, monospace); }
        .ac-chip { padding: 1px 6px; border-radius: 4px; background: rgba(110,160,255,0.15); }
        .ac-ok { background: rgba(0,255,135,0.15); color: #00ff87; } .ac-bad { background: rgba(255,107,107,0.15); color: #ff6b6b; }
        .ac-sugg { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 12px 8px; }
        .ac-sugg button { padding: 3px 10px; border-radius: 14px; font-size: 11px; cursor: pointer; color: inherit;
          background: transparent; border: 1px solid var(--color-border-subtle, #1e2a3a); }
        .ac-form { display: flex; gap: 6px; padding: 10px 12px; border-top: 1px solid var(--color-border-subtle, #1e2a3a); }
        .ac-form input { flex: 1; min-width: 0; padding: 8px 10px; border-radius: 8px; font-size: 13px; color: inherit;
          background: rgba(0,0,0,0.35); border: 1px solid var(--color-border-subtle, #1e2a3a); }
        .ac-form button { padding: 0 14px; border: none; border-radius: 8px; font-weight: 800; cursor: pointer; background: #00ff87; color: #080b0f; }
        .ac-form button:disabled { opacity: .5; cursor: default; }
        .ac-dots span { animation: acDot 1s infinite; display: inline-block; } .ac-dots span:nth-child(2) { animation-delay: .2s; } .ac-dots span:nth-child(3) { animation-delay: .4s; }
        @keyframes acDot { 50% { opacity: .2; } }
      `}</style>

      {open && (
        <section className="ac-panel" role="dialog" aria-label="Ask the match analyst">
          <div className="ac-head">
            <span style={{ fontSize: 20 }} aria-hidden="true">⚽</span>
            <div>
              <b>Match Analyst</b>
              <small>Answers as a {voice} · knows the match up to now</small>
            </div>
            <button className="ac-close" onClick={() => setOpen(false)} aria-label="Close the analyst">×</button>
          </div>

          <div className="ac-body">
            {messages.length === 0 && (
              <div className="ac-msg ac-bot">
                {language === 'es'
                  ? 'Pregúntame lo que quieras sobre el partido. Solo sé lo que ha pasado hasta este momento.'
                  : 'Ask me anything about the match. I only know what has happened up to this moment.'}
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`ac-msg ${m.role === 'user' ? 'ac-user' : 'ac-bot'}`}>
                {m.text}
                {m.meta && (
                  <div className="ac-meta">
                    <span className={`ac-chip ${m.meta.verified ? 'ac-ok' : 'ac-bad'}`}>
                      {m.meta.verified ? 'VERIFIED' : 'NOT VERIFIED'}
                    </span>
                    {m.meta.as_of_clock && (
                      <span className="ac-chip">as of {m.meta.as_of_clock} · {m.meta.as_of_score}</span>
                    )}
                    {m.meta.tools_used.map((t, j) => (
                      <span key={j} className="ac-chip" title={JSON.stringify(t.arguments)}>MCP · {t.tool}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="ac-msg ac-bot ac-dots" aria-live="polite">
                <span>●</span> <span>●</span> <span>●</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {messages.length === 0 && (
            <div className="ac-sugg">
              {(SUGGESTIONS[language] || SUGGESTIONS.en).map((s) => (
                <button key={s} onClick={() => ask(s)} disabled={busy}>{s}</button>
              ))}
            </div>
          )}

          <form className="ac-form" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={language === 'es' ? 'Pregunta sobre el partido…' : 'Ask about the match…'}
              maxLength={400}
              aria-label="Your question"
            />
            <button type="submit" disabled={busy || !input.trim()}>{language === 'es' ? 'Enviar' : 'Send'}</button>
          </form>
        </section>
      )}

      <button
        className="ac-fab"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close the match analyst' : 'Open the match analyst'}
        title="Ask the Match Analyst"
      >
        {open ? '×' : '💬'}
      </button>
    </>
  );
};
