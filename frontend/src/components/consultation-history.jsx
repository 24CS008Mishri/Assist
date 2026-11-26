import { useRef, useState } from 'react';
import { History, X } from 'lucide-react';
import { liveRequest } from '@/lib/live-assistant-api';

export const transcriptsApi = '/api/live-assistant/transcripts';
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export default function ConsultationHistory() {
  const dialog = useRef(null);
  const [items, setItems] = useState([]);
  const [next, setNext] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function load(offset = 0) {
    setBusy(true);
    setError('');
    try {
      const response = await liveRequest(`${transcriptsApi}?offset=${offset}`);
      setItems(previous => offset ? [...previous, ...response.items.filter(item => !previous.some(row => row.id === item.id))] : response.items);
      setNext(response.next_offset);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  async function read(id) {
    setBusy(true);
    setError('');
    try {
      setSelected(await liveRequest(`${transcriptsApi}/${encodeURIComponent(id)}`));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return <>
    <button type="button" className="btn" disabled={busy} onClick={() => {
      setSelected(null);
      dialog.current.showModal();
      void load();
    }}><History size={16} /> Transcript history</button>
    <dialog ref={dialog} className="consultation-history" aria-labelledby="consultation-history-title">
      <header>
        <h2 id="consultation-history-title" className="font-display">Transcript history</h2>
        <button className="btn icon-btn" type="button" aria-label="Close transcript history"
          onClick={() => dialog.current.close()}><X size={16} /></button>
      </header>
      {error && <p role="alert">{error}</p>}
      {busy && <p className="muted" role="status">Loading…</p>}
      {selected ? <>
        <button type="button" className="btn" onClick={() => { setSelected(null); setError(''); }}>Back to history</button>
        <h3>{selected.title}</h3>
        <p className="muted">{dateFormat.format(new Date(selected.created_at))}</p>
        <ol className="consultation-turns">{selected.turns.map(turn => (
          <li key={turn._id}><strong>{turn.role === 'user' ? 'You' : 'Vaani'}</strong><p>{turn.text}</p></li>
        ))}</ol>
      </> : <>
        {!busy && !error && !items.length && <p className="muted">Saved consultations will appear here.</p>}
        <ul className="consultation-history-list">{items.map(item => (
          <li key={item.id}><button type="button" disabled={busy} onClick={() => { void read(item.id); }}>
            <strong>{item.title}</strong><span>{dateFormat.format(new Date(item.created_at))}</span>
          </button></li>
        ))}</ul>
        {next !== null && <button type="button" className="btn" disabled={busy}
          onClick={() => { void load(next); }}>Load earlier consultations</button>}
        {error && <button type="button" className="btn" disabled={busy} onClick={() => { void load(); }}>Retry</button>}
      </>}
    </dialog>
  </>;
}
