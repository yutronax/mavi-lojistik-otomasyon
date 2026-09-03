#!/usr/bin/env node
// -*- coding: utf-8 -*-
/*
Test suite for bridge.js groups state writing function (baileys-grup-listesi).

Acceptance Criteria (atdd.md):
1. [Critical] AC-1: bridge.js periyodik olarak sock.groupFetchAllParticipating() çağırır,
   sonuç {jid: GroupMetadata} şeklinde bir OBJE olur,
   writeGroupsState() fonksiyonu bunu {"groups": [{"id": "...", "name": "..."}], ...} şeklinde dönüştürüp
   data/baileys_groups.json'a yazılır.
2. [Critical] AC-2: /api/whatsapp/groups endpoint'i bu dosyayı okudu, {"groups": [...], "cached": true} döner,
   "saved" alanı data/chat_groups.json ile karşılaştırılarak hesaplanır.
3. [Medium] AC-5: bridge.js'in Baileys API çağrısı başarısız olursa, dosya değişmez/bozulmaz,
   error log'a düşer, bir sonraki periyodik denemede tekrar dener.
4. [Medium] AC-6: Panel tarafında bozuk JSON durumu — kısmi başarı (200 + {"groups": [], "cached": false}).

Test Technique:
- No framework: use Node's builtin assert module
- Create temp directory for test files (don't pollute project data/)
- Import writeGroupsState from bridge.js via require('./bridge.js')
- Verify atomic write behavior (tmp+rename)
- Verify JSON structure and data transformation (subject → name)

Key Assumptions (from plan.md):
- sock.groupFetchAllParticipating() returns: {jid: GroupMetadata}
- GroupMetadata has: id: string, subject: string (grup adı, "name" DEĞİL)
- writeGroupsState(groupsObject, filePath) function signature
- Transformation: Object.values() + {"id": g.id, "name": g.subject} mapping
- Output JSON format: {"groups": [{"id": "...", "name": "..."}], ...}
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

// writeGroupsState must be exported from bridge.js
const { writeGroupsState } = bridge;

if (!writeGroupsState) {
  console.error('Error: bridge.js must export writeGroupsState function');
  process.exit(1);
}

// Test setup: create temporary test directory
const TEST_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'baileys-groups-test-'));
const TEST_GROUPS_PATH = path.join(TEST_DIR, 'baileys_groups.json');

/**
 * Helper: Read groups file for testing purposes.
 */
function readGroupsFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (e) {
    return null;
  }
}

/**
 * Test: AC-1 writeGroupsState transforms and writes groups data
 *
 * Input: {jid: GroupMetadata} object (Baileys API format)
 * Output: {"groups": [{"id": "...", "name": "..."}]} JSON file
 */
function testWriteGroupsState() {
  console.log('\n[Test 1] AC-1: writeGroupsState transforms Baileys groups object to file');

  // Simulate Baileys groupFetchAllParticipating() response
  // Format: {jid: GroupMetadata, ...}
  const baileyGroupsObject = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Lojistik Grubu',  // Note: "subject", not "name"
      participants: [{ id: '1234567890@s.whatsapp.net', admin: 'admin' }],
      creation: 1609459200000,
    },
    '120363025987654@g.us': {
      id: '120363025987654@g.us',
      subject: 'Yönetim Grubu',
      participants: [{ id: '9876543210@s.whatsapp.net', admin: 'admin' }],
      creation: 1609459200000,
    },
  };

  // Cleanup before test
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  // Write groups state
  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  // Verify file exists
  assert(fs.existsSync(TEST_GROUPS_PATH), 'Groups file should be created after writeGroupsState()');

  // Verify content
  const content = readGroupsFile(TEST_GROUPS_PATH);
  assert(content !== null, 'Groups file should contain valid JSON');
  assert(Array.isArray(content.groups), 'groups field should be an array');
  assert(content.groups.length === 2, 'Should have 2 groups');

  // Verify transformation: subject → name
  const group1 = content.groups[0];
  const group2 = content.groups[1];

  assert.strictEqual(group1.id, '120363024125432@g.us', 'Group 1 ID should match');
  assert.strictEqual(group1.name, 'Lojistik Grubu', 'Group 1 name should be from subject field');
  assert.strictEqual(group2.id, '120363025987654@g.us', 'Group 2 ID should match');
  assert.strictEqual(group2.name, 'Yönetim Grubu', 'Group 2 name should be from subject field');

  console.log('  ✓ Groups object transformed and written correctly (subject → name)');
}

