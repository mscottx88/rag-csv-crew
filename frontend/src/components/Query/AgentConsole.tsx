/**
 * Agent Console Component
 * Displays CrewAI agent reasoning and activity logs in an expandable console
 */

import React, { useState } from 'react';
import './AgentConsole.css';

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
        <button className="expand-button" aria-label={isExpanded ? 'Collapse' : 'Expand'}>
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <div className="console-body">
          {sections.map((section, index) => (
            <div key={index} className="console-section">
              <div className="section-title">{section.title}</div>
              <pre className="section-content">{section.content}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
