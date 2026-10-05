#!/usr/bin/env node
/**
 * RoosterRun Test Runner
 * 
 * Orchestrates all test suites:
 * - Python unit tests (database, delivery, categories, feeds, approvals)
 * - Node.js integration tests (security, simulator, auth, payments, etc.)
 * - Compliance & audit tests (restrictions, reconciliation, postgres bootstrap)
 * 
 * Exit codes:
 * - 0: All tests passed
 * - 1: One or more tests failed
 */

import { spawn } from 'child_process';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

// Test suite definitions
const TEST_SUITES = {
  'Python Unit Tests': [
    { cmd: 'python3', args: ['tests/database-compat.py'], desc: 'Database compatibility' },
    { cmd: 'python3', args: ['tests/delivery-engine.py'], desc: 'Delivery engine' },
    { cmd: 'python3', args: ['tests/approval-demo.py'], desc: 'Approval demo' },
    { cmd: 'python3', args: ['tests/china-feed.py'], desc: 'China feed' },
    { cmd: 'python3', args: ['tests/game-categories.py'], desc: 'Game categories' },
  ],
  
  'Node.js Security & Static': [
    { cmd: 'node', args: ['tests/security-static.mjs'], desc: 'Security static checks' },
  ],
  
  'Node.js Integration Tests': [
    { cmd: 'node', args: ['tests/simulator.mjs'], desc: 'Simulator' },
    { cmd: 'node', args: ['tests/auth-engine.mjs'], desc: 'Auth engine' },
    { cmd: 'node', args: ['tests/manual-payments.mjs'], desc: 'Manual payments' },
    { cmd: 'node', args: ['tests/admin-console.mjs'], desc: 'Admin console' },
    { cmd: 'node', args: ['tests/cockfight-engine.mjs'], desc: 'Cockfight engine' },
    { cmd: 'node', args: ['tests/streaming-engine.mjs'], desc: 'Streaming engine' },
    { cmd: 'node', args: ['tests/compliance-engine.mjs'], desc: 'Compliance engine' },
    { cmd: 'node', args: ['tests/operations-engine.mjs'], desc: 'Operations engine' },
    { cmd: 'node', args: ['tests/support-engine.mjs'], desc: 'Support engine' },
    { cmd: 'node', args: ['tests/intelligence-engine.mjs'], desc: 'Intelligence engine' },
  ],
  
  'Node.js Production Readiness': [
    { cmd: 'node', args: ['tests/production-readiness.mjs'], desc: 'Production readiness' },
    { cmd: 'node', args: ['tests/resilience-load.mjs'], desc: 'Resilience load' },
  ],
  
  'Compliance & Audit Tests': [
    { cmd: 'python3', args: ['tests/restriction-monotonicity.py'], desc: 'Restriction monotonicity (A-01)' },
    { cmd: 'python3', args: ['tests/reconciliation-ledger.py'], desc: 'Reconciliation ledger (A-08)' },
    { cmd: 'python3', args: ['tests/postgres-bootstrap.py'], desc: 'PostgreSQL bootstrap (B-03)' },
  ],
};

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const failedSuites = [];

function runTest(suite, test) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    console.log(`  ▸ ${test.desc}...`);
    
    const proc = spawn(test.cmd, test.args, {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env }
    });
    
    let stdout = '';
    let stderr = '';
    
    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    proc.on('close', (code) => {
      const duration = ((Date.now() - startTime) / 1000).toFixed(2);
      totalTests++;
      
      if (code === 0) {
        console.log(`    ✓ ${test.desc} (${duration}s)`);
        passedTests++;
        resolve({ success: true, suite, test });
      } else {
        console.log(`    ✗ ${test.desc} (${duration}s) - Exit code: ${code}`);
        if (stdout) console.log(`      stdout: ${stdout.slice(0, 200)}${stdout.length > 200 ? '...' : ''}`);
        if (stderr) console.log(`      stderr: ${stderr.slice(0, 200)}${stderr.length > 200 ? '...' : ''}`);
        failedTests++;
        failedSuites.push({ suite, test: test.desc, code, stdout, stderr });
        resolve({ success: false, suite, test });
      }
    });
    
    proc.on('error', (error) => {
      console.log(`    ✗ ${test.desc} - Error: ${error.message}`);
      failedTests++;
      failedSuites.push({ suite, test: test.desc, error: error.message });
      resolve({ success: false, suite, test });
    });
  });
}

async function runAllTests() {
  console.log('🧪 RoosterRun Test Suite\n');
  console.log('═'.repeat(60));
  
  for (const [suiteName, tests] of Object.entries(TEST_SUITES)) {
    console.log(`\n📦 ${suiteName}`);
    console.log('─'.repeat(60));
    
    for (const test of tests) {
      await runTest(suiteName, test);
    }
  }
  
  console.log('\n' + '═'.repeat(60));
  console.log(`\n📊 Test Summary:`);
  console.log(`   Total:  ${totalTests}`);
  console.log(`   Passed: ${passedTests} ✓`);
  console.log(`   Failed: ${failedTests} ✗`);
  
  if (failedTests > 0) {
    console.log(`\n❌ Failed test suites:`);
    for (const failure of failedSuites) {
      console.log(`   • ${failure.suite}: ${failure.test}`);
      if (failure.code !== undefined) {
        console.log(`     Exit code: ${failure.code}`);
      }
      if (failure.error) {
        console.log(`     Error: ${failure.error}`);
      }
    }
    console.log('\n💡 Run individual tests to see full output:');
    console.log('   python3 tests/<test-name>.py');
    console.log('   node tests/<test-name>.mjs\n');
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!\n');
    process.exit(0);
  }
}

runAllTests().catch(error => {
  console.error('Test runner error:', error);
  process.exit(1);
});
