import { Project, SyntaxKind } from "ts-morph";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// Determine project root (ES-module compatible __dirname)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");

let hasErrors = false;

const MESSAGES_DIR = path.join(PROJECT_ROOT, "packages/i18n/messages");

function reportError(filePath: string, line: number, message: string) {
  console.error(`\x1b[31m[ERROR]\x1b[0m ${filePath}:${line} - ${message}`);
  hasErrors = true;
}

function reportWarning(filePath: string, message: string) {
  console.warn(`\x1b[33m[WARN]\x1b[0m ${filePath} - ${message}`);
}

/** Flatten a nested JSON object into dot-notation keys, e.g. {a: {b: "c"}} → "a.b" → "c" */
function flattenKeys(obj: Record<string, unknown>, prefix = ""): Map<string, string> {
  const result = new Map<string, string>();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "object" && value !== null) {
      for (const [k, v] of flattenKeys(value as Record<string, unknown>, fullKey)) {
        result.set(k, v);
      }
    } else {
      result.set(fullKey, String(value));
    }
  }
  return result;
}

/** Load all namespace JSON files for a locale into a single flattened map */
function loadLocaleKeys(locale: string): Map<string, { value: string; file: string }> {
  const localeDir = path.join(MESSAGES_DIR, locale);
  const result = new Map<string, { value: string; file: string }>();

  const files = fs.readdirSync(localeDir).filter((f) => f.endsWith(".json"));
  for (const file of files) {
    const filePath = path.join(localeDir, file);
    const content = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    const flat = flattenKeys(content);
    const namespace = path.basename(file, ".json");
    for (const [key, value] of flat) {
      result.set(`${namespace}.${key}`, { value, file });
    }
  }

  return result;
}

// ==========================================
// 1. FRONTEND: AST-based check for React/TSX
// ==========================================
function checkFrontend() {
  console.log("⏳ Checking frontend components (AST via ts-morph)...");

  // Explicit path to the monorepo tsconfig
  const tsConfigFilePath = path.join(
    PROJECT_ROOT,
    "packages/web/tsconfig.json",
  );

  if (!fs.existsSync(tsConfigFilePath)) {
    reportError(tsConfigFilePath, 0, "tsconfig.json not found!");
    return;
  }

  const project = new Project({ tsConfigFilePath });

  // Filter for .tsx files, excluding tests and snapshots
  const excludePatterns = [
    ".test.tsx",
    ".spec.tsx",
    "__tests__",
    "__snapshots__",
    "global-error.tsx",      // Runs outside React context — no providers available
    "ErrorBoundary.tsx",     // Class component — cannot use hooks
  ];
  const sourceFiles = project.getSourceFiles().filter((sf) => {
    const p = sf.getFilePath();
    return p.endsWith(".tsx") && !excludePatterns.some((ex) => p.includes(ex));
  });

  for (const sourceFile of sourceFiles) {
    const filePath = sourceFile.getFilePath();
    const hasUseTranslation = sourceFile
      .getImportDeclarations()
      .some((imp) =>
        imp
          .getNamedImports()
          .some((named) => named.getName() === "useTranslation"),
      );

    let fileHasHardcodedText = false;

    // Extract JSX text nodes (text between <div> and </div>)
    const jsxTextNodes = sourceFile.getDescendantsOfKind(SyntaxKind.JsxText);

    for (const node of jsxTextNodes) {
      const text = node.getLiteralText();
      const trimmedText = text.replace(/[\n\r\s]+/g, "").trim();

      // Skip pure symbols/numbers and brand name
      const isJustSymbolsOrNumbers = /^[\W\d_]+$/.test(trimmedText);
      const isBrandName = trimmedText === "Narrare";

      if (trimmedText.length > 0 && !isJustSymbolsOrNumbers && !isBrandName) {
        const line = sourceFile.getLineAndColumnAtPos(node.getStart()).line;
        reportError(
          path.relative(PROJECT_ROOT, filePath),
          line,
          `Hardcoded text found in JSX: "${text.trim()}"`,
        );
        fileHasHardcodedText = true;
      }
    }

    if (fileHasHardcodedText && !hasUseTranslation) {
      reportError(
        path.relative(PROJECT_ROOT, filePath),
        1,
        "File contains text nodes but does not import 'useTranslation'.",
      );
    }
  }
}

