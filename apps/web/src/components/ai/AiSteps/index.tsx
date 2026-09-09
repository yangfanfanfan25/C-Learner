import { CheckCircle2, LoaderCircle } from 'lucide-react';
import type { ChatStep } from '@/services/chat';
import styles from './index.module.less';

interface AiStepsProps {
  steps: ChatStep[];
}

const KIND_ICONS: Record<ChatStep['kind'], React.ReactNode> = {
  tool_start: <LoaderCircle size={13} className={styles.spin} aria-hidden="true" />,
  tool_result: <CheckCircle2 size={13} aria-hidden="true" />,
};

const AiSteps: React.FC<AiStepsProps> = ({ steps }) => (
  <div className={styles.steps} aria-label="执行步骤">
    <ul className={styles.list}>
      {steps.map((step) => (
        <li key={step.id} className={styles.item} data-kind={step.kind}>
          <span className={styles.icon} aria-hidden="true">{KIND_ICONS[step.kind] ?? null}</span>
          <span className={styles.text}>
            <span className={styles.message}>{step.message}</span>
            {step.args ? <code className={styles.args}>{JSON.stringify(step.args)}</code> : null}
            {step.kind === 'tool_result' && step.output ? <pre className={styles.output}>{step.output}</pre> : null}
          </span>
        </li>
      ))}
    </ul>
  </div>
);

export default AiSteps;
