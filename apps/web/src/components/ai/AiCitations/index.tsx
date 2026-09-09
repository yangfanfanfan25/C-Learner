import { ArrowUpRight } from 'lucide-react';
import type { ChatSource } from '@/services/chat';
import styles from './index.module.less';

interface AiCitationsProps {
  sources: ChatSource[];
}

const hostOf = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

/**
 * 消息底部的真实来源列表（来自 aicss InlineCitations 的 footer 部分）。
 * 后端尚未提供引用编号/正文位置，故只渲染来源列表，不渲染 `[n]` 内联角标。
 */
const AiCitations: React.FC<AiCitationsProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className={styles.citeFooter}>
      {sources.map((source, index) => {
        const host = source.url ? hostOf(source.url) : undefined;
        const inner = (
          <>
            <span className={styles.citeMark}>{index + 1}</span>
            <span className={styles.citeRefLabel}>{source.title || source.id}</span>
            {host && (
              <>
                <span className={styles.citeSep}>·</span>
                <span className={styles.citeRefHost}>{host}</span>
              </>
            )}
            <span className={styles.citeArrow} aria-hidden="true">
              <ArrowUpRight size={10} strokeWidth={1.8} />
            </span>
          </>
        );
        return source.url ? (
          <a
            key={source.id || index}
            className={styles.citeRef}
            href={source.url}
            target="_blank"
            rel="noreferrer"
          >
            {inner}
          </a>
        ) : (
          <span key={source.id || index} className={styles.citeRef}>
            {inner}
          </span>
        );
      })}
    </div>
  );
};

export default AiCitations;
