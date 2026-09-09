import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileJson,
  FileText,
  XCircle,
} from 'lucide-react';
import {
  Button,
  Checkbox,
  Empty,
  Input,
  Radio,
  Result,
  Spin,
  Tag,
  message,
} from 'antd';
import { quizApi } from '@/services/quiz';
import type {
  QuizAnswerInput,
  QuizGradeResult,
  QuizPaperDetail,
  QuizQuestion,
} from '@/types/quiz';
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

type Answers = Record<string, string | string[] | boolean>;

const QuizPage: React.FC = () => {
  const { paperId = '' } = useParams<{ paperId: string }>();
  const navigate = useNavigate();

  const [paper, setPaper] = useState<QuizPaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState<Answers>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizGradeResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    quizApi
      .getPaper(paperId)
      .then((detail) => {
        if (cancelled) return;
        setPaper(detail);
      })
      .catch(() => {
        if (!cancelled) message.error('试卷加载失败，可能已失效');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [paperId]);

  const unansweredCount = useMemo(() => {
    if (!paper) return 0;
    return paper.questions.filter((question) => answers[question.id] === undefined).length;
  }, [paper, answers]);

  const setAnswer = (questionId: string, value: string | string[] | boolean) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    setResult(null);
  };

  const handleSubmit = async () => {
    if (!paper) return;
    if (unansweredCount > 0) {
      message.warning(`还有 ${unansweredCount} 题未作答`);
      return;
    }
    setSubmitting(true);
    try {
      const payload: QuizAnswerInput[] = paper.questions.map((question) => ({
        question_id: question.id,
        value: answers[question.id] ?? '',
      }));
      const grade = await quizApi.grade(paper.id, payload);
      setResult(grade);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '判分失败');
    } finally {
      setSubmitting(false);
    }
  };

  const renderInput = (question: QuizQuestion) => {
    const value = answers[question.id];
    if (question.type === 'choice') {
      return (
        <Radio.Group
          value={value as string}
          onChange={(e) => setAnswer(question.id, e.target.value)}
        >
          {question.options.map((option) => (
            <Radio key={option.key} value={option.key} className={styles.optionRow}>
              {option.key}. {option.text}
            </Radio>
          ))}
        </Radio.Group>
      );
    }
    if (question.type === 'multi_choice') {
      return (
        <Checkbox.Group
          value={(value as string[]) || []}
          onChange={(checked) => setAnswer(question.id, checked as string[])}
          className={styles.optionRow}
        >
          {question.options.map((option) => (
            <Checkbox key={option.key} value={option.key} className={styles.optionRow}>
              {option.key}. {option.text}
            </Checkbox>
          ))}
        </Checkbox.Group>
      );
    }
    if (question.type === 'true_false') {
      return (
        <Radio.Group
          value={value as boolean}
          onChange={(e) => setAnswer(question.id, e.target.value)}
        >
          <Radio value={true} className={styles.optionRow}>
            正确
          </Radio>
          <Radio value={false} className={styles.optionRow}>
            错误
          </Radio>
        </Radio.Group>
      );
    }
    if (question.type === 'fill') {
      return (
        <Input
          value={(value as string) || ''}
          placeholder="请输入答案"
          onChange={(e) => setAnswer(question.id, e.target.value)}
        />
      );
    }
    return (
      <Input.TextArea
        value={(value as string) || ''}
        placeholder="请输入答案要点"
        rows={3}
        onChange={(e) => setAnswer(question.id, e.target.value)}
      />
    );
  };

  const renderResult = (question: QuizQuestion) => {
    const item = result?.results.find((r) => r.question_id === question.id);
    if (!item) return null;
    return (
      <div className={styles.resultLine}>
        <span className={styles.resultMark}>
          {item.correct === null ? (
            <Tag color="default">未判分</Tag>
          ) : item.correct ? (
            <CheckCircle2 size={15} color="#52c41a" />
          ) : (
            <XCircle size={15} color="#ff4d4f" />
          )}
        </span>
        <span className={styles.resultText}>
          正确答案：{formatAnswer(question.answer)}
          {item.correct === false && item.user_answer !== undefined && (
            <span className={styles.wrongAnswer}>
              {' '}
              （你的答案：{formatAnswer(item.user_answer)}）
            </span>
          )}
        </span>
        {item.explanation && <span className={styles.explanation}>解析：{item.explanation}</span>}
      </div>
    );
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.center}>
          <Spin tip="试卷加载中…" />
        </div>
      </div>
    );
  }

  if (!paper) {
    return (
      <div className={styles.page}>
        <Empty description="试卷不存在或已失效">
          <Button type="primary" onClick={() => navigate('/chat')}>
            返回对话
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.toolbar}>
          <Button icon={<ArrowLeft size={14} />} onClick={() => navigate(-1)}>
            返回对话
          </Button>
          <div className={styles.toolbarSpacer} />
          {paper.downloads?.md && (
            <a className={styles.downloadLink} href={paper.downloads.md} download>
              <FileText size={13} /> Markdown
            </a>
          )}
          {paper.downloads?.json && (
            <a className={styles.downloadLink} href={paper.downloads.json} download>
              <FileJson size={13} /> JSON
            </a>
          )}
          <Download size={13} className={styles.downloadIcon} />
        </div>

        <div className={styles.header}>
          <h1 className={styles.title}>{paper.title}</h1>
          <div className={styles.meta}>
            <span>难度：{DIFFICULTY_NAMES[paper.difficulty] ?? paper.difficulty}</span>
            <span>共 {paper.total} 题</span>
            <span>题型：{(paper.question_types ?? []).map((t) => TYPE_NAMES[t] ?? t).join('、') || '—'}</span>
            {paper.document_titles.length > 0 && (
              <span>依据：{paper.document_titles.join('、')}</span>
            )}
          </div>
        </div>

        <div className={styles.questionList}>
          {paper.questions.map((question, index) => (
            <div key={question.id} className={styles.questionCard}>
              <div className={styles.questionHead}>
                <span className={styles.questionIndex}>{index + 1}.</span>
                <span className={styles.questionStem}>{question.stem}</span>
                <Tag className={styles.typeTag}>{TYPE_NAMES[question.type] ?? question.type}</Tag>
              </div>
              <div className={styles.answerArea}>{renderInput(question)}</div>
              {result && renderResult(question)}
            </div>
          ))}
        </div>

        {result ? (
          <Result
            className={styles.scoreCard}
            status="success"
            title={`得分：${result.score} 分`}
            subTitle={`答对 ${result.correct_count} / ${result.total} 题`}
            extra={[
              <Button key="again" onClick={() => setResult(null)}>
                重新作答
              </Button>,
              <Button key="back" type="primary" onClick={() => navigate(-1)}>
                返回对话
              </Button>,
            ]}
          />
        ) : (
          <div className={styles.submitBar}>
            <Button
              type="primary"
              size="large"
              loading={submitting}
              onClick={handleSubmit}
              className={styles.submitBtn}
            >
              提交并判分
            </Button>
            {unansweredCount > 0 && (
              <span className={styles.unansweredHint}>还有 {unansweredCount} 题未作答</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const formatAnswer = (value: string | string[] | boolean | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  if (Array.isArray(value)) return value.join('、');
  if (typeof value === 'boolean') return value ? '正确' : '错误';
  return String(value);
};

export default QuizPage;
