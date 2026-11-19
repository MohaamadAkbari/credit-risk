document.querySelectorAll('.cr-search').forEach((inp) => inp.addEventListener('input', () => { dash.draw('dict-body'); dash.draw('dict-count'); }));

const dictFilter = () => {
  const tSel = document.querySelector('[data-draw="dict-table"]');
  const gSel = document.querySelector('[data-draw="dict-group"]');
  const q = document.querySelector('.cr-search');
  return { table: tSel ? tSel.value : '', group: gSel ? gSel.value : '', q: q ? q.value.trim().toLowerCase() : '' };
};
window.CR.dictFilter = dictFilter;

dash.draw('dict-table', (sel) => {
  const st = dash.data('dictionary');
  const tables = st.status === 'ok' ? [...new Set(st.data.map((r) => r.table))] : [];
  const cur = sel.value;
  sel.replaceChildren(new Option('All tables', ''), ...tables.map((t) => new Option(t, t)));
  sel.value = tables.includes(cur) ? cur : '';
  sel.onchange = () => { dash.draw('dict-group'); dash.draw('dict-body'); dash.draw('dict-count'); };
});

dash.draw('dict-group', (sel) => {
  const st = dash.data('dictionary');
  const f = CR.dictFilter();
  const groups = st.status === 'ok' ? [...new Set(st.data.filter((r) => !f.table || r.table === f.table).map((r) => r.group))] : [];
  const cur = sel.value;
  sel.replaceChildren(new Option('All groups', ''), ...groups.map((g) => new Option(g, g)));
  sel.value = groups.includes(cur) ? cur : '';
  sel.onchange = () => { dash.draw('dict-body'); dash.draw('dict-count'); };
});

dash.draw('dict-body', (tb) => {
  const st = dash.data('dictionary');
  if (!CR.state(tb, st)) return;
  const f = CR.dictFilter();
  const rows = st.data.filter((r) => (!f.table || r.table === f.table) && (!f.group || r.group === f.group)
    && (!f.q || (r.column + ' ' + (r.description || '') + ' ' + r.group).toLowerCase().includes(f.q)));
  tb.replaceChildren(...rows.map((r) => {
    const tr = document.createElement('tr'); tr.dataset.key = r.table + ',' + r.column;
    const c = CR.cell(tr, ''); const code = document.createElement('code'); code.textContent = r.column; c.appendChild(code);
    if (!f.table) { const sm = document.createElement('div'); sm.className = 'cr-muted'; sm.textContent = r.table; c.appendChild(sm); }
    CR.cell(tr, r.group); CR.cell(tr, r.kind + (r.unit && r.unit !== r.kind && !['category', 'flag', 'key'].includes(r.kind) ? ' · ' + r.unit : ''));
    CR.cell(tr, r.description || '');
    const rng = r.range || (r.top_levels ? `${r.n_unique} levels: ${r.top_levels}` : '');
    CR.cell(tr, rng + (r.n_marker ? ` (${CR.f.int(r.n_marker)} code values left out)` : ''));
    CR.cell(tr, d3.format('.1f')(r.missing_pct), true);
    CR.cell(tr, r.iv_train == null ? '' : d3.format('.3f')(r.iv_train), true);
    CR.cell(tr, r.special || '');
    return tr;
  }));
});

dash.draw('dict-count', (el) => {
  const st = dash.data('dictionary');
  if (st.status !== 'ok') { el.textContent = '—'; return; }
  const f = CR.dictFilter();
  const n = st.data.filter((r) => (!f.table || r.table === f.table) && (!f.group || r.group === f.group)
    && (!f.q || (r.column + ' ' + (r.description || '') + ' ' + r.group).toLowerCase().includes(f.q))).length;
  el.textContent = `${n} of ${st.data.length}`;
});


dash.draw('seg-select', (sel) => {
  const st = dash.data('segments');
  const segs = st.status === 'ok' ? [...new Set(st.data.map((r) => r.segment))] : [];
  const cur = sel.value;
  sel.replaceChildren(...segs.map((s) => new Option(s, s)));
  sel.value = segs.includes(cur) ? cur : (segs[0] || '');
  sel.onchange = () => dash.draw('seg-chart');
});

