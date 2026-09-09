import type { ChatMessage, ChatSource, ChatStep } from '@/services/chat';
import type { QuizStreamPayload } from '@/types/quiz';
import AiCitations from '../AiCitations';
import AiMarkdown from '../AiMarkdown';
import AiThinking from '../AiThinking';
import AiWebSearch from '../AiWebSearch';
import AiSteps from '../AiSteps';
import AiQuizCard from '../AiQuizCard';
import StreamingText from '../StreamingText';
import styles from './index.module.less';

const statusText: Record<string, string> = {
  generating_quiz: '生成练习题',
  thinking: '读取会话记忆',
  searching_knowledge: '检索本地知识库',
  searching_web: '联网搜索',
  generating: '生成回答',
};

interface AiMessageProps {
  message: ChatMessage;
  /** 该消息是否正在流式生成（仅当前最后一条 assistant 消息为 true） */
  streaming?: boolean;
  /** 后端是否仍在接收 SSE，用于区分网络状态和前端打字播放状态 */
  receiving?: boolean;
  /** 当前流状态（thinking / searching_web / generating ...） */
  streamStatus?: string;
  /** 流式过程中的实时来源（优先于 message.sources） */
  sources?: ChatSource[];
  steps?: ChatStep[];
  quizPayload?: QuizStreamPayload | null;
  quizStreamText?: string;
  onPlaybackComplete?: () => void;
}

/** 消息气泡：user 右对齐纯文本，assistant 支持思考状态、流式输出与来源列表 */
const AiMessage: React.FC<AiMessageProps> = ({
  message,
  streaming,
  receiving,
  streamStatus,
  sources,
  steps,
  quizPayload,
  quizStreamText,
  onPlaybackComplete,
}) => {
  const effectiveSources = sources ?? message.sources ?? [];

  if (message.role === 'user') {
    return (
      <article className={`${styles.messageRow} ${styles.userRow}`}>
        <div className={`${styles.bubble} ${styles.userBubble}`}>{message.content}</div>
      </article>
    );
  }

  const showSearch = Boolean(streaming && streamStatus === 'searching_web');
  const showQuizCard = Boolean(message.quiz_paper_id) && !streaming;
  const showQuizStream = Boolean(streaming && quizStreamText);

  return (
    <article className={styles.messageRow}>
      <div className={styles.messageStack}>
        {steps?.length ? <AiSteps steps={steps} /> : null}
        {showQuizStream ? (
          <div className={styles.quizStreamWrap}>
            <div className={styles.quizStreamLabel}>试卷生成中...</div>
            <pre className={styles.quizStreamPanel}>{quizStreamText}</pre>
          </div>
        ) : null}

        {showQuizCard && message.quiz_paper_id ? (
          <div className={styles.bubble}>
            <AiQuizCard paperId={message.quiz_paper_id} payload={quizPayload ?? null} />
            <AiCitations sources={effectiveSources} />
          </div>
        ) : message.content ? <div className={styles.bubble}>
          {message.content ? (
            streaming ? (
              <StreamingText
                text={message.content}
                streaming={receiving}
                onComplete={onPlaybackComplete}
              />
            ) : (
              <AiMarkdown content={message.content} />
            )
          ) : null}
          <AiCitations sources={effectiveSources} />
        </div> : null}

        {showSearch ? (
          <div className={styles.statusRow}>
            <AiWebSearch status={streamStatus ?? ''} sources={effectiveSources} />
          </div>
        ) : streaming && streamStatus ? (
          <div className={styles.statusRow}>
            <AiThinking text={statusText[streamStatus] ?? '准备生成...'} />
          </div>
        ) : null}
      </div>
    </article>
  );
};

export default AiMessage;
