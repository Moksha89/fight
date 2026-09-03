import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
async function json(base,path,{method='GET',body,admin=false,expected=200,user='engine-player'}={}){const response=await fetch(`${base}${path}`,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(admin?{'X-Preview-Admin':'1'}:{}),'X-Demo-User':user},body:body?JSON.stringify(body):undefined});const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return data;}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-engine-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir,'--preview'],{stdio:['ignore','pipe','pipe']});
const base=`http://127.0.0.1:${port}`;

try{
  let ready=false;
  for(let attempt=0;attempt<60;attempt+=1){try{await json(base,'/api/cockfight/engine/health/',{user:'arena-guest'});ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}
  assert.equal(ready,true,'engine server did not start');

  const health=await json(base,'/api/cockfight/engine/health/');assert.equal(health.status,'ok');assert.equal(health.scheduler,true);
  const games=await json(base,'/api/admin/games/',{admin:true});const game=games.results[0];assert.equal(game.status,'BETTING_OPEN');
  const odds=await json(base,'/api/cockfight/odds/current/');assert.equal(odds.market_status,'OPEN');assert.ok(odds.version>=1);

  // Preview mode uses one fixed server-side guest identity; browser headers cannot impersonate another wallet.
  const user='arena-guest';
  const funded=await json(base,'/api/payments/wallet/',{user});assert.equal(funded.balance,12450);
  const quote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,user,body:{matchId:game.id,betTeam:1,amount:500}});assert.equal(quote.outcome,'RED');assert.equal(quote.stake,500);assert.equal(quote.odds_version,odds.version);

  const [firstPlace,secondPlace]=await Promise.all([
    json(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:201,user,body:{quote_id:quote.quote_id}}),
    json(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:201,user,body:{quote_id:quote.quote_id}}),
  ]);
  assert.equal(firstPlace.id,secondPlace.id,'idempotent quote consumption must return one ticket');
  assert.equal(firstPlace.status,'pending');assert.equal(firstPlace.wallet.balance,12450);assert.equal(firstPlace.wallet.available,11950);assert.equal(firstPlace.wallet.bet_exposure,500);
  const tickets=await json(base,'/api/cockfight/bets/',{user});assert.equal(tickets.results.length,1);

  const published=await json(base,`/api/admin/games/${game.id}/odds/`,{method:'POST',admin:true,body:{team_a_odds:2.6,draw_odds:8.4,team_b_odds:2.25,market_status:'OPEN',reason:'Engine test repricing'}});assert.ok(published.version>odds.version);assert.equal(published.team_a_odds,2.6);
  const newQuote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,user,body:{matchId:game.id,betTeam:2,amount:100}});assert.equal(newQuote.odds,2.25);
  await json(base,`/api/admin/games/${game.id}/odds/`,{method:'POST',admin:true,body:{team_a_odds:2.6,draw_odds:8.4,team_b_odds:2.25,market_status:'SUSPENDED',reason:'Risk review'}});
  await json(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:400,user,body:{quote_id:newQuote.quote_id}});
  await json(base,`/api/admin/games/${game.id}/odds/`,{method:'POST',admin:true,body:{team_a_odds:2.6,draw_odds:8.4,team_b_odds:2.25,market_status:'OPEN',reason:'Risk review cleared'}});

  const policy=await json(base,'/api/admin/risk/',{admin:true});
  await json(base,'/api/admin/risk/',{method:'POST',admin:true,body:{...policy,maximum_stake:100}});
  await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:400,user,body:{matchId:game.id,betTeam:1,amount:500}});
  await json(base,'/api/admin/risk/',{method:'POST',admin:true,body:{...policy}});

  await json(base,`/api/admin/games/${game.id}/transition/`,{method:'POST',admin:true,body:{status:'BETTING_CLOSED',reason:'Engine test close'}});
  await json(base,`/api/admin/games/${game.id}/transition/`,{method:'POST',admin:true,body:{status:'LIVE',reason:'Engine test live'}});
  const declared=await json(base,`/api/admin/games/${game.id}/result/`,{method:'POST',admin:true,body:{result:'RED'}});assert.equal(declared.status,'AWAITING_RESULT');
  const settlement=await json(base,`/api/admin/games/${game.id}/settle/`,{method:'POST',admin:true,body:{}});assert.equal(settlement.status,'SETTLED');assert.equal(settlement.bets,1);assert.equal(settlement.won,1);assert.equal(settlement.total_payout,1225);
  const settledAgain=await json(base,`/api/admin/games/${game.id}/settle/`,{method:'POST',admin:true,body:{}});assert.deepEqual(settledAgain,settlement,'settlement must be idempotent');
  const winningWallet=await json(base,'/api/payments/wallet/',{user});assert.equal(winningWallet.balance,13175);assert.equal(winningWallet.bet_exposure,0);assert.equal(winningWallet.available,13175);
  const statement=await json(base,'/api/user/statement/',{user});assert.equal(statement.results[0].entry_type,'BET_WIN');assert.equal(statement.results[0].amount,725);
  const settledTickets=await json(base,'/api/cockfight/bets/',{user});assert.equal(settledTickets.results[0].status,'won');assert.equal(settledTickets.results[0].payout,1225);
  const history=await json(base,'/api/cockfight/auto-history/');assert.equal(history.results[0].winTeam,1);

  const future=new Date(Date.now()+20*60*1000).toISOString();const futureClose=new Date(Date.now()+15*60*1000).toISOString();const openNow=new Date().toISOString();
  const cancelGame=await json(base,'/api/admin/games/',{method:'POST',expected:201,admin:true,body:{title:'Refund Arena · Match',arena:'Refund Arena',status:'SCHEDULED',betting_opens_at:openNow,betting_closes_at:futureClose,scheduled_at:future,team_a_name:'Scarlet',team_a_odds:2.1,draw_odds:7,team_b_name:'Cobalt',team_b_odds:2.2,stream_type:'OFFLINE',stream_url:'',featured:false}});
  await json(base,`/api/admin/games/${cancelGame.id}/transition/`,{method:'POST',admin:true,body:{status:'BETTING_OPEN',reason:'Refund test open'}});
  await json(base,`/api/admin/games/${cancelGame.id}/`,{method:'POST',expected:400,admin:true,body:{scheduled_at:new Date(Date.now()+30*60*1000).toISOString()}});
  const cancelQuote=await json(base,'/api/cockfight/bets/quote/',{method:'POST',expected:201,user,body:{matchId:cancelGame.id,betTeam:2,amount:200}});
  const cancelTicket=await json(base,'/api/cockfight/bets/place-bet/',{method:'POST',expected:201,user,body:{quote_id:cancelQuote.quote_id}});assert.equal(cancelTicket.wallet.bet_exposure,200);
  await json(base,`/api/admin/games/${cancelGame.id}/result/`,{method:'POST',admin:true,body:{result:'CANCELLED'}});
  const refundSettlement=await json(base,`/api/admin/games/${cancelGame.id}/settle/`,{method:'POST',admin:true,body:{}});assert.equal(refundSettlement.refunded,1);
  const refundedWallet=await json(base,'/api/payments/wallet/',{user});assert.equal(refundedWallet.balance,13175);assert.equal(refundedWallet.bet_exposure,0);

  const pastOpen=new Date(Date.now()-30_000).toISOString();const pastClose=new Date(Date.now()-20_000).toISOString();const pastStart=new Date(Date.now()-10_000).toISOString();
  const scheduled=await json(base,'/api/admin/games/',{method:'POST',expected:201,admin:true,body:{title:'Scheduler Arena · Match',arena:'Scheduler Arena',status:'SCHEDULED',betting_opens_at:pastOpen,betting_closes_at:pastClose,scheduled_at:pastStart,team_a_name:'Red',team_a_odds:2.4,draw_odds:8,team_b_name:'Blue',team_b_odds:2.4,stream_type:'OFFLINE',stream_url:'',featured:false}});
  let automatedStatus='SCHEDULED';for(let attempt=0;attempt<20;attempt+=1){await new Promise(resolveWait=>setTimeout(resolveWait,100));const current=await json(base,'/api/admin/games/',{admin:true});automatedStatus=current.results.find(item=>item.id===scheduled.id)?.status||automatedStatus;if(automatedStatus==='LIVE')break;}assert.equal(automatedStatus,'LIVE','scheduler should advance all due lifecycle states');

  const events=await json(base,'/api/cockfight/events/?after=0');assert.ok(events.results.some(event=>event.event_type==='BET_ACCEPTED'));assert.ok(events.results.some(event=>event.event_type==='MATCH_SETTLED'));
  const finalHealth=await json(base,'/api/cockfight/engine/health/');assert.equal(finalHealth.pending_bets,0);assert.ok(finalHealth.last_event_id>0);
  console.log('Cockfight engine transaction, risk, and settlement checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
