import { FileText, MessageCircle, Sparkles, Upload } from 'lucide-react';
import { FolioShell, Surface } from './FolioShell';

const stats = [
  { id: 'files', label: 'Documents in library', value: '4' },
  { id: 'chats', label: 'Conversations this week', value: '7' },
  { id: 'storage', label: 'Storage used', value: '9.8 MB' },
];

const recentActivity = [
  { id: 'q3', title: 'Q3 Product Strategy.pdf', detail: 'Uploaded · 12 Aug 2025' },
  { id: 'measure-question', title: 'Asked "What should we measure first?"', detail: 'Q3 strategy · 2 days ago' },
  { id: 'brand', title: 'Brand voice & editorial guide.pdf', detail: 'Uploaded · 08 Aug 2025' },
];

export function DashboardView({ onNavigate, onLogout }) {
  return (
    <FolioShell active="dashboard" onNavigate={onNavigate} onLogout={onLogout}>
      <div className="folio-heading">
        <div>
          <div className="folio-eyebrow">Welcome back</div>
          <h1>Good to see you, Mira</h1>
        </div>
        <div className="folio-actions">
          <button type="button" className="folio-button" data-testid="button-go-documents" onClick={() => onNavigate('documents')}>
            <Upload size={17} strokeWidth={1.9} />
            Upload PDF
          </button>
          <button type="button" className="folio-button pink" data-testid="button-go-chat" onClick={() => onNavigate('chat')}>
            <MessageCircle size={17} strokeWidth={1.9} />
            Start a chat
          </button>
        </div>
      </div>

      <div className="folio-stats">
        {stats.map((stat) => (
          <Surface className="folio-stat" key={stat.id}>
            <div className="folio-stat-value">{stat.value}</div>
            <div className="folio-stat-label">{stat.label}</div>
          </Surface>
        ))}
      </div>

      <div className="folio-eyebrow" style={{ marginTop: 30, marginBottom: 14 }}>
        Recent activity
      </div>
      <Surface className="folio-docs">
        {recentActivity.map((item) => (
          <div className="folio-doc" key={item.id} data-testid={`row-activity-${item.id}`}>
            <div className="folio-file">
              {item.title.toLowerCase().includes('.pdf') ? (
                <FileText size={23} strokeWidth={1.7} />
              ) : (
                <Sparkles size={23} strokeWidth={1.7} />
              )}
            </div>
            <div className="folio-doc-info">
              <div className="folio-doc-name">{item.title}</div>
              <div className="folio-meta">{item.detail}</div>
            </div>
          </div>
        ))}
      </Surface>
    </FolioShell>
  );
}
