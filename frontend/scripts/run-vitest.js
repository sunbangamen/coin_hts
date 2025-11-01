#!/usr/bin/env node

/**
 * Vitest runner script for read-only worktree environments
 *
 * 문제: Vitest는 설정 파일을 로드할 때 원본 파일 옆에
 *       vitest.config.js.timestamp-… 임시 파일을 생성하려고 해서
 *       읽기 전용 워크트리에서는 EACCES 오류 발생
 *
 * 해결책:
 *  1. VITEST_RUNTIME_DIR 환경변수 또는 ~/.cache/vitest-runtime 사용
 *  2. 디렉터리 쓰기 권한 확인 (probe 파일 테스트)
 *  3. 실패 시 명확한 안내 메시지 제공
 *  4. 설정 파일을 런타임 디렉터리로 복사 후 실행
 */

import { execSync } from 'child_process';
import {
  copyFileSync,
  unlinkSync,
  readFileSync,
  mkdirSync,
  writeFileSync,
  accessSync,
  constants
} from 'fs';
import { resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { homedir } from 'os';

const __dirname = resolve(fileURLToPath(import.meta.url), '..');
const frontendDir = resolve(__dirname, '..');
const originalConfig = resolve(frontendDir, 'vitest.config.js');

// ============================================
// 1단계: 런타임 디렉터리 결정
// ============================================

const defaultRuntimeBase = join(homedir(), '.cache', 'vitest-runtime');
const runtimeBase =
  process.env.VITEST_RUNTIME_DIR || defaultRuntimeBase;

console.log(`ℹ️  Runtime directory: ${runtimeBase}`);
console.log(`   (커스텀 경로를 원하면: VITEST_RUNTIME_DIR=/path/to/writable npm run test)\n`);

// ============================================
// 2단계: 디렉터리 생성 및 쓰기 가능 여부 확인
// ============================================

function ensureWritablePath(basePath, name) {
  try {
    // 1. 디렉터리 생성
    mkdirSync(basePath, { recursive: true });
    console.log(`✓ Created directory: ${basePath}`);

    // 2. 쓰기 권한 확인
    accessSync(basePath, constants.W_OK);
    console.log(`✓ Directory is writable: ${basePath}`);

    // 3. 실제 쓰기 테스트 (probe 파일)
    const probePath = join(basePath, '.probe');
    writeFileSync(probePath, 'ok');
    unlinkSync(probePath);
    console.log(`✓ Write test passed: ${basePath}\n`);

    return true;
  } catch (error) {
    console.error(`\n❌ Error with ${name}: ${basePath}`);
    console.error(`   Reason: ${error.message}\n`);

    console.error(`💡 해결 방법:`);
    console.error(`   1. 쓰기 가능한 디렉터리를 만든 뒤:
       mkdir -p /path/to/writable\n`);
    console.error(`   2. VITEST_RUNTIME_DIR 환경변수로 지정해서 실행하세요:
       VITEST_RUNTIME_DIR=/path/to/writable npm run test\n`);

    process.exit(1);
  }
}

ensureWritablePath(runtimeBase, 'VITEST_RUNTIME_DIR');

// ============================================
// 3단계: 런타임 디렉터리 구조 설정
// ============================================

const tmpConfigDir = join(runtimeBase, 'config');
const cacheDir = join(runtimeBase, 'cache');

// 서브디렉터리 생성
try {
  mkdirSync(tmpConfigDir, { recursive: true });
  mkdirSync(cacheDir, { recursive: true });
  console.log(`ℹ️  Subdirectories:`);
  console.log(`   Config: ${tmpConfigDir}`);
  console.log(`   Cache: ${cacheDir}\n`);
} catch (error) {
  console.error(`\n❌ Failed to create subdirectories:`);
  console.error(`   ${error.message}\n`);
  process.exit(1);
}

// ============================================
// 4단계: 설정 파일 복사 및 Vitest 실행
// ============================================

const tmpConfig = join(tmpConfigDir, `vitest-config-${Date.now()}.js`);

try {
  // 설정 파일 복사
  try {
    const configContent = readFileSync(originalConfig, 'utf-8');
    copyFileSync(originalConfig, tmpConfig);
    console.log(`✓ Config file copied to: ${tmpConfig}\n`);
  } catch (copyError) {
    console.error(`\n❌ Error copying config file:`);
    console.error(`   From: ${originalConfig}`);
    console.error(`   To: ${tmpConfig}`);
    console.error(`   Code: ${copyError.code}`);
    console.error(`   Message: ${copyError.message}\n`);

    console.error(`💡 해결 방법:`);
    console.error(`   VITEST_RUNTIME_DIR 환경변수를 사용해 다른 경로를 지정하세요:`);
    console.error(`   VITEST_RUNTIME_DIR=/path/to/writable npm run test\n`);

    throw copyError;
  }

  // 환경 변수 설정
  const env = {
    ...process.env,
    VITEST_CACHE_DIR: cacheDir,
    NODE_PATH: resolve(frontendDir, 'node_modules')
  };

  // Vitest 실행
  const cmd = `node node_modules/vitest/vitest.mjs --run --config ${tmpConfig} ${process.argv
    .slice(2)
    .join(' ')}`;

  console.log(`🧪 Running Vitest with temporary config...\n`);
  execSync(cmd, { stdio: 'inherit', cwd: frontendDir, env });
} catch (error) {
  console.error(`\n❌ Vitest execution failed`);
  console.error(`   Current runtime directory: ${runtimeBase}`);
  console.error(`   Error: ${error.message}\n`);

  console.error(`💡 해결 방법:`);
  console.error(`   VITEST_RUNTIME_DIR 환경변수를 사용해 다른 경로를 지정하세요:`);
  console.error(`   VITEST_RUNTIME_DIR=/path/to/writable npm run test\n`);

  process.exit(1);
} finally {
  // 임시 설정 파일 정리
  try {
    unlinkSync(tmpConfig);
    console.log(`\n✓ Temporary config cleaned up`);
  } catch (e) {
    // 파일이 이미 삭제되었거나 기타 오류 무시
  }
}
