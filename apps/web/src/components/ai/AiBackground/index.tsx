import type { ThemeMode } from '@/contexts/ThemeContext';
import styles from './index.module.less';

interface AiBackgroundProps {
  backgroundUrl?: string;
  theme: ThemeMode;
}

/** Background image remains visible in both themes; dark-mode treatment is CSS-only. */
const AiBackground: React.FC<AiBackgroundProps> = ({ backgroundUrl, theme }) => {
  return (
    <div
      className={styles.background}
      data-theme={theme}
      style={{ backgroundImage: backgroundUrl ? `url(${backgroundUrl})` : 'none' }}
      aria-hidden="true"
    />
  );
};

export default AiBackground;
