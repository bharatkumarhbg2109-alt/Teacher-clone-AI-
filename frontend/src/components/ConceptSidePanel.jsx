import React from 'react';
import { Info, X, Loader2 } from 'lucide-react';
import { graphStyles as styles } from './graphStyles';

export default function ConceptSidePanel({ selectedConcept, conceptDetails, onClose }) {
  if (!selectedConcept) return null;

  return (
    <div style={styles.conceptPanel}>
      <div style={styles.panelHeader}>
        <div style={styles.panelTitleRow}>
          <Info size={16} color="var(--accent-primary)" />
          <h4 style={styles.panelTitle}>{selectedConcept}</h4>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={styles.closePanelBtn}
        >
          <X size={15} />
        </button>
      </div>

      <div style={styles.panelBody}>
        {conceptDetails?.loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Loader2 size={14} className="animate-spin" />
            <span>Loading prerequisites & neighbors...</span>
          </div>
        ) : conceptDetails?.error ? (
          <div style={styles.errorText}>{conceptDetails.error}</div>
        ) : (
          <>
            <div style={styles.detailSection}>
              <span style={styles.sectionLabel}>Prerequisites Chain:</span>
              {conceptDetails?.prerequisites?.length > 0 ? (
                <ul style={styles.conceptList}>
                  {conceptDetails.prerequisites.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              ) : (
                <span style={styles.subtleText}>No prerequisite dependencies found</span>
              )}
            </div>

            <div style={styles.detailSection}>
              <span style={styles.sectionLabel}>Related Neighbors:</span>
              {conceptDetails?.neighbors && typeof conceptDetails.neighbors === 'object' ? (
                <div style={styles.neighborsGrid}>
                  {Object.entries(conceptDetails.neighbors).map(([k, v]) => (
                    <div key={k} style={styles.neighborItem}>
                      <strong>{k}:</strong> {Array.isArray(v) ? v.join(', ') : String(v)}
                    </div>
                  ))}
                </div>
              ) : (
                <span style={styles.subtleText}>No direct neighbors recorded</span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
