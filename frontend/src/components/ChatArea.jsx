import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle } from 'lucide-react';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import api from '../api/client';

export default function ChatArea({
  activeChatId,
  chatTitle,
  onUpdateChat,
  selectedSources = [],
  onRagStatusChange,
}) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorNotice, setErrorNotice] = useState(null);
  const messagesEndRef = useRef(null);
  const streamingRef = useRef(false);

  // Auto-scroll to bottom whenever messages or loading changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Load chat history when activeChatId changes
  useEffect(() => {
    if (!activeChatId) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    setErrorNotice(null);

    async function loadHistory() {
      try {
        const history = await api.getChatHistory(activeChatId);
        if (!isMounted) return;

        if (Array.isArray(history) && history.length > 0) {
          const mapped = history.map((m) => ({
            id: m.id || 'msg-' + Math.random(),
            role: m.role || 'assistant',
            content: m.content || '',
            sources_used: m.sources_used || (Array.isArray(m.attachments) ? m.attachments : []),
            rag_active: Boolean(m.rag_active || (Array.isArray(m.attachments) && m.attachments.length > 0)),
            timestamp: m.created_at
              ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : 'Just now',
          }));
          setMessages(mapped);

          const lastAssistant = [...mapped].reverse().find((m) => m.role === 'assistant');
          if (onRagStatusChange && lastAssistant) {
            onRagStatusChange(Boolean(lastAssistant.rag_active));
          }
        } else {
          try {
            const saved = localStorage.getItem('ai_teacher_chats');
            if (saved) {
              const chats = JSON.parse(saved);
              const cur = chats.find((c) => c.id === activeChatId);
              if (cur && cur.messages?.length > 0) {
                setMessages(cur.messages);
                const lastAssistant = [...cur.messages].reverse().find((m) => m.role === 'assistant');
                if (onRagStatusChange && lastAssistant) {
                  onRagStatusChange(Boolean(lastAssistant.rag_active));
                }
                return;
              }
            }
          } catch (_) {}
          setMessages([]);
          if (onRagStatusChange) onRagStatusChange(false);
        }
      } catch (err) {
        if (isMounted) {
          console.warn('Failed to load history:', err);
          setErrorNotice('Could not load chat history from backend.');
        }
      }
    }

    loadHistory();
    return () => {
      isMounted = false;
    };
  }, [activeChatId, onRagStatusChange]);

  // Typewriter effect fallback
  const runTypewriter = (fullText, messageId, timestamp, sourcesUsed = [], ragActive = false) => {
    let index = 0;
    const interval = setInterval(() => {
      index += 3;
      const slice = fullText.slice(0, index);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? { ...msg, content: slice, sources_used: sourcesUsed, rag_active: ragActive }
            : msg
        )
      );
      if (index >= fullText.length) {
        clearInterval(interval);
        setIsLoading(false);
        streamingRef.current = false;
      }
    }, 12);
  };

  const handleSend = async (userText) => {
    if (!userText.trim() || isLoading) return;

    setErrorNotice(null);
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg = {
      id: 'user-' + Date.now(),
      role: 'user',
      content: userText,
      timestamp: now,
    };

    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setIsLoading(true);

    const effectiveChatId = activeChatId || 'chat-' + Date.now();
    if (onUpdateChat) {
      onUpdateChat(effectiveChatId, nextMessages, userText.slice(0, 28));
    }

    const aiMsgId = 'ai-' + Date.now();
    const aiPlaceholder = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      sources_used: [],
      rag_active: false,
      timestamp: now,
    };

    try {
      const data = await api.sendMessage(
        effectiveChatId,
        userText,
        selectedSources.map((s) => s.id || s)
      );

      const aiReply =
        data.response || data.message || data.content || (typeof data === 'string' ? data : 'No response');
      const sourcesUsed = data.sources_used || [];
      const ragActive = data.rag_active || false;

      if (onRagStatusChange) {
        onRagStatusChange(ragActive);
      }

      setMessages((prev) => [
        ...prev,
        { ...aiPlaceholder, sources_used: sourcesUsed, rag_active: ragActive },
      ]);
      runTypewriter(aiReply, aiMsgId, now, sourcesUsed, ragActive);

      if (onUpdateChat) {
        const finalMessages = [
          ...nextMessages,
          {
            ...aiPlaceholder,
            content: aiReply,
            sources_used: sourcesUsed,
            rag_active: ragActive,
          },
        ];
        onUpdateChat(effectiveChatId, finalMessages, userText.slice(0, 28));
      }
    } catch (err) {
      console.error('Chat send error:', err);
      setIsLoading(false);
      streamingRef.current = false;
      const errorMsg = {
        id: 'err-' + Date.now(),
        role: 'assistant',
        content: `⚠️ **Connection Error**: Unable to reach backend (${err.message}). Please make sure Ollama and backend are running.`,
        timestamp: now,
      };
      setMessages((prev) => [...prev, errorMsg]);
      setErrorNotice(err.message);
    }
  };

  return (
    <div style={styles.container}>
      {errorNotice && (
        <div style={styles.errorBanner}>
          <AlertCircle size={15} color="var(--red)" />
          <span>{errorNotice}</span>
        </div>
      )}

      <div style={styles.thread}>
        {messages.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyAvatar}>
              <span style={{ fontSize: '32px' }}>🧠</span>
            </div>
            <h2 style={styles.emptyTitle}>Ask me anything about your uploaded PDFs</h2>
            <p style={styles.emptySubtitle}>
              I will analyze concepts, guide you through problem sets, and generate structured curriculum.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage key={msg.id} msg={msg} isLoading={isLoading} />
          ))
        )}

        {isLoading && !streamingRef.current && (
          <div style={styles.skeletonRow}>
            <div style={styles.skeletonAvatar}>🧠</div>
            <div style={styles.skeletonBubble}>
              <div className="dot-pulse">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span style={styles.thinkingText}>AI Teacher is thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}

import { chatStyles as styles } from './chatStyles';

