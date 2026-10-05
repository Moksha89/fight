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
 
 // Get initial balance
 let wallet=await json(base,'/api/payments/wallet/');
 const initialBalance=wallet.balance;
 
 // Test 1: Credit adjustment
 const credit=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:250,reason:'Promotional credit for testing'}});
 assert.equal(credit.amount,250);
 assert.equal(credit.new_balance,initialBalance+250);
 assert.equal(credit.user_id,userId);
 assert.ok(credit.reference.startsWith('ADJ-'));
 
 wallet=await json(base,'/api/payments/wallet/');
 assert.equal(wallet.balance,initialBalance+250,'Balance after credit should increase by 250');
 
 // Test 2: Debit adjustment
 const debit=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:-100,reason:'Correction for duplicate deposit'}});
 assert.equal(debit.amount,-100);
 assert.equal(debit.new_balance,initialBalance+150);
 
 wallet=await json(base,'/api/payments/wallet/');
 assert.equal(wallet.balance,initialBalance+150,'Balance after debit should be initial + 150');
 
 // Test 3: Zero amount rejected
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:0,reason:'This should fail'}});
 
 // Test 4: Missing reason rejected
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:50}});
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:50,reason:'ab'}});
 
 // Test 5: Debit beyond available balance rejected
 const currentBalance=initialBalance+150;
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:-(currentBalance+1000),reason:'This exceeds available balance'}});
 
 wallet=await json(base,'/api/payments/wallet/');
 assert.equal(wallet.balance,currentBalance,'Balance should remain unchanged after rejected debit');
 
 // Test 6: Exceeds max limit (env set to 100000 paise = 1000 rupees)
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:1500,reason:'This exceeds the configured maximum'}});
 
 // Test 7: Debit respects holds - place a bet to create a hold
 const games=await json(base,'/api/admin/games/',{admin:true});
 const game=games.results[0];
 const quote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,body:{matchId:game.id,betTeam:1,amount:200}});
 await json(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:201,body:{quote_id:quote.quote_id}});
 
 wallet=await json(base,'/api/payments/wallet/');
 const balanceAfterBet=wallet.balance;
 const availableAfterBet=balanceAfterBet-200;
 
 // Trying to debit more than available should fail
 if(availableAfterBet>100){
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:-(availableAfterBet+50),reason:'This exceeds available after bet hold'}});
 
 // But debit within available should work
 const debitAmount=Math.min(availableAfterBet-10,100);
 const debitWithHold=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:-debitAmount,reason:'Debit respecting holds'}});
 assert.equal(debitWithHold.new_balance,balanceAfterBet-debitAmount);
 }
 
 // Test 9: Verify audit log entry
 const audit=await json(base,'/api/admin/audit/',{admin:true});
 const walletAudits=audit.results.filter(a=>a.module==='Users'&&(a.action==='Wallet credit'||a.action==='Wallet debit'));
 assert.ok(walletAudits.length>=3,'Should have at least 3 wallet adjustment audit entries');
 
 // Test 10: Unauthorized role (not admin) should be rejected
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',expected:401,body:{amount:100,reason:'No admin auth'}});

 // Test 11: Idempotency — repeat with same key does not double-credit and returns same reference
 wallet=await json(base,'/api/payments/wallet/');
 const beforeIdempotent=wallet.balance;
 const idemKey='promo-credit-2026a';
 const firstIdem=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:75,reason:'Idempotent promotional credit',idempotency_key:idemKey}});
 assert.equal(firstIdem.reference,`ADJ-K-${idemKey}`);
 assert.equal(firstIdem.amount,75);
 const secondIdem=await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,body:{amount:75,reason:'Idempotent promotional credit',idempotency_key:idemKey}});
 assert.equal(secondIdem.reference,firstIdem.reference);
 assert.equal(secondIdem.new_balance,firstIdem.new_balance);
 wallet=await json(base,'/api/payments/wallet/');
 assert.equal(wallet.balance,beforeIdempotent+75,'Idempotent replay must not double-credit');

 // Same key with a different amount is a conflict
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:409,body:{amount:80,reason:'Different amount same key',idempotency_key:idemKey}});

 // Test 12: More than 2 decimal places rejected
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:10.125,reason:'Three decimal places must fail'}});
 await json(base,`/api/admin/users/${userId}/wallet/`,{method:'POST',admin:true,expected:400,body:{amount:'12.345',reason:'String three decimals must fail'}});

 // Test 13: Stray wallet_adjustment_* on user update returns 400
 await json(base,`/api/admin/users/${userId}/`,{method:'POST',admin:true,expected:400,body:{status:'ACTIVE',vip_tier:'Standard',wallet_adjustment_amount:50}});
 await json(base,`/api/admin/users/${userId}/`,{method:'POST',admin:true,expected:400,body:{status:'ACTIVE',vip_tier:'Standard',wallet_adjustment:true}});

 // Test 14: Reconciliation counts account_ledger ADJUSTMENT rows in the balance-vs-ledger check.
 // Preview now seeds arena-guest with a matching PREVIEW-OPENING account_ledger row, so a clean
 // PASS is expected after wallet adjustments (credits/debits also write account_ledger).
 const recon=await json(base,'/api/admin/operations/reconciliation/run/',{method:'POST',admin:true,expected:201,body:{}});
 assert.equal(recon.status,'PASS',`Expected PASS after ledgered preview seed + adjustments: ${JSON.stringify(recon)}`);
 assert.equal((recon.findings||[]).length,0);
 const guestMismatch=(recon.findings||[]).find(f=>f.check_code==='BALANCE_LEDGER_MISMATCH'&&f.entity_id===userId);
 assert.equal(guestMismatch,undefined,'Ledgered preview guest must not produce BALANCE_LEDGER_MISMATCH');

 // Test 15: Role lacking users permission — not feasible in this preview harness.
 // Preview mode grants Super Admin via X-Preview-Admin. Creating a restricted Game Operator
 // requires non-preview bootstrap (ROOSTERRUN_BOOTSTRAP_ADMIN_*), CSRF session cookies, and
 // /api/admin/team/ (see tests/auth-engine.mjs). That path is covered by auth-engine RBAC;
 // admin_permission already maps /api/admin/users/<id>/wallet/ → "users".

 console.log('Admin wallet adjustment tests passed: credit, debit, validation, holds, max limit, audit, idempotency, decimals, stray keys, reconciliation.');
}finally{
 child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
