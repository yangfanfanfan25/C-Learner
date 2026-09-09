import { useState } from 'react';
import { Check, ChevronDown, Globe, Search } from 'lucide-react';
import type { ChatSource } from '@/services/chat';
import styles from './index.module.less';

interface AiWebSearchProps {
  /** 真实 SSE 流状态：'searching_web' 时处于检索动画 */
  status: string;
  sources: ChatSource[];
  query?: string;
}

/**
 * 联网搜索状态 + 结果列表（来自 aicss WebSearch）。
 * 三态动画由真实 SSE `status`/`sources` 驱动，结果列表只展示真实来源，
 * 不使用示例 JWT 搜索结果。
 */
const AiWebSearch: React.FC<AiWebSearchProps> = ({ status, sources, query }) => {
  const [open, setOpen] = useState(true);
  const searching = status === 'searching_web';
  const done = !searching;
  const results = sources || [];

  if (!searching && results.length === 0) return null;

  return (
    <div className={styles.ws} data-state={done ? 'done' : 'loading'}>
      <div className={styles.wsRow}>
        <Search size={13} className={styles.wsSearchIcon} aria-hidden="true" />
        <span className={styles.wsLabel}>
          <span className={`${styles.wsShimmer} ${done ? styles.isDone : ''}`}>
            {done ? '已检索到' : '正在搜索'}
            {query ? <span className={styles.wsQuote}>“{query}”</span> : null}
          </span>
          <button
            type="button"
            className={styles.wsChevron}
            aria-label="展开/收起搜索结果"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <ChevronDown size={10} />
          </button>
        </span>
      </div>

      <div className={`${styles.wsCollapsible} ${open ? '' : styles.isCollapsed}`}>
        <div className={styles.wsCollapsibleInner}>
          <div className={styles.wsResults}>
            <span className={styles.wsRail} aria-hidden="true" />
            <ul className={styles.wsList}>
              {results.length === 0 ? (
                <li className={styles.wsEmpty}>正在检索来源…</li>
              ) : (
                results.map((source, index) => {
                  // 检索中：最后一个来源处于 loading（globe 动画），其余完成
                  const isLast = index === results.length - 1;
                  const state = !searching ? 'done' : isLast ? 'loading' : 'done';
                  return (
                    <li
                      key={source.id || index}
                      className={styles.wsSite}
                      data-state={state}
                    >
                      <span className={styles.wsBullet} aria-hidden="true">
                        <span className={styles.wsDots}>
                          <Globe size={14} className={styles.wsDotsIcon} />
                        </span>
                        <span className={styles.wsGlobe}>
                          <GlobeSVG />
                        </span>
                        <span className={styles.wsCheck}>
                          <Check size={14} />
                        </span>
                      </span>
                      <span className={styles.wsTitle}>{source.title || source.id}</span>
                      {source.url && (
                        <>
                          <span className={styles.wsSep}>·</span>
                          <span className={styles.wsUrl}>{source.url}</span>
                        </>
                      )}
                    </li>
                  );
                })
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

/** aicss 旋转地球动画（六条子午线，相位偏移 1/6 周期） */
const GlobeSVG: React.FC = () => {
  const L =
    'M6.057 11.565 C2.081 11.565 0.371 8.159 0.371 5.964 C0.371 3.642 2.152 0.329 6.05 0.329';
  const ML =
    'M6.012 11.55 C4.575 10.496 3.333 8.116 3.321 5.964 C3.307 3.399 4.974 0.977 6.012 0.329';
  const MR =
    'M6.012 11.55 C7.211 10.781 8.715 8.287 8.715 5.964 C8.715 3.399 7.24 1.233 6.012 0.329';
  const R =
    'M6.012 11.55 C9.677 11.55 11.65 8.487 11.65 5.964 C11.65 3.499 9.748 0.329 6.012 0.329';
  const values = [L, ML, MR, R, L].join(';');

  return (
    <svg
      viewBox="0 0 12 12"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="0.85"
      strokeLinecap="round"
      style={{ overflow: 'visible' }}
      aria-hidden="true"
    >
      <circle cx="6" cy="6" r="5.7" opacity="0.9" />
      <line x1="0.3" y1="6" x2="11.7" y2="6" opacity="0.9" />
      {['0s', '-1.2s', '-2.4s', '-3.6s', '-4.8s', '-6s'].map((begin) => (
        <path key={begin} d={L} opacity="0">
          <animate
            attributeName="d"
            dur="7.2s"
            begin={begin}
            repeatCount="indefinite"
            calcMode="spline"
            keyTimes="0;0.25;0.5;0.75;1"
            keySplines="0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1;0.42 0 0.58 1"
            values={values}
          />
          <animate
            attributeName="opacity"
            dur="7.2s"
            begin={begin}
            repeatCount="indefinite"
            calcMode="linear"
            keyTimes="0;0.05;0.7;0.75;1"
            values="0;0.9;0.9;0;0"
          />
        </path>
      ))}
    </svg>
  );
};

export default AiWebSearch;
