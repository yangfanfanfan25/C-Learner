import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Chat from './pages/Chat';
import Documents from './pages/Documents';
import DocumentsProgress from './pages/Documents/Progress';
import Quiz from './pages/Quiz';
import SetupGate from './components/SetupGate';

/**
 * 路由：只注册真实页面。
 * - `/` 与 `/chat` 进入新的智能体对话页
 * - `/chat/:sessionId` 恢复指定会话，支持刷新后保持当前聊天框
 * - `/documents` 进入文档工作台
 * - `/documents/progress` 进入文件处理进度页
 * - `/quiz/:paperId` 进入模拟练习在线答题页
 */
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SetupGate><Chat /></SetupGate>} />
        <Route path="/chat" element={<SetupGate><Chat /></SetupGate>} />
        <Route path="/chat/:sessionId" element={<SetupGate><Chat /></SetupGate>} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/documents/progress" element={<DocumentsProgress />} />
        <Route path="/quiz/:paperId" element={<Quiz />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
