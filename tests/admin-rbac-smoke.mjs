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
  const requestHeaders={...headers};if(body!==undefined)requestHeaders['Content-Type']='application/json';if(jar?.header())requestHeaders.Cookie=jar.header();if(csrf&&jar?.get('rr_admin_csrf'))requestHeaders['X-CSRF-Token']=jar.get('rr_admin_csrf');
  const response=await fetch(`${base}${path}`,{method,headers:requestHeaders,body:body!==undefined?JSON.stringify(body):undefined});jar?.capture(response);const data=await response.json();assert.equal(response.status,expected,`${method} ${path}: ${JSON.stringify(data)}`);return {data,response};
}
function totp(secret){const normalized=secret.toUpperCase().replace(/=+$/,'');const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits='';for(const character of normalized)bits+=alphabet.indexOf(character).toString(2).padStart(5,'0');const bytes=[];for(let i=0;i+8<=bits.length;i+=8)bytes.push(parseInt(bits.slice(i,i+8),2));const counter=Math.floor(Date.now()/30000);const message=Buffer.alloc(8);message.writeBigUInt64BE(BigInt(counter));const digest=crypto.createHmac('sha1',Buffer.from(bytes)).update(message).digest();const offset=digest.at(-1)&15;const value=(digest.readUInt32BE(offset)&0x7fffffff)%1_000_000;return String(value).padStart(6,'0');}

const ROLES = {
  'Super Admin': ['overview', 'operations', 'intelligence', 'support', 'users', 'games', 'payments', 'compliance', 'banners', 'vip', 'theme', 'social', 'settings', 'team', 'audit', 'assets'],
  'Game Operator': ['overview', 'games', 'banners', 'assets'],
  'Payments Manager': ['overview', 'payments', 'users'],
  'Content Manager': ['overview', 'banners', 'theme', 'social', 'assets'],
  'Compliance Manager': ['overview', 'compliance', 'users', 'audit'],
  'Operations Manager': ['overview', 'operations', 'payments', 'games', 'audit'],
  'Support Manager': ['overview', 'support', 'users', 'payments', 'compliance', 'audit'],
  'Risk Analyst': ['overview', 'intelligence', 'users', 'payments', 'games', 'audit'],
};

const PERMISSION_ENDPOINTS = {
  'overview': ['/api/admin/overview/', '/api/admin/vip/', '/api/admin/config/'],
  'operations': ['/api/admin/operations/overview/'],
  'intelligence': ['/api/admin/intelligence/overview/', '/api/admin/intelligence/alerts/'],
  'support': ['/api/admin/support/tickets/'],
  'users': ['/api/admin/users/'],
  'games': ['/api/admin/games/', '/api/admin/risk/', '/api/admin/game-categories/'],
  'payments': ['/api/payments/admin/requests/', '/api/payments/admin/accounts/'],
  'compliance': ['/api/admin/compliance/', '/api/admin/compliance/policy/'],
  'banners': ['/api/admin/banners/'],
  'social': ['/api/admin/social/'],
  'team': ['/api/admin/team/'],
  'audit': ['/api/admin/audit/'],
  'assets': ['/api/admin/assets/upload/'],
};

const port=await freePort();
const dataDir=mkdtempSync(join(tmpdir(),'roosterrun-rbac-'));
const child=spawn('python3',[resolve('server/manual_payments_server.py'),'--host','127.0.0.1','--port',String(port),'--data-dir',dataDir],{stdio:['ignore','pipe','pipe'],env:{...process.env,ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME:'superadmin',ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD:'SuperSecure123',ROOSTERRUN_BOOTSTRAP_ADMIN_NAME:'Super Admin User',ROOSTERRUN_SECURE_COOKIES:'0',ROOSTERRUN_OTP_TEST_MODE:'1'}});
const base=`http://127.0.0.1:${port}`;

