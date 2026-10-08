import React from 'react';
import Header from './Header';
import ChatArea from './ChatArea';
import TeachMode from './TeachMode';
import QuestionPractice from './QuestionPractice';
import GraphTab from './GraphTab';
import CurriculumTab from './CurriculumTab';
import { Menu } from 'lucide-react';

export default function MainArea({
  activeTab = 'chat',
  onTabChange,
  activeChatId,
  chatTitle,
  onUpdateChat,
  sources = [],
  onStartLearning,
  onToggleSidebar,
  backendStatus = 'online',
  ragActive = false,
  onRagStatusChange,
  activeMode = 'chat',
  teachSource = null,
  onExitSpecialMode,
}) {
  return (
    <div style={styles.mainArea}>
      {/* Top Header Bar */}
      <div style={styles.topBar}>
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="hamburger-btn"
            style={styles.hamburgerBtn}
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>
        )}
        <div style={styles.headerWrapper}>
          <Header
            activeTab={activeTab}
            onTabChange={onTabChange}
            backendStatus={backendStatus}
            ragActive={ragActive}
          />
        </div>
      </div>

      {/* Main Tab Content */}
      <div style={styles.tabContent}>
        {activeTab === 'chat' && activeMode === 'chat' && (
          <ChatArea
            activeChatId={activeChatId}
            chatTitle={chatTitle}
            onUpdateChat={onUpdateChat}
            selectedSources={sources}
            onRagStatusChange={onRagStatusChange}
          />
        )}

        {activeTab === 'chat' && activeMode === 'teach' && teachSource && (
          <TeachMode source={teachSource} onBack={onExitSpecialMode} />
        )}

        {activeTab === 'chat' && activeMode === 'practice' && (
          <QuestionPractice onBack={onExitSpecialMode} />
        )}

        {activeTab === 'graph' && <GraphTab />}

        {activeTab === 'curriculum' && (
          <CurriculumTab onStartLearning={onStartLearning} />
        )}
      </div>
    </div>
  );
}

const styles = {
  mainArea: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    overflow: 'hidden',
    backgroundColor: 'var(--bg-primary)',
    position: 'relative',
  },
  topBar: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    backgroundColor: 'var(--bg-secondary)',
  },
  hamburgerBtn: {
    display: 'none', // Shown via CSS media query or responsive style
    background: 'none',
    border: 'none',
    color: 'var(--text-primary)',
    padding: '0 12px',
    cursor: 'pointer',
    height: '52px',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerWrapper: {
    flex: 1,
  },
  tabContent: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
};
