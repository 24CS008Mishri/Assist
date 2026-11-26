import { useEffect, useRef, useState } from 'react';
import { BookOpen, Captions, Maximize, MessageSquare, Mic, MicOff, PhoneOff, Video, VideoOff } from 'lucide-react';

function useMediaTrack(element, track, onBlocked) {
  useEffect(() => {
    const node = element.current;
    if (!node || !track) return undefined;
    const stream = new MediaStream([track]);
    node.srcObject = stream;
    void node.play().catch(() => {
      if (node.srcObject === stream) onBlocked?.();
    });
    return () => {
      node.srcObject = null;
    };
  }, [element, track, onBlocked]);
}

function availableTrack(participant, kind) {
  const state = participant?.tracks?.[kind];
  return state?.state === 'playable' ? state.persistentTrack || state.track : null;
}

function VideoTrack({ track, className, label }) {
  const element = useRef(null);
  useMediaTrack(element, track);
  return <video ref={element} className={className} aria-label={label} autoPlay playsInline muted />;
}

export default function TavusVideo({ room, sources, onEnd, reconnecting, reconnectFailed, onDisconnected, onRetry, onTopic, onTurn }) {
  const container = useRef(null);
  const callRef = useRef(null);
  const audioElement = useRef(null);
  const handlers = useRef({ onDisconnected, onTopic, onTurn });
  const microphoneEnabled = useRef(true);
  const cameraEnabled = useRef(false);
  const [status, setStatus] = useState('Connecting…');
  const [tracks, setTracks] = useState({});
  const [playbackBlocked, setPlaybackBlocked] = useState(false);
  const [captions, setCaptions] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [partial, setPartial] = useState(null);
  const [drawer, setDrawer] = useState(null);
  const [notice, setNotice] = useState('');
  const playbackWarning = useRef(() => setPlaybackBlocked(true));
  useMediaTrack(audioElement, tracks.avatarAudio, playbackWarning.current);

  useEffect(() => { handlers.current = { onDisconnected, onTopic, onTurn }; }, [onDisconnected, onTopic, onTurn]);

  useEffect(() => {
    let disposed = false;
    let call;
    let joined = false;
    let departureTimer;
    const seenUtterances = new Set();
    setStatus('Connecting…');
    setTracks({});
    setPartial(null);

    function syncTracks() {
      if (disposed) return;
      const { local, ...remote } = call.participants();
      const avatar = Object.values(remote)[0];
      setTracks({
        avatarVideo: availableTrack(avatar, 'video'),
        avatarAudio: availableTrack(avatar, 'audio'),
        selfVideo: availableTrack(local, 'video'),
        mic: availableTrack(local, 'audio') !== null,
        camera: availableTrack(local, 'video') !== null,
        micState: local?.tracks?.audio?.state,
      });
    }

    function receiveUtterance(event) {
      if (disposed || !event.fromId || !call.participants()[event.fromId] || call.participants()[event.fromId].local) return;
      const message = event.data;
      if (message?.conversation_id !== room.id) return;
      if (!['conversation.utterance', 'conversation.utterance.streaming'].includes(message.event_type)) return;
      const { role, speech, accumulated_speech: accumulated } = message.properties || {};
      if (!['user', 'assistant', 'replica', 'pal'].includes(role)) return;
      const speaker = role === 'user' ? 'user' : 'assistant';
      const text = accumulated ?? speech;
      if (typeof text !== 'string' || !text.trim()) return;
      if (message.event_type.endsWith('.streaming')) {
        if (role !== 'replica') setPartial({ role: speaker, text });
        return;
      }
      const key = `${room.id}:${speaker}:${message.inference_id ?? message.timestamp ?? ''}:${text}`;
      if (seenUtterances.has(key)) return;
      seenUtterances.add(key);
      if (speaker === 'user') handlers.current.onTopic(text);
      handlers.current.onTurn({ role: speaker, text });
      setPartial(null);
      setTranscript(previous => [...previous.slice(-99), { key, role: speaker, text }]);
    }

    function fail() {
      if (disposed) return;
      setStatus('Connection failed');
      if (joined) handlers.current.onDisconnected();
    }

    async function connect() {
      try {
        const { default: Daily } = await import('@daily-co/daily-js');
        if (disposed) return;
        const url = new URL(room.embed_url);
        const token = url.searchParams.get('t');
        url.search = '';
        call = Daily.createCallObject();
        callRef.current = call;
        call.on('joined-meeting', () => {
          joined = true;
          if (!disposed) setStatus('Connected');
          syncTracks();
        });
        for (const event of ['participant-joined', 'participant-updated', 'participant-left', 'track-started', 'track-stopped']) {
          call.on(event, syncTracks);
        }
        call.on('participant-joined', () => window.clearTimeout(departureTimer));
        call.on('participant-left', event => {
          if (!joined || event.participant.local) return;
          window.clearTimeout(departureTimer);
          departureTimer = window.setTimeout(() => {
            if (!disposed && !Object.values(call.participants()).some(participant => !participant.local)) {
              setStatus('Video room ended');
              handlers.current.onDisconnected();
            }
          }, 1800);
        });
        call.on('app-message', receiveUtterance);
        call.on('camera-error', () => {
          if (!disposed) setNotice('Check your browser’s microphone and camera permissions.');
        });
        call.on('left-meeting', () => {
          if (disposed) return;
          setStatus('Disconnected');
          syncTracks();
          if (joined) handlers.current.onDisconnected();
        });
        call.on('error', fail);
        await call.join({
          url: url.toString(), token, startVideoOff: !cameraEnabled.current,
          startAudioOff: !microphoneEnabled.current, userName: 'Curriculum Designer',
        });
      } catch {
        fail();
      }
    }

    void connect();
    return () => {
      disposed = true;
      window.clearTimeout(departureTimer);
      callRef.current = null;
      if (call) void call.destroy().catch(() => {});
    };
  }, [room.id, room.embed_url]);

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await container.current.requestFullscreen();
    } catch {
      setNotice('Full screen is unavailable in this browser.');
    }
  }

  const connected = status === 'Connected' && !reconnecting;
  const displayStatus = reconnecting ? 'Reconnecting to Vaani…' : status;
  const latest = partial || transcript.at(-1);
  const MicIcon = tracks.mic ? Mic : MicOff;
  const CameraIcon = tracks.camera ? Video : VideoOff;
  return <div className="virtual-call" ref={container}>
    <div className="virtual-stage">
      {tracks.avatarVideo && <VideoTrack track={tracks.avatarVideo} className="virtual-avatar" label="Curriculum consultant video" />}
      <audio ref={audioElement} autoPlay />
      <div className="virtual-stage-status" role="status">
        <span className={connected ? 'virtual-dot is-connected' : 'virtual-dot'} /> {displayStatus}
        {connected && <span>· {tracks.mic ? 'Mic on' : tracks.micState === 'blocked' ? 'Mic blocked' : 'Mic off'}</span>}
      </div>
      {!tracks.avatarVideo && <div className="virtual-wait">
        {displayStatus.startsWith('Connecting') ? 'Joining the private consultation' : connected ? 'Waiting for Vaani’s video' : displayStatus}
      </div>}
      {tracks.selfVideo && <VideoTrack track={tracks.selfVideo} className="virtual-self-preview" label="Your camera preview" />}
      {captions && latest && <p className="virtual-caption">{latest.role === 'user' ? 'You' : 'Vaani'} · {latest.text}</p>}
      {playbackBlocked && <button className="btn virtual-playback" type="button" onClick={() => {
        void audioElement.current.play().then(() => setPlaybackBlocked(false)).catch(() => {});
      }}>Enable audio playback</button>}
    </div>
    <div className="virtual-call-controls" aria-label="Consultation controls">
      <button className="btn" type="button" disabled={!connected} aria-pressed={Boolean(tracks.mic)}
        onClick={() => { microphoneEnabled.current = !tracks.mic; callRef.current?.setLocalAudio(microphoneEnabled.current); }}><MicIcon size={17} /> {tracks.mic ? 'Mute' : 'Unmute'}</button>
      <button className="btn" type="button" disabled={!connected} aria-pressed={Boolean(tracks.camera)}
        onClick={() => { cameraEnabled.current = !tracks.camera; callRef.current?.setLocalVideo(cameraEnabled.current); }}><CameraIcon size={17} /> Camera</button>
      <button className="btn" type="button" aria-pressed={captions} onClick={() => setCaptions(!captions)}><Captions size={17} /> Captions</button>
      <button className="btn" type="button" aria-expanded={drawer === 'transcript'}
        onClick={() => setDrawer(drawer === 'transcript' ? null : 'transcript')}><MessageSquare size={17} /> Transcript</button>
      <button className="btn" type="button" aria-expanded={drawer === 'evidence'}
        onClick={() => setDrawer(drawer === 'evidence' ? null : 'evidence')}><BookOpen size={17} /> Evidence</button>
      <button className="btn icon-btn" type="button" aria-label="Toggle full screen" onClick={toggleFullscreen}><Maximize size={17} /></button>
      {(reconnectFailed || status === 'Connection failed') && !reconnecting &&
        <button className="btn" type="button" onClick={onRetry}>Reconnect</button>}
      <button className="btn btn-danger" type="button" onClick={onEnd}><PhoneOff size={17} /> End call</button>
    </div>
    {notice && <p className="virtual-notice" role="status">{notice}</p>}
    {drawer && <aside className="virtual-drawer" aria-label={drawer === 'transcript' ? 'Transcript' : 'Evidence'}>
      {drawer === 'transcript' ? (
        transcript.length ? <ol>{transcript.map(turn => (
          <li key={turn.key}><strong>{turn.role === 'user' ? 'You' : 'Assistant'}</strong> {turn.text}</li>
        ))}</ol> : <p>Spoken turns will appear here as they become available.</p>
      ) : (
        sources.length ? <ul>{sources.map(source => (
          <li key={JSON.stringify(source)}>{source.title}{source.page ? ` · page ${source.page}` : ''} <small>{source.kind}</small></li>
        ))}</ul> : <p>Supporting references will appear after a curriculum question.</p>
      )}
    </aside>}
  </div>;
}
