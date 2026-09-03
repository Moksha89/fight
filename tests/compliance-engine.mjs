import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-compliance-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/admin/health/',{admin:true});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'compliance server did not start');
  await json(base,'/api/admin/compliance/',{expected:401});
  const health=await json(base,'/api/admin/health/',{admin:true});assert.equal(health.compliance.operating_mode,'SOCIAL_PREVIEW');assert.equal(health.compliance.private_storage,true);
  const policy=await json(base,'/api/admin/compliance/policy/',{admin:true});assert.equal(policy.kyc_required_for_betting,false);assert.equal(policy.minimum_age,18);
  const profile=await json(base,'/api/user/compliance/');assert.equal(profile.status,'VERIFIED');

  await json(base,'/api/admin/compliance/users/arena-guest/decision/',{method:'POST',admin:true,body:{decision:'REJECTED',note:'Fresh document required'}});
  await json(base,'/api/user/compliance/submit/',{method:'POST',expected:400,body:{legal_name:'Arena Guest',date_of_birth:'2012-01-01',state_code:'KA',consent_identity:true,consent_privacy:true,documents:[{document_type:'PAN',data_url:png}]}});
  await json(base,'/api/user/compliance/submit/',{method:'POST',expected:400,body:{legal_name:'Arena Guest',date_of_birth:'1990-01-01',state_code:'KA',consent_identity:true,consent_privacy:true,documents:[{document_type:'AADHAAR',data_url:png}]}});
  const submitted=await json(base,'/api/user/compliance/submit/',{method:'POST',body:{legal_name:'Arena Guest',date_of_birth:'1990-01-01',state_code:'KA',consent_identity:true,consent_privacy:true,documents:[{document_type:'PAN',data_url:png}]}});assert.equal(submitted.status,'PENDING');assert.equal(submitted.documents.length,1);assert.equal('private_filename' in submitted.documents[0],false);
  const privateFile=await fetch(`${base}/api/admin/compliance/documents/${submitted.documents[0].id}/`);assert.equal(privateFile.status,200);assert.equal(privateFile.headers.get('cache-control'),'no-store, private');assert.equal(privateFile.headers.get('content-type'),'image/png');
  const traversal=await fetch(`${base}/uploads/../private/identity/not-public.png`);assert.equal(traversal.status,404);
  const verified=await json(base,'/api/admin/compliance/users/arena-guest/decision/',{method:'POST',admin:true,body:{decision:'VERIFIED',note:'Document and age verified'}});assert.equal(verified.status,'VERIFIED');

  let controls=await json(base,'/api/user/responsible-play/');assert.equal(controls.daily_deposit_limit,0);
  controls=await json(base,'/api/user/responsible-play/limits/',{method:'POST',body:{daily_deposit_limit:100,daily_stake_limit:200,session_limit_minutes:60}});assert.equal(controls.daily_deposit_limit,100);assert.equal(controls.daily_stake_limit,200);
  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Compliance UPI',account_type:'UPI',account_holder:'RoosterRun Test',upi_id:'safe@upi'}});
  await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:{amount:100,account_id:account.id,utr:'SAFEUTR0001',proof_data_url:png}});
  await json(base,'/api/payments/deposits/',{method:'POST',expected:403,body:{amount:100,account_id:account.id,utr:'SAFEUTR0002',proof_data_url:png}});

  const games=await json(base,'/api/admin/games/',{admin:true});const game=games.results[0];
  await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:403,body:{matchId:game.id,betTeam:1,amount:250}});
  const quote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,body:{matchId:game.id,betTeam:1,amount:200}});assert.equal(quote.stake,200);
  await json(base,'/api/user/responsible-play/restrict/',{method:'POST',body:{kind:'SELF_EXCLUDE',duration_days:180}});
  await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:403,body:{matchId:game.id,betTeam:1,amount:10}});
  await json(base,'/api/payments/deposits/',{method:'POST',expected:403,body:{amount:100,account_id:account.id,utr:'SAFEUTR0003',proof_data_url:png}});
  const withdrawal=await json(base,'/api/payments/withdrawals/',{method:'POST',expected:201,body:{amount:500,method:'UPI',account_holder:'Arena Guest',upi_id:'guest@upi'}});assert.equal(withdrawal.status,'PENDING','withdrawals must remain available during self-exclusion');

  const queue=await json(base,'/api/admin/compliance/',{admin:true});assert.ok(queue.results.some(item=>item.user_id==='arena-guest'&&item.status==='VERIFIED'));
  const audit=await json(base,'/api/admin/audit/',{admin:true});assert.ok(audit.results.some(item=>item.module==='Compliance'));
  console.log('Identity review, private documents, limits, legal mode, and self-exclusion checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
