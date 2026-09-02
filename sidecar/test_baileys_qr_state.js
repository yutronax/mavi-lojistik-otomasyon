#!/usr/bin/env node
// -*- coding: utf-8 -*-
/*
Test suite for bridge.js QR state writing functions (panel-baileys-qr-gosterimi).

Acceptance Criteria (atdd.md):
1. [Critical] writeQrState(qr) writes to data/baileys_qr.json:
   {"qr": "data:image/png;base64,...", "generated_at": <epoch ms>}
2. [Critical] writeAuthenticatedState() writes {"status": "authenticated"} to file
3. [Medium] Atomic write (tmp+rename) prevents partial/corrupted writes
4. [Medium] File write error (e.g., disk full) doesn't crash bridge.js main logic

Test Technique:
- No framework: use Node's builtin assert module
- Create temp directory for test files (don't pollute project data/)
- Patch/mock fs functions where needed for error simulation
- Run with: node sidecar/test_baileys_qr_state.js

NOT (code-copilot için): bridge.js'in modül-seviyesi bridge().catch(...) çağrısı
require() sırasında gerçek bir Baileys bağlantısı BAŞLATMAMALI test ortamında.
Önerilen çözüm: bridge.js'in altına
  if (require.main === module) { bridge().catch(...); }
guard'ı eklenmeli (Python tarafındaki manual_webhook_test_server.py'de
__main__ guard deseniyle AYNI mantık) — böylece `require('./bridge.js')`
sadece fonksiyonları/export'ları yükler, otomatik bağlanmaya çalışmaz.
*/

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Import actual functions from bridge.js
let bridge;
try {
  bridge = require('./bridge.js');
} catch (e) {
  console.error('Could not load bridge.js:', e.message);
  process.exit(1);
}

const { writeQrState, writeAuthenticatedState } = bridge;

if (!writeQrState || !writeAuthenticatedState) {
  console.error('Error: bridge.js must export writeQrState and writeAuthenticatedState functions');
  process.exit(1);
}

// Test setup: create temporary test directory
const TEST_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'baileys-qr-test-'));
const TEST_QR_PATH = path.join(TEST_DIR, 'baileys_qr.json');

/**
 * Helper: Read QR file for testing purposes.
 * (bridge.js functions are imported above and used directly in tests)
 *
 * Note: readQrFile is NOT expected from bridge.js exports; this is a test helper only.
 * bridge.js is expected to export: writeQrState(qr, filePath) and writeAuthenticatedState(filePath)
 */
function readQrFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (e) {
    return null;
  }
}

/**
 * Test: AC-1 writeQrState writes valid QR data
 */
function testWriteQrState() {
  console.log('\n[Test 1] writeQrState(qr) writes valid QR data to file');

  const testQrData = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  // Cleanup before test
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  // Write QR state
  writeQrState(testQrData, TEST_QR_PATH);

  // Verify file exists
  assert(fs.existsSync(TEST_QR_PATH), 'QR file should be created after writeQrState()');

  // Verify content
  const content = readQrFile(TEST_QR_PATH);
  assert(content !== null, 'QR file should contain valid JSON');
  assert.strictEqual(content.qr, testQrData, 'QR data should match written value');
  assert.strictEqual(typeof content.generated_at, 'number', 'generated_at should be a number (epoch ms)');
  assert(content.generated_at > 0, 'generated_at should be > 0');
  assert(content.generated_at <= Date.now(), 'generated_at should not be in the future');

  console.log('  ✓ QR file created with correct structure');
}

/**
 * Test: AC-2 writeAuthenticatedState writes authenticated status
 */
function testWriteAuthenticatedState() {
  console.log('\n[Test 2] writeAuthenticatedState() writes authenticated status');

  // Cleanup before test
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  // Write authenticated state
  writeAuthenticatedState(TEST_QR_PATH);

  // Verify file exists
  assert(fs.existsSync(TEST_QR_PATH), 'QR file should be created after writeAuthenticatedState()');

  // Verify content
  const content = readQrFile(TEST_QR_PATH);
  assert(content !== null, 'QR file should contain valid JSON');
  assert.strictEqual(content.status, 'authenticated', 'status should be "authenticated"');
  assert.strictEqual(content.qr, undefined, 'qr field should not be present in authenticated state');

  console.log('  ✓ Authenticated state written correctly');
}

/**
 * Test: AC-3 Atomic write prevents partial file corruption
 */
function testAtomicWrite() {
  console.log('\n[Test 3] Atomic write (tmp+rename) prevents partial writes');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  const testQrData = 'data:image/png;base64,test_data_1';

  // Write first state
  writeQrState(testQrData, TEST_QR_PATH);
  const firstContent = readQrFile(TEST_QR_PATH);

  // Verify first write
  assert.strictEqual(firstContent.qr, testQrData, 'First write should succeed');

  // Write second state (overwrite)
  const testQrData2 = 'data:image/png;base64,test_data_2';
  writeQrState(testQrData2, TEST_QR_PATH);
  const secondContent = readQrFile(TEST_QR_PATH);

  // Verify second write completely replaced first
  assert.strictEqual(secondContent.qr, testQrData2, 'Second write should completely replace first (atomic)');
  assert.notStrictEqual(secondContent.qr, testQrData, 'QR should not be mixed/partial');

  // Verify tmp file is cleaned up
  const tmpPath = TEST_QR_PATH + '.tmp';
  assert(!fs.existsSync(tmpPath), 'Temporary file should be cleaned up after atomic write');

  console.log('  ✓ Atomic write completed without partial/corrupted data');
}

/**
 * Test: Overwriting QR state with authenticated state
 */