dash.draw('seg-chart', (el) => {
  const st = dash.data('segments'); const ov = dash.data('overview');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const sel = document.querySelector('[data-draw="seg-select"]');
  const segs = [...new Set(st.data.map((r) => r.segment))];
  const seg = (sel && sel.value) || segs[0];
  const rows = st.data.filter((r) => r.segment === seg).sort((a, b) => a.order - b.order);
  const base = ov.status === 'ok' ? (ov.data.find((r) => r.metric === 'default_rate') || {}).value : null;
  CR.hbar(el, rows, {
    label: (r) => r.level, value: (r) => r.default_rate,
    text: (r) => `${CR.f.pct(r.default_rate)} · ${CR.f.int(r.applicants)}`,
    tip: (r) => [r.level, `Default rate ${CR.f.pct(r.default_rate, 2)}`, `${CR.f.int(r.applicants)} applicants (${CR.f.pct(r.share)} of all)`, `${CR.f.int(r.defaults)} with payment difficulty`],
    refs: base != null ? [{ v: base }] : [], aria: `Default rate by ${seg}`, xfmt: (v) => CR.f.pct(v, 0),
  });
});

const distRows = () => {
  const st = dash.data('distributions');
  if (st.status !== 'ok') return { st, rows: [], feat: '' };
  const sel = document.querySelector('[data-draw="dist-select"]');
  const feats = [...new Set(st.data.map((r) => r.feature))];
  const feat = (sel && sel.value) || feats[0];
  return { st, feat, rows: st.data.filter((r) => r.feature === feat).sort((a, b) => a.bin - b.bin) };
};
window.CR.distRows = distRows;

dash.draw('dist-select', (sel) => {
  const st = dash.data('distributions');
  const feats = st.status === 'ok' ? [...new Map(st.data.map((r) => [r.feature, r.label])).entries()] : [];
  const cur = sel.value;
  sel.replaceChildren(...feats.map(([k, l]) => new Option(l, k)));
  sel.value = feats.some(([k]) => k === cur) ? cur : (feats[0] ? feats[0][0] : '');
  sel.onchange = () => { CR.missWrap(); ['dist-chart', 'dist-median', 'dist-unit', 'dist-miss', 'dist-missrate'].forEach((n) => dash.draw(n)); };
});

// Show "whose default rate is ..." only for inputs that have missing values
window.CR.missWrap = () => {
  const { rows } = CR.distRows();
  const show = rows.length > 0 && rows[0].missing_default_rate != null && rows[0].missing_share > 0.001;
  document.querySelectorAll('.cr-missrate-wrap').forEach((w) => { w.hidden = !show; });
};
dash.onData(() => CR.missWrap());

dash.draw('dist-chart', (el) => {
  const { st, rows } = CR.distRows();
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  if (!rows.length) return;
  const h = 260;
  const { s, w } = CR.svg(el, h, `Histogram of ${rows[0].label} with default rate per range`);
  const tick = (v) => rows[0].scale === 'log' ? CR.f.si(v) : CR.f.num(v);
  const yl = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.applicants)]).nice();
  const rated = rows.filter((r) => r.applicants >= 200 && r.default_rate != null);
  const yr = d3.scaleLinear().domain([0, Math.max(0.05, d3.max(rated, (r) => r.default_rate) * 1.15)]).nice();
  const ml = CR.measure(s, yl.ticks(5).map((v) => CR.f.si(v))) + 10;
  const mr = CR.measure(s, yr.ticks(5).map((v) => CR.f.pct(v, 0))) + 10;
  const m = { l: ml, r: mr, t: 8, b: 26 };
  const x = d3.scaleBand().domain(rows.map((r) => r.bin)).range([m.l, w - m.r]).padding(0.08);
  yl.range([h - m.b, m.t]); yr.range([h - m.b, m.t]);
  s.append('g').attr('class', 'cr-gridline').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(yl).ticks(5).tickSize(-(w - m.l - m.r)).tickFormat(''))
    .call((g) => g.select('.domain').remove());
  s.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(yl).ticks(5).tickFormat((v) => CR.f.si(v)).tickSizeOuter(0));
  s.append('g').attr('transform', `translate(${w - m.r},0)`).call(d3.axisRight(yr).ticks(5).tickFormat((v) => CR.f.pct(v, 0)).tickSizeOuter(0));
  const every = w < 420 ? 5 : w < 700 ? 4 : 2;
  s.append('g').attr('transform', `translate(0,${h - m.b})`).call(d3.axisBottom(x).tickValues(rows.filter((r, i) => i % every === 0).map((r) => r.bin))
    .tickFormat((b) => tick(rows[b].lo)).tickSizeOuter(0));
  const t = CR.tip(el);
  s.selectAll('rect.cr-bar').data(rows).join('rect').attr('class', 'cr-bar').attr('x', (r) => x(r.bin)).attr('width', x.bandwidth())
    .attr('y', (r) => yl(r.applicants)).attr('height', (r) => yl(0) - yl(r.applicants)).style('fill', CR.color(0)).style('opacity', 0.55);
  s.append('path').datum(rated).attr('fill', 'none').style('stroke', CR.color(1)).attr('stroke-width', 2)
    .attr('d', d3.line().x((r) => x(r.bin) + x.bandwidth() / 2).y((r) => yr(r.default_rate)));
  s.selectAll('circle').data(rated).join('circle').attr('cx', (r) => x(r.bin) + x.bandwidth() / 2).attr('cy', (r) => yr(r.default_rate)).attr('r', 3).style('fill', CR.color(1));
  s.selectAll('rect.cr-hit').data(rows).join('rect').attr('class', 'cr-hit').attr('x', (r) => x(r.bin)).attr('width', x.bandwidth())
    .attr('y', m.t).attr('height', h - m.b - m.t).style('fill', 'transparent')
    .on('mousemove', (ev, r) => t.show(ev, [`${tick(r.lo)} to ${tick(r.hi)} ${r.unit}`, `${CR.f.int(r.applicants)} applicants`,
      r.applicants >= 200 && r.default_rate != null ? `Default rate ${CR.f.pct(r.default_rate, 1)}` : 'Too few applicants for a rate']))
    .on('mouseleave', () => t.hide());
});

