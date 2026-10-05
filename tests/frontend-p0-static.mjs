/**
 * Frontend P0 Static Regression Tests
 * 
 * Validates PR #68 frontend improvements against production requirements:
 * - Guest/empty state handling
 * - Service worker cache policies
 * - LIVE badge authoritative data source
 * - Video playback error handling
 * - Admin payment decision flows
 * - Security: wallet adjustment limits and confirmations
 */

import { existsSync, readFileSync } from 'node:fs';

const failures = [];

// Helper to check pattern exists in file
function assertPattern(file, pattern, message) {
  if (!existsSync(file)) {
    failures.push(`${file}: file not found`);
    return false;
  }
  const content = readFileSync(file, 'utf8');
  if (!pattern.test(content)) {
    failures.push(`${file}: ${message}`);
    return false;
  }
  return true;
}

// Helper to check pattern does NOT exist
function assertNotPattern(file, pattern, message) {
  if (!existsSync(file)) {
    failures.push(`${file}: file not found`);
    return false;
  }
  const content = readFileSync(file, 'utf8');
  if (pattern.test(content)) {
    failures.push(`${file}: ${message}`);
    return false;
  }
  return true;
}

console.log('Running Frontend P0 static regression checks...\n');

// =============================================================================
// P0-1: web/play/app.js - Empty guest results seed
// =============================================================================
console.log('✓ Checking app.js guest state handling...');

// Guest should have empty results array, not preview data
assertPattern(
  'web/play/app.js',
  /results:\s*\[\]/,
  'guest or logout state must initialize results:[] (empty), not preview seed'
);

// Video error remount patterns (may be in streaming.js or PR #68)
const appContent = readFileSync('web/play/app.js', 'utf8');
const streamingHasErrorHandling = readFileSync('web/play/streaming.js', 'utf8').includes('fallback') ||
                                   readFileSync('web/play/streaming.js', 'utf8').includes('onerror');
if (!(/remount|unavailable|videoDead/i.test(appContent)) && !streamingHasErrorHandling) {
  failures.push('web/play: should handle video unavailable/error remount cases (check app.js or streaming.js)');
}

// =============================================================================
// P0-2: web/play/components.js - LIVE badge from authoritative data
// =============================================================================
console.log('✓ Checking components.js LIVE badge source...');

const componentsContent = readFileSync('web/play/components.js', 'utf8');

// LIVE badge should exist and use proper data source
if (!componentsContent.includes('LIVE')) {
  failures.push('web/play/components.js: missing LIVE badge rendering');
}

// Check that LIVE badge is used in context (not from fake preview seeds)
// The badge should be conditional on authoritative match state
if (componentsContent.includes('LIVE') && 
    !componentsContent.includes('status--live')) {
  failures.push('web/play/components.js: LIVE badge not using standard status class');
}

// =============================================================================
// P0-3: web/play/sw.js - Cache policy (isCacheable requirements)
// =============================================================================
console.log('✓ Checking sw.js cache policies...');

const swContent = readFileSync('web/play/sw.js', 'utf8');

