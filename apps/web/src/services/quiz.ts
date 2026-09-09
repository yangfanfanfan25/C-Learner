import http from './http';
import type { APIResponse } from '@/types/api';
import type { QuizAnswerInput, QuizGradeResult, QuizPaperDetail } from '@/types/quiz';

const unwrap = <T>(response: { data: APIResponse<T> }) => response.data.data;

export const quizApi = {
  /** 获取试卷详情（含题目） */
  async getPaper(paperId: string): Promise<QuizPaperDetail> {
    return unwrap(await http.get<APIResponse<QuizPaperDetail>>(`/quiz/papers/${paperId}`));
  },

  /** 提交作答 → 判分 + 解析（后端不落库） */
  async grade(paperId: string, answers: QuizAnswerInput[]): Promise<QuizGradeResult> {
    return unwrap(
      await http.post<APIResponse<QuizGradeResult>>(`/quiz/papers/${paperId}/grade`, { answers }),
    );
  },

  /** 试卷导出文件下载直链（二进制流，由调用方用原生 <a download> 触发） */
  getDownloadUrl(paperId: string, format: 'md' | 'json'): string {
    return `/api/quiz/papers/${paperId}/download?format=${format}`;
  },
};
