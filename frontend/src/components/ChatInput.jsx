import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Loader2, Paperclip, X } from 'lucide-react';

export default function ChatInput({ onSend, isLoading = false }) {
  const [text, setText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-resize up to 6 lines (~140px), then scroll
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    const newHeight = Math.min(textarea.scrollHeight, 140);
    textarea.style.height = `${Math.max(newHeight, 44)}px`;
  }, [text]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if ((!trimmed && !selectedFile) || isLoading) return;
    onSend(trimmed || (selectedFile ? `Analyze this file: ${selectedFile.name}` : ''), selectedFile);
    setText('');
    clearSelectedFile();
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px';
    }
  };

  const canSend = (text.trim().length > 0 || selectedFile !== null) && !isLoading;

  return (
    <div style={styles.container}>
      {selectedFile && (
        <div style={styles.previewContainer}>
          {previewUrl ? (
            <img src={previewUrl} alt="Preview" style={styles.thumbnail} />
          ) : (
            <span style={{ fontSize: '16px' }}>📄</span>
          )}
          <span style={styles.previewName}>{selectedFile.name}</span>
          <button
            type="button"
            onClick={clearSelectedFile}
            style={styles.clearBtn}
            title="Remove attachment"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div style={styles.inputCard}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.pptx,.txt,.md,.jpg,.jpeg,.png,.gif,.webp"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          style={styles.attachBtn}
          title="Attach document or image"
          aria-label="Attach file"
        >
          <Paperclip size={18} />
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your PDFs and images... (Enter to send)"
          rows={1}
          disabled={isLoading}
          style={styles.textarea}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          style={{
            ...styles.sendBtn,
            backgroundColor: canSend ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
            color: canSend ? '#ffffff' : 'var(--text-muted)',
            cursor: canSend ? 'pointer' : 'not-allowed',
          }}
          title={isLoading ? 'Thinking...' : 'Send message (Enter)'}
          aria-label="Send message"
        >
          {isLoading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <ArrowUp size={16} strokeWidth={2.5} />
          )}
        </button>
      </div>

      {/* Footer bar with character counter & keyboard hints */}
      <div style={styles.footerRow}>
        <span style={styles.hintText}>
          Enter ↵ send • Shift+Enter newline • Attach images/PDFs
        </span>
        {text.length > 200 && (
          <span style={styles.charCounter}>{text.length} chars</span>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    padding: '12px 20px 16px 20px',
    backgroundColor: 'var(--bg-primary)',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    maxWidth: 'var(--chat-max-width)',
    width: '100%',
    margin: '0 auto',
  },
  previewContainer: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 10px',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius-sm)',
    alignSelf: 'flex-start',
  },
  thumbnail: {
    width: '28px',
    height: '28px',
    objectFit: 'cover',
    borderRadius: '4px',
  },
  previewName: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    maxWidth: '220px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  clearBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '2px',
    display: 'flex',
    alignItems: 'center',
  },
  inputCard: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '8px',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md)',
    padding: '8px 12px',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
  },
  attachBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '6px 4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  textarea: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: 'var(--text-primary)',
    fontSize: '14px',
    fontFamily: 'var(--font-sans)',
    lineHeight: '1.5',
    resize: 'none',
    minHeight: '28px',
    maxHeight: '140px',
    padding: '4px 0',
  },
  sendBtn: {
    width: '32px',
    height: '32px',
    borderRadius: 'var(--radius-sm)',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'background-color 0.15s ease, opacity 0.15s ease',
  },
  footerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 4px',
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  hintText: {
    userSelect: 'none',
  },
  charCounter: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-secondary)',
  },
};
