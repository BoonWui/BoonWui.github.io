/* Site-wide extras, loaded in <head> on every page:
   - light/dark switch (remembers the choice; otherwise follows the device setting),
   - "install as app" support (web app manifest + offline-capable service worker),
   - privacy-friendly visitor counts with GoatCounter (no cookies, no personal data). */
(function () {
  var d = document.documentElement, KEY = 'bw-theme', saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (saved === 'light' || saved === 'dark') d.setAttribute('data-theme', saved);

  var me = document.currentScript && document.currentScript.src;
  var root = me ? me.replace(/assets\/site\.js(\?.*)?$/, '') : '/';
  var framed = false; try { framed = window.top !== window; } catch (e) { framed = true; }

  function link(rel, href) { if (document.querySelector('link[rel="' + rel + '"]')) return; var l = document.createElement('link'); l.rel = rel; l.href = href; document.head.appendChild(l); }
  link('manifest', root + 'manifest.webmanifest');
  link('apple-touch-icon', root + 'assets/icon-192.png');
  link('icon', root + 'assets/icon-192.png');
  if (!document.querySelector('link[type="application/rss+xml"]')) {
    var rss = document.createElement('link'); rss.rel = 'alternate'; rss.type = 'application/rss+xml'; rss.title = 'BoonWui: palm oil notes'; rss.href = root + 'feed.xml'; document.head.appendChild(rss);
  }

  if (!framed && 'serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () { navigator.serviceWorker.register(root + 'sw.js').catch(function () {}); });
  }

  if (!framed && location.hostname === 'boonwui.github.io') {
    var gc = document.createElement('script'); gc.async = true; gc.src = 'https://gc.zgo.at/count.js';
    gc.setAttribute('data-goatcounter', 'https://boonwui.goatcounter.com/count');
    document.head.appendChild(gc);
  }

  var MOON = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M20.5 14.6A8.5 8.5 0 0 1 9.4 3.5a.6.6 0 0 0-.8-.7A9.5 9.5 0 1 0 21.2 15.4a.6.6 0 0 0-.7-.8z"/></svg>';
  var SUN = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></g></svg>';
  var DL = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 19.5h14"/></svg>';
  function isDark() { var t = d.getAttribute('data-theme'); return t ? t === 'dark' : !!(window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches); }

  var btn, inst, deferred = null;
  function paint() { if (!btn) return; var k = isDark(); btn.innerHTML = k ? SUN : MOON; var l = k ? 'Switch to light mode' : 'Switch to dark mode'; btn.setAttribute('aria-label', l); btn.title = l; }
  window.addEventListener('beforeinstallprompt', function (e) { e.preventDefault(); deferred = e; if (inst) inst.hidden = false; });

  function ui() {
    if (framed || document.querySelector('.bw-fab')) return;
    var st = document.createElement('style');
    st.textContent = '.bw-fab{position:fixed;right:max(14px,env(safe-area-inset-right,0px));bottom:max(14px,env(safe-area-inset-bottom,0px));z-index:50;display:flex;gap:8px;align-items:center}' +
      '.bw-fab button{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:40px;min-width:40px;padding:0 11px;border-radius:99px;border:1px solid var(--line,#ccc);background:var(--surface,#fff);color:var(--ink,#222);font:600 13px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.12)}' +
      '.bw-fab button:hover{color:var(--accent,#1f6f4a)}.bw-fab button:focus-visible{outline:2px solid var(--accent,#1f6f4a);outline-offset:2px}.bw-fab [hidden]{display:none}' +
      '@media print{.bw-fab{display:none}}';
    document.head.appendChild(st);
    var box = document.createElement('div'); box.className = 'bw-fab';
    inst = document.createElement('button'); inst.type = 'button'; inst.hidden = !deferred; inst.innerHTML = DL + 'Install app'; inst.title = 'Install this site as an app';
    inst.addEventListener('click', function () { if (!deferred) return; deferred.prompt(); deferred.userChoice.then(function () { deferred = null; inst.hidden = true; }); });
    btn = document.createElement('button'); btn.type = 'button';
    btn.addEventListener('click', function () { var t = isDark() ? 'light' : 'dark'; d.setAttribute('data-theme', t); try { localStorage.setItem(KEY, t); } catch (e) {} paint(); });
    box.appendChild(inst); box.appendChild(btn); document.body.appendChild(box); paint();
    if (window.matchMedia) { var mq = matchMedia('(prefers-color-scheme: dark)'); (mq.addEventListener ? mq.addEventListener.bind(mq, 'change') : mq.addListener.bind(mq))(paint); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ui); else ui();
})();