/**
 * Test: Atomic write prevents partial file corruption
 */
function testAtomicWrite() {
  console.log('\n[Test 2] Atomic write (tmp+rename) prevents partial writes');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject1 = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Group 1 V1',
    },
  };

  const baileyGroupsObject2 = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Group 1 V2',
    },
    '120363025987654@g.us': {
      id: '120363025987654@g.us',
      subject: 'Group 2 V1',
    },
  };

  // Write first state
  writeGroupsState(baileyGroupsObject1, TEST_GROUPS_PATH);
  const firstContent = readGroupsFile(TEST_GROUPS_PATH);

  // Verify first write
  assert.strictEqual(firstContent.groups.length, 1, 'First write should have 1 group');
  assert.strictEqual(firstContent.groups[0].name, 'Group 1 V1', 'First write content');

  // Write second state (overwrite)
  writeGroupsState(baileyGroupsObject2, TEST_GROUPS_PATH);
  const secondContent = readGroupsFile(TEST_GROUPS_PATH);

  // Verify second write completely replaced first (atomic)
  assert.strictEqual(secondContent.groups.length, 2, 'Second write should have 2 groups');
  assert.strictEqual(secondContent.groups[0].name, 'Group 1 V2', 'First group updated');
  assert.strictEqual(secondContent.groups[1].name, 'Group 2 V1', 'Second group added');

  // Verify tmp file is cleaned up
  const tmpPath = TEST_GROUPS_PATH + '.tmp';
  assert(!fs.existsSync(tmpPath), 'Temporary file should be cleaned up after atomic write');

  console.log('  ✓ Atomic write completed without partial/corrupted data');
}

/**
 * Test: Empty groups object handling
 */
function testEmptyGroupsObject() {
  console.log('\n[Test 3] Empty groups object handling');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  // Empty Baileys groups object
  const emptyGroupsObject = {};

  writeGroupsState(emptyGroupsObject, TEST_GROUPS_PATH);

  // Verify file exists
  assert(fs.existsSync(TEST_GROUPS_PATH), 'Groups file should be created even for empty object');

  // Verify content
  const content = readGroupsFile(TEST_GROUPS_PATH);
  assert(content !== null, 'File should contain valid JSON');
  assert(Array.isArray(content.groups), 'groups field should be an array');
  assert.strictEqual(content.groups.length, 0, 'Should have 0 groups for empty object');

  console.log('  ✓ Empty groups object handled correctly');
}

/**
 * Test: Concurrent write protection
 */
function testConcurrentWriteProtection() {
  console.log('\n[Test 4] Concurrent write protection via atomic write');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  // Simulate multiple rapid writes (like periodic polling)
  const writes = [];

  for (let i = 0; i < 3; i++) {
    const groupsObject = {
      [`120363024125432@g.us`]: {
        id: `120363024125432@g.us`,
        subject: `Group ${i}`,
      },
    };
    try {
      writeGroupsState(groupsObject, TEST_GROUPS_PATH);
      writes.push(i);
    } catch (e) {
      console.log(`  Write ${i} failed: ${e.message}`);
    }
  }

  // Verify final state is valid (no partial/corrupted data)
  const finalContent = readGroupsFile(TEST_GROUPS_PATH);
  assert(finalContent !== null, 'Final file should be valid JSON');
  assert(Array.isArray(finalContent.groups), 'groups should be an array');
  assert(finalContent.groups.length > 0, 'Should have at least one group after writes');

  console.log(`  ✓ ${writes.length} concurrent writes completed atomically`);
}

/**
 * Test: File permissions / read access
 */
