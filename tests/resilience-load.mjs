import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
function launch(port,dataDir){return spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:'ignore',env:{...process.env,ROOSTERRUN_INTERNAL_ALERT_TOKEN:'resilience-monitor-token'}});}
async function waitReady(base){for(let attempt=0;attempt<100;attempt+=1){try{const response=await fetch(`${base}/health/ready/`);if(response.ok)return;}catch{}await new Promise(resolveWait=>setTimeout(resolveWait,100));}throw new Error('Server did not become ready.');}
async function api(base,path,{method='GET',body,admin=false,token='',expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{}),...(token?{Authorization:`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}
async function stop(child,signal='SIGTERM'){if(child.exitCode!==null)return;child.kill(signal);await new Promise(resolveWait=>{const timer=setTimeout(resolveWait,5000);child.once('exit',()=>{clearTimeout(timer);resolveWait();});});}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-resilience-'));
const base=`http://127.0.0.1:${port}`;
let child=launch(port,dataDir);

try{
  await waitReady(base);
  const timings=[];
  await Promise.all(Array.from({length:50},async()=>{for(let request=0;request<6;request+=1){const started=performance.now();const response=await fetch(`${base}/api/site/config/`);assert.equal(response.status,200);await response.arrayBuffer();timings.push(performance.now()-started);}}));
  timings.sort((a,b)=>a-b);const p95=timings[Math.floor(timings.length*.95)];assert.ok(p95<5000,`load smoke p95 was ${p95.toFixed(0)}ms`);

  const games=await api(base,'/api/admin/games/',{admin:true});const game=games.results[0];
  const quotes=await Promise.all(Array.from({length:5},()=>api(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,body:{matchId:game.id,betTeam:1,amount:10}})));
  const tickets=await Promise.all(quotes.map(quote=>api(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:201,body:{quote_id:quote.quote_id}})));
  assert.equal(new Set(tickets.map(ticket=>ticket.id)).size,5,'concurrent accepted bets must remain distinct');

  await api(base,'/api/internal/monitoring/alerts/',{method:'POST',body:{alerts:[]},expected:403});
  const accepted=await api(base,'/api/internal/monitoring/alerts/',{method:'POST',token:'resilience-monitor-token',expected:202,body:{alerts:[{status:'firing',fingerprint:'resilience-test',labels:{alertname:'ResilienceTest',severity:'warning'},annotations:{summary:'Test monitoring route',description:'Synthetic alert'}}]}});assert.equal(accepted.accepted,1);
  const metrics=await (await fetch(`${base}/metrics/`)).text();assert.match(metrics,/roosterrun_http_requests_total/);assert.match(metrics,/roosterrun_delivery_queued/);

  await stop(child,'SIGKILL');
  child=launch(port,dataDir);await waitReady(base);
  const recovered=await api(base,'/api/cockfight/bets/');assert.equal(recovered.results.length,5,'accepted bets must survive abrupt process restart');
  const readiness=await api(base,'/health/ready/');assert.equal(readiness.checks.background_workers.ok,true);
  console.log(`Load (300 requests, p95 ${p95.toFixed(0)}ms), concurrency, monitoring auth, and crash-recovery checks passed.`);
}finally{
  await stop(child);
  rmSync(dataDir,{recursive:true,force:true});
}
