import AiAgent from '@/components/ai/AiAgent';

/**
 * Chat 页组装层：直接渲染智能体对话页。
 * 会话、消息、SSE 流式等逻辑全部在 `AiAgent` 内维护。
 */
const ChatPage: React.FC = () => {
  return <AiAgent />;
};

export default ChatPage;
