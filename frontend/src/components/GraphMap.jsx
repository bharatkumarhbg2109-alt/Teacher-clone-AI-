import React, { useState, useEffect, useCallback } from 'react';
import { apiGet } from '../api/client';

// Chapter colors — matches backend COLORS array
const CHAPTER_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
];

const API_BASE = (typeof process !== 'undefined' && process.env && process.env.NEXT_PUBLIC_API_URL)
  ? process.env.NEXT_PUBLIC_API_URL
  : 'http://localhost:8002';

const styles = {
  container: {
    display: 'flex',
    minHeight: '100vh',
    background: '#0f0f1a',
    color: 'white',
    fontFamily: "'Inter', -apple-system, sans-serif",
  },
  main: {
    flex: 1,
    padding: '20px',
    overflow: 'auto',
  },
  sidebar: {
    width: '300px',
    background: '#1a1a2e',
    borderLeft: '1px solid #2a2a4a',
    padding: '20px',
    overflow: 'auto',
    flexShrink: 0,
  },
  header: {
    fontSize: '24px',
    fontWeight: 'bold',
    marginBottom: '16px',
    background: 'linear-gradient(135deg, #4ECDC4, #45B7D1)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  tabs: {
    display: 'flex',
    gap: '8px',
    marginBottom: '16px',
  },
  tab: (active) => ({
    padding: '8px 20px',
    borderRadius: '20px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: active ? '600' : '400',
    background: active ? '#4ECDC4' : '#2a2a4a',
    color: active ? '#0f0f1a' : '#aaa',
    transition: 'all 0.2s',
  }),
  chapterLegend: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    marginTop: '12px',
    marginBottom: '16px',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: '#ccc',
  },
  legendDot: (color) => ({
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
  }),
  filterContainer: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginBottom: '12px',
  },
  select: {
    padding: '6px 12px',
    borderRadius: '8px',
    border: '1px solid #2a2a4a',
    background: '#1a1a2e',
    color: 'white',
    fontSize: '13px',
  },
  chapterCard: {
    background: '#1a1a2e',
    border: '1px solid #2a2a4a',
    borderRadius: '12px',
    padding: '16px',
    marginBottom: '12px',
    transition: 'border-color 0.2s',
  },
  chapterHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
  },
  chapterTitle: {
    fontSize: '16px',
    fontWeight: '600',
  },
  chapterMeta: {
    fontSize: '12px',
    color: '#888',
    marginTop: '4px',
  },
  chipRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    marginTop: '8px',
  },
  chip: (color, small = false) => ({
    padding: small ? '2px 8px' : '4px 10px',
    borderRadius: '12px',
    fontSize: small ? '11px' : '12px',
    background: color + '22',
    color: color,
    border: `1px solid ${color}44`,
    cursor: 'pointer',
    transition: 'all 0.2s',
  }),
  sidebarTitle: {
    fontSize: '18px',
    fontWeight: '600',
    marginBottom: '12px',
  },
  sidebarSection: {
    marginBottom: '16px',
  },
  sidebarLabel: {
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    color: '#888',
    marginBottom: '6px',
  },
  sidebarValue: {
    fontSize: '14px',
    color: '#ddd',
  },
  prereqList: {
    listStyle: 'none',
    padding: 0,
    margin: 0,
  },
  prereqItem: {
    padding: '4px 0',
    fontSize: '13px',
    color: '#aaa',
    borderBottom: '1px solid #2a2a4a',
  },
  emptyState: {
    textAlign: 'center',
    color: '#666',
    padding: '40px',
    fontSize: '14px',
  },
};

