const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { packageFor, run } = require('../bin/scriexe.js');

const mappings = [
  ['darwin', 'arm64', 'scriexe-darwin-arm64'],
  ['darwin', 'x64', 'scriexe-darwin-x64'],
  ['linux', 'arm64', 'scriexe-linux-arm64'],
  ['linux', 'x64', 'scriexe-linux-x64'],
  ['win32', 'x64', 'scriexe-windows-x64'],
];

for (const [platform, arch, expected] of mappings) {
  test(`${platform}-${arch} resolves native package`, () => {
    assert.equal(packageFor(platform, arch), expected);
  });
}

test('unsupported target is actionable', () => {
  assert.throws(() => packageFor('win32', 'arm64'), /unsupported.*win32-arm64/i);
});

test('run forwards arguments and inherited terminal IO', () => {
  let call;
  const runtime = {
    platform: 'linux', arch: 'x64',
    resolve: () => '/pkg/package.json',
    spawnSync: (exe, args, options) => {
      call = { exe, args, options };
      return { status: 7 };
    },
    stderr: { write() {} },
  };
  assert.equal(run(['passage', 'Jude 1'], runtime), 7);
  assert.equal(call.exe, path.join('/pkg', 'dist', 'scriexe', 'scriexe'));
  assert.deepEqual(call.args, ['passage', 'Jude 1']);
  assert.equal(call.options.stdio, 'inherit');
});

test('missing native package returns installation guidance', () => {
  let message = '';
  const runtime = {
    platform: 'linux', arch: 'x64',
    resolve: () => { throw new Error('missing'); },
    spawnSync: () => assert.fail('must not spawn'),
    stderr: { write(value) { message += value; } },
  };
  assert.equal(run([], runtime), 1);
  assert.match(message, /optional dependencies.*reinstall/i);
});
