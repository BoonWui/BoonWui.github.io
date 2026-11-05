/* Shared market-data helpers for the screener, backtester and stock pages.
   Loads a monitor's data.json (daily closes) plus live.json (hourly prices) and computes common indicators. */
window.Market = (function () {
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var MARKETS = {
    bursa: { key: 'bursa', dir: 'bursa-monitor', name: 'Bursa Malaysia', short: 'Bursa', cur: 'RM', tz: 'Asia/Kuala_Lumpur', tzName: 'Malaysia time' },
    sp500: { key: 'sp500', dir: 'sp500-monitor', name: 'S&P 500', short: 'US', cur: 'US$', tz: 'America/New_York', tzName: 'New York time' }
  };

  function getJSON(url, optional) {
    var p = fetch(url, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + url); return r.json(); });
    return optional ? p.catch(function () { return null; }) : p;
  }

  // Hourly prices update today's row, or add it if the daily history has not caught up yet.
  function mergeLive(D, LV, M) {
    D.liveNote = null; D.liveFetched = null;
    if (!LV || !LV.prices || !LV.date) return D;
    D.liveFetched = LV.fetched;
    var lastDate = D.dates[D.dates.length - 1];
    if (LV.date < lastDate) return D;
    var add = LV.date > lastDate;
    if (add) D.dates.push(LV.date);
    Object.keys(D.close).forEach(function (sym) {
      var v = LV.prices[sym]; if (v == null) { if (add) D.close[sym].push(null); return; }
      if (add) D.close[sym].push(v); else D.close[sym][D.close[sym].length - 1] = v;
    });
    var when; try { when = new Date(LV.fetched).toLocaleTimeString('en-GB', { timeZone: M.tz, hour: '2-digit', minute: '2-digit' }) + ' ' + M.tzName; } catch (e) { when = LV.fetched; }
    D.liveNote = 'Prices as of ' + when + ', ' + LV.date + ' (Yahoo Finance, about 15 minutes delayed)';
    return D;
  }

  // load('bursa', '../') -> Promise of the merged dataset with a few conveniences attached.
  function load(key, root) {
    var M = MARKETS[key], base = (root || '') + M.dir + '/';
    return Promise.all([getJSON(base + 'data.json'), getJSON(base + 'live.json', true)]).then(function (x) {
      var D = mergeLive(x[0], x[1], M);
      D.market = M;
      D.K = ffill(D.close[D.index.symbol]);
      D.series = function (sym) { return ffill(D.close[sym] || []); };
      D.stockBy = {}; D.stocks.forEach(function (s) { s.market = key; D.stockBy[s.symbol] = s; });
      return D;
    });
  }

  function ffill(arr) { var out = [], p = null; for (var i = 0; i < arr.length; i++) { if (arr[i] != null) p = arr[i]; out.push(p); } return out; }
  function mean(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s / (a.length || 1); }
  function sd(a) { var m = mean(a), s = 0; for (var i = 0; i < a.length; i++) s += (a[i] - m) * (a[i] - m); return Math.sqrt(s / Math.max(1, a.length - 1)); }
  function sma(a, n, i) { if (i < n - 1) return null; var s = 0; for (var k = i - n + 1; k <= i; k++) { if (a[k] == null) return null; s += a[k]; } return s / n; }
  function smaSeries(a, n) { var out = new Array(a.length).fill(null), s = 0, c = 0; for (var i = 0; i < a.length; i++) { if (a[i] == null) { s = 0; c = 0; continue; } s += a[i]; c++; if (c > n) { s -= a[i - n]; c = n; } if (c === n) out[i] = s / n; } return out; }
  function rsiSeries(a, n) {   // Wilder RSI, null until it has n changes
    var out = new Array(a.length).fill(null), g = 0, l = 0, k = 0;
    for (var i = 1; i < a.length; i++) {
      if (a[i] == null || a[i - 1] == null) continue;
      var ch = a[i] - a[i - 1], up = Math.max(ch, 0), dn = Math.max(-ch, 0); k++;
      if (k <= n) { g += up / n; l += dn / n; } else { g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n; }
      if (k >= n) out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    }
    return out;
  }

  // Standard metrics for one price series against the index K, at the last date.
  function metrics(a, K, dates) {
    var L = a.length - 1, Y1 = Math.max(0, L - 252);
    var ytdBase = (function () { var y = dates[L].slice(0, 4); for (var i = L; i >= 0; i--) if (dates[i].slice(0, 4) < y) return i; return 0; })();
    var r = function (k) { var b = a[Math.max(0, L - k)]; return b && a[L] ? (a[L] / b - 1) * 100 : NaN; };
    var yr = a.slice(Y1).filter(function (v) { return v != null; }), hi = Math.max.apply(null, yr), lo = Math.min.apply(null, yr);
    var dr = [], kr = [];
    for (var i = Y1 + 1; i <= L; i++) { dr.push(a[i] && a[i - 1] ? Math.log(a[i] / a[i - 1]) : 0); kr.push(K[i] && K[i - 1] ? Math.log(K[i] / K[i - 1]) : 0); }
    var mr = mean(dr), mk = mean(kr), cov = 0, vk = 0; for (var j = 0; j < dr.length; j++) { cov += (dr[j] - mr) * (kr[j] - mk); vk += (kr[j] - mk) * (kr[j] - mk); }
    var peak = 0, mdd = 0; for (var t = Y1; t <= L; t++) { if (a[t] == null) continue; peak = Math.max(peak, a[t]); mdd = Math.min(mdd, a[t] / peak - 1); }
    var m50 = sma(a, 50, L), m50p = sma(a, 50, L - 10), m200 = sma(a, 200, L), rs = rsiSeries(a.slice(Math.max(0, L - 260)), 14);
    var trend = m50 && m200 ? (a[L] > m50 && m50 > m200 && m50 > m50p ? 'Up' : a[L] < m50 && m50 < m200 && m50 < m50p ? 'Down' : 'Mixed') : '–';
    return {
      px: a[L], d1: r(1), w1: r(5), m1: r(21), m3: r(63), m6: r(126), ytd: a[ytdBase] ? (a[L] / a[ytdBase] - 1) * 100 : NaN, y1: r(252),
      hi: hi, lo: lo, pos: hi > lo ? (a[L] - lo) / (hi - lo) : 0.5, offHi: (a[L] / hi - 1) * 100,
      vol: sd(dr) * Math.sqrt(252) * 100, beta: vk ? cov / vk : NaN, mdd: mdd * 100, rsi: rs[rs.length - 1],
      m50: m50, m200: m200, vs50: m50 ? (a[L] / m50 - 1) * 100 : NaN, vs200: m200 ? (a[L] / m200 - 1) * 100 : NaN,
      trend: trend, trendN: trend === 'Up' ? 1 : trend === 'Down' ? -1 : 0, above200: m200 ? a[L] > m200 : null
    };
  }

  // Formatting
  function sg(v, d) { return !isFinite(v) ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d == null ? 1 : d); }
  function cls(v) { return v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fd(d) { var p = d.split('-'); return +p[2] + ' ' + MON[+p[1] - 1] + ' ' + p[0]; }
  function tnum(d) { var p = d.split('-'); return +p[0] + (+p[1] - 1) / 12 + (+p[2] - 1) / 365; }
  function mlab(v) { var y = Math.floor(v), m = Math.min(11, Math.floor((v - y) * 12 + 1e-6)); return MON[m] + " '" + String(y).slice(2); }
  function px(v) { return !isFinite(v) ? '–' : v >= 1000 ? v.toLocaleString('en', { maximumFractionDigits: 0 }) : v.toFixed(2); }
  function q(name) { var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(location.search); return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : null; }
  function stockUrl(root, key, sym) { return (root || '') + 'stock/?m=' + key + '&s=' + encodeURIComponent(sym); }

  return { MARKETS: MARKETS, load: load, ffill: ffill, mean: mean, sd: sd, sma: sma, smaSeries: smaSeries, rsiSeries: rsiSeries, metrics: metrics,
    sg: sg, cls: cls, esc: esc, fd: fd, tnum: tnum, mlab: mlab, px: px, q: q, stockUrl: stockUrl, MON: MON };
})();
