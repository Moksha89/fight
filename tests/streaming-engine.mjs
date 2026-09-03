import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,token='',expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{}),...(token?{Authorization:`Bearer ${token}`}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-streaming-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe'],env:{...process.env,ROOSTERRUN_WHIP_BASE_URL:'http://127.0.0.1:1985',ROOSTERRUN_WHEP_BASE_URL:'http://127.0.0.1:1985',ROOSTERRUN_HLS_BASE_URL:'http://127.0.0.1:8080',ROOSTERRUN_RECORDING_BASE_URL:'http://127.0.0.1:8080/recordings',ROOSTERRUN_SRS_HOOK_SECRET:'stream-test-hook-secret-32-characters'}});
const base=`http://127.0.0.1:${port}`;

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/cockfight/stream/health/');ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'streaming server did not start');
  const health=await json(base,'/api/cockfight/stream/health/');assert.equal(health.status,'ok');assert.equal(health.media_plane_configured,true);assert.equal(health.monitor_running,true);
  await json(base,'/api/admin/streams/',{expected:401});
  const games=await json(base,'/api/admin/games/',{admin:true});const game=games.results[0];
  const created=await json(base,`/api/admin/games/${game.id}/broadcast/session/`,{method:'POST',body:{source_type:'MOBILE',client_label:'Test phone',recording_enabled:true},admin:true,expected:201});
  assert.equal(created.status,'CREATED');assert.equal(created.source_type,'MOBILE');assert.ok(created.publisher_token.length>30);assert.equal(created.pairing_code.length,12);assert.ok(created.playback_url.includes('/rtc/v1/whep/'));assert.equal('stream_key' in created,false);
  await json(base,'/api/cockfight/broadcast/pair/',{method:'POST',body:{session_id:created.id,pairing_code:'WRONGCODE000'},expected:400});
  const paired=await json(base,'/api/cockfight/broadcast/pair/',{method:'POST',body:{session_id:created.id,pairing_code:created.pairing_code}});assert.equal(paired.session_id,created.id);assert.ok(paired.publisher_token);
  await json(base,`/api/cockfight/broadcast/sessions/${created.id}/ticket/`,{method:'POST',body:{transport:'whip'},token:created.publisher_token,expected:403});
  const ticket=await json(base,`/api/cockfight/broadcast/sessions/${created.id}/ticket/`,{method:'POST',body:{transport:'whip'},token:paired.publisher_token});assert.ok(ticket.whip_url.includes('/rtc/v1/whip/'));assert.ok(ticket.whip_url.includes('ticket='));assert.equal(ticket.session.status,'READY');
  const publishUrl=new URL(ticket.whip_url);const hookDenied=await json(base,'/api/cockfight/broadcast/hooks/srs/publish/?secret=wrong',{method:'POST',body:{stream:publishUrl.searchParams.get('stream'),param:publishUrl.search}});assert.equal(hookDenied.code,403);
  const hookAuthorized=await json(base,'/api/cockfight/broadcast/hooks/srs/publish/?secret=stream-test-hook-secret-32-characters',{method:'POST',body:{stream:publishUrl.searchParams.get('stream'),param:publishUrl.search}});assert.equal(hookAuthorized.code,0);
  const hookReplay=await json(base,'/api/cockfight/broadcast/hooks/srs/publish/?secret=stream-test-hook-secret-32-characters',{method:'POST',body:{stream:publishUrl.searchParams.get('stream'),param:publishUrl.search}});assert.equal(hookReplay.code,403,'media-plane ticket must be one-use');
  const live=await json(base,`/api/cockfight/broadcast/sessions/${created.id}/heartbeat/`,{method:'POST',token:paired.publisher_token,body:{connection_state:'connected',bitrate_kbps:2450,fps:30,width:1280,height:720,rtt_ms:62,packet_loss_percent:.5,network_type:'4g'}});assert.equal(live.status,'LIVE');assert.equal(live.health.bitrate_kbps,2450);assert.equal(live.health.width,1280);
  const current=await json(base,`/api/cockfight/stream/current/?game_id=${game.id}`);assert.equal(current.status,'LIVE');assert.equal('id' in current,false);assert.equal('client_label' in current,false);assert.ok(current.hls_url.endsWith('.m3u8'));
  const recording=await json(base,'/api/cockfight/broadcast/hooks/srs/recording/?secret=stream-test-hook-secret-32-characters',{method:'POST',body:{stream:publishUrl.searchParams.get('stream'),file:`/usr/local/srs/objs/nginx/html/recordings/live/${publishUrl.searchParams.get('stream')}.123.flv`}});assert.equal(recording.code,0);assert.ok(recording.recording_url.endsWith('.123.flv'));
  const site=await json(base,'/api/site/config/');assert.equal(site.stream.game_id,game.id);assert.equal(site.featured_game.stream_type,'WHEP');
  const sessions=await json(base,'/api/admin/streams/',{admin:true});assert.equal(sessions.results[0].id,created.id);assert.equal('publisher_token' in sessions.results[0],false);assert.equal('pairing_code' in sessions.results[0],false);
  const stopped=await json(base,`/api/cockfight/broadcast/sessions/${created.id}/stop/`,{method:'POST',token:paired.publisher_token,body:{reason:'Test complete'}});assert.equal(stopped.status,'STOPPED');
  const stoppedAgain=await json(base,`/api/admin/streams/${created.id}/stop/`,{method:'POST',admin:true,body:{reason:'Idempotent stop'}});assert.equal(stoppedAgain.status,'STOPPED');
  const offline=await json(base,`/api/cockfight/stream/current/?game_id=${game.id}`);assert.equal(offline.status,'OFFLINE');

  const preparing=await json(base,`/api/admin/games/${game.id}/broadcast/session/`,{method:'POST',body:{source_type:'CAMERA',recording_enabled:false},admin:true,expected:201});
  const rotated=await json(base,`/api/admin/streams/${preparing.id}/credentials/`,{method:'POST',body:{},admin:true});assert.notEqual(rotated.publisher_token,preparing.publisher_token);assert.notEqual(rotated.pairing_code,preparing.pairing_code);
  await json(base,`/api/cockfight/broadcast/sessions/${preparing.id}/ticket/`,{method:'POST',body:{},token:preparing.publisher_token,expected:403});
  await json(base,`/api/cockfight/broadcast/sessions/${preparing.id}/ticket/`,{method:'POST',body:{},token:rotated.publisher_token});
  const degraded=await json(base,`/api/cockfight/broadcast/sessions/${preparing.id}/heartbeat/`,{method:'POST',token:rotated.publisher_token,body:{connection_state:'disconnected',bitrate_kbps:300,rtt_ms:1500,packet_loss_percent:12}});assert.equal(degraded.status,'DEGRADED');
  await json(base,`/api/admin/streams/${preparing.id}/stop/`,{method:'POST',body:{reason:'Admin stop'},admin:true});

  const broadcastHtml=await (await fetch(`${base}/broadcast/`)).text();assert.match(broadcastHtml,/Pair this device/);assert.match(broadcastHtml,/broadcast\.js\?v=2/);
  const broadcastJs=await (await fetch(`${base}/broadcast/broadcast.js?v=2`)).text();assert.match(broadcastJs,/heartbeat/);assert.match(broadcastJs,/getStats/);assert.doesNotMatch(broadcastJs,/localStorage/);
  const finalHealth=await json(base,'/api/admin/streams/health/',{admin:true});assert.equal(finalHealth.live,0);assert.equal(finalHealth.degraded,0);assert.ok(finalHealth.sessions>=2);
  console.log('Streaming ingest, recovery routing, DVR recording, and mobile pairing checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
