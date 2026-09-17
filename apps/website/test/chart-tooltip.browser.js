// Hover or tap a chart, then paste into the browser console.
// Repeat at desktop/mobile widths and after horizontal chart scrolling.
(() => {
  const tooltip = document.querySelector('[role="tooltip"]');
  if (!tooltip) throw new Error('Open a chart tooltip first');
  if (tooltip.parentElement !== document.body)
    throw new Error('Tooltip is inside a clipping container');
  const rect = tooltip.getBoundingClientRect();
  if (rect.left < 0 || rect.top < 0 || rect.right > innerWidth || rect.bottom > innerHeight)
    throw new Error('Tooltip extends outside the viewport');
  if (tooltip.scrollWidth > tooltip.clientWidth || tooltip.scrollHeight > tooltip.clientHeight)
    throw new Error('Tooltip content is clipped');
  console.log('Chart tooltip is fully visible');
})();
