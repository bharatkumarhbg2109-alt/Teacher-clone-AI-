import React, { useState } from 'react';
import { apiFetch, apiPost } from '../api/client';

export default function QuestionPractice({ onBack }) {
  const [step, setStep] = useState('upload'); // upload | analyze | generate | practice
  const [patternId, setPatternId] = useState(null);
  const [pattern, setPattern] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [pastedText, setPastedText] = useState('');
  const [currentQ, setCurrentQ] = useState(0);
  const [answer, setAnswer] = useState('');
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const [genCount, setGenCount] = useState(10);
  const [errorMsg, setErrorMsg] = useState(null);

  const uploadQuestions = async (e) => {
    const file = e?.target?.files?.[0];
    setErrorMsg(null);
    setLoading(true);

    try {
      let res;
      if (file) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('name', file.name);
        res = await apiFetch('/questions/upload-reference', {
          method: 'POST',
          body: fd,
        });
      } else if (pastedText.trim()) {
        res = await apiFetch(
          `/questions/paste-reference?name=Reference+Questions&raw_text=${encodeURIComponent(
            pastedText.trim()
          )}`,
          { method: 'POST' }
        );
      } else {
        setLoading(false);
        return;
      }

      const data = await res.json();
      if (data.error) {
        setErrorMsg(data.error);
        setLoading(false);
        return;
      }
      setPatternId(data.pattern_id);
      setStep('analyze');
    } catch (err) {
      setErrorMsg('Failed to save reference questions: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const analyzePattern = async () => {
    setErrorMsg(null);
    setLoading(true);
    try {
      const res = await apiPost('/questions/analyze', { pattern_id: patternId });
      const data = await res.json();
      if (data.error) {
        setErrorMsg(data.error);
        setLoading(false);
        return;
      }
      setPattern(data.pattern);
      setStep('generate');
    } catch (err) {
      setErrorMsg('Pattern analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const generateQuestions = async () => {
    setErrorMsg(null);
    setLoading(true);
    try {
      const res = await apiPost('/questions/generate', { pattern_id: patternId, count: Number(genCount) || 10 });
      const data = await res.json();
      if (data.error) {
        setErrorMsg(data.error);
        setLoading(false);
        return;
      }
      const qs = (data.questions || []).map((q, i) => ({
        ...q,
        id: data.question_ids ? data.question_ids[i] : 'q-' + i,
      }));
      setQuestions(qs);
      setStep('practice');
    } catch (err) {
      setErrorMsg('Question generation failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    const q = questions[currentQ];
    if (!q || !answer.trim()) return;
    setErrorMsg(null);
    setLoading(true);

    try {
      const res = await apiPost('/questions/grade', { question_id: q.id, user_answer: answer });
      const data = await res.json();
      setResults((prev) => ({ ...prev, [currentQ]: data }));
    } catch (err) {
      setErrorMsg('Grading failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const score = Object.values(results).filter((r) => r.is_correct).length;

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
        <div style={{ fontWeight: 500, fontSize: '15px', color: 'var(--text-primary)' }}>
          Exam Question Practice
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          {['upload', 'analyze', 'generate', 'practice'].map((s, i) => (
            <div
              key={s}
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background:
                  ['upload', 'analyze', 'generate', 'practice'].indexOf(step) >= i
                    ? '#3b82f6'
                    : 'rgba(255,255,255,0.15)',
              }}
              title={`Step ${i + 1}: ${s}`}
            />
          ))}
        </div>
      </div>

      {errorMsg && (
        <div
          style={{
            padding: '10px 20px',
            background: 'rgba(248,81,73,0.15)',
            color: '#f85149',
            fontSize: '13px',
            borderBottom: '1px solid rgba(248,81,73,0.3)',
          }}
        >
          ⚠️ {errorMsg}
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
        {/* STEP 1: Upload / Paste Reference Questions */}
        {step === 'upload' && (
          <div style={{ maxWidth: '520px', margin: '0 auto' }}>
            <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>
              Upload Reference Questions
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
              Upload past papers or question banks (50–70 questions). AI will extract the pattern and generate twin questions from your study materials.
            </p>

            {/* File upload card */}
            <label
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '24px',
                border: '2px dashed var(--border-color)',
                borderRadius: '10px',
                cursor: 'pointer',
                marginBottom: '16px',
                background: 'rgba(255,255,255,0.02)',
              }}
            >
              <span style={{ fontSize: '32px', marginBottom: '8px' }}>📄</span>
              <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                Click to upload a .txt file with reference questions
              </span>
              <input type="file" accept=".txt" hidden onChange={uploadQuestions} />
            </label>

            <div
              style={{
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '12px',
                marginBottom: '12px',
              }}
            >
              OR PASTE DIRECTLY
            </div>

            <textarea
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder={
                "Paste reference questions here...\n\nQ1. What is transfer learning?\n(A) Training from scratch\n(B) Reusing pre-trained weights\n(C) Data cleaning\n(D) Data augmentation"
              }
              rows={8}
              style={{
                width: '100%',
                padding: '12px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '13px',
                resize: 'vertical',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
            />

            <button
              onClick={() => uploadQuestions(null)}
              disabled={!pastedText.trim() || loading}
              type="button"
              style={{
                marginTop: '12px',
                width: '100%',
                padding: '12px',
                background: '#3b82f6',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: !pastedText.trim() || loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: 500,
                opacity: !pastedText.trim() || loading ? 0.6 : 1,
              }}
            >
              {loading ? 'Saving...' : 'Save Questions →'}
            </button>
          </div>
        )}

        {/* STEP 2: Analyze Pattern */}
        {step === 'analyze' && (
          <div style={{ maxWidth: '500px', margin: '0 auto', textAlign: 'center', paddingTop: '40px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
            <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>Questions Saved!</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '24px' }}>
              Now AI will analyze the exam pattern — question types, difficulty, marks distribution, and language style.
            </p>
            <button
              onClick={analyzePattern}
              disabled={loading}
              type="button"
              style={{
                padding: '12px 32px',
                background: '#3b82f6',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              {loading ? 'Analyzing Pattern with AI...' : 'Analyze Pattern →'}
            </button>
          </div>
        )}

        {/* STEP 3: Pattern Review & Generate */}
        {step === 'generate' && pattern && (
          <div style={{ maxWidth: '560px', margin: '0 auto' }}>
            <h3 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>Pattern Detected ✅</h3>

            {/* Pattern summary cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '10px',
                marginBottom: '20px',
              }}
            >
              {[
                [
                  'Question Types',
                  Object.entries(pattern.question_types || {})
                    .filter(([, v]) => Number(v) > 0)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ') || 'MCQ, short answer',
                ],
                [
                  'Difficulty',
                  Object.entries(pattern.difficulty_distribution || {})
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ') || 'Easy 30%, Med 50%, Hard 20%',
                ],
                ['Language Style', pattern.language_style || 'Academic / Technical'],
                [
                  'Marks / Question',
                  String(pattern.marks_pattern?.typical_marks_per_question || '1 mark'),
                ],
              ].map(([label, value]) => (
                <div
                  key={label}
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '12px',
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                      marginBottom: '4px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {label}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>

            {pattern.key_observation && (
              <div
                style={{
                  background: 'rgba(59,130,246,0.08)',
                  border: '1px solid rgba(59,130,246,0.2)',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  marginBottom: '20px',
                  fontSize: '13px',
                  color: '#79c0ff',
                  lineHeight: '1.5',
                }}
              >
                💡 <strong>Key Observation:</strong> {pattern.key_observation}
              </div>
            )}

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                marginBottom: '16px',
                color: 'var(--text-primary)',
              }}
            >
              <span style={{ fontSize: '13px' }}>Generate</span>
              <input
                type="number"
                value={genCount}
                onChange={(e) => setGenCount(Number(e.target.value))}
                min={2}
                max={50}
                style={{
                  width: '64px',
                  padding: '6px 10px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                }}
              />
              <span style={{ fontSize: '13px' }}>questions matching this exact pattern</span>
            </div>

            <button
              onClick={generateQuestions}
              disabled={loading}
              type="button"
              style={{
                width: '100%',
                padding: '12px',
                background: '#3b82f6',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              {loading ? 'Generating questions with AI...' : `Generate ${genCount} Questions →`}
            </button>
          </div>
        )}

        {/* STEP 4: Practice & Grade */}
        {step === 'practice' && questions.length > 0 && (
          <div style={{ maxWidth: '640px', margin: '0 auto' }}>
            {/* Score Bar */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '20px',
                padding: '10px 16px',
                background: 'var(--bg-tertiary)',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
              }}
            >
              <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                Question {currentQ + 1} / {questions.length}
              </span>
              <span style={{ fontSize: '13px', color: '#3fb950', fontWeight: 600 }}>
                Score: {score} / {Object.keys(results).length}
              </span>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '240px' }}>
                {questions.map((_, i) => (
                  <div
                    key={i}
                    onClick={() => {
                      setCurrentQ(i);
                      setAnswer('');
                    }}
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      cursor: 'pointer',
                      background: results[i]
                        ? results[i].is_correct
                          ? '#3fb950'
                          : '#f85149'
                        : i === currentQ
                        ? '#3b82f6'
                        : 'rgba(255,255,255,0.15)',
                    }}
                    title={`Question ${i + 1}`}
                  />
                ))}
              </div>
            </div>

            {/* Question Card */}
            {(() => {
              const q = questions[currentQ];
              const res = results[currentQ];
              if (!q) return null;

              return (
                <div
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '12px',
                    padding: '20px',
                    marginBottom: '16px',
                  }}
                >
                  {/* Metadata tags */}
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: 'rgba(59,130,246,0.15)',
                        color: '#79c0ff',
                      }}
                    >
                      {q.question_type}
                    </span>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: 'rgba(255,255,255,0.06)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {q.marks} mark{q.marks > 1 ? 's' : ''}
                    </span>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background:
                          q.difficulty === 'hard'
                            ? 'rgba(248,81,73,0.15)'
                            : q.difficulty === 'easy'
                            ? 'rgba(63,185,80,0.15)'
                            : 'rgba(255,255,255,0.06)',
                        color:
                          q.difficulty === 'hard'
                            ? '#f85149'
                            : q.difficulty === 'easy'
                            ? '#3fb950'
                            : 'var(--text-secondary)',
                      }}
                    >
                      {q.difficulty}
                    </span>
                  </div>

                  <p
                    style={{
                      fontSize: '15px',
                      lineHeight: 1.6,
                      marginBottom: '16px',
                      color: 'var(--text-primary)',
                      fontWeight: 500,
                    }}
                  >
                    {q.question_text}
                  </p>

                  {/* MCQ Options */}
                  {q.question_type === 'MCQ' && q.options && q.options.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {q.options.map((opt, oi) => {
                        const letter = opt.split('.')[0].trim().toUpperCase();
                        const isSelected = answer.toUpperCase() === letter;

                        return (
                          <button
                            key={oi}
                            type="button"
                            onClick={() => !res && setAnswer(letter)}
                            style={{
                              padding: '10px 14px',
                              textAlign: 'left',
                              borderRadius: '8px',
                              fontSize: '13px',
                              cursor: res ? 'default' : 'pointer',
                              background:
                                isSelected && !res
                                  ? 'rgba(59,130,246,0.2)'
                                  : 'rgba(255,255,255,0.04)',
                              border: `1px solid ${
                                isSelected && !res ? '#3b82f6' : 'rgba(255,255,255,0.1)'
                              }`,
                              color: 'var(--text-primary)',
                            }}
                          >
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Subjective textarea */}
                  {q.question_type !== 'MCQ' && !res && (
                    <textarea
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      placeholder="Type your answer here..."
                      rows={4}
                      style={{
                        width: '100%',
                        padding: '10px',
                        background: 'rgba(0,0,0,0.3)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        color: 'var(--text-primary)',
                        fontSize: '13px',
                        resize: 'vertical',
                        fontFamily: 'inherit',
                        boxSizing: 'border-box',
                      }}
                    />
                  )}

                  {/* Result Feedback Banner */}
                  {res && (
                    <div
                      style={{
                        marginTop: '16px',
                        padding: '14px',
                        background: res.is_correct
                          ? 'rgba(63,185,80,0.08)'
                          : 'rgba(248,81,73,0.08)',
                        border: `1px solid ${
                          res.is_correct ? 'rgba(63,185,80,0.25)' : 'rgba(248,81,73,0.25)'
                        }`,
                        borderRadius: '8px',
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 600,
                          marginBottom: '6px',
                          color: res.is_correct ? '#3fb950' : '#f85149',
                          fontSize: '14px',
                        }}
                      >
                        {res.is_correct ? '✓ Correct!' : '✗ Incorrect'}
                        {!res.is_correct && ` (Correct: ${res.correct_answer})`}
                      </div>
                      <div
                        style={{
                          fontSize: '13px',
                          color: 'var(--text-secondary)',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {res.explanation}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
              {!results[currentQ] ? (
                <button
                  onClick={submitAnswer}
                  disabled={!answer.trim() || loading}
                  type="button"
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#3b82f6',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: !answer.trim() || loading ? 'not-allowed' : 'pointer',
                    fontSize: '14px',
                    fontWeight: 500,
                    opacity: !answer.trim() || loading ? 0.6 : 1,
                  }}
                >
                  {loading ? 'Grading Answer...' : 'Submit Answer'}
                </button>
              ) : null}

              {currentQ < questions.length - 1 && (
                <button
                  onClick={() => {
                    setCurrentQ((q) => q + 1);
                    setAnswer('');
                  }}
                  type="button"
                  style={{
                    flex: results[currentQ] ? 1 : 0,
                    padding: '12px 24px',
                    background: 'rgba(255,255,255,0.08)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 500,
                  }}
                >
                  Next Question →
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
