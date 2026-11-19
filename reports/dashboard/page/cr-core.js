window.CR = (() => {
  const f = {
    pct: (v, d = 1) => (v == null || isNaN(v)) ? '—' : (v * 100).toFixed(d) + '%',
    int: (v) => v == null ? '—' : d3.format(',')(Math.round(v)),
    num: (v) => v == null ? '—' : (Math.abs(v) >= 1000 ? d3.format(',.0f')(v) : Math.abs(v) >= 10 ? d3.format('.1f')(v) : d3.format('.3~g')(v)),
    si: (v) => v == null ? '—' : d3.format('.3~s')(v).replace('G', 'B'),
  };
  const fmt = (k, v) => {
    if (v == null || v === '') return '—';
    switch (k) {
      case 'pct': return f.pct(v, 1);
      case 'pct2': return f.pct(v, 2);
      case 'int': return f.int(v);
      case 'si': return f.si(v);
      case 'dec3': return d3.format('.3f')(v);
      case 'text': return String(v);
      default: return f.num(v);
    }
  };
  const byFormat = (format, v) => {
    if (v == null) return '—';
    if (format === 'share') return f.pct(v, 1);
    if (format === 'count') return f.int(v);
    if (format === 'auc') return d3.format('.3f')(v);
    if (format === 'years') return d3.format('.1f')(v) + ' years';
    return f.num(v);
  };
  const state = (el, st) => {
    if (st.status === 'ok') { el.classList.remove('dash-skeleton'); return true; }
    if (st.status === 'loading') return false;
    el.classList.remove('dash-skeleton');
    if (st.status === 'error' || st.status === 'missing') {
      const p = document.createElement('p'); p.className = 'cr-fail'; p.textContent = 'Failed to load';
      el.replaceChildren(p);
    } else { el.textContent = '—'; }
    return false;
  };
  const color = (i) => dash.colors[i % dash.colors.length];
  const svg = (el, h, label) => {
    const w = Math.max(260, el.clientWidth || 600);
    const s = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${w} ${h}`)
      .attr('role', 'img').attr('aria-label', label);
    return { s, w };
  };
  const measure = (s, texts, cls) => {
    const g = s.append('g').attr('class', cls || '');
    let m = 0;
    texts.forEach((t) => { const n = g.append('text').text(t).node(); m = Math.max(m, n.getComputedTextLength()); });
    g.remove();
    return m;
  };
  const fit = (node, max) => {
    let t = node.textContent;
    while (t.length > 4 && node.getComputedTextLength() > max) { t = t.slice(0, -2); node.textContent = t + '…'; }
  };
  const tip = (el) => {
    const t = document.createElement('div'); t.className = 'cr-tip'; t.hidden = true; el.appendChild(t);
    return {
      show(ev, lines) {
        t.replaceChildren(...lines.map((l, i) => { const d = document.createElement('div'); d.textContent = l; if (i === 0) d.className = 'cr-tip-h'; return d; }));
        t.hidden = false;
        const r = el.getBoundingClientRect();
        let x = ev.clientX - r.left + 12; const y = ev.clientY - r.top + 12;
        if (x + t.offsetWidth > r.width) x = Math.max(0, ev.clientX - r.left - t.offsetWidth - 12);
        t.style.left = x + 'px'; t.style.top = y + 'px';
      },
      hide() { t.hidden = true; },
    };
  };
  // Horizontal bars with a label on the left and a value on the right
  const hbar = (el, rows, o) => {
    const bh = o.barHeight || 20, gap = 6;
    const { s, w } = svg(el, 40, o.aria);
    const lw = Math.min(w * 0.42, measure(s, rows.map(o.label)) + 10);
    const tw = measure(s, rows.map(o.text), 'cr-val') + 10;
    const top = o.legend ? 0 : 0;
    const h = top + rows.length * (bh + gap) + 26;
    s.attr('viewBox', `0 0 ${w} ${h}`);
    const xmax = Math.max(d3.max(rows, o.value) || 1, o.ref || 0);
    const x = d3.scaleLinear().domain([0, xmax]).range([lw, Math.max(lw + 40, w - tw)]);
    const t = tip(el);
    const g = s.selectAll('g.cr-row').data(rows).join('g').attr('class', 'cr-row').attr('transform', (d, i) => `translate(0,${top + i * (bh + gap)})`);
    g.append('text').attr('x', lw - 8).attr('y', bh / 2).attr('dy', '0.35em').attr('text-anchor', 'end').text(o.label).each(function () { fit(this, lw - 10); });
    g.append('rect').attr('x', x(0)).attr('y', 0).attr('height', bh).attr('rx', 2)
      .attr('width', (d) => Math.max(1, x(o.value(d)) - x(0))).style('fill', (d) => o.color ? o.color(d) : color(0));
    g.append('text').attr('class', 'cr-val').attr('x', (d) => x(o.value(d)) + 6).attr('y', bh / 2).attr('dy', '0.35em').text(o.text);
    g.append('rect').attr('x', 0).attr('y', -gap / 2).attr('width', w).attr('height', bh + gap).style('fill', 'transparent')
      .on('mousemove', (ev, d) => t.show(ev, o.tip(d))).on('mouseleave', () => t.hide());
    const axis = s.append('g').attr('transform', `translate(0,${h - 20})`).call(d3.axisBottom(x).ticks(Math.max(2, Math.floor((w - lw - tw) / 90))).tickFormat(o.xfmt).tickSizeOuter(0));
    axis.select('.domain').remove();
    (o.refs || []).forEach((r) => {
      s.append('line').attr('x1', x(r.v)).attr('x2', x(r.v)).attr('y1', 0).attr('y2', h - 20)
        .style('stroke', 'var(--cds-chart-reference)').style('stroke-dasharray', '4 3');
    });
  };
  return { f, fmt, byFormat, state, color, svg, measure, fit, tip, hbar };
})();

const where = (st, w) => {
  if (!w) return st.data[0];
  const pairs = w.split('&').map((p) => p.split('=').map(decodeURIComponent));
  return st.data.find((r) => pairs.every(([k, v]) => String(r[k]) === v));
};
window.CR.where = where;

dash.draw('num', (el) => {
  const st = dash.data(el.dataset.source);
  if (!CR.state(el, st)) return;
  const row = CR.where(st, el.dataset.where);
  el.textContent = row ? CR.fmt(el.dataset.fmt, row[el.dataset.field]) : '—';
});

dash.draw('swatch', (el) => { el.style.background = CR.color(+el.dataset.i); });


// Derived tables, worked out from the data dictionary so readers can check them
dash.calc('column_groups', {
  title: 'Columns per group and kind family',
  description: 'Counts of dictionary columns by business group and broad kind of value.',
  inputs: ['dictionary'],
  fn: (dictionary) => {
    const family = { amount: 'Numbers', count: 'Numbers', number: 'Numbers', score: 'Numbers', rating: 'Numbers',
      days: 'Days and months', months: 'Days and months', category: 'Categories and flags', flag: 'Categories and flags',
      key: 'Keys and label', label: 'Keys and label' };
    const out = {};
    dictionary.forEach((r) => {
      const k = r.group + '|' + family[r.kind];
      out[k] = out[k] || { group: r.group, family: family[r.kind], columns: 0 };
      out[k].columns += 1;
    });
    return Object.values(out);
  },
});
dash.calc('column_kinds', {
  title: 'Columns per kind of value',
  description: 'Each kind of value, its unit, how many columns hold it and how it is charted.',
  inputs: ['dictionary'],
  fn: (dictionary) => {
    const out = {};
    dictionary.forEach((r) => {
      out[r.kind] = out[r.kind] || { kind: r.kind, unit: r.kind === 'number' ? 'as recorded (hours, years, codes)' : r.unit, columns: 0, chart: r.chart };
      out[r.kind].columns += 1;
    });
    return Object.values(out).sort((a, b) => b.columns - a.columns);
  },
});
dash.calc('column_verdicts', {
  title: 'Columns per leakage verdict',
  description: 'How many columns received each verdict on whether they are known at application.',
  inputs: ['dictionary'],
  fn: (dictionary) => {
    const out = {};
    dictionary.forEach((r) => { out[r.verdict] = (out[r.verdict] || 0) + 1; });
    return Object.entries(out).map(([verdict, columns]) => ({ verdict, columns })).sort((a, b) => b.columns - a.columns);
  },
});
dash.calc('missing_view', {
  title: 'Missing main-table columns (one building column shown)',
  description: 'Main-table columns with at least 0.05% missing; the 47 building-statistics columns, missing together, are represented by APARTMENTS_AVG.',
  inputs: ['missingness'],
  fn: (missingness) => missingness
    .filter((r) => r.missing_pct >= 0.05)
    .filter((r) => r.group !== 'Building statistics' || r.column === 'APARTMENTS_AVG')
    .map((r) => ({ ...r, label: r.group === 'Building statistics' ? 'Building statistics (47 columns)' : r.column })),
});

const cell = (tr, text, numeric) => {
  const td = document.createElement('td'); td.textContent = text; if (numeric) td.className = 'cr-n'; tr.appendChild(td); return td;
};
window.CR.cell = cell;

dash.draw('tables-body', (tb) => {
  const st = dash.data('tables');
  if (!CR.state(tb, st)) return;
  tb.replaceChildren(...st.data.map((r) => {
    const tr = document.createElement('tr'); tr.dataset.key = r.table;
    const c = cell(tr, ''); const code = document.createElement('code'); code.textContent = r.table; c.appendChild(code);
    cell(tr, r.one_row_is); cell(tr, CR.f.int(r.rows), true); cell(tr, CR.f.int(r.columns), true);
    cell(tr, r.train_applicants_with_rows_pct == null ? '—' : d3.format('.1f')(r.train_applicants_with_rows_pct) + '%', true);
    return tr;
  }));
});

dash.draw('kinds-body', (tb) => {
  const st = dash.data('column_kinds');
  if (!CR.state(tb, st)) return;
  tb.replaceChildren(...st.data.map((r) => {
    const tr = document.createElement('tr'); tr.dataset.key = r.kind;
    cell(tr, r.kind); cell(tr, r.unit); cell(tr, CR.f.int(r.columns), true); cell(tr, r.chart);
    return tr;
  }));
});

dash.draw('groups-chart', (el) => {
  const st = dash.data('column_groups');
  if (!CR.state(el, st)) return;
  el.replaceChildren();
  const fams = ['Numbers', 'Days and months', 'Categories and flags', 'Keys and label'];
  const totals = d3.rollup(st.data, (v) => d3.sum(v, (d) => d.columns), (d) => d.group);
  const groups = [...totals.keys()].sort((a, b) => totals.get(b) - totals.get(a));
  const leg = document.createElement('div'); leg.className = 'cr-legend';
  fams.forEach((fm, i) => { const s = document.createElement('span'); const sw = document.createElement('i'); sw.style.background = CR.color(i); s.append(sw, fm); leg.appendChild(s); });
  el.appendChild(leg);
  const bh = 16, gap = 5;
  const { s, w } = CR.svg(el, 40, 'Number of columns in each group, split by kind of value');
  const lw = Math.min(w * 0.5, CR.measure(s, groups) + 10);
  const tw = CR.measure(s, groups.map((g) => String(totals.get(g))), 'cr-val') + 10;
  const h = groups.length * (bh + gap) + 24;
  s.attr('viewBox', `0 0 ${w} ${h}`);
  const x = d3.scaleLinear().domain([0, d3.max(totals.values())]).range([lw, w - tw]);
  const t = CR.tip(el);
  groups.forEach((g, i) => {
    const y = i * (bh + gap);
    s.append('text').attr('x', lw - 8).attr('y', y + bh / 2).attr('dy', '0.35em').attr('text-anchor', 'end').text(g).each(function () { CR.fit(this, lw - 10); });
    let x0 = 0;
    fams.forEach((fm, fi) => {
      const r = st.data.find((d) => d.group === g && d.family === fm);
      if (!r) return;
      s.append('rect').attr('x', x(x0)).attr('y', y).attr('height', bh).attr('width', Math.max(1, x(x0 + r.columns) - x(x0)))
        .style('fill', CR.color(fi))
        .on('mousemove', (ev) => t.show(ev, [g, `${fm}: ${r.columns} columns`, `${totals.get(g)} columns in the group`]))
        .on('mouseleave', () => t.hide());
      x0 += r.columns;
    });
    s.append('text').attr('class', 'cr-val').attr('x', x(x0) + 6).attr('y', y + bh / 2).attr('dy', '0.35em').text(totals.get(g));
  });
  s.append('g').attr('transform', `translate(0,${h - 20})`).call(d3.axisBottom(x).ticks(4).tickSizeOuter(0)).select('.domain').remove();
});
