/* "Top movers today" block for the market monitors: a scrolling ticker tape, top gainers and losers with
   pulsing badges, and a quiet re-check every few minutes that flashes any price that changed.
   Usage: Movers.mount(element, 'bursa' | 'sp500', '../')   (needs assets/market.js) */
window.Movers = (function () {
  var CSS = '' +
    '.mv{display:grid;gap:14px}' +
    '.mv-head{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:space-between}' +
    '.mv-head h2{font:800 25px/1.15 var(--display);margin:0}' +
    '.mv-status{display:inline-flex;align-items:center;gap:8px;font:600 12.5px var(--mono);color:var(--ink-2)}' +
    '.mv-dot{width:9px;height:9px;border-radius:50%;background:var(--muted)}' +
    '.mv-status.on .mv-dot{background:var(--loss);animation:mvPing 1.6s ease-out infinite}' +
    '.mv-status.on b{color:var(--loss)}' +
    '@keyframes mvPing{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--loss) 60%,transparent)}100%{box-shadow:0 0 0 10px transparent}}' +
    '.mv-tape{overflow:hidden;white-space:nowrap;border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:9px 0;font:500 13.5px var(--mono);-webkit-mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent)}' +
    '.mv-tape .tr{display:inline-block;padding-left:100%;animation:mvTape 70s linear infinite}' +
    '.mv-tape:hover .tr{animation-play-state:paused}' +
    '.mv-tape a{text-decoration:none;margin-right:26px}.mv-tape a b{color:var(--ink);margin-right:6px}' +
    '@keyframes mvTape{to{transform:translateX(-100%)}}' +
    '.mv-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px}' +
    '.mv-col{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:grid;align-content:start}' +
    '.mv-col h3{margin:0;padding:12px 16px;font:700 16px var(--display);display:flex;gap:8px;align-items:center;border-bottom:1px solid var(--line)}' +
    '.mv-col.up h3{background:color-mix(in srgb,var(--gain) 12%,var(--surface));color:var(--gain)}' +
    '.mv-col.dn h3{background:color-mix(in srgb,var(--loss) 12%,var(--surface));color:var(--loss)}' +
    '.mv-row{display:grid;grid-template-columns:22px minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:10px 16px;border-top:1px solid var(--grid);text-decoration:none;color:inherit;position:relative}' +
    '.mv-row:first-of-type{border-top:0}.mv-row:hover{background:var(--accent-soft)}' +
    '.mv-rank{font:700 13px var(--mono);color:var(--muted)}' +
    '.mv-nm{min-width:0}.mv-nm b{font:700 15px var(--mono)}.mv-nm span{display:block;font-size:12.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.mv-px{font:500 14px var(--mono);color:var(--ink-2);text-align:right}' +
    '.mv-chg{font:700 14px var(--mono);padding:5px 10px;border-radius:8px;min-width:84px;text-align:center;color:var(--accent-ink)}' +
    '.up .mv-chg{background:var(--gain);animation:mvGlowUp 2.4s ease-in-out infinite}' +
    '.dn .mv-chg{background:var(--loss);animation:mvGlowDn 2.4s ease-in-out infinite}' +
    '.mv-row:nth-of-type(2) .mv-chg{animation-delay:.3s}.mv-row:nth-of-type(3) .mv-chg{animation-delay:.6s}.mv-row:nth-of-type(4) .mv-chg{animation-delay:.9s}.mv-row:nth-of-type(5) .mv-chg{animation-delay:1.2s}' +
    '@keyframes mvGlowUp{0%,100%{box-shadow:0 0 0 0 transparent;filter:none}50%{box-shadow:0 0 14px 2px color-mix(in srgb,var(--gain) 55%,transparent);filter:brightness(1.12)}}' +
    '@keyframes mvGlowDn{0%,100%{box-shadow:0 0 0 0 transparent;filter:none}50%{box-shadow:0 0 14px 2px color-mix(in srgb,var(--loss) 55%,transparent);filter:brightness(1.12)}}' +
    '.mv-row.top{padding-block:14px}.mv-row.top .mv-nm b{font-size:18px}.mv-row.top .mv-chg{font-size:16px;padding:7px 12px}' +
    '.mv-row.top::after{content:"";position:absolute;inset:0;pointer-events:none;animation:mvSweep 3.2s ease-in-out infinite}' +
    '.up .mv-row.top::after{background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--gain) 14%,transparent),transparent);background-size:50% 100%;background-repeat:no-repeat}' +
    '.dn .mv-row.top::after{background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--loss) 14%,transparent),transparent);background-size:50% 100%;background-repeat:no-repeat}' +
    '@keyframes mvSweep{0%{background-position:-60% 0}60%,100%{background-position:160% 0}}' +
    '.mv-bar{grid-column:2/-1;height:4px;border-radius:2px;background:var(--grid);overflow:hidden;margin-top:-4px}' +
    '.mv-bar i{display:block;height:100%;border-radius:2px;transition:width .8s ease}' +
    '.up .mv-bar i{background:var(--gain)}.dn .mv-bar i{background:var(--loss)}' +
    '.mv-flash-up{animation:mvTickUp 1.4s ease-out 2}.mv-flash-dn{animation:mvTickDn 1.4s ease-out 2}' +
    '@keyframes mvTickUp{0%{background:color-mix(in srgb,var(--gain) 40%,transparent)}100%{background:transparent}}' +
    '@keyframes mvTickDn{0%{background:color-mix(in srgb,var(--loss) 40%,transparent)}100%{background:transparent}}' +
    '.mv-foot{display:flex;flex-wrap:wrap;gap:6px 18px;justify-content:space-between;font-size:13px;color:var(--muted)}' +
    '.mv-breadth{display:flex;height:10px;border-radius:5px;overflow:hidden;min-width:180px;flex:1;max-width:420px;align-self:center}' +
    '.mv-breadth i{display:block;height:100%}' +
    '@media (prefers-reduced-motion:reduce){.mv *,.mv *::after{animation:none!important}.mv-tape .tr{padding-left:16px;white-space:normal}}';

  function mount(el, key, root) {
    if (!document.getElementById('mv-css')) { var st = document.createElement('style'); st.id = 'mv-css'; st.textContent = CSS; document.head.appendChild(st); }
    var M = Market, last = {}, timer = null, MIN = 5;
    el.classList.add('mv');
    el.innerHTML = '<div class="mv-head"><h2 id="mv-h">Today\'s top movers</h2><span class="mv-status" id="mvStatus"><span class="mv-dot"></span><span>Loading…</span></span></div>' +
      '<div class="mv-tape" aria-label="Every tracked stock, sorted by today\'s move"><span class="tr" id="mvTape"></span></div>' +
      '<div class="mv-cols"><section class="mv-col up" aria-label="Top gainers"><h3>▲ Top gainers</h3><div id="mvUp"></div></section><section class="mv-col dn" aria-label="Top losers"><h3>▼ Top losers</h3><div id="mvDn"></div></section></div>' +
      '<div class="mv-foot"><span id="mvAdv"></span><span class="mv-breadth" id="mvBreadth" aria-hidden="true"></span><span id="mvNext"></span></div>';
    var $ = function (id) { return el.querySelector('#' + id); };

    function draw(D) {
      var L = D.dates.length - 1, rows = [];
      D.stocks.forEach(function (s) {
        var a = D.series(s.symbol), now = a[L], prev = a[L - 1];
        if (now == null || !prev) return;
        rows.push({ s: s, px: now, ch: (now / prev - 1) * 100 });
      });
      rows.sort(function (x, y) { return y.ch - x.ch; });
      var up = rows.filter(function (r) { return r.ch > 0; }), dn = rows.filter(function (r) { return r.ch < 0; }).reverse();
      var maxAbs = Math.max.apply(null, rows.map(function (r) { return Math.abs(r.ch); }).concat([0.01]));
      var K = D.K, kch = (K[L] / K[L - 1] - 1) * 100;

      // live or closed?
      // "Open" follows the exchange's trading hours; prices are the latest intraday snapshot (a few a day).
      var hasToday = D.dates[L] === M.todayIn(D.market), open = M.isOpen(D.market);
      $('mv-h').textContent = hasToday ? 'Today\'s top movers' : 'Last session\'s top movers';
      var stEl = $('mvStatus');
      stEl.className = 'mv-status' + (open ? ' on' : '');
      stEl.innerHTML = '<span class="mv-dot"></span><span>' +
        (open && hasToday && D.liveNote ? '<b>MARKET OPEN</b> · prices as of ' + M.esc(D.liveNote.replace(/^Prices as of /, '').replace(/,.*$/, ''))
          : open ? '<b>MARKET OPEN</b> · waiting for today\'s first prices · showing ' + M.fd(D.dates[L]) + ' close'
          : 'Market closed · last close ' + M.fd(D.dates[L])) +
        ' · ' + M.esc(D.index.name) + ' <span class="' + M.cls(kch) + '">' + M.sg(kch, 2) + '%</span></span>';

      var item = function (r) { return '<a href="' + M.stockUrl(root, key, r.s.symbol) + '"><b>' + M.esc(r.s.code) + '</b><span class="' + M.cls(r.ch) + '">' + (r.ch >= 0 ? '▲' : '▼') + ' ' + M.sg(r.ch, 2) + '%</span></a>'; };
      $('mvTape').innerHTML = rows.map(item).join('');

      function list(arr, id) {
        $(id).innerHTML = arr.length ? arr.slice(0, 5).map(function (r, i) {
          var moved = last[r.s.symbol] != null && last[r.s.symbol] !== r.px, cls = moved ? (r.px > last[r.s.symbol] ? ' mv-flash-up' : ' mv-flash-dn') : '';
          return '<a class="mv-row' + (i === 0 ? ' top' : '') + cls + '" href="' + M.stockUrl(root, key, r.s.symbol) + '"><span class="mv-rank">' + (i + 1) + '</span>' +
            '<span class="mv-nm"><b>' + M.esc(r.s.code) + '</b><span>' + M.esc(r.s.name) + ' · ' + M.esc(r.s.sector) + '</span></span>' +
            '<span class="mv-px">' + D.market.cur + M.px(r.px) + '</span><span class="mv-chg">' + (r.ch >= 0 ? '▲ ' : '▼ ') + M.sg(r.ch, 2) + '%</span>' +
            '<span class="mv-bar"><i style="width:' + (Math.abs(r.ch) / maxAbs * 100).toFixed(0) + '%"></i></span></a>';
        }).join('') : '<p style="padding:14px 16px;margin:0;color:var(--muted)">No stock ' + (id === 'mvUp' ? 'rose' : 'fell') + ' today.</p>';
      }
      list(up, 'mvUp'); list(dn, 'mvDn');

      var flat = rows.length - up.length - dn.length;
      $('mvAdv').innerHTML = '<b class="pos">' + up.length + ' up</b> · <b class="neg">' + dn.length + ' down</b>' + (flat ? ' · ' + flat + ' unchanged' : '') + ' of ' + rows.length;
      $('mvBreadth').innerHTML = '<i style="width:' + (up.length / rows.length * 100) + '%;background:var(--gain)"></i><i style="width:' + (flat / rows.length * 100) + '%;background:var(--muted)"></i><i style="width:' + (dn.length / rows.length * 100) + '%;background:var(--loss)"></i>';
      rows.forEach(function (r) { last[r.s.symbol] = r.px; });
    }

    function tick(first) {
      M.load(key, root).then(function (D) { draw(D); }).catch(function () { if (first) $('mvStatus').lastChild.textContent = 'Movers could not be loaded.'; });
    }
    tick(true);
    // Re-check every few minutes while the tab is visible; intraday snapshots arrive from GitHub Actions.
    var nextAt = Date.now() + MIN * 60e3;
    setInterval(function () {
      var s = Math.max(0, Math.round((nextAt - Date.now()) / 1000));
      $('mvNext').textContent = 'Re-checks prices in ' + Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2);
      if (s === 0 && !document.hidden) { nextAt = Date.now() + MIN * 60e3; tick(false); }
    }, 1000);
  }
  return { mount: mount };
})();
