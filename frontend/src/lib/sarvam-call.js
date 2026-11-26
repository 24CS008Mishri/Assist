import workletUrl from './sarvam-mic-worklet.js?url';
import { liveRequest } from './live-assistant-api';

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

function wav(frames) {
  const samples = frames.reduce((count, frame) => count + frame.length, 0);
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const label = (offset, value) => [...value].forEach((letter, i) => view.setUint8(offset + i, letter.charCodeAt(0)));
  label(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  label(8, 'WAVEfmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  label(36, 'data');
  view.setUint32(40, samples * 2, true);
  let offset = 44;
  for (const frame of frames) {
    for (const value of frame) {
      view.setInt16(offset, Math.max(-1, Math.min(1, value)) * 32767, true);
      offset += 2;
    }
  }
  return buffer;
}

export function sarvamCall({ call, room, onTurn, onNotice }) {
  const endpoint = `/api/live-assistant/sessions/${encodeURIComponent(room.id)}/voice`;
  const context = new AudioContext({ sampleRate: 16000 });
  let stopped = false;
  let source;
  let processor;
  let currentTrack;
  let captureVersion = 0;
  let lead = [];
  let frames = null;
  let loudFrames = 0;
  let silenceFrames = 0;
  let playback = 0;
  let turn = 0;
  let filler;
  let participant;
  let enabled = true;

  function deliver(type, properties = {}) {
    if (!stopped && participant) call.sendAppMessage({
      message_type: 'conversation', event_type: type, conversation_id: room.id, properties,
    }, participant);
  }

  async function speak(audio) {
    const playing = ++playback;
    const inferenceId = crypto.randomUUID();
    // 3200 base64 chars encode 50 ms of 24 kHz mono PCM below Daily's app message limit.
    for (let offset = 0; offset < audio.length && !stopped && playing === playback; offset += 3200) {
      deliver('conversation.echo', {
        modality: 'audio', inference_id: inferenceId, sample_rate: 24000,
        audio: audio.slice(offset, offset + 3200), done: offset + 3200 >= audio.length,
      });
      await pause(45);
    }
  }

  async function respond(recorded, number) {
    try {
      if (filler) void speak(filler).catch(() => onNotice('Vaani could not play the spoken update.'));
      const reply = await liveRequest(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: wav(recorded), timeoutMs: 27000,
      });
      if (stopped || number !== turn || !reply.question) return;
      onTurn('user', reply.question);
      onTurn('assistant', reply.answer);
      ++playback;
      deliver('conversation.interrupt');
      await speak(reply.audio);
    } catch (error) {
      if (!stopped && number === turn) onNotice(error.message);
    }
  }

  function consume(frame) {
    if (stopped || !enabled || !participant) return;
    const rms = Math.sqrt(frame.reduce((energy, value) => energy + value * value, 0) / frame.length);
    const loud = rms > 0.019;
    if (!frames) {
      lead.push(frame);
      if (lead.length > 15) lead.shift();
      loudFrames = loud ? loudFrames + 1 : 0;
      if (loudFrames < 6) return;
      frames = lead;
      lead = [];
      silenceFrames = 0;
      ++turn;
      ++playback;
      deliver('conversation.interrupt');
      return;
    }
    frames.push(frame);
    silenceFrames = loud ? 0 : silenceFrames + 1;
    if (silenceFrames < 32 && frames.length < 900) return;
    const recorded = frames;
    frames = null;
    loudFrames = 0;
    void respond(recorded, turn);
  }

  const ready = context.audioWorklet.addModule(workletUrl).then(() => context.resume());
  ready.catch(() => { if (!stopped) onNotice('Could not start Sarvam microphone capture. Try the Tavus voice.'); });

  return {
    setEnabled(value) {
      enabled = value;
      if (!value) { lead = []; frames = null; loudFrames = 0; }
      else void context.resume().catch(() => {});
    },
    async attach(track) {
      if (currentTrack === track) return;
      currentTrack = track;
      const version = ++captureVersion;
      source?.disconnect();
      processor?.disconnect();
      if (!track) return;
      try {
        await ready;
        if (stopped || version !== captureVersion) return;
        source = context.createMediaStreamSource(new MediaStream([track]));
        processor = new AudioWorkletNode(context, 'sarvam-mic');
        processor.port.onmessage = event => consume(event.data);
        // The worklet output is silent. Connecting keeps the capture graph running.
        source.connect(processor).connect(context.destination);
      } catch { /* Capture failure is shown by the shared readiness handler. */ }
    },
    async greet(sessionId, resumed) {
      if (participant || stopped) return;
      participant = sessionId;
      try {
        const audio = await liveRequest(`${endpoint}?resumed=${resumed}`);
        if (stopped) return;
        filler = audio.filler;
        if (turn) return;
        onTurn('assistant', audio.text);
        await speak(audio.greeting);
      } catch (error) {
        if (!stopped) onNotice(error.message);
      }
    },
    stop() {
      stopped = true;
      source?.disconnect();
      processor?.disconnect();
      void context.close().catch(() => {});
    },
  };
}
