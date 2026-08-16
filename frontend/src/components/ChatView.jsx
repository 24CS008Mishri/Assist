import { useState } from 'react';
import { FileText, Send } from 'lucide-react';
import { FolioShell, Surface } from './FolioShell';
import { askQuestion } from '../api';

const recentChats = ['Current session'];

export function ChatView({ onNavigate, onLogout }) {
  const [selectedChat, setSelectedChat] = useState(recentChats[0]);
  const [messages, setMessages] = useState([]);
  const [value, setValue] = useState('');
  const [sending, setSending] = useState(false);

  const sendMessage = async () => {
    const question = value.trim();
    if (!question || sending) return;

    setValue('');
    setMessages((current) => [
      ...current,
      { id: `${Date.now()}-q`, role: 'user', content: question },
    ]);

    setSending(true);
    try {
      const { answer } = await askQuestion(question);
      setMessages((current) => [
        ...current,
        { id: `${Date.now()}-a`, role: 'assistant', content: answer },
      ]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-a`,
          role: 'assistant',
          content: `Something went wrong: ${err.message}`,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <FolioShell
      active="chat"
      onNavigate={onNavigate}
      recentChats={recentChats}
      selectedChat={selectedChat}
      onSelectChat={setSelectedChat}
      onLogout={onLogout}
    >
      <div className="folio-heading">
        <div>
          <div className="folio-eyebrow">Conversation · {selectedChat}</div>
          <h1>Chat</h1>
        </div>
        <div className="folio-actions">
          <button
            type="button"
            className="folio-button"
            data-testid="button-new-conversation"
            onClick={() => setMessages([])}
          >
            New conversation
          </button>
        </div>
      </div>
      <Surface className="folio-chatbox">
        <div className="folio-messages" aria-live="polite" data-testid="list-messages">
          {messages.length === 0 ? (
            <div className="folio-chat-empty" data-testid="empty-conversation">
              A clean page for a fresh question.
            </div>
          ) : (
            messages.map((message) => (
              <div
                className={`folio-bubble ${message.role}`}
                key={message.id}
                data-testid={`message-${message.role}-${message.id}`}
              >
                {message.role === 'assistant' && <strong>Folio assistant</strong>}
                {message.content}
                {message.bullets && (
                  <ul>
                    {message.bullets.map((bullet) => (
                      <li key={bullet}>{bullet}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))
          )}
          {sending && (
            <div className="folio-bubble assistant" data-testid="message-assistant-pending">
              <strong>Folio assistant</strong>
              Thinking...
            </div>
          )}
        </div>
        <div className="folio-composer">
          <FileText size={17} strokeWidth={1.7} />
          <input
            value={value}
            type="text"
            placeholder="Type your question..."
            aria-label="Type your question"
            data-testid="input-question"
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') sendMessage();
            }}
          />
          <button
            type="button"
            className="folio-send"
            aria-label="Send message"
            data-testid="button-send-message"
            disabled={!value.trim() || sending}
            onClick={sendMessage}
          >
            <Send size={18} strokeWidth={1.8} />
          </button>
        </div>
      </Surface>
    </FolioShell>
  );
}