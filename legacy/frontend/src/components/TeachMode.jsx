import React, { useState } from 'react';
import { apiPost, apiFetch } from '../api/client';

const BEAT_ICONS = ['🎣', '🧠', '💡', '🔗', '🔬', '✅', '📝'];

export default function TeachMode({ source, onBack }) {
  const [session, setSession] = useState(null);
  const [beats, setBeats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [followup, setFollowup] = useState('');
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizResult, setQuizResult] = useState({});

  const startLesson = async () => {
    setLoading(true);
    try {
      const res = await apiPost('/teach/start', {
        source_id: source.id || source.file_id || '',
        source_name: source.filename || source.name || 'Study Material',
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
        setLoading(false);
        return;
      }
      setSession(data);
      setBeats([
        {
          beat_label: data.beat_label,
          content: data.content,
          is_quiz: false,
        },
      ]);
    } catch (err) {
      alert('Failed to start lesson: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const nextBeat = async () => {
    if (!session) return;
    const nextIndex = beats.length;
    if (nextIndex >= 7) return;
    setLoading(true);
    try {
      const res = await apiPost('/teach/next-beat', {
        session_id: session.session_id,
        beat_index: nextIndex,
      });
      const data = await res.json();
      if (data.error && !data.lesson_done) {
        alert(data.error);
        return;
      }
      setBeats((prev) => [...prev, data]);
    } catch (err) {
      alert('Failed to load next beat: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const askFollowup = async () => {
    if (!followup.trim() || !session) return;
    const userQuestion = followup.trim();
    setFollowup('');
    setLoading(true);
    try {
      const res = await apiFetch(
        `/teach/followup?session_id=${session.session_id}&question=${encodeURIComponent(userQuestion)}`,
        { method: 'POST' }
      );
      const data = await res.json();
      setBeats((prev) => [
        ...prev,
        {
          beat_label: `💬 Q: ${userQuestion}`,
          content: data.answer || 'No answer generated.',
          is_quiz: false,
          is_followup: true,
        },
      ]);
    } catch (err) {
      alert('Follow-up error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const checkQuizAnswer = (beatIndex, qIndex, chosen) => {
    const beat = beats[beatIndex];
    if (!beat?.quiz_data) return;
    const q = beat.quiz_data[qIndex];
    const correctLetter = (q.answer || '').trim().toUpperCase();
    const chosenLetter = chosen.trim().toUpperCase();
    const correct = chosenLetter === correctLetter || chosenLetter.startsWith(correctLetter);

    setQuizResult((prev) => ({
      ...prev,
      [`${beatIndex}-${qIndex}`]: {
        chosen,
        correct,
        explanation: q.explanation || 'No explanation provided.',
      },
    }));
  };

  const currentBeatIndex = beats.length - 1;
  const lessonComplete = beats.length === 7;
  const displayTitle = (source.filename || source.name || 'Study Material')
    .replace(/\.pdf$/i, '')
    .replace(/_/g, ' ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        <button
          onClick={onBack}
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: '20px',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
          }}
          title="Back to Chat"
        >
          ←
        </button>
        <div>
          <div style={{ fontWeight: 500, fontSize: '15px', color: 'var(--text-primary)' }}>
            Teaching: {displayTitle}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Beat {Math.min(beats.length, 7)} of 7
          </div>
        </div>

        {/* Progress dots */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
          {BEAT_ICONS.map((icon, i) => (
            <span
              key={i}
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '13px',
                background:
                  i < beats.length ? 'rgba(59,130,246,0.3)' : 'rgba(255,255,255,0.05)',
                border: i === currentBeatIndex ? '1px solid #3b82f6' : '1px solid transparent',
              }}
            >
              {icon}
            </span>
          ))}
        </div>
      </div>

      {/* Beat cards scrollable area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {/* Start screen */}
        {beats.length === 0 && !loading && (
          <div style={{ textAlign: 'center', paddingTop: '60px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎓</div>
            <h2 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>
              Ready to learn {displayTitle}?
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
              AI will guide you step by step through a structured 7-beat pedagogical arc
            </p>
            <button
              onClick={startLesson}
              type="button"
              style={{
                padding: '12px 32px',
                background: 'var(--accent-primary, #3b82f6)',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '15px',
                fontWeight: 500,
              }}
            >
              Start Lesson 🚀
            </button>
          </div>
        )}

        {/* Beat cards */}
        {beats.map((beat, beatIndex) => (
          <div
            key={beatIndex}
            style={{
              background: beat.is_followup ? 'rgba(59,130,246,0.06)' : 'var(--bg-tertiary)',
              border: `1px solid ${beat.is_followup ? 'rgba(59,130,246,0.2)' : 'var(--border-color)'}`,
              borderRadius: '12px',
              padding: '16px 20px',
            }}
          >
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: '#79c0ff',
                marginBottom: '10px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {beat.beat_label}
            </div>

            {/* Quiz beat — render interactive cards */}
            {beat.is_quiz && beat.quiz_data && Array.isArray(beat.quiz_data) ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {beat.quiz_data.map((q, qi) => {
                  const result = quizResult[`${beatIndex}-${qi}`];
                  return (
                    <div
                      key={qi}
                      style={{
                        background: 'rgba(0,0,0,0.2)',
                        borderRadius: '8px',
                        padding: '14px',
                      }}
                    >
                      <p style={{ marginBottom: '10px', fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                        {qi + 1}. {q.q}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {q.options?.map((opt, oi) => {
                          const letter = opt.split('.')[0].trim().toUpperCase();
                          const chosen = result?.chosen === letter;
                          const correct = result?.correct;
                          const isKeyAnswer = letter === (q.answer || '').trim().toUpperCase();

                          return (
                            <button
                              key={oi}
                              type="button"
                              onClick={() => !result && checkQuizAnswer(beatIndex, qi, letter)}
                              style={{
                                padding: '8px 12px',
                                textAlign: 'left',
                                borderRadius: '6px',
                                cursor: result ? 'default' : 'pointer',
                                fontSize: '13px',
                                background: !result
                                  ? 'rgba(255,255,255,0.05)'
                                  : isKeyAnswer
                                  ? 'rgba(63,185,80,0.2)'
                                  : chosen
                                  ? 'rgba(248,81,73,0.2)'
                                  : 'rgba(255,255,255,0.03)',
                                border: chosen
                                  ? '1px solid ' + (correct ? '#3fb950' : '#f85149')
                                  : isKeyAnswer && result
                                  ? '1px solid #3fb950'
                                  : '1px solid rgba(255,255,255,0.1)',
                                color: 'var(--text-primary)',
                              }}
                            >
                              {opt}
                            </button>
                          );
                        })}
                      </div>
                      {result && (
                        <div
                          style={{
                            marginTop: '10px',
                            fontSize: '12px',
                            padding: '8px 12px',
                            background: result.correct
                              ? 'rgba(63,185,80,0.1)'
                              : 'rgba(248,81,73,0.1)',
                            borderRadius: '6px',
                            color: result.correct ? '#3fb950' : '#f85149',
                          }}
                        >
                          {result.correct ? '✓ Correct! ' : '✗ Incorrect. '}
                          {result.explanation}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div
                style={{
                  fontSize: '14px',
                  lineHeight: '1.7',
                  color: 'var(--text-primary)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {beat.content}
              </div>
            )}
          </div>
        ))}

        {/* Loading spinner */}
        {loading && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              color: 'var(--text-secondary)',
              fontSize: '13px',
              padding: '12px 16px',
              background: 'var(--bg-tertiary)',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
            }}
          >
            <span
              style={{
                width: '14px',
                height: '14px',
                border: '2px solid #3b82f6',
                borderTopColor: 'transparent',
                borderRadius: '50%',
                animation: 'spin 0.7s linear infinite',
                display: 'inline-block',
              }}
            />
            AI Teacher is thinking...
          </div>
        )}

        {/* Lesson complete screen */}
        {lessonComplete && (
          <div
            style={{
              textAlign: 'center',
              padding: '20px',
              background: 'rgba(63,185,80,0.08)',
              border: '1px solid rgba(63,185,80,0.2)',
              borderRadius: '12px',
            }}
          >
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>🎉</div>
            <p style={{ color: '#3fb950', fontWeight: 500, marginBottom: '4px' }}>
              Lesson Complete!
            </p>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Ask any follow-up questions below or return to chat.
            </p>
          </div>
        )}
      </div>

      {/* Bottom: Next Beat button + Follow-up Q&A input */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border-color)',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        {beats.length > 0 && !lessonComplete && !loading && (
          <button
            onClick={nextBeat}
            type="button"
            style={{
              width: '100%',
              padding: '10px',
              marginBottom: '10px',
              background: 'rgba(59,130,246,0.15)',
              color: '#79c0ff',
              border: '1px solid rgba(59,130,246,0.3)',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            Next: {BEAT_ICONS[beats.length]}{' '}
            {
              ['Hook', 'Concept', 'Example', 'Analogy', 'Deep Dive', 'Quiz', 'Summary'][
                beats.length
              ]
            }{' '}
            →
          </button>
        )}

        {/* Follow-up question input */}
        {beats.length > 0 && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              value={followup}
              onChange={(e) => setFollowup(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && askFollowup()}
              placeholder="Ask a follow-up question on this topic..."
              style={{
                flex: 1,
                padding: '8px 12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            />
            <button
              onClick={askFollowup}
              disabled={!followup.trim() || loading}
              type="button"
              style={{
                padding: '8px 16px',
                background: '#3b82f6',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: !followup.trim() || loading ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                opacity: !followup.trim() || loading ? 0.6 : 1,
              }}
            >
              Ask
            </button>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
