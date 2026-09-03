import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-support-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/admin/health/',{admin:true});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'support server did not start');
  await json(base,'/api/admin/support/tickets/',{expected:401});

  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Support UPI',account_type:'UPI',account_holder:'RoosterRun Test',upi_id:'support@upi'}});
  const deposit=await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:{amount:250,account_id:account.id,utr:'SUPPORTUTR001',proof_data_url:png}});
  await json(base,'/api/user/support/tickets/',{method:'POST',expected:400,body:{category:'PAYMENT',subject:'Reference ownership check',message:'This reference should be rejected by the server.',payment_reference:'DEP-NOT-MINE'}});

  let ticket=await json(base,'/api/user/support/tickets/',{method:'POST',expected:201,body:{category:'PAYMENT',subject:'Deposit is waiting for verification',message:'Please check the screenshot and UTR attached to my deposit request.',payment_reference:deposit.reference}});
  assert.match(ticket.reference,/^SUP-\d{8}-[A-F0-9]{6}$/);assert.equal(ticket.status,'OPEN');assert.equal(ticket.priority,'NORMAL');assert.equal(ticket.linked_payment_reference,deposit.reference);assert.equal(ticket.messages.length,1);assert.ok(ticket.sla_due_at);

  let player=await json(base,'/api/user/support/tickets/');assert.equal(player.results.length,1);assert.equal(player.results[0].reference,ticket.reference);
  let queue=await json(base,'/api/admin/support/tickets/',{admin:true});assert.equal(queue.summary.active,1);assert.equal(queue.summary.unassigned,1);assert.equal(queue.results[0].messages.length,1);

  await json(base,`/api/admin/support/tickets/${ticket.id}/messages/`,{method:'POST',admin:true,body:{message:'Proof image is readable; compare the UTR against the bank statement.',internal:true}});
  player=await json(base,'/api/user/support/tickets/');assert.equal(player.results[0].messages.length,1,'private staff notes must never be returned to players');assert.ok(!player.results[0].messages.some(message=>message.body.includes('bank statement')));

  ticket=await json(base,`/api/admin/support/tickets/${ticket.id}/messages/`,{method:'POST',admin:true,body:{message:'We are checking the submitted UTR and will update this case.',internal:false}});assert.equal(ticket.status,'WAITING_FOR_PLAYER');assert.equal(ticket.messages.length,3);
  player=await json(base,'/api/user/support/tickets/');assert.equal(player.results[0].messages.length,2);assert.ok(player.results[0].messages.some(message=>message.body.startsWith('We are checking')));

  ticket=await json(base,`/api/admin/support/tickets/${ticket.id}/`,{method:'POST',admin:true,body:{status:'RESOLVED',priority:'HIGH',assigned_admin:'Support Manager',resolution_summary:'The payment entered the standard verification queue and no evidence was missing.'}});assert.equal(ticket.status,'RESOLVED');assert.equal(ticket.priority,'HIGH');assert.equal(ticket.assigned_admin,'Support Manager');assert.ok(ticket.resolved_at);

  ticket=await json(base,`/api/user/support/tickets/${ticket.id}/messages/`,{method:'POST',body:{message:'I have one more question about the expected review time.'}});assert.equal(ticket.status,'OPEN','a player reply should reopen a resolved case');
  ticket=await json(base,`/api/admin/support/tickets/${ticket.id}/`,{method:'POST',admin:true,body:{status:'CLOSED',priority:'HIGH',assigned_admin:'Support Manager',resolution_summary:'Player was informed of the verification timeline and no further action remains.'}});assert.equal(ticket.status,'CLOSED');assert.ok(ticket.closed_at);
  await json(base,`/api/user/support/tickets/${ticket.id}/messages/`,{method:'POST',expected:400,body:{message:'Closed cases should reject replies.'}});

  const notifications=await json(base,'/api/user/notifications/');assert.ok(notifications.results.some(item=>item.event_type==='SUPPORT_TICKET_CREATED'));assert.ok(notifications.results.some(item=>item.event_type==='SUPPORT_ADMIN_REPLY'));assert.ok(notifications.results.some(item=>item.event_type==='SUPPORT_STATUS_CHANGED'));
  const audit=await json(base,'/api/admin/audit/',{admin:true});assert.ok(audit.results.some(row=>row.module==='Support'&&row.subject===ticket.reference));
  const config=await json(base,'/api/admin/config/',{admin:true});assert.ok(config.roles.some(role=>role.name==='Support Manager'&&role.permissions.includes('support')));
  const health=await json(base,'/api/admin/health/',{admin:true});assert.equal(health.support.status,'ok');assert.equal(health.support.tickets,1);assert.equal(health.support.active,0);
  console.log('Support ownership, SLA queue, private notes, replies, reopening, resolution, audit, and access checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
