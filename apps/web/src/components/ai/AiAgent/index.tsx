import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Menu, Plus } from 'lucide-react';
import { message } from 'antd';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';
import { chatApi, type ChatMessage, type ChatSession, type ChatSource, type ChatStep } from '@/services/chat';
import type { QuizStreamPayload } from '@/types/quiz';
import { BACKGROUNDS, type BackgroundOption, type ChatCapability, type ComposerPayload } from '../types';
import {
  deleteStoredBackground,
  listStoredBackgrounds,
  saveStoredBackground,
} from '../backgroundStorage';
import { useMediaQuery } from '../useMediaQuery';
import AiBackground from '../AiBackground';
import AiSidebar from '../AiSidebar';
import AiWelcome from '../AiWelcome';
import AiMessage from '../AiMessage';
import AiComposer from '../AiComposer';
import styles from './index.module.less';

const MOBILE_QUERY = '(max-width: 760px)';
const SELECTED_BACKGROUND_KEY = 'my-rag:selected-chat-background';
const HIDDEN_BACKGROUND_KEY = 'my-rag:hidden-chat-backgrounds';
const DEFAULT_BACKGROUND_ID = 'builtin-none';

const initialBackgroundId = () => {
  try {
    return localStorage.getItem(SELECTED_BACKGROUND_KEY) ?? DEFAULT_BACKGROUND_ID;
  } catch {
    return DEFAULT_BACKGROUND_ID;
  }
};

const initialHiddenBackgroundIds = () => {
  try {
    const stored = JSON.parse(localStorage.getItem(HIDDEN_BACKGROUND_KEY) ?? '[]');
    return Array.isArray(stored)
      ? stored.filter((id): id is string => typeof id === 'string')
      : [];
  } catch {
    return [];
  }
};

interface QueuedChatMessage {
  sessionId: string;
  content: string;
  capabilities: ChatCapability[];
  documentIds: string[];
  tempUserId: string;
  tempAssistantId: string;
  createdAt: string;
}

const rekeyRecord = <T,>(
  record: Record<string, T>,
  oldKey: string,
  newKey: string,
): Record<string, T> => {
  if (!(oldKey in record) || oldKey === newKey) return record;
  const next = { ...record, [newKey]: record[oldKey] };
  delete next[oldKey];
  return next;
};