// ==========================================
// 2. BACKEND: Python hardcoded string check
// ==========================================
function checkBackend() {
  console.log("⏳ Checking backend (.py files)...");
  const backendDir = path.join(PROJECT_ROOT, "apps/api/narrare");

  if (!fs.existsSync(backendDir)) return;

  const walkSync = (dir: string, filelist: string[] = []) => {
    fs.readdirSync(dir).forEach((file) => {
      const dirFile = path.join(dir, file);
      if (fs.statSync(dirFile).isDirectory())
        filelist = walkSync(dirFile, filelist);
      else filelist.push(dirFile);
    });
    return filelist;
  };

  const pyFiles = walkSync(backendDir).filter(
    (f) =>
      f.endsWith(".py") && !f.includes("test") && !f.includes("__pycache__"),
  );

  // Skip files until Python i18n is set up — these are developer-facing error strings
  const excludeFiles = [
    "auth/router.py",
    "volumes/service.py",
    "prompts/router.py",
  ];

  for (const file of pyFiles) {
    if (!file.includes("service.py") && !file.includes("router.py")) continue;
    if (excludeFiles.some(ex => file.endsWith(ex))) continue;

    const content = fs.readFileSync(file, "utf-8");
    const lines = content.split("\n");
    const hasI18n = /get_translation|gettext/.test(content);

    lines.forEach((line, i) => {
      const lineNum = i + 1;
      if (line.includes("logger.")) return;

      if (
        (line.includes("raise HTTPException") ||
          line.includes("raise ValueError") ||
          line.includes("return ")) &&
        /detail\s*=\s*["'][^"']*[A-Za-z]/.test(line) &&
        !hasI18n
      ) {
        reportError(
          path.relative(PROJECT_ROOT, file),
          lineNum,
          "Possible hardcoded error string without i18n",
        );
      }

      if (/["']File not found["']/.test(line))
        reportError(
          path.relative(PROJECT_ROOT, file),
          lineNum,
          "Hardcoded string: 'File not found'",
        );
      if (/["']Directory not found["']/.test(line))
        reportError(
          path.relative(PROJECT_ROOT, file),
          lineNum,
          "Hardcoded string: 'Directory not found'",
        );
      if (/["']Permission denied["']/.test(line))
        reportError(
          path.relative(PROJECT_ROOT, file),
          lineNum,
          "Hardcoded string: 'Permission denied'",
        );
    });
  }
}

// ==========================================
// 3. KEY COMPLETENESS: Compare locales against en
// ==========================================
function checkKeyCompleteness() {
  console.log("⏳ Checking translation key completeness...");

  if (!fs.existsSync(MESSAGES_DIR)) {
    reportError(MESSAGES_DIR, 0, "Messages directory not found!");
    return;
  }

  const locales = fs
    .readdirSync(MESSAGES_DIR)
    .filter((d) => fs.statSync(path.join(MESSAGES_DIR, d)).isDirectory());

  if (!locales.includes("en")) {
    reportError(MESSAGES_DIR, 0, "Reference locale 'en' not found!");
    return;
  }

  const enKeys = loadLocaleKeys("en");

  for (const locale of locales) {
    if (locale === "en") continue;
    const localeKeys = loadLocaleKeys(locale);

    // Missing keys: in en but not in locale
    for (const [key] of enKeys) {
      if (!localeKeys.has(key)) {
        reportError(
          `packages/i18n/messages/${locale}`,
          0,
          `${locale} missing key "${key}"`,
        );
      }
    }

    // Extra keys: in locale but not in en
    for (const [key] of localeKeys) {
      if (!enKeys.has(key)) {
        reportWarning(
          `packages/i18n/messages/${locale}`,
          `${locale} has extra key "${key}"`,
        );
      }
    }
  }

  console.log(`  ✓ Checked ${locales.length - 1} locales against en (${enKeys.size} keys)`);
}

// ==========================================
// 4. PLACEHOLDER CONSISTENCY: ICU placeholder comparison
// ==========================================
function checkPlaceholderConsistency() {
  console.log("⏳ Checking ICU placeholder consistency...");

  if (!fs.existsSync(MESSAGES_DIR)) return;

  const locales = fs
    .readdirSync(MESSAGES_DIR)
    .filter((d) => fs.statSync(path.join(MESSAGES_DIR, d)).isDirectory());

  if (!locales.includes("en")) return;

  const enKeys = loadLocaleKeys("en");
  const placeholderRe = /\{(\w+)\}/g;

  for (const locale of locales) {
    if (locale === "en") continue;
    const localeKeys = loadLocaleKeys(locale);

    for (const [key, enEntry] of enKeys) {
      const enValue = enEntry.value;
      if (enValue === "") continue; // Skip empty strings

      const enPlaceholders = new Set(
        [...enValue.matchAll(placeholderRe)].map((m) => m[1]),
      );

      const localeEntry = localeKeys.get(key);
      if (!localeEntry) continue; // Already reported by completeness check

      const localeValue = localeEntry.value;
      if (localeValue === "") continue; // Skip empty strings

      const localePlaceholders = new Set(
        [...localeValue.matchAll(placeholderRe)].map((m) => m[1]),
      );

      // Missing placeholders
      const missing = [...enPlaceholders].filter((p) => !localePlaceholders.has(p));
      if (missing.length > 0) {
        reportError(
          `packages/i18n/messages/${locale}/${localeEntry.file}`,
          0,
          `key "${key}" missing placeholders: ${missing.map((p) => `{${p}}`).join(", ")}`,
        );
      }

      // Extra placeholders
      const extra = [...localePlaceholders].filter((p) => !enPlaceholders.has(p));
      if (extra.length > 0) {
        reportError(
          `packages/i18n/messages/${locale}/${localeEntry.file}`,
          0,
          `key "${key}" has extra placeholders: ${extra.map((p) => `{${p}}`).join(", ")}`,
        );
      }
    }
  }

  console.log("  ✓ Placeholder consistency check complete");
}

// ==========================================
// PIPELINE START
// ==========================================
console.log("\n🚀 Starting i18n validation...\n");

checkFrontend();
checkBackend();
checkKeyCompleteness();
checkPlaceholderConsistency();

if (hasErrors) {
  console.error(
    "\n\x1b[31m❌ Validation failed. Please fix the i18n issues listed above.\x1b[0m\n",
  );
  process.exit(1);
} else {
  console.log(
    "\n\x1b[32m✅ All clear! i18n patterns and backend text checks passed.\x1b[0m\n",
  );
  process.exit(0);
}
