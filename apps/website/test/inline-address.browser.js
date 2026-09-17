// After editing an address and waiting for parsing, paste into the browser console.
// Repeat with multiline text, an emoji, rapid edits, and an empty input.
(() => {
  const input = document.querySelector('#address');
  const layer = document.querySelector('[data-slot="address-highlights"]');
  if (!input || !layer) throw new Error('Address editor is missing');
  if (layer.textContent !== input.value + '\u200b')
    throw new Error('Highlight layer changed the source text');
  if (!input.value && layer.querySelector('mark'))
    throw new Error('Empty input retained stale highlights');
  for (const property of ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'padding', 'whiteSpace', 'overflowWrap']) {
    if (getComputedStyle(input)[property] !== getComputedStyle(layer)[property])
      throw new Error('Highlight layout differs: ' + property);
  }
  if (input.scrollHeight > input.clientHeight + 1 || input.scrollWidth > input.clientWidth + 1)
    throw new Error('Input text scrolls out of alignment with highlights');
  console.log('Inline address checks passed');
})();