const AiAgentInner: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const isMobile = useMediaQuery(MOBILE_QUERY);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sending, setSending] = useState(false);
  const [receiving, setReceiving] = useState(false);
  const [streamStatus, setStreamStatus] = useState('');
  const [streamSources, setStreamSources] = useState<ChatSource[]>([]);
  const [messageSteps, setMessageSteps] = useState<Record<string, ChatStep[]>>({});
  const [quizPayloads, setQuizPayloads] = useState<Record<string, QuizStreamPayload>>({});
  const [quizStreamText, setQuizStreamText] = useState('');
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [backgroundId, setBackgroundId] = useState(initialBackgroundId);
  const [hiddenBackgroundIds, setHiddenBackgroundIds] = useState<string[]>(
    initialHiddenBackgroundIds,
  );
  const [customBackgrounds, setCustomBackgrounds] = useState<BackgroundOption[]>([]);
  const [backgroundsLoaded, setBackgroundsLoaded] = useState(false);
  const [defaultCapabilities, setDefaultCapabilities] = useState<ChatCapability[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const finalMessageIdsRef = useRef(new Map<string, string>());
  const playbackResolversRef = useRef(new Map<string, () => void>());
  const queueRef = useRef<QueuedChatMessage[]>([]);
  const processingRef = useRef(false);
  const activeSessionIdRef = useRef<string | null>(activeSessionId);
  const sessionCreationRef = useRef<Promise<string | null> | null>(null);
  const messageSequenceRef = useRef(0);
  const backgroundObjectUrlsRef = useRef(new Set<string>());

  const builtinBackgrounds = BACKGROUNDS.filter(
    (background) => !hiddenBackgroundIds.includes(background.id),
  );
  const backgrounds = [...builtinBackgrounds, ...customBackgrounds];
  const selectedBackground =
    backgrounds.find((background) => background.id === backgroundId) ?? backgrounds[0];

  activeSessionIdRef.current = activeSessionId;

  useEffect(() => {
    let active = true;
    void listStoredBackgrounds()
      .then((storedBackgrounds) => {
        if (!active) return;
        const options = storedBackgrounds
          .sort((left, right) => left.createdAt - right.createdAt)
          .map((background): BackgroundOption => {
            const url = URL.createObjectURL(background.blob);
            backgroundObjectUrlsRef.current.add(url);
            return {
              id: background.id,
              label: background.label,
              url,
              removable: true,
            };
          });
        setCustomBackgrounds(options);
      })
      .catch(() => message.warning('自定义背景图库加载失败'))
      .finally(() => {
        if (active) setBackgroundsLoaded(true);
      });

    return () => {
      active = false;
      backgroundObjectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      backgroundObjectUrlsRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!backgroundsLoaded) return;
    const exists = [...builtinBackgrounds, ...customBackgrounds].some(
      (background) => background.id === backgroundId,
    );
    if (!exists) setBackgroundId(backgrounds[0]?.id ?? '');
  }, [backgroundId, backgroundsLoaded, customBackgrounds, hiddenBackgroundIds]);

  useEffect(() => {
    try {
      localStorage.setItem(SELECTED_BACKGROUND_KEY, backgroundId);
    } catch {
      // Selection persistence is optional when browser storage is unavailable.
    }
  }, [backgroundId]);

  useEffect(() => {
    try {
      localStorage.setItem(HIDDEN_BACKGROUND_KEY, JSON.stringify(hiddenBackgroundIds));
    } catch {
      // Hidden preset persistence is optional when browser storage is unavailable.
    }
  }, [hiddenBackgroundIds]);

  const addBackground = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) {
      message.error('请选择图片文件');
      return;
    }
    if (file.size > 12 * 1024 * 1024) {
      message.error('背景图片不能超过 12 MB');
      return;
    }

    const id = `custom-${globalThis.crypto?.randomUUID?.() ?? Date.now()}`;
    const label = file.name.replace(/\.[^.]+$/, '') || '自定义背景';
    try {
      await saveStoredBackground({ id, label, blob: file, createdAt: Date.now() });
      const url = URL.createObjectURL(file);
      backgroundObjectUrlsRef.current.add(url);
      setCustomBackgrounds((current) => [
        ...current,
        { id, label, url },
      ]);
      setBackgroundId(id);
      message.success('背景图已添加');
    } catch {
      message.error('背景图保存失败');
    }
  }, []);

  const deleteBackground = useCallback(
    async (id: string) => {
      const target = customBackgrounds.find((background) => background.id === id);
      const builtinTarget = BACKGROUNDS.find((background) => background.id === id);
      if (!target && (!builtinTarget || !builtinTarget.removable)) return;
      try {
        if (target) {
          await deleteStoredBackground(id);
          URL.revokeObjectURL(target.url);
          backgroundObjectUrlsRef.current.delete(target.url);
          setCustomBackgrounds((current) =>
            current.filter((background) => background.id !== id),
          );
        } else {
          setHiddenBackgroundIds((current) => [...new Set([...current, id])]);
        }
        if (backgroundId === id) {
          setBackgroundId(backgrounds.find((background) => background.id !== id)?.id ?? '');
        }
        message.success('背景图已删除');
      } catch {
        message.error('背景图删除失败');
      }
    },
    [backgroundId, backgrounds, customBackgrounds],
  );

  const resetQueuedWork = useCallback(() => {
    queueRef.current = [];
    playbackResolversRef.current.forEach((resolve) => resolve());
    playbackResolversRef.current.clear();
    abortRef.current?.abort();
  }, []);

  const refreshSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await chatApi.listSessions({ page_size: 50 });
      setSessions(data.items);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载会话失败');
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const openSession = useCallback(
    async (sessionId: string) => {
      resetQueuedWork();
      setStreamingId(null);
      finalMessageIdsRef.current.clear();
      setStreamStatus('');
      setStreamSources([]);
      setMessageSteps({});
      setQuizPayloads({});
      setQuizStreamText('');
      try {
        const detail = await chatApi.getSession(sessionId);
        activeSessionIdRef.current = sessionId;
        setActiveSessionId(sessionId);
        setMessages(detail.messages);
        setDefaultCapabilities(detail.capabilities ?? []);
        if (isMobile) setMobileOpen(false);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '加载会话失败');
      }
    },
    [isMobile, resetQueuedWork],
  );

  const selectSession = useCallback(
    (sessionId: string) => {
      navigate(`/chat/${sessionId}`);
    },
    [navigate],
  );

  const startNewChat = useCallback(() => {
    if (!routeSessionId && !activeSessionIdRef.current && messages.length === 0) {
      message.info('当前已经新建对话，可以直接输入发送');
      return;
    }
    resetQueuedWork();
    activeSessionIdRef.current = null;
    setActiveSessionId(null);
    setMessages([]);
    setDefaultCapabilities([]);
    setStreamingId(null);
    finalMessageIdsRef.current.clear();
    setStreamStatus('');
    setStreamSources([]);
    setMessageSteps({});
    setQuizPayloads({});
    setQuizStreamText('');
    navigate('/chat');
  }, [messages.length, navigate, resetQueuedWork, routeSessionId]);

  const createSession = useCallback(async () => {
    try {
      const session = await chatApi.createSession();
      setSessions((prev) => [session, ...prev]);
      activeSessionIdRef.current = session.id;
      setActiveSessionId(session.id);
      navigate(`/chat/${session.id}`);
      return session.id;
    } catch (error) {
      message.error(error instanceof Error ? error.message : '创建会话失败');
      return null;
    }
  }, [navigate]);

  const deleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await chatApi.deleteSession(sessionId);
        setSessions((prev) => prev.filter((item) => item.id !== sessionId));
        if (activeSessionId === sessionId) {
          resetQueuedWork();
          activeSessionIdRef.current = null;
          setActiveSessionId(null);
          if (routeSessionId === sessionId) navigate('/chat');
          setMessages([]);
          setDefaultCapabilities([]);
          setStreamingId(null);
          setStreamStatus('');
          setStreamSources([]);
          setMessageSteps({});
          setQuizPayloads({});
          setQuizStreamText('');
        }
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除会话失败');
      }
    },
    [activeSessionId, navigate, resetQueuedWork, routeSessionId],
  );

  const ensureSession = useCallback(async () => {
    if (activeSessionIdRef.current) return activeSessionIdRef.current;
    if (!sessionCreationRef.current) {
      const pending = createSession();
      sessionCreationRef.current = pending;
      void pending.finally(() => {
        if (sessionCreationRef.current === pending) sessionCreationRef.current = null;
      });
    }
    return sessionCreationRef.current;
  }, [createSession]);

  const drainQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;
    setSending(true);

    try {
      while (queueRef.current.length > 0) {
        const job = queueRef.current.shift();
        if (!job) continue;

        const assistantMessage: ChatMessage = {
          id: job.tempAssistantId,
          session_id: job.sessionId,
          role: 'assistant',
          content: '',
          sources: [],
          created_at: job.createdAt,
        };
        let answer = '';
        let receivedToken = false;
        let completed = false;

        setStreamStatus('thinking');
        setStreamSources([]);
        setMessageSteps((prev) => ({ ...prev, [job.tempAssistantId]: [] }));
        setQuizStreamText('');
        setStreamingId(job.tempAssistantId);
        setReceiving(true);
        setMessages((prev) => [...prev, assistantMessage]);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
          await chatApi.streamMessage(
            job.sessionId,
            job.content,
            {
              onStatus: setStreamStatus,
              onStep: (step) => {
                setMessageSteps((prev) => {
                  const current = prev[job.tempAssistantId] ?? [];
                  const index = current.findIndex((item) => item.id === step.id);
                  const nextSteps = [...current];
                  if (index < 0) nextSteps.push(step);
                  else nextSteps[index] = step;
                  return { ...prev, [job.tempAssistantId]: nextSteps };
                });
              },
              onSources: (sources) => {
                setStreamSources(sources);
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === job.tempAssistantId ? { ...item, sources } : item,
                  ),
                );
              },
              onQuiz: (payload) => {
                setQuizPayloads((prev) => ({ ...prev, [job.tempAssistantId]: payload }));
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === job.tempAssistantId
                      ? { ...item, quiz_paper_id: payload.paper_id }
                      : item,
                  ),
                );
              },
              onQuizToken: (token) => {
                setQuizStreamText((prev) => prev + token);
              },
              onQuizReset: () => {
                setQuizStreamText('');
              },
              onToken: (token) => {
                receivedToken = true;
                answer += token;
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === job.tempAssistantId ? { ...item, content: answer } : item,
                  ),
                );
              },
              onDone: (messageId, sources, quizPaperId) => {
                completed = true;
                finalMessageIdsRef.current.set(job.tempAssistantId, messageId);
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === job.tempAssistantId
                      ? {
                          ...item,
                          sources,
                          quiz_paper_id: quizPaperId ?? item.quiz_paper_id,
                        }
                      : item,
                  ),
                );
              },
              onError: (errorMessage) => {
                throw new Error(errorMessage);
              },
            },
            controller.signal,
            job.documentIds,
            job.capabilities,
          );
          await refreshSessions();
        } catch (error) {
          if (controller.signal.aborted) {
            message.info('已停止生成');
          } else {
            message.error(error instanceof Error ? error.message : '发送失败');
            setMessages((prev) =>
              prev.filter(
                (item) => item.id !== job.tempUserId && item.id !== job.tempAssistantId,
              ),
            );
            setMessageSteps((prev) => {
              const next = { ...prev };
              delete next[job.tempAssistantId];
              return next;
            });
          }
        } finally {
          setReceiving(false);
          abortRef.current = null;
        }

        if (completed && receivedToken) {
          await new Promise<void>((resolve) => {
            playbackResolversRef.current.set(job.tempAssistantId, resolve);
          });
        } else {
          const finalId = finalMessageIdsRef.current.get(job.tempAssistantId);
          if (finalId) {
            finalMessageIdsRef.current.delete(job.tempAssistantId);
            setMessages((current) =>
              current.map((item) =>
                item.id === job.tempAssistantId ? { ...item, id: finalId } : item,
              ),
            );
            setMessageSteps((prev) => rekeyRecord(prev, job.tempAssistantId, finalId));
            setQuizPayloads((prev) => rekeyRecord(prev, job.tempAssistantId, finalId));
          }
          setStreamingId(null);
        }

        setStreamStatus('');
        setStreamSources([]);
      }
    } finally {
      processingRef.current = false;
      setSending(false);
      setReceiving(false);
    }
  }, [refreshSessions]);

  const sendMessage = useCallback(
    async (payload: ComposerPayload) => {
      const content = payload.content.trim();
      if (!content) return;

      const sessionId = await ensureSession();
      if (!sessionId) return;

      const sequence = ++messageSequenceRef.current;
      const tempUserId = `temp-user-${Date.now()}-${sequence}`;
      const tempAssistantId = `temp-assistant-${Date.now()}-${sequence}`;
      const createdAt = new Date().toISOString();
      const userMessage: ChatMessage = {
        id: tempUserId,
        session_id: sessionId,
        role: 'user',
        content,
        created_at: createdAt,
      };

      setMessages((prev) => [...prev, userMessage]);
      // 会话默认能力同步：本次消息用到的能力自动成为会话默认（后端由 stream 自动落库）
      setDefaultCapabilities(payload.capabilities ?? []);
      queueRef.current.push({
        sessionId,
        content,
        capabilities: payload.capabilities ?? [],
        documentIds: payload.documentIds ?? [],
        tempUserId,
        tempAssistantId,
        createdAt,
      });
      void drainQueue();
    },
    [drainQueue, ensureSession],
  );

  const abortStream = useCallback(() => abortRef.current?.abort(), []);

  const handleDefaultCapabilitiesChange = useCallback(
    (next: ChatCapability[]) => {
      setDefaultCapabilities(next);
      const sessionId = activeSessionIdRef.current;
      if (!sessionId) return;
      void chatApi.updateSessionCapabilities(sessionId, next).catch((error) => {
        message.error(error instanceof Error ? error.message : '更新会话默认能力失败');
      });
    },
    [],
  );

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (routeSessionId) {
      if (routeSessionId !== activeSessionIdRef.current) {
        void openSession(routeSessionId);
      }
      return;
    }
    activeSessionIdRef.current = null;
    setActiveSessionId(null);
    setMessages([]);
  }, [openSession, routeSessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streamStatus]);

  useEffect(() => () => resetQueuedWork(), [resetQueuedWork]);

  const sidebarVisible = isMobile ? mobileOpen : !sidebarCollapsed;

  return (
    <div
      className={`${styles.page} ${
        !isMobile && sidebarCollapsed ? styles.sidebarCollapsed : ''
      }`}
    >
      <AiBackground backgroundUrl={selectedBackground?.url} theme={theme} />

      <AiSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        loading={loadingSessions}
        collapsed={sidebarCollapsed}
        isMobile={isMobile}
        visible={sidebarVisible}
        backgrounds={backgrounds}
        backgroundId={backgroundId}
        onCollapsedChange={setSidebarCollapsed}
        onCloseMobile={() => setMobileOpen(false)}
        onCreateSession={startNewChat}
        onSelectSession={selectSession}
        onDeleteSession={deleteSession}
        onBackgroundChange={setBackgroundId}
        onBackgroundAdd={(file) => void addBackground(file)}
        onBackgroundDelete={(id) => void deleteBackground(id)}
      />

      {!sidebarVisible && (
        <div className={styles.floatingBtnGroup}>
          <button
            type="button"
            className={styles.floatingBtn}
            aria-label="新建对话"
            onClick={startNewChat}
          >
            <Plus size={16} />
          </button>
          <button
            type="button"
            className={styles.floatingBtn}
            aria-label={isMobile ? '打开侧边栏' : '展开侧边栏'}
            onClick={() => (isMobile ? setMobileOpen(true) : setSidebarCollapsed(false))}
          >
            <Menu size={16} />
          </button>
        </div>
      )}

      <main className={styles.chatPane}>
        <section ref={scrollRef} className={styles.messages}>
          {messages.length === 0 ? (
            <AiWelcome />
          ) : (
            messages.map((item) => (
              <AiMessage
                key={item.id}
                message={item}
                streaming={item.id === streamingId}
                receiving={receiving && item.id === streamingId}
                streamStatus={streamStatus}
                sources={sending && item.id === streamingId ? streamSources : undefined}
                steps={messageSteps[item.id]}
                quizPayload={quizPayloads[item.id]}
                quizStreamText={
                  sending && item.id === streamingId ? quizStreamText : undefined
                }
                onPlaybackComplete={() => {
                  const finalId = finalMessageIdsRef.current.get(item.id);
                  if (finalId) {
                    finalMessageIdsRef.current.delete(item.id);
                    setMessages((current) =>
                      current.map((messageItem) =>
                        messageItem.id === item.id
                          ? { ...messageItem, id: finalId }
                          : messageItem,
                      ),
                    );
                    setMessageSteps((prev) => rekeyRecord(prev, item.id, finalId));
                    setQuizPayloads((prev) => rekeyRecord(prev, item.id, finalId));
                  }
                  setStreamingId((current) => (current === item.id ? null : current));
                  playbackResolversRef.current.get(item.id)?.();
                  playbackResolversRef.current.delete(item.id);
                }}
              />
            ))
          )}
        </section>

        <footer className={styles.composer}>
          <AiComposer
            key={activeSessionId ?? 'new'}
            sending={sending}
            theme={theme}
            defaultCapabilities={defaultCapabilities}
            onDefaultCapabilitiesChange={handleDefaultCapabilitiesChange}
            onToggleTheme={toggleTheme}
            onSubmit={sendMessage}
            onAbort={abortStream}
            onEnhance={chatApi.enhancePrompt}
            onOpenDocuments={() => navigate('/documents')}
          />
        </footer>
      </main>
    </div>
  );
};

const AiAgent: React.FC = () => {
  return (
    <ThemeProvider>
      <AiAgentInner />
    </ThemeProvider>
  );
};

export default AiAgent;
