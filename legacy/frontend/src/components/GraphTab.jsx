import React, { useState, useEffect, useRef } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  Hammer,
  Loader2,
  Share2,
} from 'lucide-react';
import api, { apiGet } from '../api/client';
import ConceptSidePanel from './ConceptSidePanel';

export default function GraphTab() {
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [graphHtml, setGraphHtml] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [selectedConcept, setSelectedConcept] = useState(null);
  const [conceptDetails, setConceptDetails] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [errorMsg, setErrorMsg] = useState(null);
  const iframeRef = useRef(null);

  const fetchGraph = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch JSON graph data
      const dataRes = await api.getGraph();
      if (dataRes && dataRes.data && dataRes.data.nodes && dataRes.data.nodes.length > 0) {
        setGraphData(dataRes.data);
      }

      // 2. Fetch HTML pyvis visualization
      const htmlRes = await api.getGraphHtml();
      if (htmlRes && htmlRes.includes('<html')) {
        setGraphHtml(htmlRes);
      } else if (dataRes && dataRes.html_file) {
        // Fallback directly to backend static if hosted
        setGraphHtml(`<iframe src="http://localhost:8002/static/knowledge_map.html" width="100%" height="100%" frameborder="0"></iframe>`);
      }
    } catch (err) {
      console.warn('Graph load error:', err);
      setErrorMsg('Graph not built yet. Upload PDFs and run pipeline first.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  const handleBuildGraph = async () => {
    setBuilding(true);
    setErrorMsg(null);
    try {
      await api.buildGraph();
      await fetchGraph();
    } catch (err) {
      console.error('Build graph error:', err);
      setErrorMsg('Failed to build graph: ' + err.message);
    } finally {
      setBuilding(false);
    }
  };

  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(prev + 0.2, 2.5));
  };

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(prev - 0.2, 0.4));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
  };

  const handleExportPNG = () => {
    // Attempt printing or export
    if (iframeRef.current) {
      try {
        iframeRef.current.contentWindow?.focus();
        iframeRef.current.contentWindow?.print();
      } catch (_) {
        window.open('http://localhost:8002/static/knowledge_map.html', '_blank');
      }
    } else {
      window.open('http://localhost:8002/static/knowledge_map.html', '_blank');
    }
  };

  const handleSelectConcept = async (conceptName) => {
    setSelectedConcept(conceptName);
    setConceptDetails({ loading: true });
    try {
      const res = await apiGet(`/graph/concept/${encodeURIComponent(conceptName)}`);
      if (res.ok) {
        const details = await res.json();
        setConceptDetails(details);
      } else {
        setConceptDetails({ error: 'Concept details not found.' });
      }
    } catch (err) {
      setConceptDetails({ error: err.message });
    }
  };

  const hasGraph = Boolean(graphHtml || (graphData && graphData.nodes?.length > 0));

  return (
    <div style={styles.container}>
      {/* Top Controls Bar */}
      <div style={styles.controlsBar}>
        <div style={styles.controlsLeft}>
          <span style={styles.graphTitle}>Knowledge Graph</span>
          {graphData && (
            <span style={styles.metaBadge}>
              {graphData.node_count || graphData.nodes?.length || 0} nodes •{' '}
              {graphData.edge_count || graphData.links?.length || 0} edges
            </span>
          )}
        </div>

        <div style={styles.controlsRight}>
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={!hasGraph}
            style={styles.toolBtn}
            title="Zoom In"
          >
            <ZoomIn size={15} />
            <span>Zoom In</span>
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={!hasGraph}
            style={styles.toolBtn}
            title="Zoom Out"
          >
            <ZoomOut size={15} />
            <span>Zoom Out</span>
          </button>
          <button
            type="button"
            onClick={handleResetZoom}
            disabled={!hasGraph}
            style={styles.toolBtn}
            title="Reset Zoom"
          >
            <RotateCcw size={15} />
            <span>Reset</span>
          </button>
          <button
            type="button"
            onClick={handleExportPNG}
            disabled={!hasGraph}
            style={styles.toolBtn}
            title="Export Graph / Print"
          >
            <Download size={15} />
            <span>Export</span>
          </button>
          <button
            type="button"
            onClick={handleBuildGraph}
            disabled={building}
            style={styles.buildBtn}
            title="Trigger knowledge graph generation from SQLite"
          >
            {building ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Hammer size={15} />
            )}
            <span>{building ? 'Building...' : 'Build Graph'}</span>
          </button>
        </div>
      </div>

      {/* Main Visualization Canvas */}
      <div style={styles.viewport}>
        {loading ? (
          <div style={styles.skeletonContainer}>
            <div style={styles.skeletonPulse}></div>
            <div style={styles.skeletonText}>Loading knowledge graph visualization...</div>
          </div>
        ) : !hasGraph ? (
          <div style={styles.emptyContainer}>
            <div style={styles.emptyIcon}>🕸️</div>
            <h3 style={styles.emptyTitle}>Knowledge graph not generated yet</h3>
            <p style={styles.emptySubtitle}>
              Graph not built yet. Upload PDFs and run pipeline first.
            </p>
            <button
              type="button"
              onClick={handleBuildGraph}
              disabled={building}
              style={styles.primaryBuildBtn}
            >
              {building ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Share2 size={16} />
              )}
              <span>{building ? 'Building Graph...' : 'Build Graph Now'}</span>
            </button>
            {errorMsg && <div style={styles.errorText}>{errorMsg}</div>}
          </div>
        ) : (
          <div
            style={{
              ...styles.iframeWrapper,
              transform: `scale(${zoomLevel})`,
              transformOrigin: 'center center',
            }}
          >
            {graphHtml ? (
              <iframe
                ref={iframeRef}
                title="Knowledge Graph Pyvis View"
                srcDoc={graphHtml}
                style={styles.iframe}
                sandbox="allow-scripts allow-same-origin"
              />
            ) : (
              <div style={styles.nodeListFallback}>
                <h4>Concept Nodes ({graphData?.nodes?.length})</h4>
                <div style={styles.nodesPills}>
                  {graphData?.nodes?.map((n) => (
                    <button
                      key={n.id}
                      type="button"
                      onClick={() => handleSelectConcept(n.id)}
                      style={{
                        ...styles.conceptPill,
                        borderColor: n.color || 'var(--accent-primary)',
                      }}
                    >
                      {n.label || n.id}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Side Panel for Concept Details on Click */}
        <ConceptSidePanel
          selectedConcept={selectedConcept}
          conceptDetails={conceptDetails}
          onClose={() => setSelectedConcept(null)}
        />
      </div>
    </div>
  );
}

import { graphStyles as styles } from './graphStyles';

