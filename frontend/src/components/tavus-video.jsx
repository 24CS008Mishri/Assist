import { useEffect, useRef, useState } from 'react';

export default function TavusVideo({ embedUrl }) {
  const mount = useRef(null);
  const [status, setStatus] = useState('Connecting to the video room…');

  useEffect(() => {
    let cancelled = false;
    let call;
    const fail = () => {
      if (!cancelled) setStatus('Unable to join the video room. Check microphone access, then start a new call.');
    };
    async function connect() {
      try {
        const { default: Daily } = await import('@daily-co/daily-js');
        if (cancelled) return;
        const url = new URL(embedUrl);
        const token = url.searchParams.get('t');
        url.search = '';
        call = Daily.createFrame(mount.current, {
          showLeaveButton: false,
          iframeStyle: { width: '100%', height: '100%', border: '0' },
        });
        call.iframe().title = 'Live AI curriculum consultation';
        call.iframe().referrerPolicy = 'no-referrer';
        call.on('joined-meeting', () => { if (!cancelled) setStatus(''); });
        call.on('left-meeting', () => { if (!cancelled) setStatus('The video room has closed.'); });
        call.on('error', fail);
        await call.join({ url: url.toString(), token, startVideoOff: true, userName: 'Curriculum Designer' });
      } catch {
        fail();
      }
    }
    void connect();
    return () => {
      cancelled = true;
      if (call) void call.destroy().catch(() => {});
    };
  }, [embedUrl]);

  return <>
    {status && <p role="status" className="muted">{status}</p>}
    <div className="live-assistant-video" ref={mount} />
  </>;
}
