import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Download, FileText, ListChecks, Paperclip, RefreshCw, Trash2 } from 'lucide-react';
import { Button, Dropdown, Input, Modal, Select, Tooltip, message } from 'antd';
import {
  documentsApi,
  type DocumentChunkSummary,
  type DocumentDetail,
  type DocumentRecord,
} from '@/services/documents';
import styles from './index.module.less';

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

const statusLabel: Record<string, string> = {
  pending: '等待处理',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
};

const statusClass: Record<string, string> = {
  pending: styles.statusPending,
  processing: styles.statusProcessing,
  completed: styles.statusCompleted,
  failed: styles.statusFailed,
};

const renderHighlightedText = (text: string, tags: string[]) => {
  const keywords = tags.map((tag) => tag.trim()).filter(Boolean);
  if (!keywords.length) return text;
  const escaped = keywords.map((tag) => tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!escaped.length) return text;
  const parts = text.split(new RegExp(`(${escaped.join('|')})`, 'gi'));
  return parts.map((part, index) => {
    if (!keywords.some((tag) => tag.toLowerCase() === part.toLowerCase())) return part;
    return <mark key={index} style={{ color: '#b42318', fontWeight: 700 }}>{part}</mark>;
  });
};

interface SectionGroup {
  section: string;
  chunks: DocumentChunkSummary[];
}

interface ChapterGroup {
  chapter: string;
  sections: SectionGroup[];
}

