import React, { useState, useEffect } from 'react';
import { Search, Sparkles, Loader2 } from 'lucide-react';
import api from '../api/client';
import ChapterCard from './ChapterCard';
import { curriculumStyles as styles } from './curriculumStyles';

const STORAGE_PROGRESS_KEY = 'ai_teacher_curriculum_progress';

export default function CurriculumTab({ onStartLearning }) {
  const [chapters, setChapters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedChapterId, setExpandedChapterId] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Progress state: Set of completed chapter IDs saved to localStorage
  const [completedChapters, setCompletedChapters] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_PROGRESS_KEY);
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch (_) {
      return new Set();
    }
  });

  const fetchCurriculum = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await api.getCurriculum();
      if (Array.isArray(data) && data.length > 0) {
        setChapters(data);
        if (data[0]) {
          setExpandedChapterId(data[0].id || data[0].chapter_num || 1);
        }
      } else {
        setChapters([]);
      }
    } catch (err) {
      console.warn('Curriculum fetch error:', err);
      setErrorMsg('No curriculum found. Generate one below.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCurriculum();
  }, []);

  const handleToggleComplete = (chapterId) => {
    setCompletedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      try {
        localStorage.setItem(STORAGE_PROGRESS_KEY, JSON.stringify(Array.from(next)));
      } catch (_) {}
      return next;
    });
  };

  const handleGenerateCurriculum = async () => {
    setGenerating(true);
    setErrorMsg(null);
    try {
      await api.generateCurriculum();
      await fetchCurriculum();
    } catch (err) {
      console.error('Generate curriculum failed:', err);
      setErrorMsg('Generation failed: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const toggleAccordion = (chapterId) => {
    setExpandedChapterId((prev) => (prev === chapterId ? null : chapterId));
  };

  const handleStartChapter = (chapter) => {
    const title = chapter.title || `Chapter ${chapter.chapter_num || ''}`;
    const topics = Array.isArray(chapter.topic_list)
      ? chapter.topic_list.join(', ')
      : '';
    const prompt = `Let's start learning ${title}.${topics ? ` Key topics include: ${topics}.` : ''} Can you give me an introduction and initial concepts?`;
    if (onStartLearning) {
      onStartLearning(prompt);
    }
  };

  const filteredChapters = chapters.filter((c) => {
    const title = (c.title || `Chapter ${c.chapter_num || ''}`).toLowerCase();
    const desc = (c.description || '').toLowerCase();
    const q = searchQuery.toLowerCase();
    return title.includes(q) || desc.includes(q);
  });

  const progressPercent =
    chapters.length > 0
      ? Math.round((completedChapters.size / chapters.length) * 100)
      : 0;

  return (
    <div style={styles.container}>
      {/* Header Bar */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Learning Curriculum</h2>
          <p style={styles.subtitle}>
            Sequential study path auto-structured from your study materials
          </p>
        </div>

        {chapters.length > 0 && (
          <div style={styles.progressBadge} title="Overall curriculum progress">
            <span style={styles.progressLabel}>Completed:</span>
            <span style={styles.progressValue}>
              {completedChapters.size} / {chapters.length} ({progressPercent}%)
            </span>
          </div>
        )}
      </div>

      {/* Filter / Search Bar */}
      {chapters.length > 0 && (
        <div style={styles.searchBarRow}>
          <div style={styles.searchBox}>
            <Search size={15} color="var(--text-secondary)" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chapters or topics..."
              style={styles.searchInput}
            />
          </div>
        </div>
      )}

      {/* Content Body */}
      <div style={styles.content}>
        {loading ? (
          <div style={styles.centerBox}>
            <Loader2 size={32} className="animate-spin" color="var(--accent-primary)" />
            <p style={styles.loadingText}>Loading curriculum chapters...</p>
          </div>
        ) : chapters.length === 0 ? (
          <div style={styles.emptyCard}>
            <div style={styles.emptyIcon}>📚</div>
            <h3 style={styles.emptyTitle}>No curriculum yet</h3>
            <p style={styles.emptyText}>
              Upload PDFs and click below to auto-generate structured chapters with the AI Louvain pipeline.
            </p>
            <button
              type="button"
              onClick={handleGenerateCurriculum}
              disabled={generating}
              style={styles.generateBtn}
            >
              {generating ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              <span>{generating ? 'Generating Chapters...' : 'Generate Curriculum'}</span>
            </button>
            {errorMsg && <div style={styles.errorText}>{errorMsg}</div>}
          </div>
        ) : filteredChapters.length === 0 ? (
          <div style={styles.centerBox}>
            <p style={styles.loadingText}>No chapters match "{searchQuery}"</p>
          </div>
        ) : (
          <div style={styles.chapterList}>
            {filteredChapters.map((ch, idx) => {
              const chId = ch.id || ch.chapter_num || idx + 1;
              return (
                <ChapterCard
                  key={chId}
                  ch={ch}
                  idx={idx}
                  isExpanded={expandedChapterId === chId}
                  isDone={completedChapters.has(chId)}
                  onToggleExpand={toggleAccordion}
                  onToggleComplete={handleToggleComplete}
                  onStartChapter={handleStartChapter}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
