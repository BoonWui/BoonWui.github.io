/* Site-wide extras, loaded in <head> on every page:
   - menu bar, quick search (/ or Ctrl+K) and related pages (second block below),
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

/* Site-wide navigation (added 2026-11-27): a menu bar on every page, quick search (press / or Ctrl+K),
   and "Related pages" at the bottom. The page list lives only here, so a new page is added in one place. */
(function () {
  var me = document.currentScript && document.currentScript.src;
  var root = me ? me.replace(/assets\/site\.js(\?.*)?$/, '') : '/';
  var framed = false; try { framed = window.top !== window; } catch (e) { framed = true; }
  if (framed) return;
  // [path, title, short description]
  var G = [
    ['Start here', [
      ['', 'Home', 'All projects and live figures'],
      ['palm-hub/', 'Palm Oil Hub', 'Every palm page in reading order, with this week\'s read'],
      ['palm-overview/', 'Palm Oil at a Glance', 'Every palm signal on one page'],
      ['palm-world/', 'Palm Oil World 3D', 'Plantation to refinery to port to market, on a 3D globe'],
      ['fcpo-drivers/', 'FCPO Driver Tree', 'Every factor, weighted, adding up to one FCPO view'],
      ['fcpo-model/', 'FCPO Model', 'All drivers in one model: chance FCPO rises, track record, what-if'],
      ['palm-oil-fundamentals/', 'Palm Oil Fundamentals', 'The outlook and price paths to mid-2027'],
      ['palm-oil-monitor/', 'Palm Oil Market Monitor', 'Monthly report: read-out, scorecard, balance'],
      ['market-notes/', 'Palm Market Notes', 'A short note on each MPOB release day'],
      ['blog/', 'Notes', 'Articles and case studies']]],
    ['Prices & positions', [
      ['bmd-fcpo/', 'BMD FCPO Monitor', 'Bursa palm oil futures: trend, levels, bull or bear read'],
      ['dce-positions/', 'DCE Palm Broker Positions', 'Who is long and short Dalian palm oil'],
      ['dce-report/', 'DCE Daily Report', 'Palm and soy oil: broker positions, net history, call/put ratios'],
      ['cftc-positions/', 'CFTC Fund Positions', 'Hedge fund positions in 25 commodities'],
      ['open-interest/', 'Veg Oil Open Interest', 'Dalian, Zhengzhou daily; CBOT, ICE weekly'],
      ['energy-monitor/', 'Veg Oil & Energy Monitor', 'Brent, diesel, ringgit, POGO, soy discount'],
      ['oil-price-map/', 'Veg Oil Price Map', 'Where each vegetable oil is quoted'],
      ['volatility/', 'Veg Oil Volatility', 'How volatile each oil is now'],
      ['indonesia-export-tax/', 'Indonesia Export Tax', 'Next month\'s reference price, levy and duty']]],
    ['Supply & demand', [
      ['weather-monitor/', 'Palm Oil Weather Monitor', 'Rainfall against normal and the forecast'],
      ['mpob-nowcast/', 'MPOB Countdown & Nowcast', 'Our estimate before MPOB reports'],
      ['seasonality/', 'Palm Oil Seasonality', 'This year against the last five'],
      ['indonesia/', 'Indonesia Palm Oil Tracker', 'GAPKI production, exports and stocks'],
      ['world-demand/', 'World Palm Oil Demand', 'Imports and use by country (USDA)'],
      ['india-imports/', 'India Veg Oil Imports', 'Palm against soybean and sunflower (SEA)'],
      ['import-margins/', 'Palm Import Margins', 'India and China: do importers make money?'],
      ['biodiesel/', 'Palm Biodiesel Tracker', 'Mandates and the palm-gasoil spread']]],
    ['Trading tools', [
      ['fcpo-calculator/', 'FCPO Trade Calculator', 'Profit, margin, break-even, position size'],
      ['hedge-calculator/', 'FCPO Hedging Calculator', 'Lots to hedge a physical position'],
      ['fcpo-swap/', 'FCPO Swap Calculator', 'Fair fixed price of an average-price swap'],
      ['option-calculator/', 'Option Pricing Calculator', 'Black-76 prices and Greeks'],
      ['option-strategy/', 'Option Strategy Builder', 'Payoffs, break-evens and Greeks'],
      ['spread-analyser/', 'Calendar Spread Analyser', 'Mean-reversion signals for FCPO spreads'],
      ['pairs/', 'Pair-Trading Explorer', 'Spreads and z-scores between two assets'],
      ['palm-oil-tools/', 'Palm Oil Price Tools', 'Convert RM, US$, units and terms'],
      ['monte-carlo/', 'Monte Carlo Simulator', 'Simulated price paths'],
      ['market-simulator/', 'Market Simulator', 'Practise trading in the browser'],
      ['backtester/', 'Strategy Backtester', 'Test a trading rule on history']]],
    ['Stocks & AI', [
      ['bursa-monitor/', 'Bursa Malaysia Monitor', 'KLCI and about 50 large companies'],
      ['sp500-monitor/', 'S&P 500 Monitor', 'The index and its biggest companies'],
      ['screener/', 'Stock Screener', 'Filter stocks by valuation and trend'],
      ['mpob-event-study/', 'MPOB Day Event Study', 'Plantation stocks around MPOB reports'],
      ['ai-brokerage/', 'Quorvia AI Brokerage', 'An AI brokerage desk on FCPO, simulated'],
      ['rl-trader/', 'Kestrel RL Trader', 'A reinforcement-learning trading demo'],
      ['merlin-nasdaq/', 'Merlin Nasdaq Agent', 'A multi-asset agent demo']]],
    ['More', [
      ['about/', 'About me', 'Who built this site'],
      ['status/', 'Site Status', 'Is every feed and page up to date?'],
      ['palm-oil-monitor/archive/', 'Report Archive', 'Past editions of the monthly report']]]
  ];
  // hand-picked related pages; otherwise the page's own group
  var REL = {
    'palm-world/': ['import-margins/', 'world-demand/', 'india-imports/', 'indonesia/'],
    'import-margins/': ['india-imports/', 'palm-world/', 'fcpo-drivers/', 'bmd-fcpo/'],
    'open-interest/': ['dce-positions/', 'cftc-positions/', 'dce-report/', 'bmd-fcpo/'],
    'fcpo-model/': ['fcpo-drivers/', 'bmd-fcpo/', 'cftc-positions/', 'mpob-nowcast/'],
    'fcpo-drivers/': ['fcpo-model/', 'bmd-fcpo/', 'mpob-nowcast/', 'palm-oil-fundamentals/'],
    'dce-report/': ['dce-positions/', 'bmd-fcpo/', 'cftc-positions/', 'palm-hub/'],
    'bmd-fcpo/': ['dce-positions/', 'cftc-positions/', 'mpob-nowcast/', 'energy-monitor/'],
    'dce-positions/': ['bmd-fcpo/', 'cftc-positions/', 'palm-hub/', 'world-demand/'],
    'cftc-positions/': ['bmd-fcpo/', 'dce-positions/', 'energy-monitor/', 'india-imports/'],
    'mpob-nowcast/': ['seasonality/', 'weather-monitor/', 'bmd-fcpo/', 'mpob-event-study/'],
    'palm-hub/': ['palm-overview/', 'bmd-fcpo/', 'palm-oil-fundamentals/', 'mpob-nowcast/'],
    'fcpo-calculator/': ['hedge-calculator/', 'bmd-fcpo/', 'fcpo-swap/', 'spread-analyser/'],
    'hedge-calculator/': ['fcpo-calculator/', 'bmd-fcpo/', 'fcpo-swap/', 'option-strategy/'],
    'energy-monitor/': ['biodiesel/', 'bmd-fcpo/', 'cftc-positions/', 'oil-price-map/'],
    'india-imports/': ['world-demand/', 'oil-price-map/', 'bmd-fcpo/', 'indonesia-export-tax/']
  };
  var ALL = [], BY = {};
  G.forEach(function (g) { g[1].forEach(function (p) { var o = { path: p[0], title: p[1], desc: p[2], group: g[0] }; ALL.push(o); BY[p[0]] = o; }); });
  var rp = ''; try { rp = new URL(root, location.href).pathname; } catch (e) { rp = '/'; }
  var cur = location.pathname.indexOf(rp) === 0 ? location.pathname.slice(rp.length) : location.pathname.replace(/^\//, '');
  cur = cur.replace(/index\.html$/, '');
  var href = function (p) { return root + p; };
  var esc = function (t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };

  var CSS = '.bw-nav{position:sticky;top:0;z-index:60;background:color-mix(in srgb,var(--surface,#fff) 92%,transparent);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line,#ddd);font:500 14px var(--body,system-ui,sans-serif)}' +
    '.bw-nav .in{max-width:1560px;margin:0 auto;display:flex;align-items:center;gap:4px;padding:6px 16px;min-height:48px}' +
    '.bw-nav a.br{font:800 17px var(--display,system-ui);color:var(--ink,#222);text-decoration:none;margin-right:10px;white-space:nowrap}' +
    '.bw-nav .gr{position:relative}.bw-nav .gb{background:none;border:0;padding:8px 10px;border-radius:8px;color:var(--ink-2,#444);font:600 14px var(--body,system-ui);cursor:pointer;white-space:nowrap}' +
    '.bw-nav .gb:hover,.bw-nav .gb[aria-expanded="true"],.bw-nav .gb.on{background:var(--accent-soft,#eef);color:var(--ink,#111)}' +
    '.bw-nav .dd{position:absolute;top:calc(100% + 6px);left:0;min-width:300px;max-width:min(92vw,360px);background:var(--surface,#fff);border:1px solid var(--line,#ddd);border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,.16);padding:6px;display:none;max-height:calc(100vh - 70px);overflow:auto}' +
    '.bw-nav .dd::before{content:"";position:absolute;left:0;right:0;top:-10px;height:10px}.bw-nav .gr.r .dd{left:auto;right:0}.bw-nav .gr.open .dd{display:block}.bw-nav .dd a{display:grid;gap:1px;padding:8px 10px;border-radius:8px;text-decoration:none;color:var(--ink,#222)}' +
    '.bw-nav .dd a:hover,.bw-nav .dd a:focus-visible{background:var(--accent-soft,#eef);outline:none}.bw-nav .dd a b{font:600 14px var(--body,system-ui)}.bw-nav .dd a span{font-size:12.5px;color:var(--muted,#777)}' +
    '.bw-nav .dd a.cur{box-shadow:inset 3px 0 0 var(--accent,#334)}' +
    '.bw-nav .sp{flex:1}.bw-nav .sb{display:flex;align-items:center;gap:8px;border:1px solid var(--line,#ddd);background:var(--bg,#f5f5f5);color:var(--muted,#777);border-radius:9px;padding:6px 10px;cursor:pointer;font:500 13px var(--body,system-ui);min-width:190px}' +
    '.bw-nav .sb kbd,.bw-q kbd{font:600 11px var(--mono,monospace);border:1px solid var(--line,#ccc);border-radius:5px;padding:1px 5px;background:var(--surface,#fff);color:var(--ink-2,#555)}' +
    '.bw-nav .mb{display:none;background:none;border:1px solid var(--line,#ddd);border-radius:9px;padding:6px 12px;font:600 14px var(--body,system-ui);color:var(--ink,#222);cursor:pointer}' +
    '@media (max-width:980px){.bw-nav .gr{display:none}.bw-nav .mb{display:inline-block}.bw-nav .sb{min-width:0}.bw-nav .sb .t{display:none}.bw-nav.mopen .gr{display:block}.bw-nav.mopen .in{flex-wrap:wrap}.bw-nav.mopen .grs{flex-basis:100%;display:grid;gap:2px;padding:6px 0}.bw-nav.mopen .dd{position:static;display:block;box-shadow:none;border:0;max-width:none;padding:0 0 6px 8px}.bw-nav.mopen .gb{pointer-events:none;padding-left:0;color:var(--muted,#777);font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}}' +
    '.bw-nav .grs{display:flex;gap:2px}' +
    '.bw-q{position:fixed;inset:0;z-index:80;background:rgba(10,14,20,.45);display:none;align-items:flex-start;justify-content:center;padding:10vh 14px 14px}.bw-q.open{display:flex}' +
    '.bw-q .bx{width:min(640px,100%);background:var(--surface,#fff);border:1px solid var(--line,#ddd);border-radius:14px;box-shadow:0 20px 50px rgba(0,0,0,.3);overflow:hidden}' +
    '.bw-q input{width:100%;border:0;border-bottom:1px solid var(--line,#ddd);padding:16px 18px;font:500 17px var(--body,system-ui);background:var(--surface,#fff);color:var(--ink,#222);outline:none;border-radius:0}' +
    '.bw-q ul{list-style:none;margin:0;padding:6px;max-height:min(60vh,460px);overflow:auto}.bw-q li a{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:9px 12px;border-radius:9px;text-decoration:none;color:var(--ink,#222)}' +
    '.bw-q li a b{font:600 15px var(--body,system-ui)}.bw-q li a i{font-style:normal;font-size:12px;color:var(--muted,#777);align-self:center}.bw-q li a span{grid-column:1/-1;font-size:13px;color:var(--ink-2,#555)}' +
    '.bw-q li.on a{background:var(--accent-soft,#eef)}.bw-q .ft{display:flex;gap:14px;padding:8px 14px;border-top:1px solid var(--line,#ddd);font-size:12px;color:var(--muted,#777)}' +
    '.bw-rel{max-width:1180px;margin:34px auto 10px;padding:0 16px;display:grid;gap:12px}.bw-rel h2{font:800 20px var(--display,system-ui);margin:0}' +
    '.bw-rel .g{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:10px}' +
    '.bw-rel a{display:grid;gap:3px;padding:12px 14px;border:1px solid var(--line,#ddd);border-top:3px solid var(--accent,#334);border-radius:12px;background:var(--surface,#fff);text-decoration:none;color:var(--ink,#222);transition:transform .12s}' +
    '.bw-rel a:hover{transform:translateY(-2px)}.bw-rel a b{font:600 15px var(--body,system-ui)}.bw-rel a span{font-size:13px;color:var(--ink-2,#555)}.bw-rel a i{font-style:normal;font-size:11.5px;color:var(--muted,#777);text-transform:uppercase;letter-spacing:.04em}' +
    '@media print{.bw-nav,.bw-q,.bw-rel{display:none}}';

  function build() {
    if (document.querySelector('.bw-nav')) return;
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    var curGroup = BY[cur] ? BY[cur].group : null;
    var nav = document.createElement('nav'); nav.className = 'bw-nav'; nav.setAttribute('aria-label', 'Site');
    nav.innerHTML = '<div class="in"><a class="br" href="' + href('') + '">BoonWui</a><button type="button" class="mb" aria-expanded="false">Menu</button><div class="grs">' +
      G.map(function (g, i) {
        return '<div class="gr' + (i >= G.length - 2 ? ' r' : '') + '"><button type="button" class="gb' + (g[0] === curGroup ? ' on' : '') + '" aria-expanded="false" aria-controls="bwdd' + i + '">' + esc(g[0]) + ' ▾</button><div class="dd" id="bwdd' + i + '">' +
          g[1].map(function (p) { return '<a href="' + href(p[0]) + '"' + (p[0] === cur ? ' class="cur" aria-current="page"' : '') + '><b>' + esc(p[1]) + '</b><span>' + esc(p[2]) + '</span></a>'; }).join('') + '</div></div>';
      }).join('') + '</div><span class="sp"></span><button type="button" class="sb" aria-label="Search pages"><span>⌕</span><span class="t">Search pages</span><kbd>/</kbd></button></div>';
    document.body.insertBefore(nav, document.body.firstChild);
    // run edge to edge even when the page pads its body
    var bs = getComputedStyle(document.body); nav.style.marginLeft = '-' + bs.paddingLeft; nav.style.marginRight = '-' + bs.paddingRight; nav.style.marginTop = '-' + bs.paddingTop; if (parseFloat(bs.paddingTop) > 0) nav.style.marginBottom = bs.paddingTop;
    // the old "← BoonWui portfolio" row is replaced by the menu
    Array.prototype.forEach.call(document.querySelectorAll('.top'), function (t) { var a = t.querySelector('a'); if (a && /portfolio|←/.test(a.textContent)) t.style.display = 'none'; });
    var groups = nav.querySelectorAll('.gr');
    var closeAll = function (except) { Array.prototype.forEach.call(groups, function (g) { if (g !== except) { g.classList.remove('open'); g.querySelector('.gb').setAttribute('aria-expanded', 'false'); } }); };
    Array.prototype.forEach.call(groups, function (g) {
      var b = g.querySelector('.gb');
      b.addEventListener('click', function (e) { e.stopPropagation(); var o = !g.classList.contains('open'); closeAll(g); g.classList.toggle('open', o); b.setAttribute('aria-expanded', o); });
      var timer = null, desk = function () { return matchMedia('(hover:hover) and (min-width:981px)').matches; };
      g.addEventListener('mouseenter', function () { if (!desk()) return; clearTimeout(timer); closeAll(g); g.classList.add('open'); b.setAttribute('aria-expanded', 'true'); });
      // close a moment after the mouse leaves, so moving down into the list (or across a small gap) keeps it open
      g.addEventListener('mouseleave', function () { if (!desk()) return; clearTimeout(timer); timer = setTimeout(function () { g.classList.remove('open'); b.setAttribute('aria-expanded', 'false'); }, 350); });
    });
    document.addEventListener('click', function (e) { if (!nav.contains(e.target)) closeAll(); });
    var mb = nav.querySelector('.mb');
    mb.addEventListener('click', function () { var o = !nav.classList.contains('mopen'); nav.classList.toggle('mopen', o); mb.setAttribute('aria-expanded', o); mb.textContent = o ? 'Close' : 'Menu'; });

    // ---------- quick search ----------
    var q = document.createElement('div'); q.className = 'bw-q'; q.setAttribute('role', 'dialog'); q.setAttribute('aria-label', 'Search pages');
    q.innerHTML = '<div class="bx"><input type="search" placeholder="Search pages… e.g. cftc, swap, weather" aria-label="Search pages" autocomplete="off"><ul role="listbox"></ul><div class="ft"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></div></div>';
    document.body.appendChild(q);
    var inp = q.querySelector('input'), ul = q.querySelector('ul'), sel = 0, hits = [];
    var score = function (p, t) {
      if (!t) return 1; var h = (p.title + ' ' + p.desc + ' ' + p.group).toLowerCase(), ti = p.title.toLowerCase(), s = 0;
      for (var w of t.split(/\s+/)) { if (!w) continue; if (ti.indexOf(w) === 0) s += 5; else if (ti.indexOf(w) >= 0) s += 3; else if (h.indexOf(w) >= 0) s += 1; else return 0; }
      return s;
    };
    var render = function () {
      var t = inp.value.trim().toLowerCase();
      hits = ALL.map(function (p) { return { p: p, s: score(p, t) }; }).filter(function (x) { return x.s > 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 12).map(function (x) { return x.p; });
      sel = Math.min(sel, Math.max(0, hits.length - 1));
      ul.innerHTML = hits.length ? hits.map(function (p, i) { return '<li role="option"' + (i === sel ? ' class="on" aria-selected="true"' : '') + '><a href="' + href(p.path) + '"><b>' + esc(p.title) + '</b><i>' + esc(p.group) + '</i><span>' + esc(p.desc) + '</span></a></li>'; }).join('') : '<li style="padding:12px;color:var(--muted,#777)">No page matches.</li>';
      var on = ul.querySelector('.on'); if (on && on.scrollIntoView) on.scrollIntoView({ block: 'nearest' });
    };
    var open = function () { q.classList.add('open'); inp.value = ''; sel = 0; render(); setTimeout(function () { inp.focus(); }, 10); };
    var close = function () { q.classList.remove('open'); };
    nav.querySelector('.sb').addEventListener('click', open);
    q.addEventListener('click', function (e) { if (e.target === q) close(); });
    inp.addEventListener('input', function () { sel = 0; render(); });
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { sel = Math.min(hits.length - 1, sel + 1); render(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); render(); e.preventDefault(); }
      else if (e.key === 'Enter' && hits[sel]) { location.href = href(hits[sel].path); }
      else if (e.key === 'Escape') close();
    });
    document.addEventListener('keydown', function (e) {
      var tag = (e.target.tagName || '').toLowerCase(), typing = tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable;
      if ((e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); open(); }
      else if (e.key === '/' && !typing) { e.preventDefault(); open(); }
      else if (e.key === 'Escape') { close(); closeAll(); }
    });

    // ---------- related pages ----------
    if (cur && BY[cur]) {
      var me2 = BY[cur], list = (REL[cur] || ALL.filter(function (p) { return p.group === me2.group && p.path !== cur && p.path !== ''; }).map(function (p) { return p.path; })).slice(0, 4);
      var rel = document.createElement('section'); rel.className = 'bw-rel'; rel.setAttribute('aria-label', 'Related pages');
      rel.innerHTML = '<h2>Related pages</h2><div class="g">' + list.filter(function (p) { return BY[p]; }).map(function (p) { var o = BY[p]; return '<a href="' + href(p) + '"><i>' + esc(o.group) + '</i><b>' + esc(o.title) + '</b><span>' + esc(o.desc) + '</span></a>'; }).join('') + '</div>';
      var host = document.querySelector('.app') || document.querySelector('main') || document.body;
      if (host === document.body) document.body.appendChild(rel); else host.parentNode.insertBefore(rel, host.nextSibling);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
