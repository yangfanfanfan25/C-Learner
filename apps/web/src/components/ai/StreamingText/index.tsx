import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './index.module.less';

interface StreamingTextProps {
  /** 流式累积的完整文本 */
  text: string;
  /** 是否处于流式生成中（true 时光标常亮，false 时闪烁） */
  streaming?: boolean;
  /** 后端已结束且前端播放完毕时通知父组件 */
  onComplete?: () => void;
}

/**
 * 流式文本 + 光标（来自 aicss StreamingText）。
 * 适配真实 SSE 场景：`text` 随每个 token 增长，这里从上次显示位置增量继续，
 * 避免每次 token 到达都从头播放打字机动画。
 */
const StreamingText: React.FC<StreamingTextProps> = ({
  text,
  streaming = true,
  onComplete,
}) => {
  const [shown, setShown] = useState('');
  const targetRef = useRef(text);
  const shownLengthRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const streamingRef = useRef(streaming);
  const onCompleteRef = useRef(onComplete);

  streamingRef.current = streaming;
  onCompleteRef.current = onComplete;

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    if (timerRef.current !== null) return;
    timerRef.current = window.setInterval(() => {
      const target = targetRef.current;
      const current = shownLengthRef.current;
      const backlog = target.length - current;

      if (backlog <= 0) {
        stopTimer();
        if (!streamingRef.current) onCompleteRef.current?.();
        return;
      }

      // 积压越多时适度追赶，但始终分帧显示，避免后端快速返回时瞬间铺满。
      const step = backlog > 240 ? 4 : backlog > 80 ? 2 : 1;
      const next = Math.min(current + step, target.length);
      shownLengthRef.current = next;
      setShown(target.slice(0, next));

      if (next === target.length && !streamingRef.current) {
        stopTimer();
        onCompleteRef.current?.();
      }
    }, 22);
  }, [stopTimer]);

  useEffect(() => {
    if (text.length < shownLengthRef.current || !text.startsWith(targetRef.current.slice(0, shownLengthRef.current))) {
      shownLengthRef.current = 0;
      setShown('');
    }
    targetRef.current = text;
    if (shownLengthRef.current < text.length) startTimer();
  }, [startTimer, text]);

  useEffect(() => {
    if (!streaming && shownLengthRef.current >= targetRef.current.length) {
      onCompleteRef.current?.();
    } else if (shownLengthRef.current < targetRef.current.length) {
      startTimer();
    }
  }, [startTimer, streaming]);

  useEffect(() => stopTimer, [stopTimer]);

  return (
    <span className={styles.streamingText}>
      {shown}
      <span
        className={streaming ? styles.caretSteady : styles.caret}
        aria-hidden="true"
      />
    </span>
  );
};

export default StreamingText;
