/**
 * Agent Console Component
 * Displays CrewAI agent reasoning and activity logs in an expandable console.
 * Interprets ANSI escape codes for colored terminal output from CrewAI.
 */

import React, { useState } from 'react';
import { NeonScrollbar } from '../NeonScrollbar/NeonScrollbar';
import './AgentConsole.css';

/* ── ANSI escape code → neon color map ── */
const ANSI_COLORS: Record<number, string> = {
  30: 'var(--txt-muted)',   // black  → muted
  31: 'var(--err)',          // red    → neon red
  32: 'var(--green)',        // green  → neon green
  33: 'var(--gold)',         // yellow → neon gold
  34: 'var(--cyan)',         // blue   → neon cyan
  35: 'var(--pink)',         // magenta→ neon pink
  36: 'var(--cyan)',         // cyan   → neon cyan
  37: 'var(--txt)',          // white  → text
  90: 'var(--txt-muted)',   // bright black (gray)
  91: 'var(--err)',          // bright red
  92: 'var(--green)',        // bright green
  93: 'var(--gold)',         // bright yellow
  94: 'var(--cyan)',         // bright blue
  95: 'var(--pink)',         // bright magenta
  96: 'var(--cyan)',         // bright cyan
  97: 'var(--txt)',          // bright white
};

interface AnsiSpan {
  text: string;
  color: string | null;
  bold: boolean;
}

/** Parse a string containing ANSI escape codes into styled spans. */
function parseAnsi(input: string): AnsiSpan[] {
  const spans: AnsiSpan[] = [];
  // Match ESC[ ... m  sequences (both \x1b and \033 forms, plus literal bracket sequences)
  const regex: RegExp = /\x1b\[([0-9;]*)m|\[([0-9]+)m/g;
  let lastIndex: number = 0;
  let currentColor: string | null = null;
  let currentBold: boolean = false;
  let match: RegExpExecArray | null = regex.exec(input);

  while (match !== null) {
    // Push text before this escape
    if (match.index > lastIndex) {
      const text: string = input.slice(lastIndex, match.index);
      if (text) {
        spans.push({ text, color: currentColor, bold: currentBold });
      }
    }

    // Parse the SGR codes
    const codes: string = match[1] ?? match[2] ?? '0';
    const parts: string[] = codes.split(';');
    for (const part of parts) {
      const code: number = parseInt(part, 10) || 0;
      if (code === 0) {
        // Reset
        currentColor = null;
        currentBold = false;
      } else if (code === 1) {
        currentBold = true;
      } else if (ANSI_COLORS[code] !== undefined) {
        currentColor = ANSI_COLORS[code];
      }
    }

    lastIndex = match.index + match[0].length;
    match = regex.exec(input);
  }

  // Push remaining text
  if (lastIndex < input.length) {
    const text: string = input.slice(lastIndex);
    if (text) {
      spans.push({ text, color: currentColor, bold: currentBold });
    }
  }

  return spans;
}

/** Render ANSI-parsed spans as React elements. */
function renderAnsi(input: string): React.ReactNode {
  const spans: AnsiSpan[] = parseAnsi(input);
  const first: AnsiSpan | undefined = spans[0];
  if (spans.length === 1 && first && !first.color && !first.bold) {
    // No ANSI codes — return plain text
    return first.text;
  }

  return spans.map((span: AnsiSpan, i: number) => {
    if (!span.color && !span.bold) {
      return <React.Fragment key={i}>{span.text}</React.Fragment>;
    }
    const style: React.CSSProperties = {};
    if (span.color) style.color = span.color;
    if (span.bold) style.fontWeight = 700;
    return <span key={i} style={style}>{span.text}</span>;
  });
}

interface AgentConsoleProps {
  agentLogs: string | null | undefined;
}

export const AgentConsole: React.FC<AgentConsoleProps> = ({ agentLogs }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  // Don't render if no logs available
  if (!agentLogs || agentLogs.trim() === '') {
    return null;
  }

  const toggleExpanded = (): void => {
    setIsExpanded(!isExpanded);
  };

  // Parse log sections
  const sections: Array<{ title: string; content: string }> = [];
  const agentOutputMatch: RegExpMatchArray | null = agentLogs.match(
    /=== Agent Output ===\n([\s\S]*?)(?:=== |$)/
  );
  const errorOutputMatch: RegExpMatchArray | null = agentLogs.match(
    /=== Error Output ===\n([\s\S]*?)$/
  );

  if (agentOutputMatch && agentOutputMatch[1]) {
    sections.push({
      title: 'Agent Output',
      content: agentOutputMatch[1].trim(),
    });
  }

  if (errorOutputMatch && errorOutputMatch[1]) {
    sections.push({
      title: 'Error Output',
      content: errorOutputMatch[1].trim(),
    });
  }

  // If no sections parsed, show raw logs
  if (sections.length === 0) {
    sections.push({
      title: 'Agent Logs',
      content: agentLogs,
    });
  }

  return (
    <div className="agent-console">
      <div className="console-header" onClick={toggleExpanded}>
        <div className="header-left">
          <span className="console-icon">🤖</span>
          <span className="console-title">Agent Activity</span>
        </div>
        <span className={`console-expand-indicator ${isExpanded ? 'expanded' : ''}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 1.5 L9.5 6 L3 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
        </span>
      </div>

      {isExpanded && (
        <NeonScrollbar className="console-body" innerStyle={{ overflowX: 'hidden' }} color="gold">
          {sections.map((section, index) => (
            <div key={index} className="console-section">
              <div className="section-title">{section.title}</div>
              <pre className="section-content">{renderAnsi(section.content)}</pre>
            </div>
          ))}
        </NeonScrollbar>
      )}
    </div>
  );
};