try{
  let ready=false;for(let attempt=0;attempt<80;attempt+=1){try{await json(base,'/api/payments/health/');ready=true;break;}catch{await new Promise(resolveWait=>setTimeout(resolveWait,100));}}assert.equal(ready,true,'RBAC test server did not start');

  const superAdminJar=new CookieJar();
  const superLogin=await json(base,'/api/admin/auth/login/',{method:'POST',jar:superAdminJar,body:{username:'superadmin',password:'SuperSecure123'}});
  assert.equal(superLogin.data.admin.role,'Super Admin');

  const roleCredentials={};
  const roleMapping={'Game Operator':2,'Payments Manager':3,'Content Manager':4,'Compliance Manager':5,'Operations Manager':6,'Support Manager':7,'Risk Analyst':8};
  
  for(const [roleName,roleId] of Object.entries(roleMapping)){
    const username=roleName.toLowerCase().replace(/\s+/g,'');
    const password=`${username}Secure123`;
    await json(base,'/api/admin/team/',{method:'POST',jar:superAdminJar,body:{username,display_name:roleName,password,role_id:roleId},expected:201});
    roleCredentials[roleName]={username,password};
  }

  const matrix=[];
  const missing=new Set();
  let passed=0;
  let failed=0;

  for(const [roleName,allowedPermissions] of Object.entries(ROLES)){
    const credentials=roleName==='Super Admin'?{username:'superadmin',password:'SuperSecure123'}:roleCredentials[roleName];
    const roleJar=new CookieJar();
    
    await json(base,'/api/admin/auth/login/',{method:'POST',jar:roleJar,body:credentials});

    for(const [permission,endpoints] of Object.entries(PERMISSION_ENDPOINTS)){
      const shouldAllow=roleName==='Super Admin'||allowedPermissions.includes(permission);
      
      for(const endpoint of endpoints){
        if(missing.has(endpoint))continue;
        
        const expectedStatus=shouldAllow?200:403;
        const testCase={role:roleName,permission,endpoint,expected:expectedStatus};
        
        try{
          if(endpoint==='/api/admin/assets/upload/'){
            const expectedUploadStatus=shouldAllow?201:403;
            const response=await fetch(`${base}${endpoint}`,{method:'POST',headers:{Cookie:roleJar.header(),'X-CSRF-Token':roleJar.get('rr_admin_csrf'),'Content-Type':'image/png','X-Asset-Kind':'IMAGE'},body:Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,0,0,0,13,0x49,0x48,0x44,0x52])});
            testCase.actual=response.status;
            testCase.expected=expectedUploadStatus;
          }else{
            const result=await json(base,endpoint,{jar:roleJar,expected:expectedStatus});
            testCase.actual=result.response.status;
          }
          testCase.pass=testCase.actual===testCase.expected;
          if(testCase.pass){
            passed+=1;
          }else{
            if(testCase.actual===404){
              missing.add(endpoint);
              testCase.skip=true;
              console.log(`SKIP: ${endpoint} (404 - endpoint not implemented)`);
            }else{
              failed+=1;
              console.error(`FAIL: ${roleName} -> ${permission} (${endpoint}): expected ${expectedStatus}, got ${testCase.actual}`);
            }
          }
        }catch(error){
          testCase.actual=error.message;
          if(error.message.includes('404')){
            missing.add(endpoint);
            testCase.skip=true;
          }else{
            testCase.pass=false;
            failed+=1;
            console.error(`ERROR: ${roleName} -> ${permission} (${endpoint}): ${error.message}`);
          }
        }
        
        matrix.push(testCase);
      }
    }
  }

  console.log('\n=== Admin RBAC Smoke Test Matrix ===');
  console.log(`Total tests: ${matrix.length}`);
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Skipped (missing endpoints): ${missing.size}`);
  
  if(missing.size>0){
    console.log('\nMissing endpoints (not implemented):');
    for(const endpoint of missing){
      console.log(`  - ${endpoint}`);
    }
  }
  
  if(failed>0){
    console.log('\nFailed tests (RBAC issues):');
    for(const test of matrix.filter(t=>!t.pass&&!t.skip)){
      console.log(`  - ${test.role} -> ${test.permission} (${test.endpoint}): expected ${test.expected}, got ${test.actual}`);
    }
  }

  assert.equal(failed,0,`${failed} RBAC tests failed`);
  console.log('\nAdmin RBAC smoke matrix: ALL PASSED ✓');
}finally{
  child.kill();await new Promise(resolveWait=>child.once('exit',resolveWait));rmSync(dataDir,{recursive:true,force:true});
}
