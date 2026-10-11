// Renders the Mermaid blocks of the Markdown files that pre-commit passes, with
// mmdc from @mermaid-js/mermaid-cli (installed by the manual hook `mermaid`),
// and fails when a diagram does not render. It names each failing file.
//   pre-commit run --hook-stage manual mermaid --all-files
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";

const windows = process.platform === "win32";
const files = process.argv
  .slice(2)
  .filter((file) => readFileSync(file, "utf8").includes("```mermaid"));
const out = mkdtempSync(join(tmpdir(), "mermaid-check-"));
const failed = [];
try {
  for (const file of files) {
    const args = ["-i", file, "-o", join(out, basename(file))];
    // npm installs mmdc as a .cmd shim on Windows, and only a shell runs one;
    // the shell then needs each argument quoted.
    const result = windows
      ? spawnSync(
          "mmdc.cmd",
          args.map((arg) => `"${arg}"`),
          { stdio: "inherit", shell: true },
        )
      : spawnSync("mmdc", args, { stdio: "inherit" });
    if (result.error) {
      console.error(result.error.message);
    }
    if (result.status !== 0) {
      failed.push(file);
    }
  }
} finally {
  rmSync(out, { recursive: true, force: true });
}
for (const file of failed) {
  console.error(`${file}: a Mermaid diagram does not render; mmdc names it above.`);
}
process.exit(failed.length > 0 ? 1 : 0);
