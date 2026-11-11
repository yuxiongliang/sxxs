/**
 * 提交前密钥闸门（pre-commit secret gate）。
 *
 * 目标：在密钥/隐私数据进入 git 历史**之前**拦住它。历史一旦写进去就
 * 很难彻底清除（要 rewrite history + 通知所有协作者），事后补救成本极高。
 *
 * 检查两类东西：
 *   1. 文件本身就不该进仓库（.env / 证书私钥 / SSH 私钥 / 用户上传附件）
 *   2. 内容里出现已知的密钥特征（云厂商 AccessKey、GitHub Token、私钥块等）
 *
 * 用法：
 *   node scripts/check-secrets.mjs          # 只查暂存区（pre-commit 用）
 *   node scripts/check-secrets.mjs --all    # 查全部已跟踪文件（自检用）
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

/** 二进制与锁文件：无法按行扫描，且不含业务密钥 */
const SKIP_EXT =
  /\.(png|jpe?g|gif|webp|ico|svg|woff2?|ttf|eot|mp4|mov|pdf|zip|gz|tgz|lock)$/i;

/** 这些路径永远不该被提交 */
const FORBIDDEN_PATHS = [
  { re: /(^|\/)\.env$/, why: '环境变量文件（通常含数据库连接串与 JWT 密钥）' },
  {
    re: /(^|\/)\.env\.(local|production|prod|development|dev|test)$/,
    why: '环境变量文件',
  },
  { re: /\.(pem|key|p12|pfx|jks|keystore)$/i, why: '证书或私钥文件' },
  { re: /(^|\/)id_(rsa|ed25519|ecdsa)(\.pub)?$/, why: 'SSH 私钥' },
  { re: /(^|\/)backend\/uploads\//, why: '用户上传附件（可能含个人隐私）' },
];

/** 内容特征 */
const CONTENT_RULES = [
  { name: 'OpenAI 风格 API Key', re: /\bsk-[A-Za-z0-9_-]{20,}/ },
  {
    name: 'GitHub Token',
    re: /\b(gh[pous]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})/,
  },
  { name: 'AWS Access Key', re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: '阿里云 AccessKey', re: /\bLTAI[0-9A-Za-z]{12,}\b/ },
  { name: 'Google API Key', re: /\bAIza[0-9A-Za-z_-]{30,}\b/ },
  { name: 'Slack Token', re: /\bxox[baprs]-[A-Za-z0-9-]{10,}/ },
  { name: '私钥块', re: /-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----/ },
];

/** 命中这些说明只是占位符/示例，放行（例如表单里的 placeholder 文案） */
const PLACEHOLDER =
  /placeholder|<[A-Z_]+>|your[-_]?(api[-_]?)?key|change[-_]?me|xxx+|\.\.\.|示例|占位/i;

function stagedFiles() {
  const out = execFileSync(
    'git',
    ['diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'],
    {
      encoding: 'utf8',
    },
  );
  return out.split('\0').filter(Boolean);
}

function trackedFiles() {
  const out = execFileSync('git', ['ls-files', '-z'], { encoding: 'utf8' });
  return out.split('\0').filter(Boolean);
}

const problems = [];
const files = process.argv.includes('--all') ? trackedFiles() : stagedFiles();

for (const file of files) {
  if (SKIP_EXT.test(file)) continue;

  for (const rule of FORBIDDEN_PATHS) {
    if (rule.re.test(file)) {
      problems.push(`${file}\n    ↳ 不该提交的文件：${rule.why}`);
      break;
    }
  }

  // 只扫描文本类文件的内容
  if (SKIP_EXT.test(file) || /\.(lock)$/i.test(file)) continue;
  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch {
    continue;
  }
  if (text.includes('\u0000')) continue; // 二进制

  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line || PLACEHOLDER.test(line)) continue;
    for (const rule of CONTENT_RULES) {
      if (rule.re.test(line)) {
        problems.push(
          `${file}:${i + 1}\n    ↳ 疑似${rule.name}：${line.trim().slice(0, 100)}`,
        );
      }
    }
  }
}

if (problems.length === 0) {
  process.exit(0);
}

console.error('');
console.error('✖ 提交被拦截：检测到可能的密钥或隐私数据');
console.error('');
for (const item of problems) console.error('  ' + item);
console.error('');
console.error(
  '如果是误报（例如代码里的占位符文案），请把该行改为包含 placeholder / <YOUR_KEY> 等字样；',
);
console.error(
  '确需提交请用：git commit --no-verify（仅限你确认过内容安全的情况）。',
);
console.error('');
process.exit(1);
