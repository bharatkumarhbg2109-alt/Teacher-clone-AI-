import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export const useAppStore = create(
  subscribeWithSelector((set, get) => ({
    // ── Active session ─────────────────────────────
    activeChatId: null,
    setActiveChatId: (id) => set({ activeChatId: id }),

    // ── Lesson arc state ───────────────────────────
    lessonState: null,  // null | { topic, currentBeat, beats: [] }
    setLessonState: (state) => set({ lessonState: state }),
    advanceLessonBeat: (beatData) =>
      set((s) => ({
        lessonState: s.lessonState
          ? { ...s.lessonState, currentBeat: s.lessonState.currentBeat + 1, beats: [...s.lessonState.beats, beatData] }
          : s.lessonState
      })),
    clearLesson: () => set({ lessonState: null }),

    // ── Knowledge graph selection ──────────────────
    selectedConcept: null,
    setSelectedConcept: (concept) => set({ selectedConcept: concept }),

    // ── Source documents ───────────────────────────
    sources: [],
    setSources: (sources) => set({ sources }),
    addSource: (source) => set((s) => ({ sources: [...s.sources, source] })),

    // ── UI state ───────────────────────────────────
    activeTab: 'chat',  // 'chat' | 'curriculum' | 'graph' | 'practice'
    setActiveTab: (tab) => set({ activeTab: tab }),
    sidebarOpen: true,
    toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

    // ── Loading states ─────────────────────────────
    isStreaming: false,
    setIsStreaming: (v) => set({ isStreaming: v }),
  }))
);
