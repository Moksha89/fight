import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{})},body:body!==undefined?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-wallet-adjust-'));
const child=spawn('python3',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe'],env:{...process.env,ROOSTERRUN_MAX_WALLET_ADJUSTMENT_PAISE:'100000'}});
const base=`http://127.0.0.1:${port}`;
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

try{
  let ready=false;for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/admin/health/',{admin:true});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'wallet adjustment test server did not start');
  
  const userId='arena-guest';
  
  // Setup: give user some initial balance through approved deposit
  const account=await json(base,'/api/payments/admin/accounts/',{method:'POST',admin:true,expected:201,body:{label:'Test UPI',account_type:'UPI',account_holder:'Test User',upi_id:'test@upi'}});
  const deposit=await json(base,'/api/payments/deposits/',{method:'POST',expected:201,body:{amount:500,account_id:account.id,utr:'TESTADJ001',proof_data_url:png}});
  await json(base,`/api/payments/admin/requests/${deposit.id}/decision/`,{method:'POST',admin:true,body:{decision:'APPROVED',admin_note:'Initial balance'}});
  
  let wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,500,'Initial balance should be 500');
  
  // Test 1: Credit adjustment
  const credit=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:250,reason:'Promotional credit for testing'}});
  assert.equal(credit.amount,250);
  assert.equal(credit.new_balance,750);
  assert.equal(credit.user_id,userId);
  assert.ok(credit.reference.startsWith('ADJ-'));
  
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,750,'Balance after credit should be 750');
  
  // Test 2: Debit adjustment
  const debit=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:-100,reason:'Correction for duplicate deposit'}});
  assert.equal(debit.amount,-100);
  assert.equal(debit.new_balance,650);
  
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,650,'Balance after debit should be 650');
  
  // Test 3: Zero amount rejected
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:0,reason:'This should fail'}});
  
  // Test 4: Missing reason rejected
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:50}});
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:50,reason:'ab'}});
  
  // Test 5: Debit beyond available balance rejected
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:-1000,reason:'This exceeds available balance'}});
  
  wallet=await json(base,'/api/payments/wallet/');
  assert.equal(wallet.balance,650,'Balance should remain 650 after rejected debit');
  
  // Test 6: Exceeds max limit (env set to 100000 paise = 1000 rupees)
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:1500,reason:'This exceeds the configured maximum'}});
  
  // Test 7: Debit respects holds - place a bet to create a hold
  const games=await json(base,'/api/admin/games/',{admin:true});
  const game=games.results[0];
  const quote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,body:{matchId:game.id,betTeam:1,amount:200}});
  await json(base,`/api/cockfight/bets/${quote.quote_id}/confirm/`,{method:'POST',body:{}});
  
  // Now available balance is 650 - 200 = 450
  // Trying to debit 500 should fail
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:-500,reason:'This exceeds available after bet hold'}});
  
  // But debit of 400 should work
  const debitWithHold=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:-400,reason:'Debit respecting holds'}});
  assert.equal(debitWithHold.new_balance,250);
  
  // Test 8: Verify audit log entry
  const audit=await json(base,'/api/admin/audit/',{admin:true});
  const walletAudits=audit.results.filter(a=>a.module==='Users'&&(a.action==='Wallet credit'||a.action==='Wallet debit'));
  assert.ok(walletAudits.length>=3,'Should have at least 3 wallet adjustment audit entries');
  
  // Test 9: Verify ledger entries
  const ledger=await json(base,'/api/payments/ledger/');
  const adjustments=ledger.results.filter(e=>e.entry_type==='ADMIN_ADJUSTMENT');
  assert.ok(adjustments.length>=3,'Should have at least 3 adjustment ledger entries');
  
  // Test 10: Unauthorized role (not admin) should be rejected
  await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',expected:401,body:{amount:100,reason:'No admin auth'}});
  
  console.log('Admin wallet adjustment tests passed: credit, debit, validation, holds, max limit, audit, ledger.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
