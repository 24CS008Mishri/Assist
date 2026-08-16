import { useState } from 'react';
import { ChatView } from './components/ChatView';
import { DashboardView } from './components/DashboardView';
import { DocumentsView } from './components/DocumentsView';

function App() {
  const [view, setView] = useState('dashboard');
  const [notice, setNotice] = useState('');

  const logout = () => {
    setNotice('You are safely signed out of this local workspace.');
    window.setTimeout(() => setNotice(''), 2800);
  };

  return (
    <>
      {view === 'dashboard' && <DashboardView onNavigate={setView} onLogout={logout} />}
      {view === 'documents' && <DocumentsView onNavigate={setView} onLogout={logout} />}
      {view === 'chat' && <ChatView onNavigate={setView} onLogout={logout} />}
      {notice && (
        <div className="folio-toast" role="status" data-testid="status-logout">
          {notice}
        </div>
      )}
    </>
  );
}

export default App;
