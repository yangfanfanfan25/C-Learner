import http from './http';
import type { APIResponse, PaginatedData, PaginationParams } from '@/types/api';
import type { QuizStreamPayload } from '@/types/quiz';
import type { ChatCapability } from '@/types/chat';

export type ChatSessionStatus = 'active' | 'archived';
export type ChatMessageRole = 'user' | 'assistant' | 'system';

export interface ChatSource {
  id: string;
  title: string;
  document_id?: string | null;
  score?: number | null;
  url?: string | null;
}

export interface ChatSession {
  id: string;
  title: string;
  status: ChatSessionStatus;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: ChatMessageRole;
  content: string;
  sources?: ChatSource[] | null;
  quiz_paper_id?: string | null;
  /** 用户消息通过 @ 选择的文档 ID（练习模式上下文） */
  document_ids?: string[] | null;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
  capabilities: ChatCapability[];
}

export interface PromptEnhanceResponse {
  content: string;
}

/**
 * 执行步骤日志（工具开始/工具执行结果）。
 * 仅用于流式 UI 展示，不写入最终 assistant 消息内容。
 */
export interface ChatStep {
  id: string;
  kind: 'tool_start' | 'tool_result';
  tool?: string | null;
  message: string;
  args?: Record<string, unknown> | null;
  output?: string | null;
}

export interface ChatStreamCallbacks {
  onStatus?: (status: string) => void;
  onStep?: (step: ChatStep) => void;
  onToken?: (token: string) => void;
  onSources?: (sources: ChatSource[]) => void;
  onQuiz?: (payload: QuizStreamPayload) => void;
  /** 出题生成过程的流式文本（实时展示，不进入最终消息内容） */
  onQuizToken?: (token: string) => void;
  /** 出题重试前清空上一轮未通过校验的生成草稿 */
  onQuizReset?: () => void;
  onDone?: (messageId: string, sources: ChatSource[], quizPaperId?: string | null) => void;
  onError?: (message: string) => void;
}

const unwrap = <T>(response: { data: APIResponse<T> }) => response.data.data;

const parseSsePayload = (event: string, payload: string, callbacks: ChatStreamCallbacks) => {
  const data = JSON.parse(payload) as Record<string, unknown>;
  if (event === 'status') {
    callbacks.onStatus?.(String(data.status || ''));
  }
  if (event === 'step') {
    callbacks.onStep?.(data as unknown as ChatStep);
  }
  if (event === 'token') {
    callbacks.onToken?.(String(data.token || ''));
  }
  if (event === 'sources') {
    callbacks.onSources?.((data.sources as ChatSource[]) || []);
  }
  if (event === 'quiz') {
    callbacks.onQuiz?.(data as unknown as QuizStreamPayload);
  }
  if (event === 'quiz_token') {
    callbacks.onQuizToken?.(String(data.token || ''));
  }
  if (event === 'quiz_reset') {
    callbacks.onQuizReset?.();
  }
  if (event === 'done') {
    callbacks.onDone?.(
      String(data.message_id || ''),
      (data.sources as ChatSource[]) || [],
      data.quiz_paper_id ? String(data.quiz_paper_id) : null,
    );
  }
  if (event === 'error') {
    callbacks.onError?.(String(data.message || '对话处理失败'));
  }
};

export const chatApi = {
  async enhancePrompt(content: string, signal?: AbortSignal): Promise<string> {
    const response = await http.post<APIResponse<PromptEnhanceResponse>>(
      '/chat/prompts/enhance',
      { content },
      { signal },
    );
    return unwrap(response).content;
  },

  async createSession(title?: string): Promise<ChatSession> {
    return unwrap(await http.post<APIResponse<ChatSession>>('/chat/sessions', { title }));
  },

  async listSessions(params: PaginationParams = {}): Promise<PaginatedData<ChatSession>> {
    return unwrap(
      await http.get<APIResponse<PaginatedData<ChatSession>>>('/chat/sessions', {
        params: {
          page: params.page || 1,
          page_size: params.page_size || 50,
        },
      }),
    );
  },

  async getSession(sessionId: string): Promise<ChatSessionDetail> {
    return unwrap(await http.get<APIResponse<ChatSessionDetail>>(`/chat/sessions/${sessionId}`));
  },

  async deleteSession(sessionId: string): Promise<boolean> {
    return unwrap(await http.delete<APIResponse<boolean>>(`/chat/sessions/${sessionId}`));
  },

  async updateSessionCapabilities(
    sessionId: string,
    capabilities: ChatCapability[],
  ): Promise<ChatSession> {
    return unwrap(
      await http.put<APIResponse<ChatSession>>(`/chat/sessions/${sessionId}/capabilities`, {
        capabilities,
      }),
    );
  },

  async streamMessage(
    sessionId: string,
    content: string,
    callbacks: ChatStreamCallbacks,
    signal?: AbortSignal,
    documentIds: string[] = [],
    capabilities: ChatCapability[] = [],
  ): Promise<void> {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        document_ids: documentIds,
        capabilities,
      }),
      signal,
    });

    if (!response.ok || !response.body) {
      let detail = '';
      try {
        const payload = await response.json() as { message?: string; detail?: string };
        detail = payload.message || payload.detail || '';
      } catch { /* non-JSON response */ }
      throw new Error(detail || '暂时无法连接对话服务，请检查模型配置后重试。');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              parseSsePayload(currentEvent, line.slice(6), callbacks);
            } catch {
              callbacks.onError?.('对话服务返回了无法识别的响应，请稍后重试。');
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};
