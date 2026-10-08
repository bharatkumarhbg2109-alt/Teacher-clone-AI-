import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import MainArea from './components/MainArea';
import api from './api/client';
import { useAppStore } from './store/useAppStore';

const STORAGE_CHATS_KEY = 'ai_teacher_chats';
const STORAGE_SOURCES_KEY = 'ai_teacher_sources';

export default function App() {
  // Zustand global state
  const { activeTab, setActiveTab, activeChatId, setActiveChatId } = useAppStore();

  // State 3: sources array
  const [sources, setSources] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_SOURCES_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch (_) {
      return [];
    }
  });

  // State 4: chats array
  const [chats, setChats] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_CHATS_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch (_) {
      return [];
    }
  });

  const [isUploading, setIsUploading] = useState(false);
  const [backendStatus, setBackendStatus] = useState('online');
  const [ragActive, setRagActive] = useState(false);
  const [activeMode, setActiveMode] = useState('chat'); // 'chat' | 'teach' | 'practice'
  const [teachSource, setTeachSource] = useState(null);

  // Sync ragActive whenever active chat changes
  useEffect(() => {
    if (activeChatId) {
      const curChat = chats.find((c) => c.id === activeChatId);
      if (curChat && Array.isArray(curChat.messages)) {
        const lastAssistant = [...curChat.messages].reverse().find((m) => m.role === 'assistant');
        if (lastAssistant) {
          setRagActive(Boolean(lastAssistant.rag_active));
        } else {
          setRagActive(false);
        }
      } else {
        setRagActive(false);
      }
    } else {
      setRagActive(false);
    }
  }, [activeChatId, chats]);

  // Responsive state for <= 768px screens
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 768);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);

  // Monitor window resize
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      if (!mobile) {
        setSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fetch backend sources
  const fetchSources = useCallback(async () => {
    try {
      const data = await api.getSources();
      if (Array.isArray(data) && data.length > 0) {
        setSources(data);
        localStorage.setItem(STORAGE_SOURCES_KEY, JSON.stringify(data));
      }
    } catch (err) {
      console.warn('Sources load error:', err);
    }
  }, []);

  // Check backend health & initial load
  useEffect(() => {
    async function init() {
      const healthy = await api.checkHealth();
      setBackendStatus(healthy ? 'online' : 'offline');
      await fetchSources();

      // Check backend chats if available
      const remoteChats = await api.getChats();
      if (Array.isArray(remoteChats) && remoteChats.length > 0) {
        setChats(remoteChats);
      }
    }
    init();
  }, [fetchSources]);

  // Ensure activeChatId exists
  useEffect(() => {
    if (!activeChatId) {
      if (chats.length > 0) {
        setActiveChatId(chats[0].id);
      }
    }
  }, [chats, activeChatId]);

  // Persist chats to localStorage
  const syncChats = useCallback((updatedChats) => {
    setChats(updatedChats);
    try {
      localStorage.setItem(STORAGE_CHATS_KEY, JSON.stringify(updatedChats));
    } catch (_) {}
  }, []);

  // Create New Chat
  const handleNewChat = async () => {
    const newId = await api.createNewChat();
    const newChat = {
      id: newId,
      title: 'New Chat',
      messages: [],
      updatedAt: Date.now(),
    };
    const nextChats = [newChat, ...chats];
    syncChats(nextChats);
    setActiveChatId(newId);
    setActiveTab('chat');
    setActiveMode('chat');
    setTeachSource(null);
    if (isMobile) setSidebarOpen(false);
  };

  // Select Chat
  const handleSelectChat = (chatId) => {
    setActiveChatId(chatId);
    setActiveTab('chat');
    setActiveMode('chat');
    setTeachSource(null);
    if (isMobile) setSidebarOpen(false);
  };

  // Teach Me feature handler
  const handleTeachMe = (source) => {
    setTeachSource(source);
    setActiveMode('teach');
    setActiveTab('chat');
    if (isMobile) setSidebarOpen(false);
  };

  // Exam Practice feature handler
  const handleExamPractice = () => {
    setActiveMode('practice');
    setActiveTab('chat');
    if (isMobile) setSidebarOpen(false);
  };

  // Exit special mode back to standard chat
  const handleExitSpecialMode = () => {
    setActiveMode('chat');
    setTeachSource(null);
  };

  // Delete Chat
  const handleDeleteChat = async (chatId) => {
    await api.deleteChat(chatId);
    const nextChats = chats.filter((c) => c.id !== chatId);
    syncChats(nextChats);
    if (activeChatId === chatId) {
      setActiveChatId(nextChats[0]?.id || null);
    }
  };

  // Upload Source PDF
  const handleUploadSource = async (file) => {
    setIsUploading(true);
    try {
      await api.uploadSource(file);
      await fetchSources();
    } catch (err) {
      console.error('Source upload failed:', err);
      alert('Upload failed: ' + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  // Delete Source
  const handleDeleteSource = async (sourceId) => {
    try {
      await api.deleteSource(sourceId);
      const nextSources = sources.filter((s) => (s.id || s.file_id) !== sourceId);
      setSources(nextSources);
      localStorage.setItem(STORAGE_SOURCES_KEY, JSON.stringify(nextSources));
    } catch (err) {
      console.error('Delete source failed:', err);
    }
  };

  // Update Chat messages & preview title
  const handleUpdateChat = (chatId, messages, promptPreview) => {
    let targetId = chatId;
    if (!targetId) {
      targetId = 'chat-' + Date.now();
      setActiveChatId(targetId);
    }

    const title = promptPreview
      ? (promptPreview.length > 28 ? promptPreview.slice(0, 28) + '...' : promptPreview)
      : 'New Chat';

    setChats((prevChats) => {
      const exists = prevChats.some((c) => c.id === targetId);
      let updated;
      if (exists) {
        updated = prevChats.map((c) =>
          c.id === targetId
            ? {
                ...c,
                messages,
                title: c.title === 'New Chat' && promptPreview ? title : c.title,
                updatedAt: Date.now(),
              }
            : c
        );
      } else {
        updated = [
          {
            id: targetId,
            title: title || 'New Chat',
            messages,
            updatedAt: Date.now(),
          },
          ...prevChats,
        ];
      }

      try {
        localStorage.setItem(STORAGE_CHATS_KEY, JSON.stringify(updated));
      } catch (_) {}

      return updated;
    });
  };

  // Start Learning from Curriculum Tab
  const handleStartLearning = (prompt) => {
    setActiveTab('chat');
    if (!activeChatId) {
      handleNewChat();
    }
    // Give ChatArea a moment to focus
    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      if (textarea) {
        // Trigger React state change if possible
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          'value'
        )?.set;
        if (nativeInputValueSetter) {
          nativeInputValueSetter.call(textarea, prompt);
          textarea.dispatchEvent(new Event('input', { bubbles: true }));
        }
        textarea.focus();
      }
    }, 100);
  };

  const activeChat = chats.find((c) => c.id === activeChatId);
  const chatTitle = activeChat?.title || 'New Chat';

  return (
    <div style={styles.appRoot}>
      {/* Mobile backdrop overlay */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={styles.mobileBackdrop}
          aria-hidden="true"
        />
      )}

      {/* Sidebar (260px fixed) */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        sources={sources}
        onUploadSource={handleUploadSource}
        onDeleteSource={handleDeleteSource}
        isUploading={isUploading}
        isOpen={sidebarOpen}
        onCloseMobile={isMobile ? () => setSidebarOpen(false) : null}
        onTeachMe={handleTeachMe}
        onExamPractice={handleExamPractice}
      />

      {/* Main Area (flex) */}
      <MainArea
        activeTab={activeTab}
        onTabChange={setActiveTab}
        activeChatId={activeChatId}
        chatTitle={chatTitle}
        onUpdateChat={handleUpdateChat}
        sources={sources}
        onStartLearning={handleStartLearning}
        onToggleSidebar={isMobile ? () => setSidebarOpen((prev) => !prev) : null}
        backendStatus={backendStatus}
        ragActive={ragActive}
        onRagStatusChange={setRagActive}
        activeMode={activeMode}
        teachSource={teachSource}
        onExitSpecialMode={handleExitSpecialMode}
      />
    </div>
  );
}

import { appStyles as styles } from './components/appStyles';

