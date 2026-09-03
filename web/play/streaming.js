import { safeHttpUrl } from './ui.js';

let activePlayer = null;

export function stopStream() {
  if (activePlayer?.close) {
    try { activePlayer.close(); } catch { /* player already closed */ }
  }
  activePlayer = null;
}

function youtubeId(value) {
  if (!value) return '';
  try {
    const url = new URL(value, window.location.origin);
    if (url.hostname.includes('youtu.be')) return url.pathname.slice(1).split('/')[0];
    if (url.hostname.includes('youtube.com')) return url.searchParams.get('v') || url.pathname.split('/').filter(Boolean).pop() || '';
  } catch { return ''; }
  return '';
}

export async function mountStream(container, stream = {}) {
  stopStream();
  if (!container || !stream.url) return { status: 'offline' };
  const url = safeHttpUrl(stream.url);
  if (!url) return { status: 'invalid' };
  const type = String(stream.type || '').toLowerCase();
  const ytId = type === 'youtube' ? youtubeId(url) : '';

  if (ytId) {
    const frame = document.createElement('iframe');
    frame.src = `https://www.youtube.com/embed/${encodeURIComponent(ytId)}?autoplay=${stream.autoplay ? '1' : '0'}&mute=${stream.autoplay ? '1' : '0'}&playsinline=1&rel=0`;
    frame.title = 'Live cockfight stream';
    frame.allow = 'autoplay; encrypted-media; picture-in-picture';
    frame.allowFullscreen = true;
    container.replaceChildren(frame);
    return { status: 'playing', type: 'youtube' };
  }

  if (type === 'iframe') {
    const frame = document.createElement('iframe');
    frame.src = url;
    frame.title = 'Live cockfight stream';
    frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'no-referrer';
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    container.replaceChildren(frame);
    return { status: 'playing', type: 'iframe' };
  }

  if (type === 'whep' && window.SrsRtcWhipWhepAsync) {
    const video = document.createElement('video');
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.controls = true;
    container.replaceChildren(video);
    const fallback = safeHttpUrl(stream.fallbackUrl || '');
    const controller = {
      player: null,
      timer: null,
      closed: false,
      close() {
        this.closed = true;
        if (this.timer) clearTimeout(this.timer);
        try { this.player?.close?.(); } catch { /* already disconnected */ }
        this.player = null;
      },
    };
    activePlayer = controller;

    const useFallback = () => {
      if (!fallback || !video.canPlayType('application/vnd.apple.mpegurl')) return false;
      video.srcObject = null;
      video.src = fallback;
      video.play().catch(() => {});
      return true;
    };

    const connect = async (attempt = 0) => {
      if (controller.closed || activePlayer !== controller) return false;
      try { controller.player?.close?.(); } catch { /* replacing stale peer */ }
      controller.player = new window.SrsRtcWhipWhepAsync();
      video.srcObject = controller.player.stream;
      await controller.player.play(url);
      const peer = controller.player.pc;
      peer?.addEventListener?.('connectionstatechange', () => {
        if (!['failed', 'disconnected'].includes(peer.connectionState) || controller.closed) return;
        if (controller.timer) clearTimeout(controller.timer);
        controller.timer = setTimeout(() => connect(Math.min(attempt + 1, 5)), Math.min(10000, 750 * (2 ** attempt)));
      });
      return true;
    };
    try {
      await connect();
      return { status: 'playing', type: 'whep' };
    } catch {
      if (useFallback()) {
        return { status: 'fallback', type: 'hls' };
      }
      controller.timer = setTimeout(() => connect(1), 1000);
      return { status: 'recovering', type: 'whep' };
    }
  }

  const video = document.createElement('video');
  video.src = url;
  video.playsInline = true;
  video.controls = true;
  video.preload = 'metadata';
  if (type === 'live' || type === 'hls' || stream.autoplay) {
    video.autoplay = true;
    video.muted = true;
  }
  if (stream.asLive && stream.startedAt) {
    video.addEventListener('loadedmetadata',()=>{
      const startedAt=new Date(stream.startedAt).getTime();
      const elapsed=Math.max(0,(Date.now()-startedAt)/1000);
      if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=Math.min(elapsed,Math.max(0,video.duration-.25));
      video.play().catch(()=>{});
    },{once:true});
  }
  container.replaceChildren(video);
  return { status: 'playing', type: type || 'video' };
}

export function normalizeStream(match = {}) {
  const youtube = match.youtubeLiveLink || match.youtube_live_link || '';
  if (youtube) return { type: 'youtube', url: youtube };
  const playback = match.playbackUrl || match.playback_url || match.hlsUrl || match.hls_url || '';
  if (playback) return { type: playback.includes('.m3u8') ? 'hls' : 'video', url: playback };
  const key = match.webrtcStreamKey || match.webrtc_stream_key || '';
  if (key) {
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return { type: 'whep', url: `${protocol}//${window.location.host}/rtc/v1/whep/?app=live&stream=${encodeURIComponent(key)}` };
  }
  return { type: 'offline', url: '' };
}
