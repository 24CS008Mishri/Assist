import { useEffect, useRef, useState } from 'react';
import { Video } from 'lucide-react';
import { liveRequest as request } from '@/lib/live-assistant-api';
import './live-curriculum-assistant.css';
import TavusVideo from './tavus-video';
import ConsultationHistory, { transcriptsApi } from './consultation-history';

const api = '/api/live-assistant/sessions';

function closeRoom(id) {
  return fetch(`${api}/${encodeURIComponent(id)}`, { method: 'DELETE', keepalive: true });
}

export default function LiveCurriculumAssistant() {
  const [ready, setReady] = useState(false);
  const [language, setLanguage] = useState('en-in');
  const [documentKey, setDocumentKey] = useState('');
  const [documents, setDocuments] = useState([]);
  const [room, setRoom] = useState(null);
  const [existingId, setExistingId] = useState(null);
  const [sources, setSources] = useState([]);
  const [busy, setBusy] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [reconnectFailed, setReconnectFailed] = useState(false);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState(false);
  const activeRoom = useRef(null);
  const mounted = useRef(false);
  const renewing = useRef(false);
  const lastTopic = useRef('');
  const turnSequence = useRef(0);
  const pendingTurns = useRef(new Map());

  function saveTurn(item) {
    if (item.saving) return item.saving;
    item.saving = request(`${transcriptsApi}/${encodeURIComponent(item.transcriptId)}/turns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(item.turn),
      keepalive: true,
    }).then(() => {
      pendingTurns.current.delete(item.turn.id);
      if (mounted.current && !pendingTurns.current.size) setHistoryError(false);
    }).catch(() => {
      if (mounted.current) setHistoryError(true);
    }).finally(() => { item.saving = null; });
    return item.saving;
  }

  function flushTranscript() {
    return Promise.all([...pendingTurns.current.values()].map(saveTurn));
  }

  function recordTurn(transcriptId, { role, text }) {
    if (!transcriptId) return;
    const turn = { id: crypto.randomUUID(), sequence: ++turnSequence.current, role, text };
    const item = { transcriptId, turn };
    pendingTurns.current.set(turn.id, item);
    void saveTurn(item);
  }

  useEffect(() => {
    mounted.current = true;
    const disconnect = () => {
      void flushTranscript();
      const id = activeRoom.current;
      activeRoom.current = null;
      if (id) void closeRoom(id).catch(() => {});
    };
    window.addEventListener('pagehide', disconnect);
    window.addEventListener('online', flushTranscript);
    return () => {
      mounted.current = false;
      window.removeEventListener('pagehide', disconnect);
      window.removeEventListener('online', flushTranscript);
      disconnect();
    };
  }, []);

  useEffect(() => {
    if (!room) return undefined;
    let cancelled = false;
    let polls = 0;
    const refresh = async () => {
      try {
        const checkProvider = ++polls % 3 === 0;
        const response = await request(`${api}/${encodeURIComponent(room.id)}/sources?check_provider=${checkProvider}`, {
          timeoutMs: checkProvider ? 6000 : 3500,
        });
        if (!cancelled) setSources(response.sources);
      } catch (failure) {
        if (cancelled || renewing.current || activeRoom.current !== room.id) return;
        if (failure.status === 404) {
          void reconnect(room.id);
        } else if ([401, 403].includes(failure.status)) {
          activeRoom.current = null;
          setRoom(null);
          setSources([]);
          setError('The consultation ended. You can start a new call.');
        }
      }
    };
    const poll = window.setInterval(refresh, 4000);
    const expiry = window.setTimeout(() => { void reconnect(room.id); },
      Math.max(0, Date.parse(room.expires_at) - Date.now()));
    return () => {
      cancelled = true;
      window.clearInterval(poll);
      window.clearTimeout(expiry);
    };
  }, [room, reconnectFailed]);

  async function open() {
    setReady(false);
    setBusy(true);
    setError('');
    try {
      const current = await request(`${api}/current`);
      setExistingId(current.id);
      setDocuments((await request('/api/documents')).filter((item) => (
        item.source_type === 'submitted_curriculum' && item.status === 'Active' && item.document_id && item.curriculum_id
      )));
      setReady(true);
    } catch (failure) {
      setError(failure.status === 401 ? 'Sign out and sign back in to refresh your Designer session.' : failure.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void open(); }, []);

  function createRoom(resumeTopic, transcriptId) {
    const [documentId, curriculumId] = documentKey ? JSON.parse(documentKey) : [null, null];
    return request(api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language, document_id: documentId, curriculum_id: curriculumId, resume_topic: resumeTopic,
        transcript_id: transcriptId,
      }),
    });
  }

  async function reconnect(id, retry = false) {
    if (id !== activeRoom.current || renewing.current || (reconnectFailed && !retry)) return;
    renewing.current = true;
    setReconnectFailed(false);
    setReconnecting(true);
    setError('');
    try {
      await request(`${api}/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (activeRoom.current !== id) return;
      const replacement = await createRoom(lastTopic.current, room.transcript_id);
      if (!mounted.current || activeRoom.current !== id) {
        void closeRoom(replacement.id).catch(() => {});
        return;
      }
      activeRoom.current = replacement.id;
      setRoom(replacement);
    } catch (failure) {
      if (activeRoom.current === id) {
        setReconnectFailed(true);
        setError(failure.message);
      }
    } finally {
      renewing.current = false;
      if (mounted.current) setReconnecting(false);
    }
  }

  async function start(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSources([]);
    lastTopic.current = '';
    turnSequence.current = 0;
    try {
      const result = await createRoom();
      if (!mounted.current) {
        void closeRoom(result.id).catch(() => {});
        return;
      }
      activeRoom.current = result.id;
      setRoom(result);
    } catch (failure) {
      if (failure.status === 409) {
        const current = await request(`${api}/current`).catch(() => null);
        setExistingId(current?.id || null);
      }
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  async function end() {
    const sessionId = room?.id || existingId;
    activeRoom.current = null;
    setBusy(true);
    setError('');
    setReconnectFailed(false);
    // Remove the room immediately so microphone and camera access stop locally.
    setRoom(null);
    setSources([]);
    try {
      await request(`${api}/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
      await flushTranscript();
      activeRoom.current = null;
      setExistingId(null);
    } catch (failure) {
      setExistingId(sessionId);
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="virtual-assistant" aria-labelledby="virtual-assistant-heading">
      <header className="virtual-header">
        <div>
          <h1 id="virtual-assistant-heading" className="font-display">Virtual Assistant</h1>
          <p>Live curriculum consultation with Vaani, an AI-generated consultant.</p>
        </div>
        <ConsultationHistory />
      </header>
      {error && <p className="virtual-error" role="alert">{error}</p>}
      {historyError && <p className="virtual-error" role="status">
        Some transcript turns are waiting to be saved. <button type="button" className="btn"
          onClick={() => { void flushTranscript(); }}>Retry saving</button>
      </p>}
      {room ? <TavusVideo room={room} sources={sources} onEnd={end}
        reconnecting={reconnecting} reconnectFailed={reconnectFailed}
        onDisconnected={() => { void reconnect(room.id); }}
        onRetry={() => { void reconnect(room.id, true); }}
        onTurn={turn => recordTurn(room.transcript_id, turn)}
        onTopic={text => { lastTopic.current = text.slice(0, 900); }} /> : (
        <div className="virtual-lobby">
          <div className="virtual-setup surface">
            <Video size={26} aria-hidden="true" />
            <h2 className="font-display">Start a consultation</h2>
            <p className="muted">Review your courses, credits and semester structure against AICTE references.</p>
            <form className="virtual-setup-form" onSubmit={start}>
              <label className="label">Curriculum
                <select className="field" value={documentKey} onChange={event => setDocumentKey(event.target.value)} disabled={busy}>
                  <option value="">Choose in conversation</option>
                  {documents.map(document => {
                    const key = JSON.stringify([document.document_id, document.curriculum_id]);
                    return <option key={key} value={key}>{document.filename} · {document.curriculum_id}</option>;
                  })}
                </select>
              </label>
              <label className="label">Opening language
                <select className="field" value={language} onChange={event => setLanguage(event.target.value)} disabled={busy}>
                  <option value="en-in">English (India)</option>
                  <option value="hi">Hindi</option>
                  <option value="gu">Gujarati</option>
                </select>
              </label>
              {existingId ? (
                <button type="button" className="btn btn-danger" onClick={end} disabled={busy}>End previous consultation</button>
              ) : (
                <button type="submit" className="btn btn-primary" disabled={busy || !ready}>
                  <Video size={16} /> {busy ? 'Please wait…' : 'Start video call'}
                </button>
              )}
              {!ready && !busy && <button className="btn" type="button" onClick={open}>Retry connection</button>}
            </form>
            <p className="muted virtual-privacy">Tavus processes your voice and any camera video you enable. The portal saves a text transcript for you to review.</p>
          </div>
        </div>
      )}
    </section>
  );
}
