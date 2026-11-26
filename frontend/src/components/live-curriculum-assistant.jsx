import { useEffect, useRef, useState } from 'react';
import { Video, X } from 'lucide-react';
import { liveRequest as request } from '@/lib/live-assistant-api';
import './live-curriculum-assistant.css';
import TavusVideo from './tavus-video';

const api = '/api/live-assistant/sessions';

function closeRoom(id) {
  return fetch(`${api}/${encodeURIComponent(id)}`, { method: 'DELETE', keepalive: true });
}

export default function LiveCurriculumAssistant() {
  const [expanded, setExpanded] = useState(false);
  const [language, setLanguage] = useState('en-in');
  const [documentKey, setDocumentKey] = useState('');
  const [documents, setDocuments] = useState([]);
  const [room, setRoom] = useState(null);
  const [existingId, setExistingId] = useState(null);
  const [sources, setSources] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const activeRoom = useRef(null);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    const disconnect = () => {
      if (activeRoom.current) void closeRoom(activeRoom.current).catch(() => {});
    };
    window.addEventListener('pagehide', disconnect);
    return () => {
      mounted.current = false;
      window.removeEventListener('pagehide', disconnect);
      disconnect();
    };
  }, []);

  useEffect(() => {
    if (!room) return undefined;
    let cancelled = false;
    const refresh = async () => {
      try {
        const response = await request(`${api}/${encodeURIComponent(room.id)}/sources`, { timeoutMs: 3500 });
        if (!cancelled) setSources(response.sources);
      } catch (failure) {
        if (!cancelled && [401, 403, 404].includes(failure.status)) {
          activeRoom.current = null;
          setRoom(null);
          setSources([]);
          setError('The consultation ended. You can start a new call.');
        }
      }
    };
    const poll = window.setInterval(refresh, 4000);
    const expiry = window.setTimeout(() => {
      if (activeRoom.current === room.id) {
        void closeRoom(room.id).catch(() => {});
        activeRoom.current = null;
        setRoom(null);
        setSources([]);
        setError('The consultation reached its time limit.');
      }
    }, Math.max(0, Date.parse(room.expires_at) - Date.now()));
    return () => {
      cancelled = true;
      window.clearInterval(poll);
      window.clearTimeout(expiry);
    };
  }, [room]);

  async function open() {
    setExpanded(true);
    setBusy(true);
    setError('');
    try {
      const current = await request(`${api}/current`);
      setExistingId(current.id);
      setDocuments((await request('/api/documents')).filter((item) => (
        item.source_type === 'submitted_curriculum' && item.status === 'Active' && item.document_id && item.curriculum_id
      )));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  async function start(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSources([]);
    const [documentId, curriculumId] = documentKey ? JSON.parse(documentKey) : [null, null];
    try {
      const result = await request(api, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, document_id: documentId, curriculum_id: curriculumId }),
      });
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
    setBusy(true);
    setError('');
    // Remove the room immediately so microphone and camera access stop locally.
    setRoom(null);
    setSources([]);
    try {
      await request(`${api}/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
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
    <section id="live-consultation" className="surface live-assistant" aria-labelledby="live-assistant-heading">
      <div className="live-assistant-heading">
        <div>
          <h2 id="live-assistant-heading" className="font-display">AI Curriculum Assistant</h2>
          <p className="muted">Discuss AICTE guidance, your curriculum, and Analyzer findings by video.</p>
        </div>
        {!expanded && <button className="btn btn-primary" type="button" onClick={open}><Video size={16} /> Set up a video call</button>}
        {expanded && !room && !busy && !existingId && (
          <button className="btn icon-btn" type="button" onClick={() => setExpanded(false)} aria-label="Close call setup"><X size={16} /></button>
        )}
      </div>
      {expanded && !room && !existingId && (
        <form className="live-assistant-controls" onSubmit={start}>
          <label className="label">Curriculum
            <select className="field" value={documentKey} onChange={(event) => setDocumentKey(event.target.value)} disabled={busy}>
              <option value="">Search my curricula as needed</option>
              {documents.map((document) => {
                const key = JSON.stringify([document.document_id, document.curriculum_id]);
                return <option key={key} value={key}>{document.filename} · {document.curriculum_id}</option>;
              })}
            </select>
          </label>
          <label className="label">Opening language
            <select className="field" value={language} onChange={(event) => setLanguage(event.target.value)} disabled={busy}>
              <option value="en-in">English (India)</option>
              <option value="hi">Hindi</option>
              <option value="gu">Gujarati</option>
            </select>
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy}><Video size={16} /> {busy ? 'Please wait…' : 'Start video call'}</button>
          <p className="muted live-assistant-note">Tavus processes your voice and any camera video you enable. You can switch languages during the call.</p>
        </form>
      )}
      {error && expanded && <p className="live-assistant-error" role="alert">{error}</p>}
      {existingId && !room && (
        <button type="button" className="btn btn-danger" onClick={end} disabled={busy}>End previous consultation</button>
      )}
      {room && (
        <>
          <TavusVideo embedUrl={room.embed_url} />
          <button type="button" className="btn btn-danger" onClick={end}>End consultation</button>
          {!!sources.length && <div className="live-assistant-sources" aria-live="polite">
            <h3>Evidence retrieved for the latest question</h3>
            <ul>{sources.map((source) => (
              <li key={JSON.stringify(source)}>{source.title}{source.page ? ` · page ${source.page}` : ''} <span className="muted">({source.kind})</span></li>
            ))}</ul>
          </div>}
        </>
      )}
    </section>
  );
}
