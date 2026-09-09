/** 统一 API 响应格式 */
export interface APIResponse<T = unknown> {
  success?: boolean;
  code: number;
  message: string;
  data: T;
}

/** 分页数据 */
export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** 分页请求参数 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}
