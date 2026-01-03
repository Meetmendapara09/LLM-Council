import { useState, useEffect } from 'react';
import './Sidebar.css';
import { api } from '../api';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
}) {
  const [memory, setMemory] = useState(null);
  const [modeInfo, setModeInfo] = useState(null);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!currentConversationId) {
      setMemory(null);
      return;
    }

    const load = async () => {
      setLoadingMemory(true);
      try {
        const m = await api.getMemory(currentConversationId);
        setMemory(m);
      } catch (e) {
        console.error('Failed to load memory:', e);
        setMemory(null);
      }
      setLoadingMemory(false);
    };

    load();
  }, [currentConversationId]);

  useEffect(() => {
    // load runtime memory mode
    const loadMode = async () => {
      try {
        const m = await api.getMemoryMode();
        setModeInfo(m);
      } catch (e) {
        console.error('Failed to load memory mode:', e);
        setModeInfo(null);
      }
    };
    loadMode();
  }, []);

  const handleClearMemory = async (e) => {
    e.stopPropagation();
    if (!currentConversationId) return;
    try {
      await api.clearMemory(currentConversationId);
      const m = await api.getMemory(currentConversationId);
      setMemory(m);
    } catch (err) {
      console.error('Failed to clear memory:', err);
    }
  };

  const handleSetMode = async (newMode) => {
    try {
      await api.setMemoryMode(newMode);
      const m = await api.getMemoryMode();
      setModeInfo(m);
    } catch (err) {
      console.error('Failed to set memory mode:', err);
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'New Conversation'}
              </div>
              <div className="conversation-meta">
                {conv.message_count} messages
              </div>
            </div>
          ))
        )}
      </div>

      {/* Memory panel */}
      <div className="memory-panel">
        <h3>Memory</h3>
        {!currentConversationId && <div className="muted">Select a conversation to view memory</div>}

        {currentConversationId && (
          <div>
            {loadingMemory ? (
              <div className="muted">Loading memory...</div>
            ) : memory ? (
              <div className="memory-content">
                <div className="memory-summary">
                  <strong>Summary:</strong>
                  <div>{memory.summary || <span className="muted">(no summary)</span>}</div>
                </div>

                <div className="memory-short">
                  <strong>Recent:</strong>
                  {memory.short && memory.short.length > 0 ? (
                    <ul>
                      {memory.short.slice().reverse().map((entry, i) => (
                        <li key={i}>
                          <em>{entry.role}:</em> {entry.content}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="muted">No recent memory entries</div>
                  )}
                </div>

                <div className="memory-actions">
                  {!confirmClear ? (
                    <button
                      onClick={() => setConfirmClear(true)}
                      disabled={!(memory.summary || (memory.short && memory.short.length > 0))}
                      title={!(memory.summary || (memory.short && memory.short.length > 0)) ? 'No memory to clear' : 'Clear memory for this conversation'}
                    >
                      Clear memory
                    </button>
                  ) : (
                    <div className="confirm-clear">
                      <span>Confirm clear?</span>
                      <button
                        className="confirm-yes"
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            await api.clearMemory(currentConversationId);
                            const m = await api.getMemory(currentConversationId);
                            setMemory(m);
                          } catch (err) {
                            console.error('Failed to clear memory:', err);
                          } finally {
                            setConfirmClear(false);
                          }
                        }}
                      >
                        Yes
                      </button>
                      <button
                        className="confirm-cancel"
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmClear(false);
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="muted">No memory available</div>
            )}
          </div>
        )}

        <div className="memory-mode">
          <strong>Mode:</strong>
          <select
            value={(modeInfo && modeInfo.mode) || 'local'}
            onChange={(e) => handleSetMode(e.target.value)}
          >
            <option value="local">Local (on-device)</option>
            <option value="model">Model (remote)</option>
          </select>
        </div>
      </div>
    </div>
  );
}
