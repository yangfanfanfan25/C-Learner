/** 模拟练习（Quiz）相关类型 —— 与后端 app/schemas/quiz.py 逐字段对齐 */

export type QuizQuestionType =
  | 'choice'
  | 'multi_choice'
  | 'true_false'
  | 'fill'
  | 'short_answer';

export interface QuizOption {
  key: string;
  text: string;
}

export interface QuizQuestion {
  id: string;
  type: QuizQuestionType;
  stem: string;
  options: QuizOption[];
  answer: string | string[] | boolean;
  explanation: string;
  knowledge_points: string[];
  difficulty: number;
}

/** 试卷核心结构（LLM 结构化输出的目标结构） */
export interface QuizPaper {
  title: string;
  difficulty: number;
  question_types: QuizQuestionType[];
  total: number;
  questions: QuizQuestion[];
}

/** 试卷详情响应（聊天重载与在线答题页共用） */
export interface QuizPaperDetail {
  id: string;
  session_id?: string | null;
  title: string;
  document_ids: string[];
  document_titles: string[];
  requirements?: string | null;
  difficulty: number;
  question_types: QuizQuestionType[];
  total: number;
  questions: QuizQuestion[];
  downloads?: { md: string; json: string } | null;
  created_at: string;
}

/** SSE quiz 事件载荷（一次性下发，用于聊天内联卡片） */
export interface QuizStreamPayload {
  paper_id: string;
  title: string;
  total: number;
  difficulty: number;
  question_types: QuizQuestionType[];
  downloads?: { md: string; json: string } | null;
  questions: QuizQuestion[];
}

export interface QuizAnswerInput {
  question_id: string;
  value: string | string[] | boolean;
}

export interface QuizGradeResultItem {
  question_id: string;
  correct: boolean | null;
  user_answer?: string | string[] | boolean | null;
  correct_answer?: string | string[] | boolean | null;
  explanation: string;
}

export interface QuizGradeResult {
  paper_id: string;
  total: number;
  correct_count: number;
  score: number;
  results: QuizGradeResultItem[];
}
