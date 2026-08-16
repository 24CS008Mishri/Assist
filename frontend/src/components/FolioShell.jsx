import { useState } from 'react';
import { ChevronDown, FileText, Home, LogOut, MessageCircle, Plus, UserRound } from 'lucide-react';

export function FolioShell({
  active,
  onNavigate,
  recentChats = [],
  selectedChat,
  onSelectChat,
  onLogout,
  children,
}) {
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <div className="folio-root">
      <div className="folio-frame">
        <header className="folio-topbar">
          <div className="folio-logo" aria-label="FOLIO home">
            <span className="folio-brand">FOLIO</span>
          </div>
          <div className="folio-profile-wrap">
            <button
              className="folio-profile"
              type="button"
              aria-label="Open profile menu"
              data-testid="button-profile"
              onClick={() => setProfileOpen((open) => !open)}
            >
              <UserRound className="folio-profile-icon" size={21} strokeWidth={1.8} />
            </button>
            {profileOpen && (
              <div className="folio-profile-menu" role="menu" data-testid="menu-profile">
                <strong>Mira Chen</strong>
                <span>Personal workspace</span>
                <button
                  type="button"
                  role="menuitem"
                  data-testid="button-sign-out"
                  onClick={() => {
                    setProfileOpen(false);
                    onLogout?.();
                  }}
                >
                  Sign out safely
                </button>
              </div>
            )}
          </div>
        </header>
        <div className="folio-layout">
          <aside className="folio-sidebar" aria-label="Main navigation">
            <nav className="folio-nav">
              <button
                type="button"
                className={`folio-nav-button ${active === 'dashboard' ? 'active' : ''}`}
                data-testid="button-dashboard"
                onClick={() => onNavigate('dashboard')}
              >
                <Home className="folio-nav-icon" size={20} strokeWidth={1.8} />
                <span>Dashboard</span>
              </button>
              <button
                type="button"
                className={`folio-nav-button ${active === 'documents' ? 'active' : ''}`}
                data-testid="button-documents"
                onClick={() => onNavigate('documents')}
              >
                <FileText className="folio-nav-icon" size={20} strokeWidth={1.8} />
                <span>Documents</span>
              </button>
              <button
                type="button"
                className={`folio-nav-button ${active === 'chat' ? 'active' : ''}`}
                data-testid="button-chat"
                onClick={() => onNavigate('chat')}
              >
                <MessageCircle className="folio-nav-icon" size={20} strokeWidth={1.8} />
                <span>Chat</span>
                <Plus className="folio-plus" size={16} strokeWidth={2} />
                {active === 'chat' && <ChevronDown size={15} strokeWidth={1.8} />}
              </button>
              {active === 'chat' && recentChats.length > 0 && (
                <div className="folio-chat-list" aria-label="Recent conversations">
                  {recentChats.map((chat) => (
                    <button
                      type="button"
                      className={`folio-chat-item ${selectedChat === chat ? 'selected' : ''}`}
                      key={chat}
                      data-testid={`button-chat-${chat.toLowerCase().replaceAll(' ', '-')}`}
                      onClick={() => onSelectChat?.(chat)}
                    >
                      {chat}
                    </button>
                  ))}
                </div>
              )}
            </nav>
            <button type="button" className="folio-logout" data-testid="button-logout" onClick={onLogout}>
              <LogOut size={20} strokeWidth={1.8} />
              <span>Log out</span>
            </button>
          </aside>
          <main className="folio-content">{children}</main>
        </div>
      </div>
    </div>
  );
}

export function Surface({ children, className = '' }) {
  return <section className={`folio-surface ${className}`}>{children}</section>;
}
