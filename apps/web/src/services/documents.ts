import http from './http';
import type { APIResponse, PaginatedData, PaginationParams } from '@/types/api';

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface DocumentRecord {
  id: string;
  filename: string;
  course_name: string;
  academic_year: number;
  semester: number;
  content_type: string;
  file_size: number;
  status: DocumentStatus;
  error_message: string | null;
  chapter_count: number;
  chunk_count: number;
  created_at: string;
  processed_at: string | null;
}

export interface DocumentChunkSummary {
  id: string;
  title: string;
  chapter: string;
  section: string;
  content: string;
  source_pages: number[];
  tags: string[];
}

export interface DocumentDetail extends DocumentRecord {
  chunks: DocumentChunkSummary[];
}

export interface DocumentProcessResponse {
  document: DocumentRecord;
  chapter_count: number;
  chunk_count: number;
  indexed_count: number;
}

const unwrap = <T>(response: { data: APIResponse<T> }) => response.data.data;

export const documentsApi = {
  async processFile(file: File, metadata: { course_name: string; academic_year: number; semester: number }): Promise<DocumentProcessResponse> {
    const form = new FormData();
    form.append('file', file);
    form.append('course_name', metadata.course_name);
    form.append('academic_year', String(metadata.academic_year));
    form.append('semester', String(metadata.semester));
    return unwrap(
      await http.post<APIResponse<DocumentProcessResponse>>('/documents/process', form, {
        // http 实例默认 Content-Type 为 application/json，会把 FormData 序列化成 JSON，
        // 后端 multipart 校验失败返回 422。置为 undefined 由浏览器生成 multipart 头。
        headers: { 'Content-Type': undefined },
      }),
    );
  },

  async listDocuments(params: PaginationParams = {}): Promise<PaginatedData<DocumentRecord>> {
    return unwrap(
      await http.get<APIResponse<PaginatedData<DocumentRecord>>>('/documents', {
        params: {
          page: params.page || 1,
          page_size: params.page_size || 20,
        },
      }),
    );
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    return unwrap(
      await http.get<APIResponse<DocumentDetail>>(`/documents/${documentId}`),
    );
  },

  async deleteDocument(documentId: string): Promise<boolean> {
    return unwrap(await http.delete<APIResponse<boolean>>(`/documents/${documentId}`));
  },

  /**
   * 原始文件下载直链。
   * 返回二进制流，不走 axios（拦截器按 APIResponse 解析，处理二进制流会出错），
   * 由调用方用原生 fetch / <a download> 触发。
   */
  getFileDownloadUrl(documentId: string): string {
    return `/api/documents/${documentId}/file`;
  },

  /**
   * 加工后知识点（Markdown）下载直链。
   * 同样返回二进制流，由调用方用原生 fetch 触发。
   */
  getKnowledgeMarkdownUrl(documentId: string): string {
    return `/api/documents/${documentId}/knowledge.md`;
  },
};