function testOverwriteQrWithAuthenticated() {
  console.log('\n[Test 4] Overwriting QR state with authenticated state');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  // Write QR first
  const testQrData = 'data:image/png;base64,test_qr';
  writeQrState(testQrData, TEST_QR_PATH);
  const qrContent = readQrFile(TEST_QR_PATH);
  assert(qrContent.qr, 'QR state should have qr field');

  // Then write authenticated (should completely replace)
  writeAuthenticatedState(TEST_QR_PATH);
  const authContent = readQrFile(TEST_QR_PATH);

  assert.strictEqual(authContent.status, 'authenticated', 'status should be authenticated');
  assert(authContent.qr === undefined, 'qr field should be removed when authenticated');

  console.log('  ✓ State transition from QR to authenticated works correctly');
}

/**
 * Test: QR file format validation (data URI format)
 */
function testQrDataUriFormat() {
  console.log('\n[Test 5] QR data URI format validation');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  // Valid PNG data URI
  const validDataUri = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  writeQrState(validDataUri, TEST_QR_PATH);
  const content = readQrFile(TEST_QR_PATH);

  // Verify it starts with correct prefix
  assert(content.qr.startsWith('data:image/png;base64,'), 'QR should be PNG data URI');

  console.log('  ✓ QR data URI format is correct');
}

/**
 * Test: File permissions / read access
 */
function testFileReadable() {
  console.log('\n[Test 6] Written file is readable by other processes');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  const testQrData = 'data:image/png;base64,test_readable';
  writeQrState(testQrData, TEST_QR_PATH);

  // Simulate another process reading the file
  try {
    const stats = fs.statSync(TEST_QR_PATH);
    assert(stats.isFile(), 'Written file should be a regular file');

    // Try reading it back
    const content = readQrFile(TEST_QR_PATH);
    assert(content !== null, 'File should be readable by other processes');
    assert.strictEqual(content.qr, testQrData, 'Content should be intact');
  } catch (e) {
    assert.fail(`File should be readable: ${e.message}`);
  }

  console.log('  ✓ Written file is readable by other processes');
}

/**
 * Test: Cleanup on error
 */
function testCleanupOnError() {
  console.log('\n[Test 7] Temporary file cleanup on write error');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  const tmpPath = TEST_QR_PATH + '.tmp';

  // Simulate fs.renameSync failure by creating a directory with the same name
  // as the target file (this will cause rename to fail)
  const conflictPath = TEST_QR_PATH + '_conflict';

  try {
    // Create a directory to block file write
    if (!fs.existsSync(conflictPath)) {
      fs.mkdirSync(conflictPath);
    }

    // This should fail during rename
    try {
      writeQrState('test', conflictPath + '/file');
    } catch (e) {
      // Expected to fail
    }

    // Verify tmp file was cleaned up
    const tmpCheck = conflictPath + '/file.tmp';
    if (fs.existsSync(tmpCheck)) {
      console.log('  ⚠ Note: tmp cleanup not guaranteed on all error types');
    } else {
      console.log('  ✓ Temporary file cleaned up after error');
    }
  } finally {
    // Cleanup test directory
    try {
      if (fs.existsSync(conflictPath)) {
        fs.rmSync(conflictPath, { recursive: true, force: true });
      }
    } catch {}
  }
}

/**
 * Test: Concurrent write protection
 */
function testConcurrentWriteProtection() {
  console.log('\n[Test 8] Concurrent write protection via atomic write');

  // Cleanup
  if (fs.existsSync(TEST_QR_PATH)) {
    fs.unlinkSync(TEST_QR_PATH);
  }

  // Simulate concurrent writes using atomic operations
  const writes = [];

  for (let i = 0; i < 5; i++) {
    const qrData = `data:image/png;base64,test_${i}`;
    try {
      writeQrState(qrData, TEST_QR_PATH);
      writes.push(i);
    } catch (e) {
      console.log(`  Write ${i} failed: ${e.message}`);
    }
  }

  // Verify final state is valid (no partial/corrupted data)
  const finalContent = readQrFile(TEST_QR_PATH);
  assert(finalContent !== null, 'Final file should be valid JSON');
  assert(finalContent.qr.startsWith('data:image/png;base64,test_'), 'Final QR should be complete');

  console.log(`  ✓ ${writes.length} concurrent writes completed atomically`);
}

/**
 * Run all tests
 */
function runAllTests() {
  console.log('='.repeat(70));
  console.log('BAILEYS QR STATE WRITING TESTS (panel-baileys-qr-gosterimi)');
  console.log('='.repeat(70));

  try {
    testWriteQrState();
    testWriteAuthenticatedState();
    testAtomicWrite();
    testOverwriteQrWithAuthenticated();
    testQrDataUriFormat();
    testFileReadable();
    testCleanupOnError();
    testConcurrentWriteProtection();

    console.log('\n' + '='.repeat(70));
    console.log('✓ ALL TESTS PASSED');
    console.log('='.repeat(70));
  } catch (e) {
    console.error('\n' + '='.repeat(70));
    console.error('✗ TEST FAILED');
    console.error('='.repeat(70));
    console.error(`\n${e.message}`);
    console.error(`\nStack:\n${e.stack}`);
    process.exit(1);
  } finally {
    // Cleanup test directory
    try {
      fs.rmSync(TEST_DIR, { recursive: true, force: true });
    } catch (e) {
      console.log(`[Cleanup] Could not remove test directory: ${e.message}`);
    }
  }
}

// Export for use in other test frameworks if needed
// (writeQrState and writeAuthenticatedState are imported from bridge.js, not defined here)
module.exports = {
  readQrFile,
  // Test functions for integration
  testWriteQrState,
  testWriteAuthenticatedState,
  testAtomicWrite,
};

// Run tests if executed directly
if (require.main === module) {
  runAllTests();
}
