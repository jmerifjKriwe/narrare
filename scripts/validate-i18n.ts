import { Project, SyntaxKind } from "ts-morph";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// Determine project root (ES-module compatible __dirname)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");

let hasErrors = false;

function reportError(filePath: string, line: number, message: string) {
  console.error(`\x1b[31m[ERROR]\x1b[0m ${filePath}:${line} - ${message}`);
  hasErrors = true;
}

function reportWarning(filePath: string, message: string) {
  console.warn(`\x1b[33m[WARN]\x1b[0m ${filePath} - ${message}`);
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
// PIPELINE START
// ==========================================
console.log("\n🚀 Starting i18n validation...\n");

checkFrontend();
checkBackend();

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