export default function GraphMap() {
  const [activeView, setActiveView] = useState('pyvis');
  const [curriculum, setCurriculum] = useState([]);
  const [expandedChapter, setExpandedChapter] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [conceptData, setConceptData] = useState(null);
  const [filterChapter, setFilterChapter] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch curriculum on mount
  useEffect(() => {
    apiGet('/curriculum')
      .then((r) => r.json())
      .then(setCurriculum)
      .catch(() => {});
  }, []);

  // Fetch concept details when selected
  useEffect(() => {
    if (!selectedNode) {
      setConceptData(null);
      return;
    }
    apiGet(`/graph/concept/${encodeURIComponent(selectedNode)}`)
      .then((r) => r.json())
      .then(setConceptData)
      .catch(() => setConceptData(null));
  }, [selectedNode]);

  const getChapterColor = (id) => {
    if (id == null) return '#CCCCCC';
    return CHAPTER_COLORS[id % CHAPTER_COLORS.length];
  };

  const handleConceptClick = (name) => {
    setSelectedNode(name);
  };

  return (
    <div style={styles.container}>
      <div style={styles.main}>
        <div style={styles.header}>Knowledge Graph Explorer</div>

        {/* Tabs */}
        <div style={styles.tabs}>
          <button
            style={styles.tab(activeView === 'pyvis')}
            onClick={() => setActiveView('pyvis')}
          >
            🗺️ Knowledge Map
          </button>
          <button
            style={styles.tab(activeView === 'curriculum')}
            onClick={() => setActiveView('curriculum')}
          >
            📚 Curriculum
          </button>
        </div>

        {/* Chapter filter */}
        <div style={styles.filterContainer}>
          <select
            style={styles.select}
            value={filterChapter || ''}
            onChange={(e) => setFilterChapter(e.target.value || null)}
          >
            <option value="">All Chapters</option>
            {curriculum.map((ch) => (
              <option key={ch.community_id} value={ch.community_id}>
                Ch {ch.chapter_num}: {ch.chapter_name}
              </option>
            ))}
          </select>
        </div>

        {/* Pyvis Tab */}
        {activeView === 'pyvis' && (
          <>
            <iframe
              src={`${API_BASE.replace(':8000', ':8002')}/static/knowledge_map.html${filterChapter ? `?chapter=${filterChapter}` : ''}`}
              width="100%"
              height="700px"
              style={{ border: 'none', borderRadius: '8px' }}
              title="Knowledge Map"
            />
            {/* Chapter Legend */}
            <div style={styles.chapterLegend}>
              {curriculum.map((ch) => (
                <div key={ch.community_id} style={styles.legendItem}>
                  <div style={styles.legendDot(getChapterColor(ch.community_id))} />
                  <span>Ch {ch.chapter_num}: {ch.chapter_name}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Curriculum Tab */}
        {activeView === 'curriculum' && (
          <div>
            {curriculum.length === 0 && (
              <div style={styles.emptyState}>
                No curriculum generated yet. Run <code>/generate-curriculum</code> first.
              </div>
            )}
            {curriculum.map((ch) => {
              const isExpanded = expandedChapter === ch.id;
              const color = getChapterColor(ch.community_id);
              return (
                <div key={ch.id} style={{ ...styles.chapterCard, borderColor: isExpanded ? color : '#2a2a4a' }}>
                  <div
                    style={styles.chapterHeader}
                    onClick={() => setExpandedChapter(isExpanded ? null : ch.id)}
                  >
                    <div>
                      <div style={{ ...styles.chapterTitle, color }}>
                        Ch {ch.chapter_num}: {ch.chapter_name}
                      </div>
                      <div style={styles.chapterMeta}>
                        {ch.estimated_hours}h • {ch.topic_list?.length || 0} topics • {ch.concept_list?.length || 0} concepts
                      </div>
                    </div>
                    <span style={{ color: '#888', fontSize: '18px' }}>
                      {isExpanded ? '▼' : '▶'}
                    </span>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: '12px' }}>
                      <div style={{ fontSize: '13px', color: '#aaa', marginBottom: '8px' }}>
                        {ch.chapter_description}
                      </div>
                      {ch.topic_list?.length > 0 && (
                        <div style={{ marginBottom: '8px' }}>
                          <div style={styles.sidebarLabel}>Topics</div>
                          <div style={styles.chipRow}>
                            {ch.topic_list.map((t) => (
                              <span
                                key={t}
                                style={styles.chip(color)}
                                onClick={() => handleConceptClick(t)}
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {ch.concept_list?.length > 0 && (
                        <div>
                          <div style={styles.sidebarLabel}>Concepts</div>
                          <div style={styles.chipRow}>
                            {ch.concept_list.map((c) => (
                              <span
                                key={c}
                                style={styles.chip(color, true)}
                                onClick={() => handleConceptClick(c)}
                              >
                                {c}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Sidebar — Concept Details */}
      {selectedNode && (
        <div style={styles.sidebar}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={styles.sidebarTitle}>{selectedNode}</div>
            <button
              onClick={() => setSelectedNode(null)}
              style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '18px' }}
            >
              ✕
            </button>
          </div>

          {conceptData ? (
            <>
              {conceptData.neighbors?.error ? (
                <div style={styles.emptyState}>{conceptData.neighbors.error}</div>
              ) : (
                <>
                  {/* Prerequisites */}
                  {conceptData.prerequisites?.length > 0 && (
                    <div style={styles.sidebarSection}>
                      <div style={styles.sidebarLabel}>Prerequisites (learn first)</div>
                      <ol style={styles.prereqList}>
                        {conceptData.prerequisites.map((p, i) => (
                          <li
                            key={i}
                            style={styles.prereqItem}
                            onClick={() => handleConceptClick(p)}
                          >
                            {p}
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* Neighbors */}
                  {conceptData.neighbors?.neighbors?.length > 0 && (
                    <div style={styles.sidebarSection}>
                      <div style={styles.sidebarLabel}>Connected Concepts</div>
                      {conceptData.neighbors.neighbors.map((n) => (
                        <div
                          key={n.name}
                          style={{ ...styles.prereqItem, display: 'flex', justifyContent: 'space-between' }}
                          onClick={() => handleConceptClick(n.name)}
                        >
                          <span>{n.name}</span>
                          <span style={{ fontSize: '11px', color: '#666' }}>
                            {n.relation} (d{n.depth})
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          ) : (
            <div style={styles.emptyState}>Loading...</div>
          )}
        </div>
      )}
    </div>
  );
}
