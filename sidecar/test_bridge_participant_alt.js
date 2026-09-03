#!/usr/bin/env node
/**
 * Test suite for baileys-pro-model-kaldir-ve-blacklist-lid-fix: participantAlt support in bridge.js
 *
 * Acceptance Criteria:
 * 3. [Critical] Given `sidecar/bridge.js`'in `toWhapiShape()` fonksiyonu bir
 *    grup mesajı işliyor ve `msg.key.participantAlt` alanı DOLU (gerçek
 *    telefon numarası), When mesaj dönüştürülür, Then hem `from` alanı hem
 *    de (dolaylı olarak) blacklist kontrolüne giden değer `participantAlt`
 *    olmalı, LID (`participant`) DEĞİL.
 * 4. [High] Given `msg.key.participantAlt` alanı BOŞ/undefined (Baileys'in
 *    bu alanı her zaman sağlama garantisi yok), When mesaj dönüştürülür,
 *    Then mevcut davranışa (regresyon olmadan) geri dönülmeli — `from`
 *    alanı `participant` (LID) olarak dolmaya devam etmeli, mesaj İŞLENMEYE
 *    devam etmeli (reddedilmemeli).
 * 5. [Medium] Given kara listeye gerçek bir telefon numarası eklenmiş VE
 *    gelen mesajın `participantAlt`'ı bu numarayla eşleşiyor, When
 *    `toWhapiShape()` çalışır, Then mesaj dönüştürülmesi başarılı olmalı
 *    ve `senderName` hesaplaması da yeni `senderJid` değerini (participantAlt
 *    öncelikli) kullanmalı.
 *
 * Technique:
 * - Same pattern as test_bridge_reliability.js
 * - Node builtin assert
 * - require('./bridge.js') to get toWhapiShape
 * - Hard exit on failure (process.exit(1)) — no fake green tests
 */

const assert = require('assert');
const path = require('path');

// Import toWhapiShape from bridge.js
// NOTE: toWhapiShape must be exported from module.exports in bridge.js
// Currently (pre-implementation), it is NOT exported — this test assumes
// it will be added to module.exports as part of the implementation.
let toWhapiShape;
try {
  const bridge = require('./bridge.js');
  toWhapiShape = bridge.toWhapiShape;
  if (!toWhapiShape) {
    console.error('[FATAL] toWhapiShape is not exported from bridge.js');
    console.error('Implementation note: Add toWhapiShape to module.exports in bridge.js');
    process.exit(1);
  }
} catch (e) {
  console.error('[FATAL] Failed to load bridge.js:', e.message);
  process.exit(1);
}

/**
 * AC-3: participantAlt (real phone number) takes priority over participant (LID)
 */
