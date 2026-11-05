/* Share links: keep a tool's inputs in the URL hash so a scenario can be bookmarked or sent.
   Reads every text input and select that has an id, plus the pressed button in each .seg group. */
(function () {
  var fields = Array.prototype.slice.call(document.querySelectorAll('form input[type="text"][id], form select[id]'));
  if (!fields.length) return;
  var segBtns = function () { return Array.prototype.slice.call(document.querySelectorAll('.seg button[id]')); };

  function read() {
    var p = new URLSearchParams();
    fields.forEach(function (f) { if (f.value !== '') p.set(f.id, f.value); });
    var on = segBtns().filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; }).map(function (b) { return b.id; });
    if (on.length) p.set('on', on.join(','));
    return p.toString();
  }
  function apply() {
    var h = location.hash.replace(/^#/, ''); if (!h || h.indexOf('=') < 0) return;
    var p = new URLSearchParams(h), known = {};
    fields.forEach(function (f) { known[f.id] = f; });
    p.forEach(function (v, k) {
      var f = known[k]; if (!f) return;
      f.value = String(v).slice(0, 60);
      f.dispatchEvent(new Event(f.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    });
    (p.get('on') || '').split(',').forEach(function (id) {
      var b = id && document.getElementById(id);
      if (b && b.closest('.seg') && b.getAttribute('aria-pressed') !== 'true') b.click();
    });
    // presets may overwrite fields on change: re-apply plain values once more
    p.forEach(function (v, k) { var f = known[k]; if (f && f.tagName !== 'SELECT') { f.value = String(v).slice(0, 60); f.dispatchEvent(new Event('input', { bubbles: true })); } });
  }
  var t;
  function save() { clearTimeout(t); t = setTimeout(function () { try { history.replaceState(null, '', '#' + read()); } catch (e) {} }, 300); }

  apply();
  document.addEventListener('input', save);
  document.addEventListener('change', save);
  document.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('.seg')) save(); });

  var top = document.querySelector('.top');
  if (top) {
    var btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'btn'; btn.textContent = 'Copy link to this scenario';
    btn.style.fontSize = '13px'; btn.style.padding = '6px 12px';
    btn.addEventListener('click', function () {
      try { history.replaceState(null, '', '#' + read()); } catch (e) {}
      var url = location.href, done = function (msg) { btn.textContent = msg; setTimeout(function () { btn.textContent = 'Copy link to this scenario'; }, 2000); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { done('Link copied'); }, function () { fallback(url); done('Link copied'); });
      else { fallback(url); done('Link copied'); }
    });
    top.insertBefore(btn, top.lastElementChild);
  }
  function fallback(url) {
    var ta = document.createElement('textarea'); ta.value = url; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) {} document.body.removeChild(ta);
  }
})();
