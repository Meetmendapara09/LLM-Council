import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Tracks which conversation the active stream belongs to so late events
  // from a previous conversation are ignored after the user switches.
  const activeStreamConversationRef = useRef(null);
  // Monotonically increasing id: events from older streams are ignored once
  // a newer stream starts.
  const streamIdRef = useRef(0);
  // AbortController for the in-flight stream, if any.
  const abortControllerRef = useRef(null);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  // Load conversations on mount (fetch inlined: the linter only permits
  // setState inside effects via a locally defined async function)
  useEffect(() => {
    const load = async () => {
      try {
        const convs = await api.listConversations();
        setConversations(convs);
      } catch (error) {
        console.error('Failed to load conversations:', error);
      }
    };
    load();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (!currentConversationId) {
      return;
    }
    const load = async () => {
      try {
        const conv = await api.getConversation(currentConversationId);
        setCurrentConversation(conv);
      } catch (error) {
        console.error('Failed to load conversation:', error);
      }
    };
    load();
  }, [currentConversationId]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    // Invalidate any in-flight stream for the previous conversation so its
    // late events are ignored.
    streamIdRef.current += 1;
    activeStreamConversationRef.current = id;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setError(null);
    setIsLoading(false);
    setCurrentConversationId(id);
  };

  const cancelStream = () => {
    abortControllerRef.current?.abort();
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === currentConversationId) {
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        setCurrentConversationId(null);
        setCurrentConversation(null);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    const conversationId = currentConversationId;
    const streamId = streamIdRef.current + 1;
    streamIdRef.current = streamId;
    activeStreamConversationRef.current = conversationId;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const isStale = () =>
      streamId !== streamIdRef.current ||
      activeStreamConversationRef.current !== conversationId;

    setIsLoading(true);
    setError(null);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(
        conversationId,
        content,
        (eventType, event) => {
          // Ignore events from a stale stream (user switched conversations
          // or started a newer stream).
          if (isStale()) return;

          switch (eventType) {
            case 'stage1_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage1: true,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'stage1_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  stage1: event.data,
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage1: false,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'stage2_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage2: true,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'stage2_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  stage2: event.data,
                  metadata: event.metadata,
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage2: false,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'stage3_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage3: true,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'stage3_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = {
                  ...messages[messages.length - 1],
                  stage3: event.data,
                  loading: {
                    ...messages[messages.length - 1].loading,
                    stage3: false,
                  },
                };
                messages[messages.length - 1] = lastMsg;
                return { ...prev, messages };
              });
              break;

            case 'title_complete':
              // Reload conversations to get updated title
              loadConversations();
              break;

            case 'complete':
              // Stream complete, reload conversations list
              loadConversations();
              setIsLoading(false);
              break;

            case 'error': {
              console.error('Stream error:', event.message);
              const message = event.message || 'Stream failed. Please try again.';
              setError(message);
              // Roll back the optimistic partial assistant message but keep
              // the user message so it can be retried.
              setCurrentConversation((prev) => ({
                ...prev,
                messages: prev.messages.slice(0, -1),
              }));
              setIsLoading(false);
              break;
            }

            default:
              console.log('Unknown event type:', eventType);
          }
        },
        controller.signal
      );

      if (!isStale()) {
        setIsLoading(false);
      }
    } catch (error) {
      if (isStale()) return;
      if (error?.name === 'AbortError') {
        console.log('Stream cancelled by user');
        setError('Request cancelled.');
        // Roll back the partial assistant message, keep the user message.
        setCurrentConversation((prev) => ({
          ...prev,
          messages: prev.messages.slice(0, -1),
        }));
        setIsLoading(false);
        return;
      }
      console.error('Failed to send message:', error);
      setError(error?.message || 'Failed to send message. Please try again.');
      // Remove optimistic messages on hard failure
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        error={error}
        onCancel={cancelStream}
      />
    </div>
  );
}

export default App;
