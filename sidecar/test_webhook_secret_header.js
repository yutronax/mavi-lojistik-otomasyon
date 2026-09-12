#!/usr/bin/env node
// -*- coding: utf-8 -*-
/*
Test suite for bridge.js X-Webhook-Secret header handling (baileys-sidecar-webhook-secret-header).

Acceptance Criteria (from atdd.md):
1. [Critical] AC-1: Given WEBHOOK_SHARED_SECRET env var is defined, When postToWebhook(messages) is called,
   Then fetch request headers must contain X-Webhook-Secret: <secret value>.
2. [Critical] AC-2: Given WEBHOOK_SHARED_SECRET is undefined/empty, When postToWebhook is called,
   Then header is not sent/empty AND process logs a warning (at startup, once).
3. [Critical] AC-S1 (threat-model): Given WEBHOOK_SHARED_SECRET has a defined value,
   When bridge.js calls console.log/error/warn, Then the ACTUAL SECRET VALUE must never appear
   in any log output — only "defined/undefined" status is permitted.

Test Technique:
- Node's builtin assert module
- Mock global.fetch to capture headers
- Mock console.log/error/warn to verify secret logging behavior
- Direct require('./bridge.js')
- Verify postToWebhook is exported (or not)
- Clean up mocks after each test to prevent cross-test pollution
*/

const assert = require('assert');

// Import bridge.js
let bridge;
try {
  bridge = require('./bridge.js');
} catch (e) {
  console.error('Could not load bridge.js:', e.message);
  process.exit(1);
}

/**
 * Preserve original fetch and console methods for restoration
 */
const originalFetch = global.fetch;
const originalConsoleLog = console.log;
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

/**
 * Test: AC-1 postToWebhook is exported from bridge.js
 */
function testPostToWebhookExported() {
  console.log('\n[Test 1] AC-1: postToWebhook function must be exported from bridge.js');

  if (typeof bridge.postToWebhook !== 'function') {
    console.error('  ✗ FAIL: postToWebhook is not exported or not a function');
    console.error('  Exported properties:', Object.keys(bridge));
    throw new Error('postToWebhook must be exported for testability');
  }

  console.log('  ✓ postToWebhook is exported and callable');
}

/**
 * Test: AC-1 postToWebhook adds X-Webhook-Secret header when WEBHOOK_SHARED_SECRET is defined
 */