/** 文档工作台：左侧文件列表 + 右侧知识点预览，按 chapter → section 分组。 */
const DocumentsPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [queuedVisible, setQueuedVisible] = useState(false);
  const [uploadFormVisible, setUploadFormVisible] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [academicYear, setAcademicYear] = useState<number | undefined>(undefined);
  const [semester, setSemester] = useState<number | undefined>(undefined);
  const processingCount = documents.filter((doc) => doc.status === 'pending' || doc.status === 'processing').length;

  const refreshList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await documentsApi.listDocuments({ page_size: 50 });
      setDocuments(data.items);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载文档列表失败');
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const openDetail = useCallback(async (documentId: string) => {
    setSelectedId(documentId);
    setLoadingDetail(true);
    try {
      const data = await documentsApi.getDocument(documentId);
      setDetail(data);
    } catch (e) {
      setDetail(null);
      message.error(e instanceof Error ? e.message : '加载文档详情失败');
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  /** 选文件即上传入队；成功后刷新列表、自动选中新文档并弹出队列提示。 */
  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      setError(null);
      try {
        if (!courseName.trim() || !academicYear || !semester) return;
        const response = await documentsApi.processFile(file, {
          course_name: courseName.trim(), academic_year: academicYear, semester,
        });
        if (fileInputRef.current) fileInputRef.current.value = '';
        await refreshList();
        // 自动选中新文档，让顶部"处理进度"按钮可见，配合入队弹窗指引
        await openDetail(response.document.id);
        setQueuedVisible(true);
      } catch (e) {
        setError(e instanceof Error ? e.message : '处理文档失败');
        message.error(e instanceof Error ? e.message : '处理文档失败');
      } finally {
        setUploading(false);
      }
    },
    [refreshList, openDetail, courseName, academicYear, semester],
  );

  const handleDelete = useCallback(
    async (documentId: string) => {
      setDeletingId(documentId);
      try {
        await documentsApi.deleteDocument(documentId);
        message.success('删除成功');
        setDocuments((prev) => prev.filter((item) => item.id !== documentId));
        // 删除当前选中文档 → 清空右栏回到空态
        if (selectedId === documentId) {
          setSelectedId(null);
          setDetail(null);
        }
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败');
      } finally {
        setDeletingId(null);
      }
    },
    [selectedId],
  );

  /**
   * 下载原始文件。
   * 不走 axios（拦截器按 APIResponse 解析，处理二进制流会出错），
   * 用原生 fetch 下载并临时 Blob URL 触发浏览器下载，
   * 同时能识别 404（记录存在但磁盘文件缺失）给出明确提示。
   */
  const handleDownload = useCallback(async (doc: DocumentRecord) => {
    const url = documentsApi.getFileDownloadUrl(doc.id);
    try {
      const response = await fetch(url);
      if (!response.ok) {
        message.error('文件不存在');
        return;
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = doc.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      message.error('文件不存在');
    }
  }, []);

  /** 下载加工后的知识点（.md），同样走原生 fetch 以支持 404 识别。 */
  const handleDownloadMarkdown = useCallback(async (doc: DocumentRecord) => {
    const url = documentsApi.getKnowledgeMarkdownUrl(doc.id);
    const filename = `${(doc.filename || 'knowledge').replace(/\.[^.]+$/, '')}.md`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        message.error('该文档暂无知识切片');
        return;
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      message.error('下载知识点失败');
    }
  }, []);

  const documentTree = useMemo(() => {
    const years = new Map<string, Map<string, Map<string, DocumentRecord[]>>>();
    for (const doc of documents) {
      const yearKey = doc.academic_year > 0 ? String(doc.academic_year) : '未设置学年';
      const semesters = years.get(yearKey) ?? new Map<string, Map<string, DocumentRecord[]>>();
      const semesterKey = doc.semester === 1 ? '第一学期' : '第二学期';
      const courses = semesters.get(semesterKey) ?? new Map<string, DocumentRecord[]>();
      const items = courses.get(doc.course_name) ?? [];
      items.push(doc); courses.set(doc.course_name, items); semesters.set(semesterKey, courses); years.set(yearKey, semesters);
    }
    return years;
  }, [documents]);

  const chapterGroups = useMemo<ChapterGroup[]>(() => {
    const chunks = detail?.chunks ?? [];
    const chapterMap = new Map<string, ChapterGroup>();
    for (const chunk of chunks) {
      let group = chapterMap.get(chunk.chapter);
      if (!group) {
        group = { chapter: chunk.chapter, sections: [] };
        chapterMap.set(chunk.chapter, group);
      }
      const sectionKey = chunk.section || '';
      let sectionGroup = group.sections.find((s) => s.section === sectionKey);
      if (!sectionGroup) {
        sectionGroup = { section: sectionKey, chunks: [] };
        group.sections.push(sectionGroup);
      }
      sectionGroup.chunks.push(chunk);
    }
    return Array.from(chapterMap.values());
  }, [detail]);

  const chunkSequenceById = useMemo(
    () => new Map((detail?.chunks ?? []).map((chunk, index) => [chunk.id, index + 1])),
    [detail],
  );

  return (
    <div className={styles.workbench}>
      {/* 左栏：文件列表 */}
      <aside className={styles.sidebar} aria-label="文档列表">
        <div className={styles.sidebarTop}>
          <h1 className={styles.sidebarTitle}>文档工作台</h1>
          <div className={styles.sidebarActions}>
            <button
              type="button"
              className={styles.uploadBtn}
              disabled={uploading}
              onClick={() => setUploadFormVisible(true)}
            >
              <span>{uploading ? '处理中...' : '上传文档'}</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              className={styles.hiddenInput}
              accept=".pdf,.pptx,.docx,.doc,.xlsx,.xls,.csv,.txt,.text,.md,.markdown,.json,.jsonl,.html,.htm,.epub,.ipynb,.msg,.zip"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
            <button type="button" className={styles.iconBtn} aria-label="刷新文档列表" title="刷新文档列表" onClick={refreshList}>
              <RefreshCw size={15} />
            </button>
            <button type="button" className={styles.iconBtn} aria-label="返回智能体对话" title="返回智能体对话" onClick={() => navigate('/chat')}>
              <ArrowLeft size={15} />
            </button>
          </div>
        </div>

        <div className={styles.fileList}>
          {loadingList && <div className={styles.empty}>加载中...</div>}
          {!loadingList && documents.length === 0 && <div className={styles.empty}>暂无文档</div>}
          {Array.from(documentTree.entries()).map(([year, semesters]) => (
            <details key={year} className={styles.treeYear} open>
              <summary className={styles.treeLabel}>{year} 学年</summary>
              {Array.from(semesters.entries()).map(([semesterLabel, courses]) => (
                <details key={semesterLabel} className={styles.treeSemester} open>
                  <summary className={styles.treeLabel}>{semesterLabel}</summary>
                  {Array.from(courses.entries()).map(([course, courseDocs]) => (
                    <details key={course} className={styles.treeCourse} open>
                      <summary className={styles.treeLabel}>{course}</summary>
                  {courseDocs.map((doc) => {
            const active = doc.id === selectedId;
            return (
              <div
                key={doc.id}
                className={`${styles.fileItem} ${active ? styles.fileItemActive : ''}`}
                role="button"
                tabIndex={0}
                aria-label={`查看 ${doc.filename} 的知识切片`}
                onClick={() => openDetail(doc.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openDetail(doc.id);
                  }
                }}
              >
                <div className={styles.fileInfo}>
                  <span className={styles.fileTitle}>{doc.filename}</span>
                  <span className={styles.fileMeta}>
                    <span className={`${styles.badge} ${statusClass[doc.status] || ''}`}>
                      {statusLabel[doc.status] || doc.status}
                    </span>
                    {doc.status === 'completed' ? ` · ${doc.chunk_count} 切片` : ''} ·{' '}
                    {formatTime(doc.created_at)}
                  </span>
                </div>
                <button
                  type="button"
                  className={styles.deleteBtn}
                  aria-label={`删除文档 ${doc.filename}`}
                  disabled={deletingId === doc.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(doc.id);
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
                  })}
                    </details>
                  ))}
                </details>
              ))}
            </details>
          ))}
        </div>
      </aside>

      {/* 右栏：预览区 */}
      <main className={styles.main}>
        {detail ? (
          <>
            <header className={styles.mainHeader}>
              <FileText size={16} className={styles.headerIcon} />
              <span className={styles.mainTitle}>{detail.filename}</span>
              <button
                type="button"
                className={styles.headerIconBtn}
                aria-label="处理进度"
                title="处理进度"
                onClick={() => navigate('/documents/progress')}
              >
                <ListChecks size={16} />
                {processingCount > 0 && <span className={styles.progressBadge}>{processingCount}</span>}
              </button>
              <Tooltip title="可选择下载原始文件或加工后知识点">
                <Dropdown
                  menu={{
                    items: [
                      {
                        key: 'raw',
                        label: '下载原始文件',
                        onClick: () => handleDownload(detail),
                      },
                      {
                        key: 'knowledge',
                        label: '下载加工后知识点（.md）',
                        onClick: () => handleDownloadMarkdown(detail),
                      },
                    ],
                  }}
                  trigger={['click']}
                  placement="bottomRight"
                >
                  <button type="button" className={styles.downloadBtn} aria-label="下载文件">
                    <Download size={16} />
                  </button>
                </Dropdown>
              </Tooltip>
            </header>

            {error && <div className={styles.errorBanner}>{error}</div>}
            {uploading && (
              <div className={styles.processingBanner}>正在解析、规范化和索引，请稍候…</div>
            )}

            <div className={styles.content}>
              {loadingDetail && <div className={styles.empty}>加载中...</div>}
              {!loadingDetail && detail.chunks.length === 0 && (
                <div className={styles.empty}>该文档暂无知识切片</div>
              )}
              {!loadingDetail && detail.chunks.length > 0 && (
                <>
                  {chapterGroups.map((group) => (
                    <section key={group.chapter} className={styles.chapterBlock}>
                      <Paperclip size={42} className={styles.paperclip} aria-hidden="true" />
                      <h3 className={styles.chapterTitle}>§ {group.chapter}</h3>
                      {group.sections.map((sectionGroup) => (
                        <div key={sectionGroup.section} className={styles.sectionBlock}>
                          {sectionGroup.section && (
                            <h4 className={styles.sectionTitle}>▸ {sectionGroup.section}</h4>
                          )}
                          {sectionGroup.chunks.map((chunk) => {
                            const sequence = chunkSequenceById.get(chunk.id) ?? 0;
                            return (
                              <article
                                key={chunk.id}
                                className={styles.chunkItem}
                                aria-label={`知识点 ${sequence}：${chunk.title}`}
                                tabIndex={0}
                              >
                                <div className={styles.chunkHeader}>
                                  <span className={styles.chunkNumber} aria-hidden="true">
                                    {String(sequence).padStart(2, '0')}
                                  </span>
                                  <h5 className={styles.chunkTitle}>{chunk.title}</h5>
                                </div>
                                <div className={styles.chunkBody}>
                                  <p className={styles.chunkContent}>{renderHighlightedText(chunk.content, chunk.tags)}</p>
                                  {false && chunk.tags.length > 0 && (
                                    <footer className={styles.chunkFooter}>
                                      <span className={styles.tagLabel}>关键词</span>
                                      <div className={styles.chunkTags}>
                                        {chunk.tags.map((tag) => (
                                          <span key={tag} className={styles.tag}>
                                            {tag}
                                          </span>
                                        ))}
                                      </div>
                                    </footer>
                                  )}
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      ))}
                    </section>
                  ))}
                </>
              )}
            </div>
          </>
        ) : (
          <div className={styles.mainEmpty}>
            {error && <div className={styles.errorBanner}>{error}</div>}
            {uploading && (
              <div className={styles.processingBanner}>正在解析、规范化和索引，请稍候…</div>
            )}
            <p className={styles.mainEmptyText}>从左侧选择一个文件，查看提取的知识点</p>
          </div>
        )}
      </main>

      <Modal
        open={uploadFormVisible}
        title="上传知识资料"
        okText="选择文件"
        cancelText="取消"
        onCancel={() => setUploadFormVisible(false)}
        onOk={() => {
          if (!courseName.trim() || !academicYear || !semester) {
            message.warning('请填写课程名称、学年和学期');
            return;
          }
          setUploadFormVisible(false);
          fileInputRef.current?.click();
        }}
      >
        <div className={styles.uploadForm}>
          <label>课程名称<Input value={courseName} onChange={(e) => setCourseName(e.target.value)} placeholder="例如：高等数学" /></label>
          <label>学年<Input type="number" min={1} value={academicYear} onChange={(e) => setAcademicYear(Number(e.target.value) || undefined)} placeholder="例如：2025" /></label>
          <label>学期<Select value={semester} onChange={setSemester} placeholder="请选择学期" options={[{ value: 1, label: '第一学期' }, { value: 2, label: '第二学期' }]} /></label>
        </div>
      </Modal>

      <Modal
        open={queuedVisible}
        centered
        onCancel={() => setQueuedVisible(false)}
        title="文件已进入处理队列"
        footer={[
          <Button key="close" onClick={() => setQueuedVisible(false)}>
            知道了
          </Button>,
          <Button
            key="progress"
            type="primary"
            onClick={() => {
              setQueuedVisible(false);
              navigate('/documents/progress');
            }}
          >
            查看进度
          </Button>,
        ]}
      >
        <p>该文件已进入处理队列，点击右上角进度列表按钮查看。</p>
      </Modal>
    </div>
  );
};

export default DocumentsPage;
