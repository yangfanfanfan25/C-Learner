import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import {
  ArrowUp,
  BookOpen,
  ChevronRight,
  FileText,
  Loader2,
  Moon,
  Plus,
  Square,
  Sun,
  X,
} from 'lucide-react';
import type { ChatCapability } from '../types';
import { documentsApi, type DocumentRecord } from '@/services/documents';
import type { ThemeMode } from '@/contexts/ThemeContext';
import { MAX_CONTENT_LENGTH, SKILLS, type ComposerPayload, type Skill } from '../types';
import styles from './index.module.less';

const skillName = (id: string) => SKILLS.find((skill) => skill.id === id)?.name ?? id;

const escapeHtml = (str: string) =>
  str.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] ?? c));

/** 提取提交正文：克隆 DOM 后移除能力 pill（能力标签不进入消息正文） */
const extractContent = (root: HTMLElement): string => {
  const clone = root.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[data-capability]').forEach((el) => {
    const next = el.nextSibling;
    if (next && next.nodeType === Node.TEXT_NODE && (next.textContent ?? '').trim() === '') {
      next.remove();
    }
    el.remove();
  });
  return (clone.textContent ?? '').replace(/[ \u00a0]{2,}/g, ' ').trim();
};

/** 收集正文中启用的能力（能力 pill，去重） */
const collectCapabilities = (root: HTMLElement): ChatCapability[] =>
  Array.from(
    new Set(
      Array.from(root.querySelectorAll<HTMLElement>('[data-capability]'))
        .map((el) => el.dataset.capability)
        .filter((id): id is ChatCapability => Boolean(id)),
    ),
  );

/** 合并会话默认能力与当次消息新增的能力 pill（去重） */
const mergeCapabilities = (...lists: ChatCapability[][]): ChatCapability[] =>
  Array.from(new Set(lists.flat()));

/** 能力 id → 中文名 */
const capabilityName = (capability: ChatCapability): string =>
  SKILLS.find((skill) => skill.capability === capability)?.name ?? capability;

type Phase = 'idle' | 'enhancing' | 'enhanced';

interface AiComposerProps {
  sending: boolean;
  theme: ThemeMode;
  /** 会话默认能力（后端持久化，消息自动携带；提示条展示，可取消） */
  defaultCapabilities: ChatCapability[];
  onDefaultCapabilitiesChange: (capabilities: ChatCapability[]) => void;
  onToggleTheme: () => void;
  onSubmit: (payload: ComposerPayload) => void;
  onAbort: () => void;
  /** Enhance 接口：通过 chat service 调用后端，支持 AbortSignal */
  onEnhance: (prompt: string, signal?: AbortSignal) => Promise<string>;
  /** 打开文档工作台（/documents） */
  onOpenDocuments: () => void;
}

/**
 * 智能体输入框（完整还原 aicss PromptInput）。
 * 技能以文本前缀提交；提示词增强通过后端 Chat API 完成。
 * 模型切换和附件消息尚无后端契约，因此相关入口不在生产界面暴露。
 */