async function testPostToWebhookHeaderWithSecret() {
  console.log('\n[Test 2] AC-1: postToWebhook includes X-Webhook-Secret header when env var is defined');

  // Setup: set environment variable
  const testSecret = 'super-secret-value-12345';
  process.env.WEBHOOK_SHARED_SECRET = testSecret;

  let capturedHeaders = null;
  let capturedUrl = null;
  let capturedOptions = null;

  // Mock fetch
  global.fetch = async (url, opts) => {
    capturedUrl = url;
    capturedOptions = opts;
    capturedHeaders = opts.headers || {};
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    // Call postToWebhook
    await bridge.postToWebhook([{ id: '1', text: 'test' }]);

    // Verify header was set
    assert(
      capturedHeaders['X-Webhook-Secret'] === testSecret,
      `X-Webhook-Secret header must be set to '${testSecret}', got '${capturedHeaders['X-Webhook-Secret']}'`
    );

    console.log(`  ✓ X-Webhook-Secret header correctly set to '${testSecret}'`);
  } finally {
    // Cleanup
    global.fetch = originalFetch;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Test: AC-2 postToWebhook does not send X-Webhook-Secret when env var is undefined
 */
async function testPostToWebhookNoHeaderWithoutSecret() {
  console.log('\n[Test 3] AC-2: postToWebhook does not send X-Webhook-Secret header when env var is undefined');

  // Ensure env var is NOT set
  delete process.env.WEBHOOK_SHARED_SECRET;

  let capturedHeaders = null;

  // Mock fetch
  global.fetch = async (url, opts) => {
    capturedHeaders = opts.headers || {};
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    // Call postToWebhook
    await bridge.postToWebhook([{ id: '1', text: 'test' }]);

    // Verify header is NOT set or is empty
    const headerValue = capturedHeaders['X-Webhook-Secret'];
    assert(
      headerValue === undefined || headerValue === null || headerValue === '',
      `X-Webhook-Secret header should not be set when env is undefined, got '${headerValue}'`
    );

    console.log('  ✓ X-Webhook-Secret header correctly omitted when env var is undefined');
  } finally {
    // Cleanup
    global.fetch = originalFetch;
  }
}

/**
 * Test: AC-2 postToWebhook logs a warning when WEBHOOK_SHARED_SECRET is undefined
 */
function testPostToWebhookWarnsAboutMissingSecret() {
  console.log('\n[Test 4] AC-2: postToWebhook logs a warning when WEBHOOK_SHARED_SECRET is undefined');

  const { execSync } = require('child_process');

  // Create a clean environment without WEBHOOK_SHARED_SECRET
  const env = { ...process.env };
  delete env.WEBHOOK_SHARED_SECRET;

  let output = '';

  try {
    // Run node in a subprocess with fresh require context and no WEBHOOK_SHARED_SECRET
    // This ensures bridge.js loads in a clean state where the startup warning will trigger
    // Use shell to redirect both stdout and stderr into a single capture
    // Note: console.warn writes to stderr, so we must merge stderr into stdout
    output = execSync('node -e "require(\'./bridge.js\')" 2>&1', {
      cwd: __dirname,
      env,
      encoding: 'utf-8',
      timeout: 5000,
      stdio: 'pipe',
    });
  } catch (e) {
    // Subprocess might fail due to dependencies (baileys, etc.), but warning should be in output
    output = e.stdout || e.message || '';
  }

  // Verify that the warning about WEBHOOK_SHARED_SECRET is in the subprocess output
  assert(
    output.includes('WEBHOOK_SHARED_SECRET'),
    `Expected startup warning about WEBHOOK_SHARED_SECRET in subprocess output.\nGot: "${output}"`
  );

  console.log('  ✓ Startup warning correctly logged when WEBHOOK_SHARED_SECRET is missing');
}

/**
 * Test: AC-S1 Secret value never appears in console.log/error/warn output
 */
async function testPostToWebhookDoesNotLogSecretValue() {
  console.log('\n[Test 5] AC-S1 (threat-model): Secret value never appears in any console output');

  const testSecret = 'super-secret-value-12345';
  process.env.WEBHOOK_SHARED_SECRET = testSecret;

  const capturedLogs = [];

  // Mock all console methods to capture output
  console.log = (...args) => {
    capturedLogs.push({ level: 'log', args });
  };

  console.error = (...args) => {
    capturedLogs.push({ level: 'error', args });
  };

  console.warn = (...args) => {
    capturedLogs.push({ level: 'warn', args });
  };

  // Mock fetch
  global.fetch = async (url, opts) => {
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    // Call postToWebhook
    await bridge.postToWebhook([{ id: '1', text: 'test message' }]);

    // Check that secret value never appears in any log
    for (const logEntry of capturedLogs) {
      for (const arg of logEntry.args) {
        const argString = String(arg);
        assert(
          !argString.includes(testSecret),
          `Secret value '${testSecret}' must not appear in console.${logEntry.level}('${argString}')`
        );
      }
    }

    console.log = originalConsoleLog;
    console.log('  ✓ Secret value never appears in any console output');
  } finally {
    // Cleanup
    global.fetch = originalFetch;
    console.log = originalConsoleLog;
    console.error = originalConsoleError;
    console.warn = originalConsoleWarn;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Test: AC-1/AC-2 Fetch is called with correct URL
 */
async function testPostToWebhookFetchUrl() {
  console.log('\n[Test 6] postToWebhook calls fetch with WEBHOOK_URL');

  process.env.WEBHOOK_SHARED_SECRET = 'test-secret';
  let capturedUrl = null;

  // Mock fetch
  global.fetch = async (url, opts) => {
    capturedUrl = url;
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    await bridge.postToWebhook([{ id: '1', text: 'test' }]);

    // URL should be from env or default
    assert(
      capturedUrl !== null,
      'fetch must be called with a URL'
    );

    console.log(`  ✓ fetch called with URL: ${capturedUrl}`);
  } finally {
    global.fetch = originalFetch;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Test: postToWebhook handles fetch errors gracefully
 */
async function testPostToWebhookErrorHandling() {
  console.log('\n[Test 7] postToWebhook handles fetch errors gracefully (no crash)');

  process.env.WEBHOOK_SHARED_SECRET = 'test-secret';

  const consoleLogs = [];
  console.error = (msg) => {
    consoleLogs.push(msg);
  };

  // Mock fetch to throw error
  global.fetch = async (url, opts) => {
    throw new Error('Network error: connection refused');
  };

  try {
    // Should not throw (error handled internally)
    await bridge.postToWebhook([{ id: '1', text: 'test' }]);

    console.error = originalConsoleError;
    console.log('  ✓ postToWebhook handles fetch error without crashing');
  } finally {
    global.fetch = originalFetch;
    console.error = originalConsoleError;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Test: X-Webhook-Secret header preserves exact secret value (no encoding/mutation)
 */
async function testPostToWebhookHeaderExactValue() {
  console.log('\n[Test 8] X-Webhook-Secret header value matches exactly (no encoding/mutation)');

  const testSecret = 'secret-with-special-chars-!@#$%^&*()*';
  process.env.WEBHOOK_SHARED_SECRET = testSecret;

  let capturedHeaders = null;

  // Mock fetch
  global.fetch = async (url, opts) => {
    capturedHeaders = opts.headers || {};
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    await bridge.postToWebhook([{ id: '1' }]);

    assert.strictEqual(
      capturedHeaders['X-Webhook-Secret'],
      testSecret,
      'Header value must match secret exactly (case-sensitive, no encoding changes)'
    );

    console.log('  ✓ X-Webhook-Secret header value is exact match (no mutation)');
  } finally {
    global.fetch = originalFetch;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Test: Content-Type header is still present when X-Webhook-Secret is added
 */
async function testPostToWebhookPreservesContentType() {
  console.log('\n[Test 9] X-Webhook-Secret addition does not remove Content-Type header');

  process.env.WEBHOOK_SHARED_SECRET = 'test-secret';
  let capturedHeaders = null;

  // Mock fetch
  global.fetch = async (url, opts) => {
    capturedHeaders = opts.headers || {};
    return { ok: true, status: 200, statusText: 'OK' };
  };

  try {
    await bridge.postToWebhook([{ id: '1' }]);

    assert(
      capturedHeaders['Content-Type'] === 'application/json',
      'Content-Type header must still be application/json'
    );

    console.log('  ✓ Content-Type header is preserved as application/json');
  } finally {
    global.fetch = originalFetch;
    delete process.env.WEBHOOK_SHARED_SECRET;
  }
}

/**
 * Run all tests
 */
async function runAllTests() {
  console.log('='.repeat(70));
  console.log('WEBHOOK SECRET HEADER TESTS (baileys-sidecar-webhook-secret-header)');
  console.log('='.repeat(70));

  try {
    testPostToWebhookExported();
    await testPostToWebhookHeaderWithSecret();
    await testPostToWebhookNoHeaderWithoutSecret();
    await testPostToWebhookWarnsAboutMissingSecret();
    await testPostToWebhookDoesNotLogSecretValue();
    await testPostToWebhookFetchUrl();
    await testPostToWebhookErrorHandling();
    await testPostToWebhookHeaderExactValue();
    await testPostToWebhookPreservesContentType();

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
  }
}

// Export for use in other test frameworks if needed
module.exports = {
  testPostToWebhookExported,
  testPostToWebhookHeaderWithSecret,
  testPostToWebhookNoHeaderWithoutSecret,
};

// Run tests if executed directly
if (require.main === module) {
  runAllTests().catch((e) => {
    console.error('Unexpected error:', e);
    process.exit(1);
  });
}