const distFirst = (el, field, fmt) => {
  const { st, rows, feat } = CR.distRows();
  if (!CR.state(el, st)) return;
  if (!rows.length) { el.textContent = '—'; return; }
  el.dataset.where = `feature=${encodeURIComponent(feat)}&bin=0`;
  el.textContent = fmt(rows[0][field], rows[0]);
};
dash.draw('dist-median', (el) => distFirst(el, 'median', (v, r) => r.scale === 'log' ? CR.f.int(v) : CR.f.num(v)));
dash.draw('dist-unit', (el) => { const { rows } = CR.distRows(); el.textContent = rows.length ? rows[0].unit : '—'; });
dash.draw('dist-miss', (el) => distFirst(el, 'missing_share', (v) => CR.f.pct(v, 1)));
dash.draw('dist-missrate', (el) => distFirst(el, 'missing_default_rate', (v) => v == null ? '—' : CR.f.pct(v, 1)));

dash.draw('loan-panel', (el) => {
  const st = dash.data('loan_size_term');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const rows = st.data.filter((r) => r.variable === el.dataset.var).sort((a, b) => a.fifth - b.fifth);
  const h = 200;
  const { s, w } = CR.svg(el, h, `Default rate by fifth of ${rows[0] ? rows[0].label : ''}`);
  const short = (v) => Math.abs(v) >= 1000 ? CR.f.si(v) : Math.abs(v) >= 10 ? d3.format('.0f')(v) : d3.format('.2f')(v);
  const m = { l: 6, r: 6, t: 20, b: 34 };
  const x = d3.scaleBand().domain(rows.map((r) => r.fifth)).range([m.l, w - m.r]).padding(0.18);
  const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.default_rate) * 1.1]).range([h - m.b, m.t]);
  const t = CR.tip(el);
  const g = s.selectAll('g.cr-q').data(rows).join('g').attr('class', 'cr-q');
  g.append('rect').attr('x', (r) => x(r.fifth)).attr('width', x.bandwidth()).attr('y', (r) => y(r.default_rate))
    .attr('height', (r) => y(0) - y(r.default_rate)).attr('rx', 2).style('fill', CR.color(0));
  g.append('text').attr('class', 'cr-val').attr('x', (r) => x(r.fifth) + x.bandwidth() / 2).attr('y', (r) => y(r.default_rate) - 5)
    .attr('text-anchor', 'middle').text((r) => CR.f.pct(r.default_rate, 1));
  g.append('text').attr('x', (r) => x(r.fifth) + x.bandwidth() / 2).attr('y', h - m.b + 14).attr('text-anchor', 'middle').text((r) => short(r.lo));
  g.append('text').attr('x', (r) => x(r.fifth) + x.bandwidth() / 2).attr('y', h - m.b + 28).attr('text-anchor', 'middle').text((r) => '–' + short(r.hi));
  g.append('rect').attr('x', (r) => x(r.fifth)).attr('width', x.bandwidth()).attr('y', m.t).attr('height', h - m.b - m.t).style('fill', 'transparent')
    .on('mousemove', (ev, r) => t.show(ev, [`${r.label}: ${short(r.lo)} to ${short(r.hi)}`, `Default rate ${CR.f.pct(r.default_rate, 2)}`,
      `Weighted by amount ${CR.f.pct(r.default_rate_amount, 2)}`, `${CR.f.int(r.applicants)} applicants`]))
    .on('mouseleave', () => t.hide());
});


