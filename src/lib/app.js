const root = document.documentElement;
const themeButton = document.querySelector('.theme-toggle');
const systemDark = window.matchMedia('(prefers-color-scheme: dark)');
function activeTheme() { return root.dataset.theme || (systemDark.matches ? 'dark' : 'light'); }
function updateThemeControl() {
 const theme = activeTheme();
 if (themeButton) {
  themeButton.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
  themeButton.setAttribute('title', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
  themeButton.setAttribute('aria-pressed', String(theme === 'dark'));
 }
 const meta = document.querySelector('meta[name="theme-color"]:not([media])');
 if (meta) meta.content = getComputedStyle(root).getPropertyValue('--md-sys-color-surface').trim();
}
try { const saved = localStorage.getItem('maichat-theme'); if (saved === 'light' || saved === 'dark') root.dataset.theme = saved; } catch { /* The system theme works when browser storage is unavailable. */ }
updateThemeControl();
themeButton?.addEventListener('click', () => {
 root.dataset.theme = activeTheme() === 'dark' ? 'light' : 'dark';
 try { localStorage.setItem('maichat-theme', root.dataset.theme); } catch { /* Apply for this page even without storage. */ }
 updateThemeControl();
});
systemDark.addEventListener('change', updateThemeControl);
for (const widget of document.querySelectorAll('[data-tabs]')) {
 const tabs = [...widget.querySelectorAll('[role="tab"]')];
 const panels = [...widget.querySelectorAll('[role="tabpanel"]')];
 function selectTab(tab, moveFocus = false) {
  for (const item of tabs) { item.setAttribute('aria-selected', String(item === tab)); item.tabIndex = item === tab ? 0 : -1; }
  for (const panel of panels) panel.hidden = panel.id !== tab.getAttribute('aria-controls');
  if (moveFocus) tab.focus({ preventScroll: true });
 }
 tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', (event) => {
   let next;
   if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
   if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
   if (event.key === 'Home') next = 0;
   if (event.key === 'End') next = tabs.length - 1;
   if (next === undefined) return;
   event.preventDefault();
   selectTab(tabs[next], true);
  });
 });
}
document.querySelector('[data-download]')?.addEventListener('click', () => {
 document.querySelector('#download-status').textContent = 'Download requested. Check your browser’s downloads for the APK.';
});
document.querySelector('[data-copy-checksum]')?.addEventListener('click', async () => {
 const code = document.querySelector('#release-checksum');
 const status = document.querySelector('#copy-status');
 try {
  await navigator.clipboard.writeText(code.textContent.trim());
  status.textContent = 'Checksum copied.';
 } catch {
  const selection = window.getSelection();
  const range = document.createRange(); range.selectNodeContents(code); selection.removeAllRanges(); selection.addRange(range);
  status.textContent = 'Checksum selected. Use your browser’s Copy command.';
 }
});
