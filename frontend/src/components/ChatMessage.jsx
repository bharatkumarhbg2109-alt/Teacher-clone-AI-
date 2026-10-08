import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';

export default function ChatMessage({ msg, isLoading = false }) {
  const isUser = msg.role === 'user';

  return (
    <div
      style={{
        ...styles.messageRow,
        justifyContent: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      {!isUser && (
        <div style={styles.aiAvatar} title="AI Teacher">
          <span style={{ fontSize: '15px' }}>🧠</span>
        </div>
      )}

      <div
        style={{
          ...styles.bubbleWrapper,
          alignItems: isUser ? 'flex-end' : 'flex-start',
        }}
      >
        <div
          style={{
            ...styles.bubble,
            backgroundColor: isUser ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
            color: isUser ? '#ffffff' : 'var(--text-primary)',
            borderTopRightRadius: isUser ? '2px' : 'var(--radius-md)',
            borderTopLeftRadius: !isUser ? '2px' : 'var(--radius-md)',
          }}
        >
          {isUser ? (
            <div style={styles.userText}>{msg.content}</div>
          ) : (
            <div style={styles.markdownContent}>
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }) {
                    return inline ? (
                      <code style={styles.inlineCode} {...props}>
                        {children}
                      </code>
                    ) : (
                      <pre style={styles.codeBlock}>
                        <code {...props}>{children}</code>
                      </pre>
                    );
                  },
                }}
              >
                {msg.content || (isLoading ? '...' : '')}
              </ReactMarkdown>
            </div>
          )}

          {!isUser && ((msg.sources_used && msg.sources_used.length > 0) || (msg.sources && msg.sources.length > 0)) && (
            <div
              style={{
                marginTop: '8px',
                paddingTop: '8px',
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>📄 Sources:</span>
              {((msg.sources && msg.sources.some((s) => s.type === 'image' || /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(s.name || s.filename || ''))) ||
                (msg.sources_used && msg.sources_used.some((s) => typeof s === 'object' ? s.type === 'image' : /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(s)))) && (
                <span style={{
                  background: '#8E44AD', color: '#fff', 
                  borderRadius: 4, padding: '2px 8px', 
                  fontSize: 11, marginLeft: 4
                }}>
                  📷 Visual
                </span>
              )}
              {(msg.sources_used || []).slice(0, 3).map((src, i) => {
                const srcName = typeof src === 'object' ? (src.name || src.filename || 'source') : src;
                return (
                  <span
                    key={i}
                    style={{
                      fontSize: '10px',
                      background: 'rgba(59, 130, 246, 0.12)',
                      color: 'var(--text-accent)',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      maxWidth: '140px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={srcName}
                  >
                    {srcName.replace(/\.[a-z0-9]+$/i, '')}
                  </span>
                );
              })}
              {msg.sources_used && msg.sources_used.length > 3 && (
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                  +{msg.sources_used.length - 3} more
                </span>
              )}
            </div>
          )}
        </div>

        <span style={styles.timestamp}>{msg.timestamp}</span>
      </div>

      {isUser && (
        <div style={styles.userAvatar} title="You">
          <User size={16} color="#ffffff" />
        </div>
      )}
    </div>
  );
}

const styles = {
  messageRow: {
    display: 'flex',
    gap: '12px',
    width: '100%',
  },
  aiAvatar: {
    width: '34px',
    height: '34px',
    borderRadius: '50%',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-color)',
    boxShadow: '0 0 10px var(--accent-glow)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  userAvatar: {
    width: '34px',
    height: '34px',
    borderRadius: '50%',
    backgroundColor: 'var(--accent-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  bubbleWrapper: {
    display: 'flex',
    flexDirection: 'column',
    maxWidth: '82%',
  },
  bubble: {
    padding: '12px 16px',
    borderRadius: 'var(--radius-md)',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
    wordBreak: 'break-word',
    lineHeight: '1.6',
    fontSize: '14px',
  },
  userText: {
    whiteSpace: 'pre-wrap',
  },
  markdownContent: {},
  inlineCode: {
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '12px',
    color: 'var(--text-accent)',
  },
  codeBlock: {
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px',
    overflowX: 'auto',
    fontSize: '13px',
    color: 'var(--text-primary)',
  },
  timestamp: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '4px',
    padding: '0 4px',
  },
};
