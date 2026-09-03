import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort() {
  return new Promise((resolvePort,reject)=>{
    const server=createServer();
    server.once('error',reject);
    server.listen(0,'127.0.0.1',()=>{
      const {port}=server.address();
      server.close(error=>error?reject(error):resolvePort(port));
    });
  });
}

async function json(base,path,{method='GET',body,admin=false,expected=200}={}) {
  const response=await fetch(`${base}${path}`,{
    method,
    headers:{...(body?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},
    body:body?JSON.stringify(body):undefined,
  });
  const data=await response.json();
  assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);
  return data;
}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-payments-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try {
  let ready=false;
  for(let attempt=0;attempt<50;attempt+=1){
    try { await json(base,'/api/payments/health/'); ready=true; break; }
    catch { await new Promise(resolveWait=>setTimeout(resolveWait,100)); }
  }
  assert.equal(ready,true,'manual payments server did not start');
  const live=await json(base,'/health/live/');
  assert.equal(live.status,'alive');
  const readiness=await json(base,'/health/ready/');
  assert.equal(readiness.status,'ready');
  assert.equal(readiness.checks.background_workers.ok,true);

  await json(base,'/api/payments/admin/accounts/',{expected:401});
  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Test UPI',account_type:'UPI',account_holder:'RoosterRun Test',upi_id:'test@upi',qr_data_url:png}});
  assert.equal(account.active,true);

  const depositPayload={amount:100,account_id:account.id,utr:'UTR123456789',proof_data_url:png};
  const deposit=await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:depositPayload});
  assert.equal(deposit.status,'PENDING');
  assert.match(deposit.deposit_proof_url,/^\/api\/payments\/requests\/\d+\/deposit-proof\/$/);
  const privateProofs=readdirSync(join(dataDir,'private','payments'));
  assert.equal(privateProofs.length,1,'deposit proof must be stored in the private evidence directory');
  assert.equal(existsSync(join(dataDir,'uploads',privateProofs[0])),false,'deposit proof must not remain in public uploads');
  assert.equal((await fetch(`${base}/uploads/${privateProofs[0]}`)).status,404,'private proof must not be publicly downloadable');
  const playerProof=await fetch(`${base}${deposit.deposit_proof_url}`);
  assert.equal(playerProof.status,200);
  assert.equal(playerProof.headers.get('cache-control'),'no-store, private');
  const adminQueue=await json(base,'/api/payments/admin/requests/',{admin:true});
  const adminDeposit=adminQueue.results.find(item=>item.id===deposit.id);
  assert.match(adminDeposit.deposit_proof_url,/^\/api\/payments\/admin\/requests\/\d+\/deposit-proof\/$/);
  assert.equal((await fetch(`${base}${adminDeposit.deposit_proof_url}`)).status,200);
  await json(base,'/api/payments/deposits/',{method:'POST',expected:400,body:depositPayload});
  const approvedDeposit=await json(base,`/api/payments/admin/requests/${deposit.id}/decision/`,{method:'POST',admin:true,body:{decision:'APPROVED',admin_note:'Verified'}});
  assert.equal(approvedDeposit.status,'APPROVED');
  await json(base,`/api/payments/admin/requests/${deposit.id}/decision/`,{method:'POST',admin:true,expected:400,body:{decision:'APPROVED'}});

  let wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,12550);
  const withdrawal=await json(base,'/api/payments/withdrawals/',{method:'POST',expected:201,body:{amount:500,method:'BANK',account_holder:'Arena Guest',bank_name:'State Bank of India',account_number:'123456789012',ifsc:'SBIN0001234'}});
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.pending_withdrawal,500);
  assert.equal(wallet.available,12050);
  await json(base,`/api/payments/admin/requests/${withdrawal.id}/decision/`,{method:'POST',admin:true,expected:400,body:{decision:'APPROVED'}});
  const paid=await json(base,`/api/payments/admin/requests/${withdrawal.id}/decision/`,{method:'POST',admin:true,body:{decision:'APPROVED',payout_utr:'PAY123456789',admin_note:'Paid'}});
  assert.equal(paid.status,'APPROVED');
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,12050);
  assert.equal(wallet.pending_withdrawal,0);

  const rejectedRequest=await json(base,'/api/payments/withdrawals/',{method:'POST',expected:201,body:{amount:500,method:'UPI',account_holder:'Arena Guest',upi_id:'guest@upi'}});
  await json(base,`/api/payments/admin/requests/${rejectedRequest.id}/decision/`,{method:'POST',admin:true,expected:400,body:{decision:'REJECTED',admin_note:''}});
  const rejected=await json(base,`/api/payments/admin/requests/${rejectedRequest.id}/decision/`,{method:'POST',admin:true,body:{decision:'REJECTED',admin_note:'Beneficiary details do not match'}});
  assert.equal(rejected.status,'REJECTED');
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.available,12050);

  const ledger=await json(base,'/api/payments/ledger/');
  assert.equal(ledger.results.length,2);
  assert.deepEqual(ledger.results.map(entry=>entry.amount),[-500,100]);
  console.log('Manual Indian payments workflow checks passed.');
} finally {
  child.kill();
  await new Promise(resolveWait=>child.once('exit',resolveWait));
  rmSync(dataDir,{recursive:true,force:true});
}
