import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-operations-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/admin/health/',{admin:true});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'operations server did not start');
  await json(base,'/api/admin/operations/overview/',{expected:401});
  let operations=await json(base,'/api/admin/operations/overview/',{admin:true});assert.equal(operations.database.integrity,'ok');assert.equal(operations.open_incidents,0);assert.equal(operations.external_delivery.in_app,'ACTIVE');

  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Operations UPI',account_type:'UPI',account_holder:'RoosterRun Test',upi_id:'operations@upi'}});
  const deposit=await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:{amount:100,account_id:account.id,utr:'OPSUTR000001',proof_data_url:png}});
  let notifications=await json(base,'/api/user/notifications/');assert.equal(notifications.unread,1);assert.equal(notifications.results[0].event_type,'DEPOSIT_SUBMITTED');assert.equal(notifications.results[0].delivery_status,'DELIVERED');
  const marked=await json(base,`/api/user/notifications/${notifications.results[0].id}/read/`,{method:'POST',body:{}});assert.equal(marked.read,true);
  await json(base,`/api/payments/admin/requests/${deposit.id}/decision/`,{method:'POST',admin:true,body:{decision:'APPROVED',admin_note:'UTR and proof verified'}});
  notifications=await json(base,'/api/user/notifications/');assert.equal(notifications.unread,1);assert.equal(notifications.results[0].event_type,'DEPOSIT_APPROVED');
  const readAll=await json(base,'/api/user/notifications/read-all/',{method:'POST',body:{}});assert.equal(readAll.updated,1);
  notifications=await json(base,'/api/user/notifications/');assert.equal(notifications.unread,0);

  const reconciliation=await json(base,'/api/admin/operations/reconciliation/run/',{method:'POST',admin:true,expected:201,body:{}});assert.equal(reconciliation.status,'PASS');assert.equal(reconciliation.findings.length,0);assert.equal(reconciliation.check_count,7);
  const backup=await json(base,'/api/admin/operations/backups/create/',{method:'POST',admin:true,expected:201,body:{}});assert.equal(backup.status,'COMPLETED');assert.equal(backup.sha256.length,64);assert.equal(backup.contents.database_integrity,'ok');assert.equal(backup.contents.restore_exposed_in_ui,false);
  const denied=await fetch(`${base}${backup.download_url}`);assert.equal(denied.status,200,'loopback preview permits direct protected downloads for interface testing');
  assert.equal(denied.headers.get('cache-control'),'no-store, private');assert.match(denied.headers.get('content-disposition'),/^attachment/);const archive=Buffer.from(await denied.arrayBuffer());assert.equal(createHash('sha256').update(archive).digest('hex'),backup.sha256);assert.deepEqual([...archive.subarray(0,2)],[0x1f,0x8b]);
  const privatePath=await fetch(`${base}/private/backups/anything.tar.gz`);assert.equal(privatePath.status,404);

  operations=await json(base,'/api/admin/operations/overview/',{admin:true});assert.equal(operations.latest_reconciliation.reference,reconciliation.reference);assert.equal(operations.backups[0].reference,backup.reference);assert.ok(operations.notifications.some(item=>item.event_type==='BACKUP_COMPLETED'));assert.ok(operations.notifications.some(item=>item.event_type==='PAYMENT_REVIEW_REQUIRED'));
  await json(base,'/api/admin/operations/incidents/999999/',{method:'POST',admin:true,expected:404,body:{status:'ACKNOWLEDGED',note:''}});
  console.log('Durable notifications, reconciliation, private backups, and operations access checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
