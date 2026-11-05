/* Tiny SVG line-chart helper shared by the portfolio tools. */
window.MiniChart = (function () {
  function nice(lo, hi, n) {
    var raw = (hi - lo) / (n || 4) || 1, mag = Math.pow(10, Math.floor(Math.log10(raw))), e = raw / mag;
    return (e <= 1 ? 1 : e <= 2 ? 2 : e <= 2.5 ? 2.5 : e <= 5 ? 5 : 10) * mag;
  }
  function fmt(v) {
    var a = Math.abs(v), s = a >= 1e6 ? (a / 1e6).toFixed(1) + 'M' : a >= 1e4 ? (a / 1e3).toFixed(0) + 'k' : a >= 1e3 ? (a / 1e3).toFixed(1) + 'k' : a >= 10 ? a.toFixed(0) : a >= 1 ? a.toFixed(1) : a.toFixed(2);
    return (v < 0 ? '−' : '') + s.replace('.0k', 'k');
  }
  // opts: { width, height, xs:[...], xLabel(fn), series:[{pts:[[x,y]], color, width, dash, fill:[lowerPts]}], hlines:[{y,color,label,dash}], vlines:[{x,color,label}], yFmt, points:[{x,y,color}] }
  function draw(svg, o) {
    var W = o.width || 640, H = o.height || 260, ml = 58, mr = 12, mt = 14, mb = 28, pw = W - ml - mr, ph = H - mt - mb;
    var xs = [], ys = [];
    o.series.forEach(function (s) { s.pts.forEach(function (p) { xs.push(p[0]); ys.push(p[1]); }); if (s.fill) s.fill.forEach(function (p) { ys.push(p[1]); }); });
    (o.hlines || []).forEach(function (h) { ys.push(h.y); });
    if (!xs.length) { svg.innerHTML = ''; return; }
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    if (o.zero) { y0 = Math.min(y0, 0); y1 = Math.max(y1, 0); }
    var pad = (y1 - y0) * 0.06 || Math.abs(y1) * 0.1 || 1; y0 -= pad; y1 += pad;
    if (x1 === x0) x1 = x0 + 1;
    var X = function (v) { return ml + (v - x0) / (x1 - x0) * pw; }, Y = function (v) { return mt + (1 - (v - y0) / (y1 - y0)) * ph; };
    var yf = o.yFmt || fmt, s = '', st = nice(y0, y1, 4);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    for (var t = Math.ceil(y0 / st) * st; t <= y1; t += st) {
      s += '<line class="grid" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '"/>';
      s += '<text x="' + (ml - 7) + '" y="' + (Y(t) + 4).toFixed(1) + '" text-anchor="end">' + yf(t) + '</text>';
    }
    var xl = o.xLabel || function (v) { return fmt(v); };
    for (var k = 0; k <= 5; k++) { var xv = x0 + (x1 - x0) * k / 5; s += '<text x="' + X(xv).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="' + (k === 0 ? 'start' : k === 5 ? 'end' : 'middle') + '">' + xl(xv) + '</text>'; }
    (o.hlines || []).forEach(function (h) {
      s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(h.y).toFixed(1) + '" y2="' + Y(h.y).toFixed(1) + '" style="stroke:' + (h.color || 'var(--muted)') + '" stroke-dasharray="' + (h.dash || '4 3') + '"/>';
      if (h.label) s += '<text x="' + (W - mr - 2) + '" y="' + (Y(h.y) - 4).toFixed(1) + '" text-anchor="end" style="fill:' + (h.color || 'var(--muted)') + '">' + h.label + '</text>';
    });
    (o.vlines || []).forEach(function (v) {
      s += '<line x1="' + X(v.x).toFixed(1) + '" x2="' + X(v.x).toFixed(1) + '" y1="' + mt + '" y2="' + (mt + ph) + '" style="stroke:' + (v.color || 'var(--muted)') + '" stroke-dasharray="3 4"/>';
      if (v.label) s += '<text x="' + (X(v.x) + 4).toFixed(1) + '" y="' + (mt + 11) + '" style="fill:' + (v.color || 'var(--muted)') + '">' + v.label + '</text>';
    });
    var path = function (pts) { return pts.map(function (p, i) { return (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1); }).join(''); };
    o.series.forEach(function (sr) {
      if (sr.fill) s += '<path d="' + path(sr.pts) + path(sr.fill.slice().reverse()).replace('M', 'L') + 'Z" style="fill:' + sr.color + ';opacity:' + (sr.opacity || 0.15) + '"/>';
      else s += '<path d="' + path(sr.pts) + '" style="fill:none;stroke:' + sr.color + ';stroke-width:' + (sr.width || 2) + (sr.dash ? ';stroke-dasharray:' + sr.dash : '') + ';stroke-linejoin:round"/>';
    });
    (o.points || []).forEach(function (p) { s += '<circle cx="' + X(p.x).toFixed(1) + '" cy="' + Y(p.y).toFixed(1) + '" r="' + (p.r || 4) + '" style="fill:' + p.color + ';stroke:var(--surface);stroke-width:1.5"/>'; });
    svg.innerHTML = s;
  }
  return { draw: draw, fmt: fmt };
})();
