import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-intelligence-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/admin/health/',{admin:true});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'intelligence server did not start');
  await json(base,'/api/admin/intelligence/overview/',{expected:401});
  await json(base,'/api/admin/intelligence/policy/',{method:'POST',admin:true,expected:400,body:{large_withdrawal_rupees:20}});
  const policy=await json(base,'/api/admin/intelligence/policy/',{method:'POST',admin:true,body:{large_withdrawal_rupees:500,rapid_cashout_minutes:120,rapid_cashout_percent:75,rejected_payments_24h:3,rejected_risk_checks_15m:3,betting_velocity_5m:6,betting_velocity_stake_rupees:20000,shared_beneficiary_users:2}});assert.equal(policy.large_withdrawal_rupees,500);

  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Intelligence UPI',account_type:'UPI',account_holder:'RoosterRun Test',upi_id:'intelligence@upi'}});
  const deposit=await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:{amount:2000,account_id:account.id,utr:'INTELUTR0001',proof_data_url:png}});
  await json(base,`/api/payments/admin/requests/${deposit.id}/decision/`,{method:'POST',admin:true,body:{decision:'APPROVED',admin_note:'Verified for intelligence test'}});
  const withdrawal=await json(base,'/api/payments/withdrawals/',{method:'POST',expected:201,body:{amount:1500,method:'UPI',account_holder:'Arena Guest',upi_id:'arena@upi'}});

  const first=await json(base,'/api/admin/intelligence/scan/',{method:'POST',admin:true,expected:201,body:{}});assert.equal(first.status,'COMPLETED');assert.ok(first.alert_count>=2);assert.ok(first.new_alert_count>=2);
  const second=await json(base,'/api/admin/intelligence/scan/',{method:'POST',admin:true,expected:201,body:{}});assert.equal(second.new_alert_count,0,'scans must be idempotent for the same evidence');

  let queue=await json(base,'/api/admin/intelligence/alerts/',{admin:true});assert.ok(queue.summary.high_risk>=2);assert.ok(queue.results.some(alert=>alert.alert_type==='LARGE_WITHDRAWAL'&&alert.linked_reference===withdrawal.reference));assert.ok(queue.results.some(alert=>alert.alert_type==='RAPID_CASH_OUT'));
  const alert=queue.results[0];
  let updated=await json(base,`/api/admin/intelligence/alerts/${alert.id}/`,{method:'POST',admin:true,body:{status:'REVIEWING',assigned_admin:'Risk Analyst',resolution_note:''}});assert.equal(updated.status,'REVIEWING');assert.equal(updated.assigned_admin,'Risk Analyst');
  await json(base,`/api/admin/intelligence/alerts/${alert.id}/`,{method:'POST',admin:true,expected:400,body:{status:'CLEARED',assigned_admin:'Risk Analyst',resolution_note:''}});
  updated=await json(base,`/api/admin/intelligence/alerts/${alert.id}/`,{method:'POST',admin:true,body:{status:'CLEARED',assigned_admin:'Risk Analyst',resolution_note:'Payment ownership and source evidence were reviewed and accepted.'}});assert.equal(updated.status,'CLEARED');assert.ok(updated.reviewed_at);

  const overview=await json(base,'/api/admin/intelligence/overview/',{admin:true});assert.equal(overview.funds.users,1);assert.equal(overview.payments.DEPOSIT.APPROVED.count,1);assert.equal(overview.payments.WITHDRAWAL.PENDING.count,1);assert.equal(overview.daily.length,14);assert.equal(overview.latest_scan.reference,second.reference);
  const denied=await fetch(`${base}/api/admin/intelligence/export/`);assert.equal(denied.status,401);
  const exported=await fetch(`${base}/api/admin/intelligence/export/`,{headers:{'X-Preview-Admin':'1'}});assert.equal(exported.status,200);assert.match(exported.headers.get('content-type'),/text\/csv/);assert.match(exported.headers.get('content-disposition'),/^attachment/);const csv=await exported.text();assert.match(csv,/RoosterRun financial intelligence export/);assert.match(csv,/LARGE_WITHDRAWAL/);

  const audit=await json(base,'/api/admin/audit/',{admin:true});assert.ok(audit.results.some(row=>row.module==='Intelligence'&&row.action==='Detection scan completed'));assert.ok(audit.results.some(row=>row.module==='Intelligence'&&row.action==='Alert reviewed'));
  const config=await json(base,'/api/admin/config/',{admin:true});assert.ok(config.roles.some(role=>role.name==='Risk Analyst'&&role.permissions.includes('intelligence')));
  const health=await json(base,'/api/admin/health/',{admin:true});assert.equal(health.intelligence.status,'ok');assert.ok(health.intelligence.alerts>=2);
  console.log('Financial reporting, policy, idempotent detection, human review, protected export, RBAC, audit, and health checks passed.');
}finally{child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});}
