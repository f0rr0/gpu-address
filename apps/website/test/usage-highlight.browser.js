// Run in the browser console on the website after highlighting has loaded.
(() => {
  const code = document.querySelector("[data-slot=usage-code] code");
  if (!code?.querySelector('[data-syntax="keyword"]'))
    throw new Error("Missing gpu-lexer highlighting");
  if (!code.querySelector('[data-syntax="string"]'))
    throw new Error("Missing string highlighting");
  if (
    !code.textContent.startsWith(
      "import { createParser } from 'gpu-postal';\n\n",
    )
  )
    throw new Error("Source text changed");
  if (!code.textContent.endsWith("await parser.dispose();"))
    throw new Error("Source text truncated");
  if (code.querySelector("script, img"))
    throw new Error("Source rendered as HTML");
  return "Usage highlighting passed";
})();
