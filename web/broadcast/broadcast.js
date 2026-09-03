(function(){
  'use strict';
  const preview=document.getElementById('preview');
  const camera=document.getElementById('camera');
  const pairForm=document.getElementById('pair-form');
  const controls=document.getElementById('controls');
  let sessionId=new URLSearchParams(location.search).get('session')||'';
  let publisherToken=sessionId?sessionStorage.getItem(`roosterrun_broadcast_${sessionId}`)||'':'';
  let publisher=null,localStream=null,startedAt=0,timer=null,heartbeatTimer=null,lastBytes=0,lastStatsAt=0,lastFrames=0;

  document.getElementById('session-id').value=sessionId;

  function setStatus(text,state=''){
    const element=document.getElementById('status');
    element.className=`status ${state}`;
    document.getElementById('status-text').textContent=text;
  }

  function authorize(id,token){
    sessionId=id;publisherToken=token;
    sessionStorage.setItem(`roosterrun_broadcast_${sessionId}`,publisherToken);
    history.replaceState(null,'',`?session=${encodeURIComponent(sessionId)}`);
    document.getElementById('session-id').value=sessionId;
    pairForm.hidden=true;controls.hidden=false;
    document.getElementById('session-label').textContent='Session authorized. Preview the arena camera before going live.';
    setStatus('Session authorized','ready');
  }

  window.addEventListener('message',event=>{
    if(event.origin!==location.origin||event.data?.type!=='roosterrun-broadcast-token')return;
    authorize(String(event.data.sessionId||''),String(event.data.token||''));
    if(window.opener)window.opener.postMessage({type:'roosterrun-broadcast-token-received',sessionId},location.origin);
  });

  function constraints(){
    const height=Number(document.getElementById('quality').value);
    return {audio:document.getElementById('audio').value==='true',video:{deviceId:camera.value?{exact:camera.value}:undefined,facingMode:camera.value?undefined:{ideal:'environment'},height:{ideal:height},width:{ideal:Math.round(height*16/9)},frameRate:{ideal:30,max:30}}};
  }

  async function request(path,{method='POST',body,token=publisherToken}={}){
    const headers={'Content-Type':'application/json'};
    if(token)headers.Authorization=`Bearer ${token}`;
    const response=await fetch(path,{method,headers,body:JSON.stringify(body||{})});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail||'The streaming request failed.');
    return data;
  }

  async function pairDevice(event){
    event.preventDefault();
    const form=new FormData(pairForm);
    try{
      const result=await request('/api/cockfight/broadcast/pair/',{body:{session_id:String(form.get('session_id')||'').trim(),pairing_code:String(form.get('pairing_code')||'').trim()},token:''});
      authorize(result.session_id,result.publisher_token);
    }catch(error){document.getElementById('session-label').textContent=error.message;}
  }

  async function devices(){
    const list=await navigator.mediaDevices.enumerateDevices();
    const cameras=list.filter(device=>device.kind==='videoinput');
    camera.replaceChildren(new Option('Default camera',''),...cameras.map((device,index)=>new Option(device.label||`Camera ${index+1}`,device.deviceId)));
    document.getElementById('flip').disabled=cameras.length<2;
  }

  function stopLocal(){if(localStream)localStream.getTracks().forEach(track=>track.stop());localStream=null;preview.srcObject=null;}

  async function prepare(){
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera publishing requires HTTPS or localhost.');
      stopLocal();localStream=await navigator.mediaDevices.getUserMedia(constraints());preview.srcObject=localStream;
      document.getElementById('empty').style.display='none';
      const settings=localStream.getVideoTracks()[0]?.getSettings()||{};
      document.getElementById('resolution').textContent=`${settings.width||'?'}×${settings.height||'?'}`;
      document.getElementById('start').disabled=false;
      await devices();setStatus('Ready to broadcast','ready');
    }catch(error){setStatus(error.name==='NotAllowedError'?'Camera permission denied':error.message||'Camera unavailable','error');}
  }

  async function ticket(){return request(`/api/cockfight/broadcast/sessions/${encodeURIComponent(sessionId)}/ticket/`,{body:{transport:'whip'}});}

  async function start(){
    try{
      document.getElementById('start').disabled=true;setStatus('Authorizing secure publisher…');
      const authorization=await ticket();stopLocal();publisher=new SrsRtcWhipWhepAsync();publisher.constraints=constraints();preview.srcObject=publisher.stream;
      await publisher.publish(authorization.whip_url,{camera:true,screen:false,audio:constraints().audio,vcodec:'h264',acodec:'opus'});
      startedAt=Date.now();lastStatsAt=startedAt;lastBytes=0;lastFrames=0;
      document.getElementById('empty').style.display='none';document.getElementById('live').classList.add('on');document.getElementById('stop').disabled=false;
      setStatus('Broadcasting live','live-state');tick();timer=setInterval(tick,1000);await sendHeartbeat();heartbeatTimer=setInterval(sendHeartbeat,5000);
    }catch(error){publisher?.close?.();publisher=null;document.getElementById('start').disabled=false;setStatus(error.message||'Could not start stream','error');}
  }

  async function collectStats(){
    const metrics={connection_state:publisher?.pc?.connectionState||'connected',bitrate_kbps:0,fps:0,width:0,height:0,rtt_ms:0,packet_loss_percent:0,network_type:navigator.connection?.effectiveType||'online'};
    if(!publisher?.pc?.getStats)return metrics;
    const reports=await publisher.pc.getStats();let outbound=null,remoteInbound=null;
    reports.forEach(report=>{if(report.type==='outbound-rtp'&&report.kind==='video'&&!report.isRemote)outbound=report;if(report.type==='remote-inbound-rtp'&&report.kind==='video')remoteInbound=report;});
    const now=Date.now();
    if(outbound){
      const elapsed=Math.max(1,now-lastStatsAt);metrics.bitrate_kbps=Math.max(0,Math.round(((Number(outbound.bytesSent||0)-lastBytes)*8)/elapsed));
      metrics.fps=Number(outbound.framesPerSecond||0)||Math.max(0,Math.round(((Number(outbound.framesEncoded||0)-lastFrames)*1000)/elapsed));
      metrics.width=Number(outbound.frameWidth||0);metrics.height=Number(outbound.frameHeight||0);lastBytes=Number(outbound.bytesSent||0);lastFrames=Number(outbound.framesEncoded||0);lastStatsAt=now;
    }
    if(remoteInbound){const lost=Math.max(0,Number(remoteInbound.packetsLost||0));const received=Math.max(0,Number(remoteInbound.packetsReceived||0));metrics.rtt_ms=Math.round(Number(remoteInbound.roundTripTime||0)*1000);metrics.packet_loss_percent=received+lost?Math.round((lost/(received+lost))*10000)/100:0;}
    return metrics;
  }

  async function sendHeartbeat(){
    if(!publisher)return;
    try{const metrics=await collectStats();await request(`/api/cockfight/broadcast/sessions/${encodeURIComponent(sessionId)}/heartbeat/`,{body:metrics});document.getElementById('bitrate').textContent=metrics.bitrate_kbps?`${metrics.bitrate_kbps} kbps`:'Starting';document.getElementById('latency').textContent=metrics.rtt_ms?`${metrics.rtt_ms} ms`:'—';document.getElementById('network').textContent=metrics.network_type;}
    catch(error){setStatus(error.message||'Stream health update failed','error');}
  }

  function tick(){const seconds=Math.floor((Date.now()-startedAt)/1000);document.getElementById('duration').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;document.getElementById('network').textContent=navigator.connection?.effectiveType||'online';}

  async function stop(){
    if(publisher){try{publisher.close();}catch{}publisher=null;}
    if(timer)clearInterval(timer);if(heartbeatTimer)clearInterval(heartbeatTimer);timer=null;heartbeatTimer=null;stopLocal();
    document.getElementById('live').classList.remove('on');document.getElementById('stop').disabled=true;document.getElementById('start').disabled=true;document.getElementById('empty').style.display='grid';setStatus('Stream ended');
    try{await request(`/api/cockfight/broadcast/sessions/${encodeURIComponent(sessionId)}/stop/`,{body:{reason:'Publisher ended stream'}});}catch(error){setStatus(error.message||'Stream ended locally','error');}
  }

  pairForm.addEventListener('submit',pairDevice);document.getElementById('prepare').onclick=prepare;document.getElementById('start').onclick=start;document.getElementById('stop').onclick=stop;
  document.getElementById('flip').onclick=()=>{const options=[...camera.options].filter(option=>option.value);if(!options.length)return;const index=options.findIndex(option=>option.value===camera.value);camera.value=options[(index+1)%options.length].value;prepare();};
  camera.onchange=prepare;window.addEventListener('beforeunload',()=>{publisher?.close?.();stopLocal();});
  if(sessionId&&publisherToken)authorize(sessionId,publisherToken);else if(sessionId)document.getElementById('session-label').textContent='Enter the one-time code from the admin console to pair this device.';
})();