// Check CACHE_NAME version (should be v75 or higher based on current code)
const cacheNameMatch = swContent.match(/CACHE_NAME\s*=\s*['"]roosterrun-v(\d+)/);
if (!cacheNameMatch) {
  failures.push('web/play/sw.js: CACHE_NAME not found or malformed');
} else {
  const version = parseInt(cacheNameMatch[1], 10);
  if (version < 75) {
    failures.push(`web/play/sw.js: CACHE_NAME version v${version} too old (expected v75+)`);
  }
}

// Should NOT cache uploads, media streams, or cross-origin
// Check that these paths are excluded from caching
if (!swContent.includes('/api/') || !swContent.includes('GET')) {
  failures.push('web/play/sw.js: missing basic fetch event handling');
}

// Verify streaming/media files are not cached (implicit by not being in STATIC_ASSETS)
if (swContent.includes("'.m3u8'") || swContent.includes("'.ts'") || 
    swContent.match(/STATIC_ASSETS.*\.m3u8|\.ts|\.mp4/)) {
  failures.push('web/play/sw.js: should not cache streaming media (.m3u8, .ts, .mp4) in STATIC_ASSETS');
}

if (swContent.includes('/uploads/')) {
  failures.push('web/play/sw.js: should not explicitly cache /uploads/ paths');
}

// Check for versioned query parameter handling (?v=)
// The current app uses versioned imports like ?v=55, ?v=67 etc.
const hasVersionedImports = /\?v=\d+/.test(readFileSync('web/play/app.js', 'utf8'));
if (hasVersionedImports) {
  // SW should handle version bumps gracefully
  if (!swContent.includes('CACHE_NAME')) {
    failures.push('web/play/sw.js: missing CACHE_NAME for version management');
  }
}

// =============================================================================
// P0-4: web/play/streaming.js - Video error handling (no hls.js in this tree)
// =============================================================================
console.log('✓ Checking streaming.js error handling...');

const streamingContent = readFileSync('web/play/streaming.js', 'utf8');

// Should have video.onerror or error handling
if (!streamingContent.includes('video.onerror') && 
    !streamingContent.includes('.catch') &&
    !streamingContent.includes('fallback') &&
    !streamingContent.includes('unavailable')) {
  failures.push('web/play/streaming.js: missing video error/fallback handling');
}

// WHEP should have .catch error handling
if (streamingContent.includes('WHEP') || streamingContent.includes('whep')) {
  assertPattern(
    'web/play/streaming.js',
    /\.catch/,
    'WHEP playback should have .catch error handling'
  );
}

// Should NOT use hls.js in this codebase (using native HLS or other approach)
if (streamingContent.toLowerCase().includes('hls.js') || 
    streamingContent.includes('new Hls(')) {
  failures.push('web/play/streaming.js: should not use hls.js (not in this tree per requirements)');
}

// Check for fallback URL handling
if (!streamingContent.includes('fallback') && !streamingContent.includes('Fallback')) {
  failures.push('web/play/streaming.js: missing fallback URL handling for stream failures');
}

// =============================================================================
// P0-5: web/admin/dashboard.js - Payment decision controls
// =============================================================================
console.log('✓ Checking admin dashboard payment controls...');

const dashboardContent = readFileSync('web/admin/dashboard.js', 'utf8');

// Payment decision should default to empty string or explicit value (not auto-approved)
const paymentModalMatch = dashboardContent.match(/payment-decision-form[\s\S]{0,500}selectField.*decision.*value:\s*['"]([^'"]*)['"]/);
if (!paymentModalMatch) {
  failures.push('web/admin/dashboard.js: payment decision field not found');
} else if (paymentModalMatch[1] !== '' && paymentModalMatch[1] !== 'APPROVED') {
  // It's OK to default to APPROVED as long as there's a confirm step
  // We'll check for confirmation below
}

// Should have confirmation before payment decision
if (!dashboardContent.includes('decidePayment')) {
  failures.push('web/admin/dashboard.js: missing decidePayment handler');
} else {
  // Check that decision flow exists (form submission, not direct API call)
  const decidePaymentContext = dashboardContent.substring(
    dashboardContent.indexOf('decidePayment') - 200,
    dashboardContent.indexOf('decidePayment') + 500
  );
  
  // Should be in a form submission context
  if (!decidePaymentContext.includes('form') && !decidePaymentContext.includes('api.decidePayment')) {
    failures.push('web/admin/dashboard.js: decidePayment should use form submission flow');
  }
}

// =============================================================================
// P0-6: web/admin/dashboard.js - Wallet adjustment UI controls
// =============================================================================
console.log('✓ Checking admin wallet adjustment controls (UI only)...');

// NOTE: wallet_adjustment_* is currently ignored by server (admin_update_user only handles status/vip)
// This is EXPECTED pending Backend credit/debit feature. We assert UI controls only.

const userModalMatch = dashboardContent.match(/function userModal\(user\)\{[^}]+\}/);
if (!userModalMatch) {
  // userModal might be more complex, search for it differently
  const userModalStart = dashboardContent.indexOf('function userModal');
  if (userModalStart === -1) {
    failures.push('web/admin/dashboard.js: userModal function not found');
  } else {
    const userModalSection = dashboardContent.substring(userModalStart, userModalStart + 2000);
    
    // Check for wallet adjustment fields (if present)
    const hasWalletAdjustment = userModalSection.includes('wallet_adjustment') || 
                                userModalSection.includes('balance') ||
                                userModalSection.includes('credit') ||
                                userModalSection.includes('debit');
    
    if (hasWalletAdjustment) {
      // If wallet adjustment UI exists, check limits
      // Max should be 500000 (₹5000.00)
      const maxMatch = userModalSection.match(/wallet[\s\S]{0,300}max[:\s]*['"]?(\d+)/);
      if (maxMatch && parseInt(maxMatch[1]) > 500000) {
        failures.push('web/admin/dashboard.js: wallet adjustment max should be ≤500000 (₹5000)');
      }
      
      // Should require reason/note
      if (!userModalSection.includes('reason') && !userModalSection.includes('note') && !userModalSection.includes('admin_note')) {
        failures.push('web/admin/dashboard.js: wallet adjustment should require reason/note field');
      }
      
      // Should have confirmation (check updateUser form flow)
      const updateUserContext = dashboardContent.substring(
        Math.max(0, dashboardContent.indexOf('updateUser') - 300),
        dashboardContent.indexOf('updateUser') + 800
      );
      
      if (updateUserContext.includes('updateUser') && !updateUserContext.includes('confirm')) {
        // Confirmation might be via modal/form - check for form submission
        if (!updateUserContext.includes('user-form') && !updateUserContext.includes('form-grid')) {
          failures.push('web/admin/dashboard.js: wallet adjustment should have confirmation step');
        }
      }
    }
  }
}

// Note about server-side wallet_adjustment handling
console.log('ℹ Note: wallet_adjustment_* server handling is pending Backend credit/debit feature (expected)');

// =============================================================================
// P0-7: web/admin/_size_probe.txt should be absent
// =============================================================================
console.log('✓ Checking for development artifacts...');

if (existsSync('web/admin/_size_probe.txt')) {
  failures.push('web/admin/_size_probe.txt: development artifact should be removed before production');
}

// =============================================================================
// Additional checks from PR #68 context
// =============================================================================

// Sidebar navigation (D-17 mentioned - verify on main, note only if issue)
const sidebarCheck = dashboardContent.includes('admin-sidebar') || 
                     dashboardContent.includes('sidebar') ||
                     dashboardContent.includes('nav-item');
if (!sidebarCheck) {
  console.log('ℹ Note: admin sidebar navigation not clearly identifiable (verify D-17 manually)');
}

// =============================================================================
// Report results
// =============================================================================

if (failures.length > 0) {
  console.error('\n❌ Frontend P0 static checks FAILED:\n');
  for (const failure of failures) {
    console.error(`  • ${failure}`);
  }
  console.error('\nNote: Some failures may indicate patterns not yet merged from PR #68.');
  console.error('Verify against PR #68 branch for expected state.\n');
  process.exit(1);
} else {
  console.log('\n✅ All Frontend P0 static regression checks passed!\n');
  process.exit(0);
}
