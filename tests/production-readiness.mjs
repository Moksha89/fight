import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { createServer as createHttpServer } from 'node:http';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}

const port=await freePort();
const mediaPort=await freePort();
const mediaServer=createHttpServer((_request,response)=>{response.writeHead(200,{'Content-Type':'application/json'});response.end('{"code":0}');});
await new Promise(resolveListen=>mediaServer.listen(mediaPort,'127.0.0.1',resolveListen));
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-production-'));
process.env.ROOSTERRUN_REQUIRE_POSTGRES='0';
process.env.ROOSTERRUN_REQUIRE_DATABASE_TLS='0';
process.env.ROOSTERRUN_REQUIRE_OFFSITE_BACKUP='0';
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir],{stdio:['ignore','pipe','pipe'],env:{...process.env,ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME:'owner',ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD:'ProductionOwner123',ROOSTERRUN_SMS_WEBHOOK_URL:'https://sms.vendor.com/otp',ROOSTERRUN_ALERT_WEBHOOK_URL:'https://alerts.vendor.com/roosterrun',ROOSTERRUN_SECURE_COOKIES:'1',ROOSTERRUN_REQUIRE_STREAMING:'1',ROOSTERRUN_REQUIRE_RECORDING:'1',ROOSTERRUN_REQUIRE_MEDIA_HEALTH:'1',ROOSTERRUN_SRS_API_URL:`http://127.0.0.1:${mediaPort}/api/v1/versions`,ROOSTERRUN_WHIP_BASE_URL:'https://stream.vendor.com',ROOSTERRUN_WHEP_BASE_URL:'https://stream.vendor.com',ROOSTERRUN_HLS_BASE_URL:'https://stream.vendor.com/media',ROOSTERRUN_RECORDING_BASE_URL:'https://stream.vendor.com/media/recordings',ROOSTERRUN_SRS_HOOK_SECRET:'production-stream-hook-secret-32-characters',ROOSTERRUN_SECRET_GENERATION:'1',ROOSTERRUN_SECRET_ROTATED_AT:new Date().toISOString()}});
const base=`http://127.0.0.1:${port}`;

try{
  let response;
  for(let attempt=0;attempt<80;attempt+=1){try{response=await fetch(`${base}/health/ready/`);break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}
  assert.ok(response,'production server did not start');
  assert.equal(response.status,200);
  const readiness=await response.json();
  assert.equal(readiness.status,'ready');
  assert.equal(readiness.mode,'production');
  assert.ok(Object.values(readiness.checks).every(check=>check.ok));
  assert.match(response.headers.get('strict-transport-security')||'',/max-age=31536000/);
  assert.equal(response.headers.get('server'),'RoosterRun ');
  const page=await fetch(`${base}/play/`);
  assert.equal(page.status,200);
  assert.match(page.headers.get('content-security-policy')||'',/frame-ancestors 'none'/);
  console.log('Production readiness gates, headers, and runtime checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));await new Promise(resolveClose=>mediaServer.close(resolveClose));rmSync(dataDir,{recursive:true,force:true});
}
