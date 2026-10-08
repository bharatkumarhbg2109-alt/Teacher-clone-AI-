import React, { useRef, useState } from 'react';
import {
  FileText,
  Plus,
  Trash2,
  Upload,
  Loader2,
  MessageSquare,
  GraduationCap,
  X,
} from 'lucide-react';

export default function Sidebar({
  chats = [],
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  sources = [],
  onUploadSource,
  onDeleteSource,
  isUploading = false,
  isOpen = true,
  onCloseMobile,
  onTeachMe,
  onExamPractice,
}) {
  const fileInputRef = useRef(null);
  const [hoveredSourceId, setHoveredSourceId] = useState(null);
  const [hoveredChatId, setHoveredChatId] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file && onUploadSource) {
      onUploadSource(file);
    }
    e.target.value = '';
  };

  const truncate = (str = '', max = 24) => {
    return str.length > max ? str.slice(0, max) + '…' : str;
  };

  return (
    <aside
      style={{
        ...styles.sidebar,
        transform: isOpen ? 'translateX(0)' : 'translateX(-100%)',
      }}
    >
      {/* Top Header: Logo + Branding */}
      <div style={styles.brandRow}>
        <div style={styles.brand}>
          <div style={styles.logoIcon}>
            <GraduationCap size={20} color="var(--accent-primary)" />
          </div>
          <div>
            <h1 style={styles.brandTitle}>AI Teacher</h1>
            <span style={styles.brandSubtitle}>Personal Local Tutor</span>
          </div>
        </div>

        {/* Mobile close button if displayed on small screen */}
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            style={styles.mobileCloseBtn}
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.pptx,.txt,.md,.jpg,.jpeg,.png,.gif,.webp"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {/* Main Scrollable Content */}
      <div style={styles.scrollArea}>
        {/* SECTION 1: SOURCES */}
        <section style={styles.section}>
          <div style={styles.sectionHeader}>
            <div style={styles.sectionTitleRow}>
              <span style={styles.sectionTitle}>Sources</span>
              <span style={styles.countBadge}>{sources.length}</span>
            </div>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              style={styles.uploadBtn}
              title="Upload PDF source"
            >
              {isUploading ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Upload size={13} />
              )}
              <span>{isUploading ? 'Uploading...' : 'Upload PDF'}</span>
            </button>
          </div>

          {sources.length === 0 ? (
            <div style={styles.emptyState}>Upload PDFs to start teaching</div>
          ) : (
            <div style={styles.sourcesList}>
              {sources.map((src) => {
                const id = src.id || src.file_id;
                const name = src.filename || src.name || 'document.pdf';
                const isHovered = hoveredSourceId === id;

                return (
                  <div
                    key={id}
                    onMouseEnter={() => setHoveredSourceId(id)}
                    onMouseLeave={() => setHoveredSourceId(null)}
                    style={styles.sourcePill}
                    title={name}
                  >
                    <span style={styles.pdfIcon}>📄</span>
                    <span style={styles.sourceName}>{truncate(name, 18)}</span>

                    {onTeachMe && (
                      <button
                        type="button"
                        className="teach-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          onTeachMe(src);
                        }}
                        style={{
                          opacity: isHovered ? 1 : 0,
                          pointerEvents: isHovered ? 'auto' : 'none',
                          transition: 'opacity 0.15s ease',
                          fontSize: '11px',
                          padding: '2px 8px',
                          background: 'rgba(59, 130, 246, 0.2)',
                          color: '#79c0ff',
                          border: '1px solid rgba(59, 130, 246, 0.4)',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          whiteSpace: 'nowrap',
                          flexShrink: 0,
                        }}
                        title="Teach me this PDF"
                      >
                        Teach Me
                      </button>
                    )}

                    {onDeleteSource && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`Delete "${name}"?`)) {
                            onDeleteSource(id);
                          }
                        }}
                        style={{
                          ...styles.deleteBtn,
                          opacity: isHovered ? 1 : 0,
                          pointerEvents: isHovered ? 'auto' : 'none',
                        }}
                        title="Delete source"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* SECTION 2: CHATS */}
        <section style={styles.section}>
          <div style={styles.sectionHeader}>
            <div style={styles.sectionTitleRow}>
              <span style={styles.sectionTitle}>Chats</span>
              <span style={styles.countBadge}>{chats.length}</span>
            </div>
            <button
              type="button"
              onClick={onNewChat}
              style={styles.newChatBtn}
              title="Create new chat"
            >
              <Plus size={14} />
              <span>New</span>
            </button>
          </div>

          {chats.length === 0 ? (
            <div style={styles.emptyState}>No chats yet. Click "＋ New" to start!</div>
          ) : (
            <div style={styles.chatList}>
              {chats.map((chat) => {
                const isActive = chat.id === activeChatId;
                const isHovered = hoveredChatId === chat.id;
                const title = chat.title || 'New Chat';
                const timestamp = chat.updatedAt || chat.created_at;
                const timeStr = timestamp
                  ? new Date(timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })
                  : '';

                return (
                  <div
                    key={chat.id}
                    onMouseEnter={() => setHoveredChatId(chat.id)}
                    onMouseLeave={() => setHoveredChatId(null)}
                    onClick={() => onSelectChat(chat.id)}
                    style={{
                      ...styles.chatRow,
                      backgroundColor: isActive ? 'var(--accent-glow)' : isHovered ? 'var(--bg-hover)' : 'transparent',
                      borderColor: isActive ? 'var(--accent-primary)' : 'transparent',
                    }}
                    title={title}
                  >
                    <MessageSquare
                      size={15}
                      color={isActive ? 'var(--accent-primary)' : 'var(--text-secondary)'}
                      style={{ flexShrink: 0 }}
                    />
                    <div style={styles.chatMeta}>
                      <span
                        style={{
                          ...styles.chatTitle,
                          color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                          fontWeight: isActive ? '600' : '400',
                        }}
                      >
                        {truncate(title, 28)}
                      </span>
                      {timeStr && <span style={styles.chatTime}>{timeStr}</span>}
                    </div>

                    {onDeleteChat && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteChat(chat.id);
                        }}
                        style={{
                          ...styles.deleteBtn,
                          opacity: isHovered ? 1 : 0,
                          pointerEvents: isHovered ? 'auto' : 'none',
                        }}
                        title="Delete chat"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* SECTION 3: EXAM PRACTICE */}
        {onExamPractice && (
          <section style={{ padding: '0 16px 16px 16px' }}>
            <button
              type="button"
              onClick={onExamPractice}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                padding: '10px 14px',
                backgroundColor: 'rgba(59, 130, 246, 0.12)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '8px',
                color: '#79c0ff',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background-color 0.15s ease',
              }}
              title="Practice exam questions matching your pattern"
            >
              <span>📝</span>
              <span>Exam Practice</span>
            </button>
          </section>
        )}
      </div>

      {/* Footer Version Tag */}
      <footer style={styles.footer}>
        <span style={styles.versionTag}>v1.0 • Local AI</span>
      </footer>
    </aside>
  );
}

import { sidebarStyles as styles } from './sidebarStyles';