dash.draw('missing-chart', (el) => {
  const st = dash.data('missing_view');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const rows = [...st.data].sort((a, b) => b.missing_pct - a.missing_pct);
  const leg = document.createElement('div'); leg.className = 'cr-legend';
  [['Default rate when missing', 1], ['Default rate when present', 0]].forEach(([l, i]) => { const s = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = CR.color(i); s.append(sw, l); leg.appendChild(s); });
  el.appendChild(leg);
  const bh = 18, gap = 4;
  const { s, w } = CR.svg(el, 40, 'Default rate when each column is missing versus present');
  const lw = Math.min(w * 0.42, CR.measure(s, rows.map((r) => r.label)) + 10);
  const tw = CR.measure(s, rows.map((r) => d3.format('.1f')(r.missing_pct) + '% missing'), 'cr-val') + 10;
  const h = rows.length * (bh + gap) + 26;
  s.attr('viewBox', `0 0 ${w} ${h}`);
  const xmax = d3.max(rows, (r) => Math.max(r.default_if_missing, r.default_if_present)) * 1.08;
  const x = d3.scaleLinear().domain([0, xmax]).range([lw, w - tw]);
  const t = CR.tip(el);
  s.append('g').attr('class', 'cr-gridline').attr('transform', `translate(0,${h - 20})`).call(d3.axisBottom(x).ticks(5).tickSize(-(h - 20)).tickFormat('')).select('.domain').remove();
  rows.forEach((r, i) => {
    const y = i * (bh + gap) + bh / 2;
    s.append('text').attr('x', lw - 8).attr('y', y).attr('dy', '0.35em').attr('text-anchor', 'end').text(r.label).each(function () { CR.fit(this, lw - 10); });
    s.append('line').attr('x1', x(r.default_if_present)).attr('x2', x(r.default_if_missing)).attr('y1', y).attr('y2', y).style('stroke', 'var(--cds-chart-muted)').attr('stroke-width', 2);
    s.append('circle').attr('cx', x(r.default_if_present)).attr('cy', y).attr('r', 4.5).style('fill', CR.color(0));
    s.append('circle').attr('cx', x(r.default_if_missing)).attr('cy', y).attr('r', 4.5).style('fill', CR.color(1));
    s.append('text').attr('class', 'cr-val').attr('x', w - tw + 8).attr('y', y).attr('dy', '0.35em').text(d3.format('.1f')(r.missing_pct) + '% missing');
    s.append('rect').attr('x', 0).attr('y', y - (bh + gap) / 2).attr('width', w).attr('height', bh + gap).style('fill', 'transparent')
      .on('mousemove', (ev) => t.show(ev, [r.label, `${d3.format('.1f')(r.missing_pct)}% missing`, `Default when missing ${CR.f.pct(r.default_if_missing, 1)}`,
        `Default when present ${CR.f.pct(r.default_if_present, 1)}`, `Missing for ${d3.format('.1f')(r.missing_in_thin_file_pct)}% of thin-file applicants vs ${d3.format('.1f')(r.missing_with_bureau_pct)}% of others`]))
      .on('mouseleave', () => t.hide());
  });
  s.append('g').attr('transform', `translate(0,${h - 20})`).call(d3.axisBottom(x).ticks(5).tickFormat((v) => CR.f.pct(v, 0)).tickSizeOuter(0)).select('.domain').remove();
});

dash.draw('signals-chart', (el) => {
  const st = dash.data('signals');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const sources = [...new Set(st.data.map((r) => r.source))];
  const leg = document.createElement('div'); leg.className = 'cr-legend';
  sources.forEach((src, i) => { const s = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = CR.color(i); s.append(sw, src); leg.appendChild(s); });
  el.appendChild(leg);
  CR.hbar(el, st.data, {
    barHeight: 16, label: (r) => r.feature, value: (r) => r.iv, text: (r) => d3.format('.3f')(r.iv),
    color: (r) => CR.color(sources.indexOf(r.source)),
    tip: (r) => [r.feature, r.source, `IV ${d3.format('.3f')(r.iv)}`, `Risk shape: ${r.shape}`, r.bin_rates ? `Default % by decile: ${r.bin_rates}` : ''].filter(Boolean),
    refs: [{ v: 0.1 }, { v: 0.3 }], aria: 'Information value of the 25 strongest inputs', xfmt: (v) => d3.format('.1f')(v),
  });
});