const AiComposer: React.FC<AiComposerProps> = ({
  sending,
  theme,
  defaultCapabilities,
  onDefaultCapabilitiesChange,
  onToggleTheme,
  onSubmit,
  onAbort,
  onEnhance,
  onOpenDocuments,
}) => {
  const [value, setValue] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [menuOpen, setMenuOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [pillMounted, setPillMounted] = useState(false);
  const [pillExiting, setPillExiting] = useState(false);
  const [slashOpen, setSlashOpen] = useState(false);
  const [slashQuery, setSlashQuery] = useState('');
  const [slashIndex, setSlashIndex] = useState(0);
  const [slashKeyboard, setSlashKeyboard] = useState(false);
  const [editorCapabilities, setEditorCapabilities] = useState<ChatCapability[]>([]);
  /** 消息实际携带的能力 = 会话默认 + 当次新增 pill（去重） */
  const effectiveCapabilities = mergeCapabilities(defaultCapabilities, editorCapabilities);
  const practiceMode = effectiveCapabilities.includes('practice');
  const [atOpen, setAtOpen] = useState(false);
  const [atQuery, setAtQuery] = useState('');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);

  const editorRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const plusRef = useRef<HTMLDivElement>(null);
  const preEnhanceHTML = useRef('');
  const pendingHTML = useRef<string | null>(null);
  const pendingCapabilitiesRef = useRef<ChatCapability[]>([]);
  const flipFrom = useRef<number | null>(null);
  const savedRange = useRef<Range | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const slashOpenRef = useRef(false);
  const slashIndexRef = useRef(0);
  const slashResultsRef = useRef<Skill[]>([]);
  const slashQueryRef = useRef('');
  const slashTokenRef = useRef<{ node: Text; start: number; end: number } | null>(null);
  const ignoreHoverRef = useRef(false);
  const applySlashRef = useRef<(id: string) => void>(() => {});
  const slashKeyLock = useRef(false);

  const hasText = value.trim().length > 0;
  const enhancing = phase === 'enhancing';
  const overLimit = value.length > MAX_CONTENT_LENGTH;
  const sendActive = hasText && !enhancing && !overLimit;
  const showPill = hasText && !enhancing;
  const slashResults = SKILLS.filter((skill) =>
    skill.name.toLowerCase().includes(slashQuery.toLowerCase()),
  );
  slashOpenRef.current = slashOpen;
  slashIndexRef.current = slashIndex;
  slashResultsRef.current = slashResults;
  const documentResults = documents.filter((document) =>
    document.filename.toLowerCase().includes(atQuery.toLowerCase()),
  );

  useEffect(() => {
    if (!practiceMode) {
      setAtOpen(false);
      return;
    }
    let cancelled = false;
    void documentsApi.listDocuments({ page_size: 50 }).then((result) => {
      if (!cancelled) setDocuments(result.items.filter((item) => item.status === 'completed'));
    }).catch(() => {
      if (!cancelled) setDocuments([]);
    });
    return () => { cancelled = true; };
  }, [practiceMode]);

  const focusEnd = () => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.focus();
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    savedRange.current = range.cloneRange();
  };

  const syncFromEditor = () => {
    const editor = editorRef.current;
    if (!editor) return;
    setValue(extractContent(editor));
    setEditorCapabilities(collectCapabilities(editor));
    editor.querySelectorAll<HTMLElement>('.' + styles.skillPill).forEach((pill) => {
      let atStart = true;
      let node = pill.previousSibling as ChildNode | null;
      while (node) {
        if (node.nodeType === Node.TEXT_NODE && (node.textContent ?? '').trim() === '') {
          node = node.previousSibling;
          continue;
        }
        atStart = false;
        break;
      }
      pill.toggleAttribute('data-start', atStart);
    });
  };

  const saveSelection = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (selection && selection.rangeCount && editor && editor.contains(selection.anchorNode)) {
      savedRange.current = selection.getRangeAt(0).cloneRange();
    }
  };

  const closeSlash = () => {
    setSlashOpen(false);
    setSlashQuery('');
    setSlashIndex(0);
    setSlashKeyboard(false);
    slashQueryRef.current = '';
    slashTokenRef.current = null;
    ignoreHoverRef.current = false;
  };

  const buildPill = (id: string) => {
    const name = skillName(id);
    const capability = SKILLS.find((item) => item.id === id)?.capability;
    const el = document.createElement('span');
    el.className = styles.skillPill;
    el.setAttribute('contenteditable', 'false');
    el.dataset.skill = id;
    if (capability) el.dataset.capability = capability;
    el.innerHTML =
      '<span class="' + styles.skillPillLabel + '">/' + escapeHtml(name) + '</span>' +
      '<button type="button" class="' + styles.skillPillX +
      '" data-remove="1" aria-label="移除 ' + escapeHtml(name) +
      '"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>';
    return el;
  };

  const insertPillOverRange = (range: Range, id: string) => {
    const editor = editorRef.current;
    if (!editor) return;
    range.deleteContents();
    const pill = buildPill(id);
    range.insertNode(pill);
    const space = document.createTextNode(' ');
    pill.after(space);
    const after = document.createRange();
    after.setStartAfter(space);
    after.collapse(true);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(after);
    editor.focus();
    savedRange.current = after.cloneRange();
    syncFromEditor();
  };

  const addSkillFromMenu = (id: string) => {
    const editor = editorRef.current;
    if (!editor) return;
    const selection = window.getSelection();
    let range: Range | null = null;
    if (selection && selection.rangeCount && editor.contains(selection.anchorNode)) {
      range = selection.getRangeAt(0).cloneRange();
    } else if (savedRange.current && editor.contains(savedRange.current.startContainer)) {
      range = savedRange.current.cloneRange();
    }
    if (!range) {
      range = document.createRange();
      range.selectNodeContents(editor);
      range.collapse(false);
    }
    insertPillOverRange(range, id);
    setMenuOpen(false);
  };

  const applySlash = (id: string) => {
    const editor = editorRef.current;
    if (!editor) {
      closeSlash();
      return;
    }
    let range: Range | null = null;
    const token = slashTokenRef.current;
    if (
      token &&
      token.node.isConnected &&
      editor.contains(token.node) &&
      token.end <= (token.node.textContent?.length ?? 0)
    ) {
      range = document.createRange();
      range.setStart(token.node, token.start);
      range.setEnd(token.node, token.end);
    } else {
      const selection = window.getSelection();
      if (selection && selection.rangeCount) {
        const caret = selection.getRangeAt(0);
        range = caret.cloneRange();
        const node = caret.startContainer;
        if (node.nodeType === Node.TEXT_NODE && editor.contains(node)) {
          const before = (node.textContent ?? '').slice(0, caret.startOffset);
          const match = before.match(/\/([^\s/]*)$/);
          if (match) {
            range = document.createRange();
            range.setStart(node, caret.startOffset - match[0].length);
            range.setEnd(node, caret.startOffset);
          }
        }
      }
    }
    if (!range) {
      closeSlash();
      return;
    }
    insertPillOverRange(range, id);
    closeSlash();
  };
  applySlashRef.current = applySlash;

  const detectSlash = () => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection || !selection.rangeCount || !selection.isCollapsed) {
      return closeSlash();
    }
    const range = selection.getRangeAt(0);
    const node = range.startContainer;
    if (node.nodeType !== Node.TEXT_NODE || !editor.contains(node)) return closeSlash();
    const before = (node.textContent ?? '').slice(0, range.startOffset);
    const match = before.match(/(?:^|\s)\/([^\s/]*)$/);
    if (!match) return closeSlash();
    const q = match[1];
    const slashStart = before.length - match[1].length - 1;
    slashTokenRef.current = {
      node: node as Text,
      start: slashStart,
      end: range.startOffset,
    };
    if (q !== slashQueryRef.current) {
      slashQueryRef.current = q;
      setSlashIndex(0);
    }
    setSlashQuery(q);
    setSlashOpen(true);
  };

  const onEditorInput = () => {
    syncFromEditor();
    if (phase === 'enhanced') setPhase('idle');
    detectSlash();
    const editor = editorRef.current;
    if (editor && mergeCapabilities(defaultCapabilities, collectCapabilities(editor)).includes('practice')) {
      const selection = window.getSelection();
      const node = selection?.anchorNode;
      let before = '';
      if (node && selection) {
        if (node.nodeType === Node.TEXT_NODE) {
          before = (node.textContent ?? '').slice(0, selection.anchorOffset);
        } else if (editor.contains(node)) {
          // 光标锚定在元素边界（如编辑器末尾）：取从编辑器开头到光标处的文本
          const range = document.createRange();
          range.setStart(editor, 0);
          range.setEnd(node, selection.anchorOffset);
          before = range.toString();
        }
      }
      const match = before.match(/(?:^|\s)@([^\s@]*)$/);
      setAtQuery(match?.[1] ?? '');
      setAtOpen(Boolean(match));
    }
  };

  const selectDocument = (documentRecord: DocumentRecord) => {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (!editor || !selection?.rangeCount) return;
    const caret = selection.getRangeAt(0);
    const node = caret.startContainer;
    if (node.nodeType !== Node.TEXT_NODE || !editor.contains(node)) return;
    const before = (node.textContent ?? '').slice(0, caret.startOffset);
    const match = before.match(/(?:^|\s)@([^\s@]*)$/);
    if (!match) return;
    const range = document.createRange();
    range.setStart(node, caret.startOffset - match[0].trimStart().length);
    range.setEnd(node, caret.startOffset);
    range.deleteContents();
    const pill = document.createElement('span');
    pill.className = styles.skillPill;
    pill.setAttribute('contenteditable', 'false');
    pill.dataset.docId = documentRecord.id;
    pill.textContent = `@${documentRecord.filename}`;
    range.insertNode(pill);
    const space = document.createTextNode('\u00a0');
    pill.after(space);
    const after = document.createRange();
    after.setStartAfter(space);
    after.collapse(true);
    selection.removeAllRanges();
    selection.addRange(after);
    savedRange.current = after.cloneRange();
    setAtOpen(false);
    setAtQuery('');
    syncFromEditor();
  };

  const moveSlash = (delta: number) => {
    const results = slashResultsRef.current;
    if (!results.length) return;
    ignoreHoverRef.current = true;
    setSlashKeyboard(true);
    setSlashIndex((i) => (i + delta + results.length * 10) % results.length);
  };

  const handleSlashKey = (e: {
    key: string;
    preventDefault: () => void;
    stopPropagation?: () => void;
  }) => {
    const results = slashResultsRef.current;
    if (!slashOpenRef.current || !results.length) return false;
    if (
      e.key !== 'ArrowDown' &&
      e.key !== 'ArrowUp' &&
      e.key !== 'Enter' &&
      e.key !== 'Tab' &&
      e.key !== 'Escape'
    ) {
      return false;
    }
    e.preventDefault();
    e.stopPropagation?.();
    if (slashKeyLock.current) return true;
    slashKeyLock.current = true;
    queueMicrotask(() => {
      slashKeyLock.current = false;
    });
    if (e.key === 'ArrowDown') {
      moveSlash(1);
      return true;
    }
    if (e.key === 'ArrowUp') {
      moveSlash(-1);
      return true;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      applySlashRef.current((results[slashIndexRef.current] ?? results[0]).id);
      return true;
    }
    if (e.key === 'Escape') {
      closeSlash();
      return true;
    }
    return false;
  };

  const onEditorKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (handleSlashKey(e)) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  useEffect(() => {
    if (!slashOpen) return;
    const onKey = (e: KeyboardEvent) => {
      handleSlashKey(e);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slashOpen]);

  useEffect(() => {
    if (!slashOpen || !slashResults.length) return;
    if (slashIndex >= slashResults.length) setSlashIndex(0);
  }, [slashOpen, slashResults.length, slashIndex]);

  const onEditorClick = (e: ReactMouseEvent<HTMLDivElement>) => {
    const remove = (e.target as HTMLElement).closest('[data-remove]');
    if (remove) {
      e.preventDefault();
      const pill = remove.closest<HTMLElement>('[data-skill]');
      if (pill) {
        const sep = pill.nextSibling;
        const width = pill.getBoundingClientRect().width;
        pill.style.maxWidth = `${width}px`;
        pill.style.overflow = 'hidden';
        pill.style.whiteSpace = 'nowrap';
        void pill.offsetWidth;
        pill.style.transition =
          'max-width 180ms cubic-bezier(0.22,1,0.36,1), margin 180ms cubic-bezier(0.22,1,0.36,1), padding 180ms cubic-bezier(0.22,1,0.36,1)';
        pill.setAttribute('data-exit', '');
        pill.style.maxWidth = '0px';
        pill.style.marginLeft = '0px';
        pill.style.marginRight = '0px';
        pill.style.paddingLeft = '0px';
        pill.style.paddingRight = '0px';
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          if (sep && sep.nodeType === Node.TEXT_NODE && sep.textContent?.startsWith(' ')) {
            const rest = sep.textContent.slice(1);
            if (rest) sep.textContent = rest;
            else sep.parentNode?.removeChild(sep);
          }
          pill.remove();
          syncFromEditor();
          editorRef.current?.focus();
        };
        pill.addEventListener('animationend', finish, { once: true });
        window.setTimeout(finish, 220);
      }
      return;
    }
    saveSelection();
  };

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: PointerEvent) => {
      if (!plusRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) {
      setSkillsOpen(false);
    }
  }, [menuOpen]);

  useLayoutEffect(() => {
    if (enhancing || pendingHTML.current === null) return;
    const editor = editorRef.current;
    if (!editor) return;
    editor.innerHTML = pendingHTML.current;
    pendingHTML.current = null;
    if (pendingCapabilitiesRef.current.length) {
      pendingCapabilitiesRef.current.forEach((cap) => {
        const skill = SKILLS.find((s) => s.capability === cap);
        if (!skill) return;
        editor.appendChild(buildPill(skill.id));
        editor.appendChild(document.createTextNode(' '));
      });
      pendingCapabilitiesRef.current = [];
    }
    syncFromEditor();
    requestAnimationFrame(focusEnd);

    const frame = frameRef.current;
    const from = flipFrom.current;
    flipFrom.current = null;
    if (!frame || from === null) return;
    const to = frame.offsetHeight;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || from === to) return;
    frame.style.height = from + 'px';
    frame.style.overflow = 'hidden';
    void frame.offsetHeight;
    frame.style.transition = 'height 200ms cubic-bezier(0.22, 1, 0.36, 1)';
    frame.style.height = to + 'px';
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      frame.style.transition = '';
      frame.style.height = '';
      frame.style.overflow = '';
      frame.removeEventListener('transitionend', finish);
    };
    frame.addEventListener('transitionend', finish);
    window.setTimeout(finish, 260);
  }, [phase, enhancing]);

  useEffect(() => {
    if (showPill) {
      setPillMounted(true);
      setPillExiting(false);
      return;
    }
    if (!pillMounted) return;
    if (enhancing) {
      setPillMounted(false);
      setPillExiting(false);
      return;
    }
    setPillExiting(true);
    const timer = window.setTimeout(() => {
      setPillMounted(false);
      setPillExiting(false);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [showPill, enhancing, pillMounted]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const runEnhance = async () => {
    if (!hasText || enhancing) return;
    preEnhanceHTML.current = editorRef.current?.innerHTML ?? '';
    pendingCapabilitiesRef.current = editorRef.current ? collectCapabilities(editorRef.current) : [];
    setPhase('enhancing');
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const result = await onEnhance(value, ac.signal);
      if (ac.signal.aborted) return;
      pendingHTML.current = escapeHtml(result);
      flipFrom.current = frameRef.current?.offsetHeight ?? null;
      setPhase('enhanced');
    } catch {
      if (ac.signal.aborted) return;
      pendingHTML.current = preEnhanceHTML.current;
      pendingCapabilitiesRef.current = [];
      setPhase('idle');
    }
  };

  const revert = () => {
    abortRef.current?.abort();
    pendingCapabilitiesRef.current = [];
    pendingHTML.current = preEnhanceHTML.current;
    flipFrom.current = frameRef.current?.offsetHeight ?? null;
    setPhase('idle');
  };

  const send = () => {
    if (!sendActive) return;
    const editor = editorRef.current;
    // 消息携带能力 = 会话默认能力 + 当次新增能力 pill（去重）
    const capabilities = editor
      ? mergeCapabilities(defaultCapabilities, collectCapabilities(editor))
      : defaultCapabilities;
    const documentIds = editor
      ? Array.from(editor.querySelectorAll<HTMLElement>('[data-doc-id]'))
          .map((item) => item.dataset.docId)
          .filter((id): id is string => Boolean(id))
      : [];
    const content = editor ? extractContent(editor) : value.trim();
    if (editor) editor.innerHTML = '';
    setValue('');
    setEditorCapabilities([]);
    setPhase('idle');
    closeSlash();
    onSubmit({ content, documentIds, capabilities });
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  return (
    <div className={styles.wrap}>
      {defaultCapabilities.length > 0 && (
        <div className={styles.capabilityStrip} role="status">
          {defaultCapabilities.map((capability) => (
            <span key={capability} className={styles.capabilityChip}>
              {capabilityName(capability)}
              <button
                type="button"
                className={styles.capabilityChipX}
                aria-label={`移除 ${capabilityName(capability)}`}
                onClick={() =>
                  onDefaultCapabilitiesChange(
                    defaultCapabilities.filter((item) => item !== capability),
                  )
                }
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div ref={frameRef} className={styles.frame} data-enhancing={enhancing || undefined}>
        <div className={styles.editorWrap}>
          {enhancing ? (
            <div className={styles.enhancingText} aria-live="polite">
              {value}
            </div>
          ) : (
            <div
              ref={editorRef}
              className={styles.field}
              contentEditable
              autoFocus
              suppressContentEditableWarning
              role="textbox"
              aria-multiline="true"
              aria-label={practiceMode ? '@你想要复习的资料' : '向智能体提问'}
              onInput={onEditorInput}
              onKeyDown={onEditorKeyDown}
              onKeyUp={saveSelection}
              onMouseUp={saveSelection}
              onBlur={saveSelection}
              onClick={onEditorClick}
            />
          )}

          {slashOpen && !enhancing && (
            <div
              className={styles.slashMenu}
              role="listbox"
              aria-label="技能"
              data-keyboard={slashKeyboard || undefined}
              onMouseMove={() => {
                ignoreHoverRef.current = false;
                if (slashKeyboard) setSlashKeyboard(false);
              }}
            >
              <div className={styles.slashLabel}>技能</div>
              {slashResults.length ? (
                slashResults.map((skill, i) => (
                  <button
                    key={skill.id}
                    type="button"
                    role="option"
                    aria-selected={i === slashIndex}
                    className={[
                      styles.menuItem,
                      i === slashIndex && styles.menuItemActive,
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => {
                      if (ignoreHoverRef.current) return;
                      setSlashIndex(i);
                    }}
                    onClick={() => applySlash(skill.id)}
                  >
                    <span className={styles.menuName}>{skill.name}</span>
                  </button>
                ))
              ) : (
                <div className={styles.slashEmpty}>没有匹配的技能</div>
              )}
            </div>
          )}
          {atOpen && !enhancing && (
            <div className={styles.atMenu} role="listbox" aria-label="选择复习资料">
              <div className={styles.slashLabel}>选择已上传的资料</div>
              {documentResults.length ? documentResults.map((documentRecord) => (
                <button
                  key={documentRecord.id}
                  type="button"
                  role="option"
                  className={styles.menuItem}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectDocument(documentRecord)}
                >
                  <FileText size={14} />
                  <span className={styles.menuName}>{documentRecord.filename}</span>
                </button>
              )) : (
                <div className={styles.slashEmpty}>
                  {documents.length ? '没有匹配的文件' : '暂无已处理的文件'}
                </div>
              )}
            </div>
          )}
        </div>

        <div className={styles.row}>
          <div className={styles.left}>
            <div className={styles.plusWrap} ref={plusRef}>
            <button
              type="button"
              className={[styles.iconBtn, styles.plus].join(' ')}
              data-open={menuOpen || undefined}
              aria-label="添加技能"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span className={styles.plusIcon}>
                <Plus size={14} />
              </span>
            </button>

            {menuOpen && (
              <div className={styles.menu} role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className={styles.menuItem}
                  onClick={() => {
                    setMenuOpen(false);
                    onOpenDocuments();
                  }}
                >
                  <span className={styles.menuIcon}>
                    <FileText size={14} />
                  </span>
                  <span className={styles.menuName}>文档工作台</span>
                </button>

                <div
                  className={styles.menuSub}
                  onMouseEnter={() => setSkillsOpen(true)}
                  onMouseLeave={() => setSkillsOpen(false)}
                >
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.menuItem}
                    aria-haspopup="menu"
                    aria-expanded={skillsOpen}
                    onClick={() => setSkillsOpen(true)}
                  >
                    <span className={styles.menuIcon}>
                      <BookOpen size={14} />
                    </span>
                    <span className={styles.menuName}>技能</span>
                    <span className={styles.menuChevron}>
                      <ChevronRight size={14} />
                    </span>
                  </button>
                  {skillsOpen && (
                    <div className={styles.menuFlyout} role="menu">
                      {SKILLS.map((skill) => (
                        <button
                          key={skill.id}
                          type="button"
                          role="menuitem"
                          className={styles.menuItem}
                          onClick={() => addSkillFromMenu(skill.id)}
                        >
                          <span className={styles.menuName}>{skill.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            </div>

            <button
              type="button"
              className={styles.iconBtn}
              aria-label={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
              title={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
              onClick={onToggleTheme}
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>

          <div className={styles.right}>
            {enhancing ? (
              <span className={[styles.iconBtn, styles.spinnerBtn].join(' ')} aria-label="正在增强提示词">
                <Loader2 size={14} className={styles.spinner} />
              </span>
            ) : (
              pillMounted && (
                <button
                  type="button"
                  className={[styles.pill, pillExiting && styles.pillExit]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={phase === 'enhanced' ? revert : runEnhance}
                >
                  {phase === 'enhanced' ? '撤销' : '增强提示词'}
                </button>
              )
            )}
            {sending && (
              <button
                type="button"
                className={[styles.iconBtn, styles.send, styles.sendActive].join(' ')}
                aria-label="停止生成"
                onClick={onAbort}
              >
                <Square size={14} />
              </button>
            )}
            <button
              type="button"
              className={[styles.iconBtn, styles.send, sendActive && styles.sendActive]
                .filter(Boolean)
                .join(' ')}
              aria-label="发送"
              disabled={!sendActive}
              onClick={send}
            >
              <ArrowUp size={14} />
            </button>
          </div>
        </div>
      </div>

      <div className={styles.footerRow}>
        <span className={styles.composerHint}>
          {practiceMode ? '@你想要复习的资料' : '向智能体提问'}
        </span>
        {overLimit && (
          <span className={styles.limitHint} role="alert">
            内容超过 {MAX_CONTENT_LENGTH} 字上限
          </span>
        )}
      </div>
    </div>
  );
};

export default AiComposer;