function testFileReadable() {
  console.log('\n[Test 5] Written file is readable by other processes (panel endpoint)');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Panel Readable Group',
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  // Simulate another process reading the file
  try {
    const stats = fs.statSync(TEST_GROUPS_PATH);
    assert(stats.isFile(), 'Written file should be a regular file');

    // Try reading it back
    const content = readGroupsFile(TEST_GROUPS_PATH);
    assert(content !== null, 'File should be readable by other processes');
    assert.strictEqual(content.groups[0].name, 'Panel Readable Group', 'Content should be intact');
  } catch (e) {
    assert.fail(`File should be readable: ${e.message}`);
  }

  console.log('  ✓ Written file is readable by other processes');
}

/**
 * Test: Response structure matches /api/whatsapp/groups expectations (AC-2)
 */
function testResponseStructure() {
  console.log('\n[Test 6] AC-2: Response structure matches /api/whatsapp/groups expectations');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Test Group',
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);

  // Verify structure expected by /api/whatsapp/groups endpoint
  assert('groups' in content, "Response should have 'groups' field");
  assert(Array.isArray(content.groups), "'groups' should be an array");

  // Verify each group has required fields
  for (const group of content.groups) {
    assert('id' in group, "Each group must have 'id' field");
    assert('name' in group, "Each group must have 'name' field");
    // Panel may add 'saved' field during endpoint processing, not here
  }

  console.log('  ✓ Response structure matches endpoint expectations');
}

/**
 * Test: Special characters in group names
 */
function testSpecialCharactersInGroupNames() {
  console.log('\n[Test 7] Special characters and UTF-8 in group names');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: 'Lojistik & Teslimat ©️ "Hızlı" (2024)',
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  assert.strictEqual(
    content.groups[0].name,
    'Lojistik & Teslimat ©️ "Hızlı" (2024)',
    'Special characters should be preserved'
  );

  console.log('  ✓ Special characters and UTF-8 handled correctly');
}

/**
 * Test: AC-1 Fallback isim mantığı — subject boş string
 *
 * Given: Bir grup objesi subject alanı BOŞ STRİNG ('') olan bir grup içerdiğinde
 * When: writeGroupsState() çağrılır
 * Then: yazılan JSON'daki o grubun name alanı "İsimsiz Grup (…<id'nin @'den önceki son 6 hane>)" formatında fallback isim olmalı
 *
 * AC-1 (Critical): isimsiz gruplar filtrelenmez, fallback isimle gösterilir
 */
