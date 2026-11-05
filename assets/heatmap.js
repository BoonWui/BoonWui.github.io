/* Market heatmap: every stock as a tile, grouped by sector (squarified treemap), coloured by its move.
   Usage: Heatmap.mount(element, 'bursa' | 'sp500', '../')   (needs assets/market.js) */
window.Heatmap = (function () {
  var CSS = '' +
    '.hm{display:grid;gap:12px}' +
    '.hm-head{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:space-between}' +
    '.hm-head h2{font:800 25px/1.15 var(--display);margin:0}' +
    '.hm-seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}' +
    '.hm-seg button{font:600 13px var(--body);padding:6px 12px;border:0;background:var(--surface);color:var(--ink-2);cursor:pointer}' +
    '.hm-seg button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink)}' +
    '.hm-box{position:relative;width:100%;height:clamp(420px,62vw,600px);border-radius:12px;overflow:hidden;background:var(--line)}' +
    '.hm-sec{position:absolute;box-sizing:border-box;padding:16px 1px 1px 1px;background:var(--line)}' +
    '.hm-sec>span{position:absolute;left:5px;top:1px;font:600 10.5px/15px var(--body);color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;right:4px;text-transform:uppercase;letter-spacing:.04em}' +
    '.hm-t{position:absolute;box-sizing:border-box;border:1px solid var(--line);display:flex;flex-direction:column;align-items:center;justify-content:center;text-decoration:none;color:#fff;overflow:hidden;text-align:center;line-height:1.15;transition:filter .15s}' +
    '.hm-t:hover{filter:brightness(1.15);z-index:2;outline:2px solid var(--ink);outline-offset:-2px}' +
    '.hm-t b{font:700 13px var(--mono)}.hm-t i{font:500 11.5px var(--mono);font-style:normal;opacity:.95}' +
    '.hm-t.sm b{font-size:10.5px}.hm-t.sm i{display:none}' +
    '.hm-t.big b{font-size:17px}.hm-t.big i{font-size:13.5px}' +
    '.hm-scale{display:flex;align-items:center;gap:8px;font:500 12px var(--mono);color:var(--muted)}' +
    '.hm-scale span.bar{width:200px;height:10px;border-radius:5px}' +
    '@keyframes hmPop{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:none}}' +
    '.hm-t{animation:hmPop .45s ease-out both}' +
    '@media (prefers-reduced-motion:reduce){.hm-t{animation:none}}';

  // squarified treemap (Bruls et al.): items [{w}] into rect {x,y,w,h}; returns rects in the same order
  function squarify(items, rect) {
    var total = items.reduce(function (s, it) { return s + it.w; }, 0), out = new Array(items.length);
    if (!total) return out;
    var scale = rect.w * rect.h / total, idx = items.map(function (it, i) { return { i: i, a: it.w * scale }; }).sort(function (a, b) { return b.a - a.a; });
    var r = { x: rect.x, y: rect.y, w: rect.w, h: rect.h }, row = [];
    function worst(row, side) { var s = 0, mx = 0, mn = Infinity; row.forEach(function (o) { s += o.a; mx = Math.max(mx, o.a); mn = Math.min(mn, o.a); }); return Math.max(side * side * mx / (s * s), s * s / (side * side * mn)); }
    function layout(row) {
      var s = row.reduce(function (t, o) { return t + o.a; }, 0);
      if (r.w >= r.h) { var cw = s / r.h, y = r.y; row.forEach(function (o) { var hh = o.a / cw; out[o.i] = { x: r.x, y: y, w: cw, h: hh }; y += hh; }); r.x += cw; r.w -= cw; }
      else { var ch = s / r.w, x = r.x; row.forEach(function (o) { var ww = o.a / ch; out[o.i] = { x: x, y: r.y, w: ww, h: ch }; x += ww; }); r.y += ch; r.h -= ch; }
    }
    idx.forEach(function (o) {
      var side = Math.min(r.w, r.h);
      if (!row.length || worst(row.concat([o]), side) <= worst(row, side)) row.push(o);
      else { layout(row); row = [o]; }
    });
    if (row.length) layout(row);
    return out;
  }

  var PER = [['d1', '1 day', 3], ['w1', '1 week', 6], ['m1', '1 month', 10], ['m3', '3 months', 20], ['ytd', 'Year to date', 30]];
  function color(v, cap) {
    if (!isFinite(v)) return 'var(--muted)';
    var t = Math.max(-1, Math.min(1, v / cap)), a = Math.round(25 + Math.abs(t) * 75);
    return 'color-mix(in srgb, ' + (t >= 0 ? '#12804a' : '#c0392b') + ' ' + a + '%, #3b4440)';
  }

  function mount(el, key, root) {
    if (!document.getElementById('hm-css')) { var st = document.createElement('style'); st.id = 'hm-css'; st.textContent = CSS; document.head.appendChild(st); }
    var M = Market, per = 'd1', D = null, rows = [];
    el.classList.add('hm');
    el.innerHTML = '<div class="hm-head"><h2 id="hm-h">Market heatmap</h2><div class="hm-seg" id="hmSeg" role="group" aria-label="Period">' +
      PER.map(function (p) { return '<button type="button" data-p="' + p[0] + '" aria-pressed="' + (p[0] === per) + '">' + p[1] + '</button>'; }).join('') + '</div></div>' +
      '<div class="hm-box" id="hmBox" role="img" aria-label="Heatmap of every tracked stock grouped by sector"></div>' +
      '<div class="hm-scale" id="hmScale"></div>';
    var box = el.querySelector('#hmBox');
    el.querySelector('#hmSeg').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; per = b.dataset.p; Array.prototype.forEach.call(el.querySelectorAll('#hmSeg button'), function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); });

    function draw() {
      if (!D) return;
      var W = box.clientWidth, H = box.clientHeight, cap = PER.filter(function (p) { return p[0] === per; })[0][2];
      var secs = {}; rows.forEach(function (r) { (secs[r.sector] = secs[r.sector] || []).push(r); });
      var names = Object.keys(secs).sort(function (a, b) { return secs[b].length - secs[a].length; });
      var sr = squarify(names.map(function (n) { return { w: secs[n].length }; }), { x: 0, y: 0, w: W, h: H });
      var html = '';
      names.forEach(function (n, si) {
        var R = sr[si], list = secs[n].slice().sort(function (a, b) { return b[per] - a[per]; }), avg = list.reduce(function (s, r) { return s + (isFinite(r[per]) ? r[per] : 0); }, 0) / list.length;
        html += '<div class="hm-sec" style="left:' + R.x + 'px;top:' + R.y + 'px;width:' + R.w + 'px;height:' + R.h + 'px"><span title="' + M.esc(n) + '">' + M.esc(n) + ' ' + M.sg(avg) + '%</span></div>';
        var inner = { x: R.x + 1, y: R.y + 16, w: Math.max(1, R.w - 2), h: Math.max(1, R.h - 17) };
        var tr = squarify(list.map(function () { return { w: 1 }; }), inner);
        list.forEach(function (r, i) {
          var t = tr[i], size = Math.min(t.w, t.h), c = size < 34 ? ' sm' : size > 90 ? ' big' : '';
          html += '<a class="hm-t' + c + '" href="' + M.stockUrl(root, key, r.sym) + '" style="left:' + t.x + 'px;top:' + t.y + 'px;width:' + t.w + 'px;height:' + t.h + 'px;background:' + color(r[per], cap) + ';animation-delay:' + (Math.min(40, si * 3 + i) * 12) + 'ms" title="' + M.esc(r.name + ' (' + r.code + '): ' + M.sg(r[per], 2) + '%') + '"><b>' + M.esc(r.code) + '</b><i>' + M.sg(r[per], 1) + '%</i></a>';
        });
      });
      box.innerHTML = html;
      el.querySelector('#hmScale').innerHTML = '<span>' + M.sg(-cap, 0) + '%</span><span class="bar" style="background:linear-gradient(90deg,' + color(-cap, cap) + ',' + color(0, cap) + ',' + color(cap, cap) + ')"></span><span>' + M.sg(cap, 0) + '%</span><span>· every tile is one stock, grouped by sector; click a tile for its page</span>';
    }
    M.load(key, root).then(function (d) {
      D = d;
      rows = d.stocks.map(function (s) { var m = M.metrics(d.series(s.symbol), d.K, d.dates); m.sym = s.symbol; m.code = s.code; m.name = s.name; m.sector = s.sector; return m; })
        .filter(function (r) { return isFinite(r.px); });
      draw();
      var tmo; window.addEventListener('resize', function () { clearTimeout(tmo); tmo = setTimeout(draw, 150); });
    }).catch(function () { box.textContent = 'The heatmap could not be loaded.'; });
  }
  return { mount: mount };
})();
