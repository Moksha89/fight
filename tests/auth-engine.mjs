import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function freePort(){return new Promise((resolvePort,reject)=>{const server=createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(error=>error?reject(error):resolvePort(port));});});}
function splitSetCookie(value){if(!value)return[];return value.split(/,(?=\s*[A-Za-z0-9_-]+=)/g).map(item=>item.trim());}
class CookieJar{
  constructor(){this.values=new Map();this.last=[];}
  capture(response){this.last=typeof response.headers.getSetCookie==='function'?response.headers.getSetCookie():splitSetCookie(response.headers.get('set-cookie'));for(const line of this.last){const pair=line.split(';',1)[0];const index=pair.indexOf('=');if(index<0)continue;const name=pair.slice(0,index);const value=pair.slice(index+1);if(/Max-Age=0/i.test(line))this.values.delete(name);else this.values.set(name,value);}}
  header(){return [...this.values].map(([name,value])=>`${name}=${value}`).join('; ');}
  get(name){return this.values.get(name)||'';}
}
async function json(base,path,{method='GET',body,jar,csrf=true,headers={},expected=200}={}){
  const requestHeaders={...headers};if(body!==undefined)requestHeaders['Content-Type']='application/json';if(jar?.header())requestHeaders.Cookie=jar.header();if(csrf&&jar?.get('rr_user_csrf'))requestHeaders['X-CSRF-Token']=jar.get('rr_user_csrf');if(csrf&&jar?.get('rr_admin_csrf'))requestHeaders['X-CSRF-Token']=jar.get('rr_admin_csrf');
  const response=await fetch(`${base}${path}`,{method,headers:requestHeaders,body:body!==undefined?JSON.stringify(body):undefined});jar?.capture(response);const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return {data,response};
}
function totp(secret){const normalized=secret.toUpperCase().replace(/=+$/,'');const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits='';for(const character of normalized)bits+=alphabet.indexOf(character).toString(2).padStart(5,'0');const bytes=[];for(let i=0;i+8<=bits.length;i+=8)bytes.push(parseInt(bits.slice(i,i+8),2));const counter=Math.floor(Date.now()/30000);const message=Buffer.alloc(8);message.writeBigUInt64BE(BigInt(counter));const digest=crypto.createHmac('sha1',Buffer.from(bytes)).update(message).digest();const offset=digest.at(-1)&15;const value=(digest.readUInt32BE(offset)&0x7fffffff)%1_000_000;return String(value).padStart(6,'0');}

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-auth-'));
const child=spawn('python',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir],{stdio:['ignore','pipe','pipe'],env:{...process.env,ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME:'owner',ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD:'OwnerSecure123',ROOSTERRUN_BOOTSTRAP_ADMIN_NAME:'Platform Owner',ROOSTERRUN_SECURE_COOKIES:'0',ROOSTERRUN_OTP_TEST_MODE:'1'}});
const base=`http://127.0.0.1:${port}`;

