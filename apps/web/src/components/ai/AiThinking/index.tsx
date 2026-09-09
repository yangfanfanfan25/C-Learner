import { LoaderCircle } from 'lucide-react';
import styles from './index.module.less';

interface AiThinkingProps {
  /** 思考/处理中展示的文字，默认 "思考中..." */
  text?: string;
}

/** 思考/处理中状态文字（扫光动画），来自 aicss ThinkingState */
const AiThinking: React.FC<AiThinkingProps> = ({ text = '思考中...' }) => {
  return (
    <div className={styles.status} role="status" aria-live="polite">
      <LoaderCircle size={14} className={styles.icon} aria-hidden="true" />
      <span className={styles.shimmer}>{text}</span>
    </div>
  );
};

export default AiThinking;
