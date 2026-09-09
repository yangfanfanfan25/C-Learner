import { useEffect, useState, type ReactNode } from 'react';
import { Alert, Button, Input, Select, Spin, Typography } from 'antd';
import { CheckCircle2, KeyRound, RefreshCw, ServerCog } from 'lucide-react';
import { setupApi, type ModelOption, type SetupStatus } from '@/services/setup';
import styles from './index.module.less';

interface SetupGateProps { children: ReactNode }
const FALLBACK_MODELS: ModelOption[] = [
  { id: 'deepseek-chat', label: 'DeepSeek Chat', base_url: 'https://api.deepseek.com/v1', provider: 'openai' },
  { id: 'deepseek-reasoner', label: 'DeepSeek Reasoner', base_url: 'https://api.deepseek.com/v1', provider: 'openai' },
];

const SetupGate: React.FC<SetupGateProps> = ({ children }) => {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [models, setModels] = useState(FALLBACK_MODELS);
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState(FALLBACK_MODELS[0].id);
  const [baseUrl, setBaseUrl] = useState(FALLBACK_MODELS[0].base_url);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = async () => { setLoading(true); try { const next = await setupApi.getStatus(); setStatus(next); setModelName(next.model_name || FALLBACK_MODELS[0].id); setBaseUrl(next.base_url || FALLBACK_MODELS[0].base_url); } catch (err) { setError(err instanceof Error ? err.message : '无法读取模型配置，请确认后端已启动。'); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  const save = async () => {
    if (!apiKey.trim()) { setError('请输入 API Key 后再检测连接。'); return; }
    setSaving(true); setError('');
    try { const result = await setupApi.saveConfig({ api_key: apiKey.trim(), model_name: modelName, base_url: baseUrl.trim(), provider: 'openai' }); setStatus(result.status); setModels(result.models.length ? result.models : FALLBACK_MODELS); if (!result.status.connected) setError(result.status.message); else setApiKey(''); }
    catch (err) { setError(err instanceof Error ? err.message : '保存配置失败，请重试。'); } finally { setSaving(false); }
  };
  if (loading) return <div className={styles.loading}><Spin /><span>正在检查模型连接...</span></div>;
  if (status?.connected) return <>{children}</>;
  return <div className={styles.page}><section className={styles.panel} aria-labelledby="setup-title"><div className={styles.icon}><ServerCog size={22} /></div><Typography.Title level={2} id="setup-title">开始使用 C-Learner</Typography.Title><Typography.Paragraph className={styles.lead}>先配置模型连接，连接成功后即可进入智能对话。</Typography.Paragraph><label className={styles.label} htmlFor="setup-model">模型</label><Select id="setup-model" value={modelName} onChange={(value) => { const option = models.find((item) => item.id === value); setModelName(value); if (option) setBaseUrl(option.base_url); }} options={models.map((item) => ({ value: item.id, label: item.label }))} className={styles.control} /><label className={styles.label} htmlFor="setup-key">API Key</label><Input.Password id="setup-key" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={status?.api_key_configured ? '已配置，输入新 Key 可替换' : '粘贴你的 API Key'} prefix={<KeyRound size={16} />} className={styles.control} /><label className={styles.label} htmlFor="setup-base-url">Base URL</label><Input id="setup-base-url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} className={styles.control} />{error && <Alert type="error" showIcon message={error} className={styles.alert} />}{status?.message && !error && <Alert type="info" showIcon message={status.message} className={styles.alert} />}<Button type="primary" size="large" block loading={saving} onClick={() => void save()} icon={status?.configured ? <RefreshCw size={16} /> : <CheckCircle2 size={16} />}>{status?.configured ? '重新检测连接' : '保存并检测连接'}</Button><Typography.Text type="secondary" className={styles.note}>密钥仅写入本机环境文件，不会保存到应用设置或数据库。</Typography.Text></section></div>;
};
export default SetupGate;