try{
  let ready=false;for(let attempt=0;attempt<80;attempt+=1){try{await json(base,'/api/payments/health/');ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'authentication test server did not start');
  await json(base,'/api/payments/wallet/',{expected:401,headers:{'X-Demo-User':'arena-guest'}});
  await json(base,'/api/user/register/',{method:'POST',body:{mobile:'9876543210',username:'player.one',password:'weak'},expected:400});

  const userJar=new CookieJar();
  const registration=(await json(base,'/api/user/register/',{method:'POST',body:{mobile:'9876543210',username:'player.one',password:'PlayerSecure123',confirmPassword:'PlayerSecure123'},expected:202})).data;
  assert.equal(registration.otp_required,true);assert.match(registration.preview_otp,/^\d{6}$/);
  const registered=await json(base,'/api/user/register/',{method:'POST',jar:userJar,body:{challenge_id:registration.challenge_id,otp:registration.preview_otp},expected:201});
  assert.equal(registered.data.authenticated,true);assert.equal(registered.data.user.username,'player.one');assert.equal('session_token' in registered.data,false);assert.ok(userJar.get('rr_user_session'));assert.ok(userJar.get('rr_user_csrf'));assert.ok(userJar.last.some(line=>/rr_user_session=.*HttpOnly.*SameSite=Strict/i.test(line)));
  const me=(await json(base,'/api/user/me/',{jar:userJar})).data;assert.equal(me.username,'player.one');
  await json(base,'/api/user/logout/',{method:'POST',jar:userJar,csrf:false,body:{},expected:403});

  const recovery=(await json(base,'/api/user/forgot-password/request-otp/',{method:'POST',body:{mobile:'9876543210'},expected:202})).data;
  assert.match(recovery.preview_otp,/^\d{6}$/);
  await json(base,'/api/user/forgot-password/reset/',{method:'POST',body:{challenge_id:recovery.challenge_id,otp:recovery.preview_otp,password:'NewPlayerSecure456',confirmPassword:'NewPlayerSecure456'}});
  await json(base,'/api/user/me/',{jar:userJar,expected:401});
  const reloginJar=new CookieJar();await json(base,'/api/user/login/',{method:'POST',jar:reloginJar,body:{identifier:'player.one',password:'NewPlayerSecure456'}});await json(base,'/api/user/me/',{jar:reloginJar});
  await json(base,'/api/user/password/change/',{method:'POST',jar:reloginJar,body:{current_password:'WrongPassword999',new_password:'FinalPlayerSecure789',confirm_password:'FinalPlayerSecure789'},expected:401});
  const changed=(await json(base,'/api/user/password/change/',{method:'POST',jar:reloginJar,body:{current_password:'NewPlayerSecure456',new_password:'FinalPlayerSecure789',confirm_password:'FinalPlayerSecure789'}})).data;assert.equal(changed.reauthentication_required,true);assert.equal(reloginJar.get('rr_user_session'),'');
  await json(base,'/api/user/login/',{method:'POST',body:{identifier:'player.one',password:'NewPlayerSecure456'},expected:401});
  const finalUserJar=new CookieJar();await json(base,'/api/user/login/',{method:'POST',jar:finalUserJar,body:{identifier:'player.one',password:'FinalPlayerSecure789'}});await json(base,'/api/user/me/',{jar:finalUserJar});

  const adminJar=new CookieJar();
  const ownerLogin=await json(base,'/api/admin/auth/login/',{method:'POST',jar:adminJar,body:{username:'owner',password:'OwnerSecure123'}});assert.equal(ownerLogin.data.admin.role,'Super Admin');assert.ok(adminJar.get('rr_admin_session'));assert.equal('session_token' in ownerLogin.data,false);
  const productionGames=(await json(base,'/api/admin/games/',{jar:adminJar})).data.results;assert.equal(productionGames.length,0,'non-preview databases must not seed a dummy match');
  await json(base,'/api/admin/team/',{method:'POST',jar:adminJar,csrf:false,body:{username:'operator',display_name:'Arena Operator',password:'OperatorSecure123',role_id:2},expected:403});
  const staff=(await json(base,'/api/admin/team/',{method:'POST',jar:adminJar,body:{username:'operator',display_name:'Arena Operator',password:'OperatorSecure123',role_id:2},expected:201})).data;assert.equal(staff.role,'Game Operator');

  const staffJar=new CookieJar();await json(base,'/api/admin/auth/login/',{method:'POST',jar:staffJar,body:{username:'operator',password:'OperatorSecure123'}});await json(base,'/api/admin/games/',{jar:staffJar});await json(base,'/api/admin/users/',{jar:staffJar,expected:403});await json(base,'/api/admin/config/',{jar:staffJar});
  for(let attempt=0;attempt<5;attempt+=1)await json(base,'/api/admin/auth/login/',{method:'POST',body:{username:'operator',password:'WrongPassword999'},expected:401});
  await json(base,'/api/admin/auth/login/',{method:'POST',body:{username:'operator',password:'OperatorSecure123'},expected:429});

  const enrollment=(await json(base,'/api/admin/auth/mfa/enroll/',{method:'POST',jar:adminJar,body:{}})).data;assert.match(enrollment.secret,/^[A-Z2-7]+$/);
  const confirmed=(await json(base,'/api/admin/auth/mfa/confirm/',{method:'POST',jar:adminJar,body:{code:totp(enrollment.secret)}})).data;assert.equal(confirmed.mfa_enabled,true);assert.equal(confirmed.recovery_codes.length,8);
  await json(base,'/api/admin/auth/logout/',{method:'POST',jar:adminJar,body:{}});
  const mfaJar=new CookieJar();const challenge=(await json(base,'/api/admin/auth/login/',{method:'POST',jar:mfaJar,body:{username:'owner',password:'OwnerSecure123'},expected:202})).data;assert.equal(challenge.mfa_required,true);
  await json(base,'/api/admin/auth/mfa/verify/',{method:'POST',jar:mfaJar,body:{challenge_id:challenge.challenge_id,code:'000000'},expected:401});
  await json(base,'/api/admin/auth/mfa/verify/',{method:'POST',jar:mfaJar,body:{challenge_id:challenge.challenge_id,code:totp(enrollment.secret)}});await json(base,'/api/admin/team/',{jar:mfaJar});
  const audit=(await json(base,'/api/admin/audit/?limit=30',{jar:mfaJar})).data.results;assert.ok(audit.some(row=>row.action==='Administrator created'&&row.actor_role==='Super Admin'));
  console.log('User sessions, OTP recovery, admin RBAC, CSRF, MFA, and audit checks passed.');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
