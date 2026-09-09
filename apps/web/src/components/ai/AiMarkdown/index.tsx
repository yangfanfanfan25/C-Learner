import MarkdownRenderer from '@/components/MarkdownRenderer';
import AiCodeBlock from '../AiCodeBlock';
import styles from './index.module.less';

interface AiMarkdownProps {
  content: string;
}

/** Markdown 渲染（复用 MarkdownRenderer，代码块增强为 aicss AiCodeBlock） */
const AiMarkdown: React.FC<AiMarkdownProps> = ({ content }) => {
  return (
    <div className={styles.markdown}>
      <MarkdownRenderer
        content={content}
        codeRenderer={({ lang, code }) => <AiCodeBlock lang={lang} code={code} />}
      />
    </div>
  );
};

export default AiMarkdown;
