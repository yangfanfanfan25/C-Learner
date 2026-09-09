import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileJson, FileText, Play } from 'lucide-react';
import { message } from 'antd';
import { quizApi } from '@/services/quiz';
import type { QuizPaperDetail, QuizQuestion, QuizStreamPayload } from '@/types/quiz';
import styles from './index.module.less';

const TYPE_NAMES: Record<string, string> = {
  choice: '选择题',
  multi_choice: '多选题',
  true_false: '判断题',
  fill: '填空题',
  short_answer: '简答题',
};

const DIFFICULTY_NAMES: Record<number, string> = {
  1: '基础',
  2: '进阶',
  3: '综合',
};

interface AiQuizCardProps {
  paperId: string;
  /** 流式期间直接使用 SSE quiz 事件载荷；会话重载时为 undefined，由卡片内部获取 */
  payload?: QuizStreamPayload | null;
}

/** 聊天内联试卷卡片：元信息 + 题目预览 + 下载链接 + 开始答题跳转 */
const AiQuizCard: React.FC<AiQuizCardProps> = ({ paperId, payload }) => {
  const navigate = useNavigate();
  const [paper, setPaper] = useState<QuizPaperDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (payload) return;
    let cancelled = false;
    setLoading(true);
    quizApi
      .getPaper(paperId)
      .then((detail) => {
        if (!cancelled) setPaper(detail);
      })
      .catch(() => {
        if (!cancelled) message.error('试卷加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [paperId, payload]);

  if (loading) {
    return <div className={styles.card}>试卷加载中…</div>;
  }

  const detail = payload
    ? {
        id: paperId,
        title: payload.title,
        difficulty: payload.difficulty,
        question_types: payload.question_types,
        total: payload.total,
        questions: payload.questions,
        downloads: payload.downloads,
      }
    : paper;
  if (!detail) {
    return <div className={styles.card}>试卷已失效</div>;
  }

  const previewQuestions = expanded ? detail.questions : detail.questions.slice(0, 3);

  const renderQuestion = (question: QuizQuestion, index: number) => (
    <div key={question.id} className={styles.question}>
      <div className={styles.questionHead}>
        <span className={styles.questionIndex}>{index + 1}</span>
        <span className={styles.questionStem}>{question.stem}</span>
      </div>
      {question.options.length > 0 && (
        <div className={styles.options}>
          {question.options.map((option) => (
            <div key={option.key} className={styles.option}>
              <span className={styles.optionKey}>{option.key}.</span>
              <span>{option.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <div className={styles.title}>{detail.title}</div>
        <div className={styles.meta}>
          <span>难度：{DIFFICULTY_NAMES[detail.difficulty] ?? detail.difficulty}</span>
          <span>共 {detail.total} 题</span>
          <span>题型：{(detail.question_types ?? []).map((t) => TYPE_NAMES[t] ?? t).join('、') || '—'}</span>
        </div>
      </div>

      <div className={styles.preview}>{previewQuestions.map(renderQuestion)}</div>
      {detail.questions.length > 3 && (
        <button type="button" className={styles.expandBtn} onClick={() => setExpanded((v) => !v)}>
          {expanded ? '收起' : `展开全部 ${detail.questions.length} 题`}
        </button>
      )}

      <div className={styles.actions}>
        {detail.downloads?.md && (
          <a className={styles.actionBtn} href={detail.downloads.md} download>
            <FileText size={13} />
            下载 Markdown
          </a>
        )}
        {detail.downloads?.json && (
          <a className={styles.actionBtn} href={detail.downloads.json} download>
            <FileJson size={13} />
            下载 JSON
          </a>
        )}
        <button
          type="button"
          className={`${styles.actionBtn} ${styles.primaryBtn}`}
          onClick={() => navigate(`/quiz/${paperId}`)}
        >
          <Play size={13} />
          开始答题 →
        </button>
      </div>
    </div>
  );
};

export default AiQuizCard;
