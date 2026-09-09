import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, ListTodo, ListX } from 'lucide-react';
import styles from './index.module.less';

export interface TodoTask {
  id: string;
  label: string;
}

interface AiTodoListProps {
  tasks: TodoTask[];
  /** 当前进行中的任务下标；-1 表示未开始，>= tasks.length 表示全部完成 */
  current: number;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}

/** 待办/任务流（滚动计数 + 进度），来自 aicss TodoList，改为 props 驱动。生产页无数据时不渲染 */
const AiTodoList: React.FC<AiTodoListProps> = ({
  tasks,
  current,
  collapsed: collapsedProp,
  onCollapsedChange,
}) => {
  const [collapsedLocal, setCollapsedLocal] = useState(false);
  const collapsed = collapsedProp ?? collapsedLocal;
  const setCollapsed = onCollapsedChange ?? setCollapsedLocal;

  if (!tasks || tasks.length === 0) return null;

  const n = tasks.length;
  const allDone = current >= n;
  const running = current >= 0 && !allDone;
  const pct = Math.round((Math.min(Math.max(current, 0), n) / n) * 100);
  const countText = `${Math.min(Math.max(current, 0), n)}/${n}`;

  return (
    <div className={styles.todo}>
      <button
        type="button"
        className={styles.todoHead}
        aria-expanded={!collapsed}
        aria-label="切换待办列表"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className={styles.todoHeadIcon}>
          {allDone ? (
            <Check size={15} className={styles.todoHeadCheck} aria-hidden="true" />
          ) : running ? (
            <span className={styles.todoHeadPie} style={{ '--todo-pie': `${pct}%` } as React.CSSProperties} aria-hidden="true">
              <span className={styles.todoHeadPieFill} />
            </span>
          ) : (
            <ListTodo size={15} className={styles.todoListIcon} aria-hidden="true" />
          )}
          <ChevronDown size={13} className={styles.todoChevron} aria-hidden="true" />
        </span>
        <span className={styles.todoTitle}>待办</span>
        <span className={styles.todoCount}>
          <RollingCount value={countText} />
        </span>
      </button>

      <div className={`${styles.todoCollapsible} ${collapsed ? styles.isCollapsed : ''}`}>
        <div className={styles.todoInner}>
          <ul className={styles.todoList}>
            {tasks.map((task, index) => {
              const done = current >= 0 && index < current;
              const active = current >= 0 && index === current && !allDone;
              return (
                <li
                  key={task.id}
                  className={`${styles.todoItem} ${done ? styles.done : active ? styles.active : ''}`}
                  style={{ '--i': index } as React.CSSProperties}
                >
                  <span className={styles.todoIconWrap}>
                    {done ? (
                      <Check size={14} className={styles.todoIconOn} aria-hidden="true" />
                    ) : active ? (
                      <ListX size={14} className={styles.todoIconOn} aria-hidden="true" />
                    ) : (
                      <ListTodo size={14} className={styles.todoIconPending} aria-hidden="true" />
                    )}
                  </span>
                  <span className={styles.todoLabel} data-label={task.label}>
                    {task.label}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
};

const RollingCount: React.FC<{ value: string }> = ({ value }) => {
  return (
    <span className={styles.rollCount} aria-label={value}>
      {value.split('').map((char, index) => (
        <RollDigit key={index} char={char} />
      ))}
    </span>
  );
};

const RollDigit: React.FC<{ char: string }> = ({ char }) => {
  const prev = useRef(char);
  const [roll, setRoll] = useState<{ from: string; to: string } | null>(null);
  const [up, setUp] = useState(false);

  useEffect(() => {
    if (char === prev.current) return;
    const from = prev.current;
    prev.current = char;
    setRoll({ from, to: char });
    setUp(false);
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setUp(true)));
    const done = window.setTimeout(() => setRoll(null), 380);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(done);
    };
  }, [char]);

  if (!roll) return <span className={styles.rollDigit}>{char}</span>;
  return (
    <span className={styles.rollDigit}>
      <span className={`${styles.rollInner} ${up ? styles.on : ''}`}>
        <span>{roll.from}</span>
        <span>{roll.to}</span>
      </span>
    </span>
  );
};

export default AiTodoList;
