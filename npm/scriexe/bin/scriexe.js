#!/usr/bin/env node
'use strict';

const path = require('node:path');
const childProcess = require('node:child_process');

const PACKAGES = {
  'darwin-arm64': 'scriexe-darwin-arm64',
  'darwin-x64': 'scriexe-darwin-x64',
  'linux-arm64': 'scriexe-linux-arm64',
  'linux-x64': 'scriexe-linux-x64',
  'win32-x64': 'scriexe-win32-x64',
};

function packageFor(platform, arch) {
  const target = `${platform}-${arch}`;
  const name = PACKAGES[target];
  if (!name) {
    throw new Error(`Unsupported scriexe platform: ${target}. Supported: ${Object.keys(PACKAGES).join(', ')}`);
  }
  return name;
}

function run(argv, supplied = {}) {
  const runtime = {
    platform: supplied.platform || process.platform,
    arch: supplied.arch || process.arch,
    resolve: supplied.resolve || require.resolve,
    spawnSync: supplied.spawnSync || childProcess.spawnSync,
    stderr: supplied.stderr || process.stderr,
  };
  let packageName;
  try {
    packageName = packageFor(runtime.platform, runtime.arch);
  } catch (error) {
    runtime.stderr.write(`${error.message}\n`);
    return 1;
  }
  let packageJson;
  try {
    packageJson = runtime.resolve(`${packageName}/package.json`);
  } catch (_error) {
    runtime.stderr.write(
      `Native optional dependencies are missing (${packageName}). Reinstall scriexe with optional dependencies enabled.\n`
    );
    return 1;
  }
  const extension = runtime.platform === 'win32' ? '.exe' : '';
  const executable = path.join(path.dirname(packageJson), 'dist', 'scriexe', `scriexe${extension}`);
  const result = runtime.spawnSync(executable, argv, { stdio: 'inherit' });
  if (result.error) {
    runtime.stderr.write(`Unable to start scriexe: ${result.error.message}\n`);
    return 1;
  }
  return result.status === null ? 1 : result.status;
}

if (require.main === module) {
  process.exitCode = run(process.argv.slice(2));
}

module.exports = { packageFor, run };
