import type { ChatSource } from '@/services/chat';
import type { ChatCapability } from '@/types/chat';

/** 技能项（前端预置；能力类技能插入正文的 pill 在提交时剥离出 content，转入 capabilities 字段） */
export interface Skill {
  id: string;
  name: string;
  /** 若存在，该项是聊天能力：提交时以 id 进入 capabilities 字段 */
  capability?: ChatCapability;
}

export const SKILLS: Skill[] = [
  { id: 'knowledge', name: '知识问答', capability: 'knowledge' },
  { id: 'practice', name: '模拟练习', capability: 'practice' },
  { id: 'web_search', name: '联网搜索', capability: 'web_search' },
  { id: 'deep-research', name: '深度研究' },
  { id: 'code-review', name: '代码审查' },
  { id: 'summarize', name: '内容总结' },
];

/** 后端 content 字段字符上限（防止拼接技能文本后超限） */
export const MAX_CONTENT_LENGTH = 10000;

/** AiComposer 提交负载（技能文本已拼入 content，@ 选择的文档 ID 单独携带） */
export interface ComposerPayload {
  content: string;
  /** 通过 @ 选择的文档 ID 列表（练习模式作为出题上下文） */
  documentIds?: string[];
  capabilities?: ChatCapability[];
}

export interface BackgroundOption {
  id: string;
  label: string;
  url: string;
  removable?: boolean;
}

/** 背景图选项（仅「无背景」为内置项，其余背景由用户上传后动态加入） */
export const BACKGROUNDS: BackgroundOption[] = [
  { id: 'builtin-none', label: '无背景', url: '' },
];

export type { ChatSource };
export type { ChatCapability };
