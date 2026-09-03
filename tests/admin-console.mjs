import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
const futureIso=(minutes)=>new Date(Date.now()+minutes*60_000).toISOString().replace(/\.\d{3}Z$/,'Z');

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=true,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}
async function upload(base,body,{contentType,kind,admin=true,expected=201}){const response=await fetch(`${base}/api/admin/assets/upload/`,{method:'POST',headers:{'Content-Type':contentType,'X-Asset-Kind':kind,...(admin?{'X-Preview-Admin':'1'}:{})},body});const data=await response.json();assert.equal(response.status,expected,`upload ${kind}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-admin-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;

try{
  let ready=false;
  for(let attempt=0;attempt<50;attempt+=1){try{await json(base,'/api/admin/health/');ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}
  assert.equal(ready,true,'admin server did not start');
  await json(base,'/api/admin/overview/',{admin:false,expected:401});
  const page=await fetch(`${base}/admin/`);assert.equal(page.status,200);assert.match(await page.text(),/RoosterRun Admin/);

  const overview=await json(base,'/api/admin/overview/');assert.equal(overview.users,1);assert.equal(overview.active_games,1);
  const png=Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,0,0,0,0]);
  await upload(base,png,{contentType:'image/png',kind:'IMAGE',admin:false,expected:401});
  const imageAsset=await upload(base,png,{contentType:'image/png',kind:'IMAGE'});assert.match(imageAsset.url,/^\/uploads\/admin-image-/);
  const mp4=Buffer.from([0,0,0,24,0x66,0x74,0x79,0x70,0x69,0x73,0x6f,0x6d,0,0,0,0]);
  const videoAsset=await upload(base,mp4,{contentType:'video/mp4',kind:'VIDEO'});assert.match(videoAsset.url,/^\/uploads\/admin-video-/);
  const range=await fetch(`${base}${videoAsset.url}`,{headers:{Range:'bytes=4-7'}});assert.equal(range.status,206);assert.equal(range.headers.get('content-range'),`bytes 4-7/${mp4.length}`);assert.deepEqual(Buffer.from(await range.arrayBuffer()),mp4.subarray(4,8));
  const games=await json(base,'/api/admin/games/');assert.equal(games.results.length,1);
  const game=await json(base,'/api/admin/games/',{method:'POST',expected:201,body:{title:'Test Arena · Match 2',arena:'Test Arena',status:'SCHEDULED',betting_opens_at:futureIso(60),scheduled_at:futureIso(120),betting_closes_at:futureIso(119),team_a_name:'Ruby',team_a_odds:2.1,draw_odds:7.5,team_b_name:'Azure',team_b_odds:2.2,thumbnail_url:imageAsset.url,stream_type:'VIDEO',stream_url:videoAsset.url,featured:true}});assert.equal(game.status,'SCHEDULED');assert.equal(game.thumbnail_url,imageAsset.url);assert.equal(game.stream_url,videoAsset.url);
  await json(base,`/api/admin/games/${game.id}/transition/`,{method:'POST',body:{status:'BETTING_OPEN',reason:'Test open'}});
  await json(base,`/api/admin/games/${game.id}/transition/`,{method:'POST',body:{status:'BETTING_CLOSED',reason:'Test close'}});
  const live=await json(base,`/api/admin/games/${game.id}/transition/`,{method:'POST',body:{status:'LIVE',reason:'Test live'}});assert.equal(live.status,'LIVE');

  const banner=await json(base,'/api/admin/banners/',{method:'POST',expected:201,body:{title:'Weekend live arena',subtitle:'Watch the featured match',placement:'HOME_HERO',image_url:imageAsset.url,cta_label:'Watch live',cta_route:'#live',sort_order:1,active:true}});assert.equal(banner.active,true);assert.equal(banner.image_url,imageAsset.url);
  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',expected:201,body:{label:'Linked QR UPI',account_type:'UPI',account_holder:'Rooster Test',upi_id:'rooster@test',qr_url:imageAsset.url}});assert.equal(account.qr_url,imageAsset.url);
  const tier=await json(base,'/api/admin/vip/',{method:'POST',expected:201,body:{name:'Test Elite',minimum_turnover:100000,cashback_percent:2.5,withdrawal_priority:4,color:'#55CCFF',active:true}});assert.equal(tier.name,'Test Elite');
  const user=await json(base,'/api/admin/users/arena-guest/',{method:'POST',body:{status:'SUSPENDED',vip_tier:'Test Elite'}});assert.equal(user.status,'SUSPENDED');assert.equal(user.vip_tier,'Test Elite');

  const config=await json(base,'/api/admin/config/');config.theme.primary='#CC9900';await json(base,'/api/admin/config/',{method:'POST',body:{theme:config.theme,brand:{...config.brand,site_name:'Rooster Test'}}});
  await json(base,'/api/admin/social/',{method:'POST',body:{links:[{platform:'YouTube',url:'https://youtube.com/@roostertest',active:true}]}});
  const publicConfig=await json(base,'/api/site/config/',{admin:false});assert.equal(publicConfig.brand.site_name,'Rooster Test');assert.equal(publicConfig.theme.primary,'#CC9900');assert.equal(publicConfig.banners.length,1);assert.equal(publicConfig.social.length,1);assert.equal(publicConfig.featured_game.id,game.id);assert.equal(publicConfig.featured_game.thumbnail_url,imageAsset.url);
  const audit=await json(base,'/api/admin/audit/');assert.ok(audit.results.length>=6,'admin actions should be audited');
  console.log('Unified admin console workflow checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
