import { useState } from 'react';
import { Check, ChevronsRight, Copy } from 'lucide-react';
import styles from './index.module.less';

interface AiCodeBlockProps {
  lang: string;
  code: string;
}

/** 代码块（行号 + 复制），来自 aicss CodeBlock */
const AiCodeBlock: React.FC<AiCodeBlockProps> = ({ lang, code }) => {
  const [copied, setCopied] = useState(false);
  const lines = code.split('\n');

  const copy = () => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(code).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1200);
      },
      () => {},
    );
  };

  return (
    <div className={styles.cb}>
      <div className={styles.cbHead}>
        <span className={styles.cbFile}>
          <ChevronsRight size={15} className={styles.cbIcon} aria-hidden="true" />
          <span className={styles.cbLang}>{lang}</span>
        </span>
        <button
          type="button"
          className={styles.cbCopy}
          onClick={copy}
          aria-label={copied ? '已复制' : '复制代码'}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      <div className={styles.cbBody}>
        {lines.map((line, index) => (
          <div className={styles.cbRow} key={index}>
            <span className={styles.cbLn}>{index + 1}</span>
            <code className={styles.cbCode}>{line || ' '}</code>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AiCodeBlock;
