import http from './http';
import type { APIResponse } from '@/types/api';

export interface ModelOption { id: string; label: string; base_url: string; provider: string }
export interface SetupStatus { configured: boolean; connected: boolean; model_name: string; base_url: string; api_key_configured: boolean; message: string }
export interface SetupConfig { api_key: string; model_name: string; base_url: string; provider: string }
export interface SetupConfigResponse { status: SetupStatus; models: ModelOption[] }

const unwrap = <T>(response: { data: APIResponse<T> }) => response.data.data;
export const setupApi = {
  async getStatus(): Promise<SetupStatus> { return unwrap(await http.get<APIResponse<SetupStatus>>('/setup/status')); },
  async saveConfig(config: SetupConfig): Promise<SetupConfigResponse> { return unwrap(await http.post<APIResponse<SetupConfigResponse>>('/setup/config', config)); },
};
