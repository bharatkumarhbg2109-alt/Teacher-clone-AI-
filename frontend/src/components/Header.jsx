import React from 'react';
import { MessageSquare, Network, BookOpen, Circle } from 'lucide-react';

export default function Header({ activeTab, onTabChange, backendStatus = 'online', ragActive = false }) {
  const tabs = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'graph', label: 'Graph', icon: Network },
    { id: 'curriculum', label: 'Curriculum', icon: BookOpen },
  ];

  return (
    <header style={styles.header}>
      {/* Tab Navigation */}
      <nav style={styles.tabNav} aria-label="Main Navigation">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              style={{
                ...styles.tabBtn,
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                borderBottom: isActive ? '2px solid var(--accent-primary)' : '2px solid transparent',
              }}
              title={`Switch to ${tab.label}`}
            >
              <Icon size={16} color={isActive ? 'var(--accent-primary)' : 'currentColor'} />
              <span style={{ fontWeight: isActive ? '600' : '400' }}>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Right side: RAG Indicator + Model Indicator Chip */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            color: ragActive ? 'var(--green)' : 'var(--text-muted)',
            padding: '3px 8px',
            background: ragActive ? 'rgba(63,185,80,0.1)' : 'transparent',
            borderRadius: '12px',
            border: `1px solid ${ragActive ? 'rgba(63,185,80,0.3)' : 'transparent'}`,
          }}
          title={ragActive ? 'RAG active: using uploaded study materials' : 'No RAG context active'}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: ragActive ? 'var(--green)' : 'var(--text-muted)',
            }}
          />
          {ragActive ? 'RAG Active' : 'No RAG'}
        </div>

        <div style={styles.modelChip} title={`Ollama LLM: llama3.1:8b (${backendStatus})`}>
          <Circle
            size={8}
            fill={backendStatus === 'online' ? 'var(--green)' : 'var(--red)'}
            color={backendStatus === 'online' ? 'var(--green)' : 'var(--red)'}
          />
          <span style={styles.modelText}>llama3.1:8b</span>
          <span style={styles.statusBadge}>
            {backendStatus === 'online' ? 'Local' : 'Offline'}
          </span>
        </div>
      </div>
    </header>
  );
}

const styles = {
  header: {
    height: '52px',
    minHeight: '52px',
    backgroundColor: 'var(--bg-secondary)',
    borderBottom: '1px solid var(--border-color)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
    userSelect: 'none',
    zIndex: 10,
  },
  tabNav: {
    display: 'flex',
    gap: '8px',
    height: '100%',
  },
  tabBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'none',
    border: 'none',
    padding: '0 16px',
    cursor: 'pointer',
    fontSize: '14px',
    fontFamily: 'var(--font-sans)',
    transition: 'color 0.15s ease, border-color 0.15s ease',
  },
  modelChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'var(--bg-tertiary)',
    border: '1px solid var(--border-color)',
    borderRadius: '20px',
    padding: '4px 12px',
    fontSize: '12px',
    color: 'var(--text-secondary)',
  },
  modelText: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-primary)',
    fontWeight: '500',
  },
  statusBadge: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    borderLeft: '1px solid var(--border-color)',
    paddingLeft: '6px',
  },
};