const tableBody = (id, key, cols) => (tb) => {
  const st = dash.data(id);
  if (!CR.state(tb, st)) return;
  tb.replaceChildren(...st.data.map((r) => {
    const tr = document.createElement('tr'); tr.dataset.key = r[key];
    cols.forEach(([fn, numeric]) => CR.cell(tr, fn(r), numeric));
    return tr;
  }));
};
dash.draw('thin-body', tableBody('thin_file', 'metric', [[(r) => r.metric], [(r) => CR.byFormat(r.format, r.has_bureau), true], [(r) => CR.byFormat(r.format, r.thin_file), true]]));
dash.draw('drift-body', tableBody('drift', 'metric', [[(r) => r.metric], [(r) => CR.byFormat(r.format, r.training), true], [(r) => r.kaggle_test == null ? '' : CR.byFormat(r.format, r.kaggle_test), true]]));
dash.draw('quality-body', tableBody('quality', 'issue', [[(r) => r.type], [(r) => r.issue], [(r) => CR.f.int(r.rows), true], [(r) => r.handling]]));

dash.draw('fair-chart', (el) => {
  const st = dash.data('fairness');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const bands = [...new Set([...st.data].sort((a, b) => a.order - b.order).map((r) => r.age_band))];
  const genders = [...new Set(st.data.map((r) => r.gender))];
  const { s, w } = CR.svg(el, 40, 'Default rate by gender and age band');
  const lw = CR.measure(s, genders) + 12;
  const cw = (w - lw) / bands.length, ch = 54, top = 22;
  const h = top + genders.length * ch + 4;
  s.attr('viewBox', `0 0 ${w} ${h}`);
  const max = d3.max(st.data, (r) => r.default_rate);
  const op = d3.scaleLinear().domain([0, max]).range([0.12, 0.95]);
  const t = CR.tip(el);
  bands.forEach((b, j) => s.append('text').attr('x', lw + j * cw + cw / 2).attr('y', 14).attr('text-anchor', 'middle').text(b));
  genders.forEach((g, i) => {
    s.append('text').attr('x', lw - 8).attr('y', top + i * ch + ch / 2).attr('dy', '0.35em').attr('text-anchor', 'end').text(g);
    bands.forEach((b, j) => {
      const r = st.data.find((d) => d.gender === g && d.age_band === b);
      if (!r) return;
      const x0 = lw + j * cw, y0 = top + i * ch;
      s.append('rect').attr('x', x0 + 1).attr('y', y0 + 1).attr('width', cw - 2).attr('height', ch - 2).attr('rx', 3)
        .style('fill', CR.color(0)).style('fill-opacity', op(r.default_rate));
      const dark = op(r.default_rate) > 0.55;
      s.append('text').attr('class', 'cr-val').attr('x', x0 + cw / 2).attr('y', y0 + ch / 2 - 4).attr('text-anchor', 'middle')
        .style('fill', dark ? 'var(--color-bg)' : 'var(--color-fg)').text(CR.f.pct(r.default_rate, 1));
      s.append('text').attr('x', x0 + cw / 2).attr('y', y0 + ch / 2 + 12).attr('text-anchor', 'middle')
        .style('fill', dark ? 'var(--color-bg)' : 'var(--cds-text-secondary)').text(cw > 70 ? `n ${CR.f.si(r.applicants)}` : '');
      s.append('rect').attr('x', x0).attr('y', y0).attr('width', cw).attr('height', ch).style('fill', 'transparent')
        .on('mousemove', (ev) => t.show(ev, [`${g}, ${b}`, `Default rate ${CR.f.pct(r.default_rate, 1)} ± ${CR.f.pct(r.ci95, 1)}`, `${CR.f.int(r.applicants)} applicants`]))
        .on('mouseleave', () => t.hide());
    });
  });
});

dash.draw('verdict-chart', (el) => {
  const st = dash.data('column_verdicts');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const meaning = { ok: 'known at application', ok_recode: 'known; has a code to recode', ok_planned: 'known; planned future dates', ok_filter: 'known; a few rows dropped',
    review: 'assumed known; timing undocumented', key: 'identifier, not a feature', protected: 'kept for fairness only', exclude: 'excluded by policy', label: 'the outcome' };
  CR.hbar(el, st.data, {
    barHeight: 16, label: (r) => r.verdict, value: (r) => r.columns, text: (r) => String(r.columns),
    tip: (r) => [r.verdict, meaning[r.verdict] || '', `${r.columns} columns`], aria: 'Number of columns per leakage verdict', xfmt: (v) => d3.format('d')(v),
  });
});
