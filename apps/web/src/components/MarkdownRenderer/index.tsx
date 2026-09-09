import React, { useCallback, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { Button, message } from 'antd';
import styles from './index.module.less';

/** 代码块自定义渲染器：接收语言与代码，返回替代默认代码块的 ReactNode */
export interface CodeRendererProps {
  lang: string;
  code: string;
}

interface MarkdownRendererProps {
  content: string;
  /** 提供时，代码块使用该渲染器（用于接入 aicss AiCodeBlock） */
  codeRenderer?: (props: CodeRendererProps) => React.ReactNode;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, codeRenderer }) => {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const handleCopyCode = useCallback((code: string) => {
    navigator.clipboard.writeText(code).then(() => {
      setCopiedCode(code);
      message.success('代码已复制');
      setTimeout(() => setCopiedCode(null), 2000);
    });
  }, []);

  return (
    <div className={styles.markdownContent}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const codeString = String(children).replace(/\n$/, '');

            // 如果是代码块（有语言标识）
            if (match) {
              if (codeRenderer) {
                return codeRenderer({ lang: match[1], code: codeString });
              }
              return (
                <div className={styles.codeBlock}>
                  <div className={styles.codeHeader}>
                    <span className={styles.codeLanguage}>{match[1]}</span>
                    <Button
                      type="text"
                      size="small"
                      icon={copiedCode === codeString ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={() => handleCopyCode(codeString)}
                      className={styles.copyCodeBtn}
                    >
                      {copiedCode === codeString ? '已复制' : '复制'}
                    </Button>
                  </div>
                  <pre>
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
              );
            }

            // 行内代码
            return (
              <code className={styles.inlineCode} {...props}>
                {children}
              </code>
            );
          },
          a({ children, ...props }) {
            return (
              <a target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
