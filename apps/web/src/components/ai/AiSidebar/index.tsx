import { useRef } from 'react';
import { ImagePlus, PanelLeftClose, Trash2, X } from 'lucide-react';
import type { ChatSession } from '@/services/chat';
import type { BackgroundOption } from '../types';
import styles from './index.module.less';

interface AiSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  loading: boolean;
  /** 桌面端是否折叠（宽度收缩为 0） */
  collapsed: boolean;
  /** 移动端断点（<760px） */
  isMobile: boolean;
  /** 移动端抽屉是否打开 */
  visible: boolean;
  backgrounds: BackgroundOption[];
  backgroundId: string;
  onCollapsedChange: (collapsed: boolean) => void;
  onCloseMobile: () => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onBackgroundChange: (id: string) => void;
  onBackgroundAdd: (file: File) => void;
  onBackgroundDelete: (id: string) => void;
}

const formatTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/** 会话侧边栏：新建/删除会话、背景切换、主题切换。移动端以抽屉形式呈现 */
const AiSidebar: React.FC<AiSidebarProps> = ({
  sessions,
  activeSessionId,
  loading,
  collapsed,
  isMobile,
  visible,
  backgrounds,
  backgroundId,
  onCollapsedChange,
  onCloseMobile,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
  onBackgroundChange,
  onBackgroundAdd,
  onBackgroundDelete,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selectedBackground = backgrounds.find((option) => option.id === backgroundId);
  const asideClass = [
    styles.sidebar,
    isMobile ? styles.mobileSidebar : '',
    isMobile && visible ? styles.mobileOpen : '',
    isMobile && !visible ? styles.mobileHidden : '',
    !isMobile && collapsed ? styles.collapsed : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      {isMobile && (
        <div
          className={`${styles.backdrop} ${visible ? styles.backdropVisible : ''}`}
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}
      <aside className={asideClass} aria-label="会话侧边栏">
        <div className={styles.brandHeader}>
          <div className={styles.brandLogo}>
            <img src="/C-Learner_combined_logo.svg" alt="C-Learner" />
          </div>
          {isMobile ? (
            <button
              type="button"
              className={styles.iconBtn}
              aria-label="关闭侧边栏"
              onClick={onCloseMobile}
            >
              <X size={16} />
            </button>
          ) : (
            <button
              type="button"
              className={styles.iconBtn}
              aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
              onClick={() => onCollapsedChange(!collapsed)}
            >
              <PanelLeftClose size={16} />
            </button>
          )}
        </div>
        <div className={styles.sidebarTop}>
          <button type="button" className={styles.newSessionBtn} onClick={onCreateSession}>
            <span>新建对话</span>
          </button>
        </div>

        <div className={styles.sessionList}>
          {loading && <div className={styles.empty}>加载中...</div>}
          {!loading && sessions.length === 0 && <div className={styles.empty}>暂无会话</div>}
          {sessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                className={`${styles.sessionItem} ${active ? styles.sessionItemActive : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => onSelectSession(session.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectSession(session.id);
                  }
                }}
              >
                <div className={styles.sessionInfo}>
                  <span className={styles.sessionTitle}>{session.title}</span>
                  <span className={styles.sessionMeta}>
                    {formatTime(session.updated_at)} · {session.message_count} 条
                  </span>
                </div>
                <button
                  type="button"
                  className={styles.deleteBtn}
                  aria-label={`删除会话 ${session.title}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })}
        </div>

        <div className={styles.sidebarFooter}>
          <div className={styles.bgSection}>
            <div className={styles.bgHeader}>
              <span className={styles.bgLabel}>背景图</span>
              <div className={styles.bgActions}>
                <button
                  type="button"
                  className={styles.bgActionBtn}
                  aria-label="添加背景图"
                  title="添加背景图"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <ImagePlus size={14} />
                </button>
                <button
                  type="button"
                  className={styles.bgActionBtn}
                  aria-label="删除当前背景图"
                  title={selectedBackground ? '删除当前背景图' : '暂无可删除的背景图'}
                  disabled={!selectedBackground?.removable}
                  onClick={() => onBackgroundDelete(backgroundId)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <input
                ref={fileInputRef}
                className={styles.fileInput}
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onBackgroundAdd(file);
                  event.target.value = '';
                }}
              />
            </div>
            <div className={styles.bgThumbs}>
              {backgrounds.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`${styles.bgThumb} ${
                    backgroundId === option.id ? styles.bgThumbActive : ''
                  }`}
                  style={{ backgroundImage: `url(${option.url})` }}
                  aria-label={`切换背景：${option.label}`}
                  aria-pressed={backgroundId === option.id}
                  onClick={() => onBackgroundChange(option.id)}
                />
              ))}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default AiSidebar;
