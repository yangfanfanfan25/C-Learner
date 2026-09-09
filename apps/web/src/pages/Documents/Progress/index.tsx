import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Clock, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { message } from 'antd';
import { documentsApi, type DocumentRecord } from '@/services/documents';
import styles from './index.module.less';

const statusLabel: Record<string, string> = {
  pending: '等待处理',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
};

const formatTime = (value: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const StatusIcon: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'processing') {
    return <Loader2 size={14} className={styles.spin} />;
  }
  if (status === 'completed') return <CheckCircle2 size={14} />;
  if (status === 'failed') return <XCircle size={14} />;
  return <Clock size={14} />;
};

/** 文件处理进度页：轮询文档列表，展示每个文件的排队/处理/完成/失败状态。 */
const ProgressPage: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await documentsApi.listDocuments({ page_size: 100 });
      setDocuments(data.items);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载进度失败');
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="返回文档工作台"
          title="返回文档工作台"
          onClick={() => navigate('/documents')}
        >
          <ArrowLeft size={16} />
        </button>
        <h1 className={styles.title}>处理进度</h1>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="刷新"
          title="刷新"
          onClick={refresh}
        >
          <RefreshCw size={16} className={refreshing ? styles.spin : ''} />
        </button>
      </header>

      <div className={styles.list}>
        {documents.length === 0 && <div className={styles.empty}>暂无处理任务</div>}
        {documents.map((doc) => (
          <div key={doc.id} className={styles.item}>
            <div className={styles.itemInfo}>
              <span className={styles.itemTitle}>{doc.filename}</span>
              <span className={styles.itemMeta}>
                {formatTime(doc.created_at)}
                {doc.status === 'completed' ? ` · ${doc.chunk_count} 切片` : ''}
              </span>
              {doc.status === 'failed' && doc.error_message && (
                <span className={styles.errorMsg}>{doc.error_message}</span>
              )}
            </div>
            <span className={`${styles.badge} ${styles[`status_${doc.status}`] || ''}`}>
              <StatusIcon status={doc.status} />
              {statusLabel[doc.status] || doc.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProgressPage;