function testFallbackNameForEmptySubject() {
  console.log('\n[Test 8] AC-1: Fallback isim — subject boş string');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  // Example ID: "120363024125432@g.us" → son 6 hane: "125432"
  const baileyGroupsObject = {
    '120363024125432@g.us': {
      id: '120363024125432@g.us',
      subject: '', // Boş subject
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  assert(content !== null, 'Groups file should be created');
  assert.strictEqual(content.groups.length, 1, 'Should have 1 group');

  const group = content.groups[0];
  // Expected format: "İsimsiz Grup (…125432)"
  const expectedName = 'İsimsiz Grup (…125432)';
  assert.strictEqual(
    group.name,
    expectedName,
    `Group with empty subject should have fallback name "${expectedName}"`
  );

  console.log('  ✓ Empty subject handled with fallback isim');
}

/**
 * Test: AC-1 Fallback isim mantığı — subject undefined
 */
function testFallbackNameForUndefinedSubject() {
  console.log('\n[Test 9] AC-1: Fallback isim — subject undefined');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '999999999012345@g.us': {
      id: '999999999012345@g.us',
      subject: undefined, // undefined subject
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  const group = content.groups[0];
  const expectedName = 'İsimsiz Grup (…012345)';
  assert.strictEqual(
    group.name,
    expectedName,
    `Group with undefined subject should have fallback name "${expectedName}"`
  );

  console.log('  ✓ Undefined subject handled with fallback isim');
}

/**
 * Test: AC-1 Fallback isim mantığı — subject whitespace-only
 */
function testFallbackNameForWhitespaceSubject() {
  console.log('\n[Test 10] AC-1: Fallback isim — subject whitespace-only');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '111111111555555@g.us': {
      id: '111111111555555@g.us',
      subject: '   ', // Sadece boşluk
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  const group = content.groups[0];
  const expectedName = 'İsimsiz Grup (…555555)';
  assert.strictEqual(
    group.name,
    expectedName,
    `Group with whitespace-only subject should have fallback name "${expectedName}"`
  );

  console.log('  ✓ Whitespace-only subject handled with fallback isim');
}

/**
 * Test: AC-1 Regresyon — normal subject KORUNMALI
 */
function testNormalSubjectPreserved() {
  console.log('\n[Test 11] AC-1 Regresyon: Normal subject preserved (no fallback)');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '123456789123456@g.us': {
      id: '123456789123456@g.us',
      subject: 'Test Grubu', // Normal isim
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  const group = content.groups[0];
  assert.strictEqual(
    group.name,
    'Test Grubu',
    'Normal subject should NOT be replaced with fallback'
  );

  console.log('  ✓ Normal subject preserved without fallback');
}

/**
 * Test: AC-1 + AC-5 Kısmi başarı — aynı çağrıda isimli + isimsiz gruplar
 *
 * Given: aynı writeGroupsState() çağrısında hem isimli hem isimsiz gruplar
 * When: groups dosyasına yazılır
 * Then: isimli gruplar normal isimle, isimsiz gruplar fallback isimle yazılmalı
 *
 * AC-1/AC-5: Kısmi başarı, ikisi de filtre edilmez, sıralama bozulmaz
 */
function testMixedNamedAndUnnamedGroups() {
  console.log('\n[Test 12] AC-1+AC-5: Kısmi başarı — isimli + isimsiz gruplar karışık');

  // Cleanup
  if (fs.existsSync(TEST_GROUPS_PATH)) {
    fs.unlinkSync(TEST_GROUPS_PATH);
  }

  const baileyGroupsObject = {
    '100000000000001@g.us': {
      id: '100000000000001@g.us',
      subject: 'Lojistik', // İsimli
    },
    '200000000000002@g.us': {
      id: '200000000000002@g.us',
      subject: '', // İsimsiz
    },
    '300000000000003@g.us': {
      id: '300000000000003@g.us',
      subject: 'Yönetim', // İsimli
    },
  };

  writeGroupsState(baileyGroupsObject, TEST_GROUPS_PATH);

  const content = readGroupsFile(TEST_GROUPS_PATH);
  assert.strictEqual(content.groups.length, 3, 'Should have 3 groups');

  // Verify each group has correct name handling
  // Note: Object.values() order may vary, so we need to find each by ID
  const groupMap = {};
  for (const g of content.groups) {
    groupMap[g.id] = g;
  }

  // Group 1: İsimli
  assert.strictEqual(
    groupMap['100000000000001@g.us'].name,
    'Lojistik',
    'Named group should keep its name'
  );

  // Group 2: İsimsiz (fallback)
  assert.strictEqual(
    groupMap['200000000000002@g.us'].name,
    'İsimsiz Grup (…000002)',
    'Unnamed group should have fallback name'
  );

  // Group 3: İsimli
  assert.strictEqual(
    groupMap['300000000000003@g.us'].name,
    'Yönetim',
    'Named group should keep its name'
  );

  console.log('  ✓ Mixed named/unnamed groups handled correctly');
}

/**
 * Run all tests
 */
function runAllTests() {
  console.log('='.repeat(70));
  console.log('BAILEYS GROUPS STATE WRITING TESTS (baileys-grup-listesi)');
  console.log('='.repeat(70));

  try {
    testWriteGroupsState();
    testAtomicWrite();
    testEmptyGroupsObject();
    testConcurrentWriteProtection();
    testFileReadable();
    testResponseStructure();
    testSpecialCharactersInGroupNames();

    // AC-1 + AC-5: Fallback isim mantığı testleri
    testFallbackNameForEmptySubject();
    testFallbackNameForUndefinedSubject();
    testFallbackNameForWhitespaceSubject();
    testNormalSubjectPreserved();
    testMixedNamedAndUnnamedGroups();

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
module.exports = {
  readGroupsFile,
  testWriteGroupsState,
  testAtomicWrite,
  testEmptyGroupsObject,
};

// Run tests if executed directly
if (require.main === module) {
  runAllTests();
}