function test_ac3_participantAlt_takes_priority() {
  const msg = {
    key: {
      remoteJid: '905070096982-1234567890@g.us',  // Group
      participant: '905070096982@lid',             // LID (should NOT be used)
      participantAlt: '905070096982@s.whatsapp.net', // Real phone (should be used)
      id: 'test_ac3_123'
    },
    message: {
      conversation: 'Test message for participantAlt priority'
    },
    messageTimestamp: 1234567890
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should return a non-null object for valid message');

  // Verify that 'from' field contains participantAlt, not participant (LID)
  assert.strictEqual(
    result.from,
    '905070096982@s.whatsapp.net',
    `AC-3 FAILED: from should be participantAlt value, got "${result.from}"`
  );

  // Verify senderName is derived from participantAlt (the numeric part before @)
  const expectedSenderName = '905070096982';
  assert.strictEqual(
    result.sender_name,
    expectedSenderName,
    `AC-3 FAILED: sender_name should be derived from participantAlt, got "${result.sender_name}"`
  );

  console.log('✓ AC-3 PASSED: participantAlt takes priority over participant (LID)');
}

/**
 * AC-4: Regression — when participantAlt is undefined, fallback to participant (LID)
 * No rejection, message still processes.
 */
function test_ac4_no_participantAlt_fallback_to_participant() {
  const msg = {
    key: {
      remoteJid: '905070096982-1234567890@g.us',  // Group
      participant: '905070096982@lid',             // LID (fallback)
      // participantAlt: undefined  (omitted intentionally)
      id: 'test_ac4_123'
    },
    message: {
      conversation: 'Test message without participantAlt'
    },
    messageTimestamp: 1234567890
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should return non-null even without participantAlt');

  // Verify that 'from' field contains participant (LID) when participantAlt is missing
  assert.strictEqual(
    result.from,
    '905070096982@lid',
    `AC-4 FAILED: from should fall back to participant when participantAlt missing, got "${result.from}"`
  );

  // Message should not be rejected
  assert.strictEqual(
    result.type,
    'text',
    'AC-4 FAILED: message should still be processed (type should be "text")'
  );

  console.log('✓ AC-4 PASSED: Without participantAlt, fallback to participant (LID) works, no rejection');
}

/**
 * AC-5: senderName calculation uses the new senderJid (participantAlt priority)
 */
function test_ac5_senderName_uses_new_senderJid() {
  const msg = {
    key: {
      remoteJid: '905070096982-1234567890@g.us',  // Group
      participant: '905070096982@lid',             // LID
      participantAlt: '905070096982@s.whatsapp.net', // Real phone
      id: 'test_ac5_123'
    },
    message: {
      conversation: 'Test for senderName calculation'
    },
    messageTimestamp: 1234567890
    // No pushName — senderName should be derived from senderJid
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should return non-null');

  // senderName should be extracted from participantAlt (new senderJid)
  // participantAlt is '905070096982@s.whatsapp.net', so sender_name should be '905070096982'
  const expectedSenderName = '905070096982';
  assert.strictEqual(
    result.sender_name,
    expectedSenderName,
    `AC-5 FAILED: sender_name should be "905070096982" (from participantAlt), got "${result.sender_name}"`
  );

  console.log('✓ AC-5 PASSED: senderName correctly calculated from new senderJid (participantAlt)');
}

/**
 * AC-5 Variant: pushName takes precedence over senderJid extraction
 */
function test_ac5_pushName_takes_precedence() {
  const msg = {
    key: {
      remoteJid: '905070096982-1234567890@g.us',
      participant: '905070096982@lid',
      participantAlt: '905070096982@s.whatsapp.net',
      id: 'test_ac5_pushname_123'
    },
    message: {
      conversation: 'Test with pushName'
    },
    pushName: 'Test User Name',
    messageTimestamp: 1234567890
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should return non-null');

  // pushName takes precedence
  assert.strictEqual(
    result.sender_name,
    'Test User Name',
    `AC-5 FAILED: sender_name should be pushName when available, got "${result.sender_name}"`
  );

  console.log('✓ AC-5 Variant PASSED: pushName precedence maintained');
}

/**
 * Edge case: participantAlt is empty string (falsy) — should fallback to participant
 */
function test_edge_case_empty_participantAlt() {
  const msg = {
    key: {
      remoteJid: '905070096982-1234567890@g.us',
      participant: '905070096982@lid',
      participantAlt: '',  // Empty string (falsy)
      id: 'test_edge_empty_123'
    },
    message: {
      conversation: 'Test with empty participantAlt'
    },
    messageTimestamp: 1234567890
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should handle empty participantAlt');

  // Should fallback to participant when participantAlt is empty
  assert.strictEqual(
    result.from,
    '905070096982@lid',
    `Edge case FAILED: empty participantAlt should fallback to participant, got "${result.from}"`
  );

  console.log('✓ Edge case PASSED: Empty participantAlt falls back to participant');
}

/**
 * Edge case: Non-group message (1:1 direct message) without participant
 */
function test_edge_case_direct_message() {
  const msg = {
    key: {
      remoteJid: '905070096982@s.whatsapp.net',  // Direct message (not group)
      participant: undefined,                    // Undefined in 1:1
      participantAlt: undefined,                 // Also undefined in 1:1
      id: 'test_direct_123'
    },
    message: {
      conversation: 'Direct message test'
    },
    messageTimestamp: 1234567890
  };

  const result = toWhapiShape(msg);
  assert.ok(result, 'toWhapiShape should handle direct messages');

  // For 1:1 messages, from should be the remoteJid itself
  assert.strictEqual(
    result.from,
    '905070096982@s.whatsapp.net',
    `Edge case FAILED: direct message from should be remoteJid, got "${result.from}"`
  );

  console.log('✓ Edge case PASSED: Direct message (1:1) handled correctly');
}

/**
 * Run all tests
 */
function runAllTests() {
  const tests = [
    { name: 'AC-3: participantAlt priority', fn: test_ac3_participantAlt_takes_priority },
    { name: 'AC-4: No participantAlt fallback', fn: test_ac4_no_participantAlt_fallback_to_participant },
    { name: 'AC-5: senderName calculation', fn: test_ac5_senderName_uses_new_senderJid },
    { name: 'AC-5 Variant: pushName precedence', fn: test_ac5_pushName_takes_precedence },
    { name: 'Edge case: empty participantAlt', fn: test_edge_case_empty_participantAlt },
    { name: 'Edge case: direct message', fn: test_edge_case_direct_message }
  ];

  let passed = 0;
  let failed = 0;

  console.log('\n========================================');
  console.log('Running bridge.js participantAlt tests');
  console.log('========================================\n');

  for (const test of tests) {
    try {
      test.fn();
      passed++;
    } catch (e) {
      console.error(`✗ ${test.name}: ${e.message}`);
      failed++;
    }
  }

  console.log(`\n========================================`);
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log('========================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

// Run tests
runAllTests();
