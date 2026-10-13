// Preserve Mermaid's natural diagram size instead of stretching narrow flowcharts.
// Responsive max-width still shrinks wide diagrams; fullscreen controls own their sizing.
(() => {
  const fit = () => {
    document.querySelectorAll('pre.mermaid > svg').forEach((svg) => {
      if (svg.closest('.mermaid-fullscreen-modal')) return;
      const width = svg.viewBox.baseVal.width;
      if (width > 0) svg.style.width = `${Math.ceil(width)}px`;
    });
  };
  const start = () => {
    fit();
    new MutationObserver(fit).observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
