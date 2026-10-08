import React from 'react';
import {
  CheckCircle2,
  Circle,
  Clock,
  Play,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { curriculumStyles as styles } from './curriculumStyles';

export default function ChapterCard({
  ch,
  idx,
  isExpanded,
  isDone,
  onToggleExpand,
  onToggleComplete,
  onStartChapter,
}) {
  const chId = ch.id || ch.chapter_num || idx + 1;
  const chNum = ch.chapter_num || idx + 1;
  const duration = ch.duration || `${15 + (idx % 4) * 10} mins`;
  const topics = Array.isArray(ch.topic_list) ? ch.topic_list : [];
  const concepts = Array.isArray(ch.concept_list) ? ch.concept_list : [];

  return (
    <div
      style={{
        ...styles.chapterCard,
        borderColor: isExpanded ? 'var(--border-color)' : 'var(--border-subtle)',
      }}
    >
      {/* Chapter Header Row */}
      <div
        style={styles.chapterHeader}
        onClick={() => onToggleExpand(chId)}
      >
        <div style={styles.headerLeft}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleComplete(chId);
            }}
            style={styles.checkboxBtn}
            title={isDone ? 'Mark as incomplete' : 'Mark as complete'}
          >
            {isDone ? (
              <CheckCircle2 size={18} color="var(--green)" />
            ) : (
              <Circle size={18} color="var(--text-muted)" />
            )}
          </button>

          <div style={styles.chapterInfo}>
            <span style={styles.chapterNumber}>Chapter {chNum}</span>
            <h4
              style={{
                ...styles.chapterTitle,
                textDecoration: isDone ? 'line-through' : 'none',
                color: isDone ? 'var(--text-muted)' : 'var(--text-primary)',
              }}
            >
              {ch.title || `Chapter ${chNum}`}
            </h4>
          </div>
        </div>

        <div style={styles.headerRight}>
          <div style={styles.durationChip}>
            <Clock size={12} />
            <span>{duration}</span>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStartChapter(ch);
            }}
            style={styles.startLearningBtn}
            title="Start learning in Chat"
          >
            <Play size={12} fill="currentColor" />
            <span>Start Learning</span>
          </button>
          <div style={styles.expandIcon}>
            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </div>
        </div>
      </div>

      {/* Accordion Expandable Details */}
      {isExpanded && (
        <div style={styles.chapterBody}>
          {ch.description && (
            <p style={styles.chapterDesc}>{ch.description}</p>
          )}

          {topics.length > 0 && (
            <div style={styles.subSection}>
              <span style={styles.subSectionTitle}>Sub-topics:</span>
              <div style={styles.topicPills}>
                {topics.map((t, i) => (
                  <span key={i} style={styles.topicPill}>
                    {typeof t === 'string' ? t : t.title || t.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {concepts.length > 0 && (
            <div style={styles.subSection}>
              <span style={styles.subSectionTitle}>Core Concepts:</span>
              <div style={styles.conceptChips}>
                {concepts.map((c, i) => (
                  <span key={i} style={styles.conceptChip}>
                    🏷️ {typeof c === 'string' ? c : c.name || c.id}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
