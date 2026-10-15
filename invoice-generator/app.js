(function () {
  'use strict';

  var STORE_CURRENT = 'invoiceBuilder.current';
  var STORE_DEFAULT = 'invoiceBuilder.default';

  var CURRENCIES = [
    ['USD', 'US Dollar'], ['EUR', 'Euro'], ['GBP', 'British Pound'],
    ['CAD', 'Canadian Dollar'], ['AUD', 'Australian Dollar'], ['NZD', 'New Zealand Dollar'],
    ['JPY', 'Japanese Yen'], ['CNY', 'Chinese Yuan'], ['INR', 'Indian Rupee'],
    ['PHP', 'Philippine Peso'], ['SGD', 'Singapore Dollar'], ['HKD', 'Hong Kong Dollar'],
    ['CHF', 'Swiss Franc'], ['SEK', 'Swedish Krona'], ['NOK', 'Norwegian Krone'],
    ['DKK', 'Danish Krone'], ['ZAR', 'South African Rand'], ['MXN', 'Mexican Peso'],
    ['BRL', 'Brazilian Real'], ['AED', 'UAE Dirham'], ['SAR', 'Saudi Riyal'],
    ['KRW', 'South Korean Won'], ['MYR', 'Malaysian Ringgit'], ['IDR', 'Indonesian Rupiah'],
    ['THB', 'Thai Baht'], ['NGN', 'Nigerian Naira'], ['KES', 'Kenyan Shilling']
  ];

  var paper = document.getElementById('invoice');
  var itemsBody = document.getElementById('items-body');
  var currencySelect = document.getElementById('currency');
  var logoBox = document.getElementById('logo-box');
  var logoInput = document.getElementById('logo-input');
  var logoImg = document.getElementById('logo-img');
  var logoPlaceholder = document.getElementById('logo-placeholder');
  var logoRemove = document.getElementById('logo-remove');
  var savedNote = document.getElementById('saved-note');

  // ---------- Storage (may be unavailable) ----------
  function load(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* ignore */ }
  }

  // ---------- Path helpers ----------
  function getPath(obj, path) {
    return path.split('.').reduce(function (o, k) { return o == null ? undefined : o[k]; }, obj);
  }
  function setPath(obj, path, value) {
    var keys = path.split('.');
    var last = keys.pop();
    var target = keys.reduce(function (o, k) { return o[k] || (o[k] = {}); }, obj);
    target[last] = value;
  }

  // ---------- Default state ----------
  function today(offsetDays) {
    var d = new Date();
    d.setDate(d.getDate() + (offsetDays || 0));
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  // Label defaults come straight from the markup so there is one source of truth.
  var defaultLabels = {};
  paper.querySelectorAll('[data-key^="labels."]').forEach(function (el) {
    setPath(defaultLabels, el.dataset.key.slice(7), el.value);
  });

  function blankInvoice() {
    return {
      from: '', billTo: '', shipTo: '',
      number: '1', date: today(0), paymentTerms: '', dueDate: '', poNumber: '',
      notes: '', terms: '',
      items: [{ desc: '', qty: 1, rate: 0 }],
      tax: { enabled: true, type: 'percent', value: 0 },
      discount: { enabled: false, type: 'percent', value: 0 },
      shipping: { enabled: false, value: 0 },
      amountPaid: 0,
      currency: 'USD',
      logo: null,
      labels: JSON.parse(JSON.stringify(defaultLabels))
    };
  }

  function merge(base, extra) {
    if (!extra) return base;
    Object.keys(extra).forEach(function (k) {
      var v = extra[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') {
        merge(base[k], v);
      } else if (v !== undefined) {
        base[k] = v;
      }
    });
    return base;
  }

  var state = merge(blankInvoice(), load(STORE_CURRENT) || load(STORE_DEFAULT));

  // ---------- Money formatting ----------
  function formatter() {
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: state.currency });
    } catch (e) {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' });
    }
  }
  function money(n) { return formatter().format(isFinite(n) ? n : 0); }
  function symbol() {
    var part = formatter().formatToParts(0).find(function (p) { return p.type === 'currency'; });
    return part ? part.value : '';
  }
  function num(v) {
    var n = parseFloat(v);
    return isFinite(n) ? n : 0;
  }

  // ---------- Calculations ----------
  function totals() {
    var subtotal = state.items.reduce(function (s, it) { return s + num(it.qty) * num(it.rate); }, 0);

    var discount = 0;
    if (state.discount.enabled) {
      discount = state.discount.type === 'percent'
        ? subtotal * num(state.discount.value) / 100
        : num(state.discount.value);
    }

    var tax = 0;
    if (state.tax.enabled) {
      tax = state.tax.type === 'percent'
        ? (subtotal - discount) * num(state.tax.value) / 100
        : num(state.tax.value);
    }

    var shipping = state.shipping.enabled ? num(state.shipping.value) : 0;
    var total = subtotal - discount + tax + shipping;
    return {
      subtotal: subtotal, discount: discount, tax: tax, shipping: shipping,
      total: total, paid: num(state.amountPaid), balance: total - num(state.amountPaid)
    };
  }

  // ---------- Rendering ----------
  function autosize(el) {
    if (el.tagName !== 'TEXTAREA') return;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 2 + 'px';
  }

  function renderItems() {
    itemsBody.innerHTML = '';
    state.items.forEach(function (item, i) {
      var row = document.createElement('div');
      row.className = 'item-row';
      row.innerHTML =
        '<textarea class="field item-desc" rows="1" placeholder="Description of item/service..."></textarea>' +
        '<input class="field num" type="number" step="any" min="0" aria-label="Quantity">' +
        '<input class="field num" type="number" step="any" aria-label="Rate">' +
        '<span class="item-amount"></span>' +
        '<button type="button" class="item-remove" title="Remove line item" aria-label="Remove line item">&times;</button>';

      var desc = row.children[0], qty = row.children[1], rate = row.children[2];
      desc.value = item.desc;
      qty.value = item.qty;
      rate.value = item.rate;

      desc.addEventListener('input', function () { item.desc = desc.value; autosize(desc); persist(); });
      qty.addEventListener('input', function () { item.qty = qty.value; update(); });
      rate.addEventListener('input', function () { item.rate = rate.value; update(); });
      row.children[4].addEventListener('click', function () {
        state.items.splice(i, 1);
        if (!state.items.length) state.items.push({ desc: '', qty: 1, rate: 0 });
        renderItems();
        update();
      });

      itemsBody.appendChild(row);
      autosize(desc);
    });
  }

  function renderFields() {
    paper.querySelectorAll('[data-key]').forEach(function (el) {
      var v = getPath(state, el.dataset.key);
      el.value = v == null ? '' : v;
      autosize(el);
    });
  }

  function renderLogo() {
    var has = !!state.logo;
    logoImg.hidden = !has;
    logoRemove.hidden = !has;
    logoPlaceholder.hidden = has;
    logoBox.classList.toggle('has-logo', has);
    if (has) logoImg.src = state.logo; else logoImg.removeAttribute('src');
  }

  function update() {
    var t = totals();
    var sym = symbol();

    itemsBody.querySelectorAll('.item-amount').forEach(function (el, i) {
      var it = state.items[i];
      el.textContent = money(num(it.qty) * num(it.rate));
    });
    paper.querySelectorAll('[data-out]').forEach(function (el) {
      el.textContent = money(t[el.dataset.out]);
    });

    ['tax', 'discount', 'shipping'].forEach(function (name) {
      var adj = state[name];
      paper.querySelector('[data-adj="' + name + '"]').hidden = !adj.enabled;
      paper.querySelector('[data-add="' + name + '"]').hidden = adj.enabled;
      var isPct = adj.type === 'percent';
      paper.querySelector('[data-prefix="' + name + '"]').textContent = isPct ? '' : sym;
      paper.querySelector('[data-suffix="' + name + '"]').textContent = isPct ? '%' : '';
    });
    paper.querySelector('[data-prefix="paid"]').textContent = sym;

    persist();
  }

  var persistTimer;
  function persist() {
    clearTimeout(persistTimer);
    persistTimer = setTimeout(function () { save(STORE_CURRENT, state); }, 250);
  }

  function renderAll() {
    currencySelect.value = state.currency;
    renderFields();
    renderItems();
    renderLogo();
    update();
  }

  // ---------- Print / PDF ----------
  var printView = document.getElementById('print-view');

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function prettyDate(v) {
    if (!v) return '';
    var d = new Date(v + 'T00:00:00');
    return isNaN(d) ? v : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }
  function qtyText(v) {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(num(v));
  }
  function pct(v) {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(num(v)) + '%';
  }
  // First line of a multi-line block is shown bold, the way an address reads.
  function block(text, firstClass) {
    var lines = String(text).trim().split('\n');
    var first = '<div class="' + firstClass + '">' + esc(lines.shift()) + '</div>';
    return first + (lines.length ? '<div class="pv-pre">' + esc(lines.join('\n')) + '</div>' : '');
  }

  function renderPrint() {
    var L = state.labels;
    var t = totals();
    var h = '';

    h += '<header class="pv-head"><div class="pv-from">';
    if (state.logo) h += '<img class="pv-logo" src="' + esc(state.logo) + '" alt="">';
    if (state.from.trim()) h += block(state.from, 'pv-from-text');
    h += '</div><div class="pv-title"><h1>' + esc(L.title) + '</h1>';
    if (String(state.number).trim()) h += '<div class="pv-number pv-muted"># ' + esc(state.number) + '</div>';
    h += '</div></header>';

    h += '<section class="pv-info"><div class="pv-parties">';
    [['billTo', L.billTo], ['shipTo', L.shipTo]].forEach(function (p) {
      if (!state[p[0]].trim()) return;
      h += '<div class="pv-party"><div class="pv-label pv-muted">' + esc(p[1]) + '</div>' +
        block(state[p[0]], 'pv-party-name') + '</div>';
    });
    h += '</div><table class="pv-meta"><tbody>';
    [[L.date, prettyDate(state.date)], [L.terms, state.paymentTerms],
     [L.dueDate, prettyDate(state.dueDate)], [L.po, state.poNumber]].forEach(function (r) {
      if (!String(r[1]).trim()) return;
      h += '<tr><td class="pv-muted">' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td></tr>';
    });
    h += '<tr class="pv-balance"><td>' + esc(L.balanceDue) + '</td><td>' + money(t.balance) + '</td></tr>';
    h += '</tbody></table></section>';

    h += '<table class="pv-items"><colgroup><col><col class="c-qty"><col class="c-rate"><col class="c-amt"></colgroup>' +
      '<thead><tr><th>' + esc(L.item) + '</th><th class="n">' + esc(L.qty) + '</th><th class="n">' +
      esc(L.rate) + '</th><th class="n">' + esc(L.amount) + '</th></tr></thead><tbody>';
    state.items.forEach(function (it) {
      if (!String(it.desc).trim() && !num(it.rate)) return;
      h += '<tr><td class="pv-pre">' + esc(String(it.desc).trim()) + '</td><td class="n">' + qtyText(it.qty) +
        '</td><td class="n">' + money(num(it.rate)) + '</td><td class="n">' + money(num(it.qty) * num(it.rate)) + '</td></tr>';
    });
    h += '</tbody></table>';

    h += '<section class="pv-bottom"><div class="pv-notes">';
    [[L.notes, state.notes], [L.termsBlock, state.terms]].forEach(function (n) {
      if (!String(n[1]).trim()) return;
      h += '<div class="pv-note"><div class="pv-label pv-muted">' + esc(n[0]) + '</div><div class="pv-pre">' +
        esc(String(n[1]).trim()) + '</div></div>';
    });
    h += '</div><table class="pv-totals"><tbody>';
    function row(label, value, cls) {
      h += '<tr' + (cls ? ' class="' + cls + '"' : '') + '><td' + (cls === 'pv-balance' ? '' : ' class="pv-muted"') +
        '>' + esc(label) + '</td><td>' + value + '</td></tr>';
    }
    row(L.subtotal, money(t.subtotal));
    if (state.discount.enabled && t.discount) {
      row(L.discount + (state.discount.type === 'percent' ? ' (' + pct(state.discount.value) + ')' : ''), '&minus;' + money(t.discount));
    }
    if (state.tax.enabled && t.tax) {
      row(L.tax + (state.tax.type === 'percent' ? ' (' + pct(state.tax.value) + ')' : ''), money(t.tax));
    }
    if (state.shipping.enabled && t.shipping) row(L.shipping, money(t.shipping));
    row(L.total, money(t.total), 'pv-total');
    if (t.paid) row(L.amountPaid, money(t.paid));
    row(L.balanceDue2, money(t.balance), 'pv-balance');
    h += '</tbody></table></section>';

    printView.innerHTML = h;
  }

  function flash(msg) {
    savedNote.textContent = msg;
    clearTimeout(flash.t);
    flash.t = setTimeout(function () { savedNote.textContent = ''; }, 2500);
  }

  // ---------- Events ----------
  paper.addEventListener('input', function (e) {
    var key = e.target.dataset && e.target.dataset.key;
    if (!key) return;
    setPath(state, key, e.target.value);
    autosize(e.target);
    update();
  });

  // Payment terms like "Net 30" fill in an empty due date.
  paper.querySelector('[data-key="paymentTerms"]').addEventListener('change', function (e) {
    var m = /(\d+)/.exec(e.target.value);
    if (m && !state.dueDate && state.date) {
      var d = new Date(state.date + 'T00:00:00');
      d.setDate(d.getDate() + parseInt(m[1], 10));
      state.dueDate = d.toISOString().slice(0, 10);
      renderFields();
      update();
    }
  });

  document.getElementById('add-item').addEventListener('click', function () {
    state.items.push({ desc: '', qty: 1, rate: 0 });
    renderItems();
    update();
    var rows = itemsBody.querySelectorAll('.item-desc');
    rows[rows.length - 1].focus();
  });

  paper.querySelectorAll('[data-add]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      state[btn.dataset.add].enabled = true;
      update();
    });
  });
  paper.querySelectorAll('[data-remove]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var adj = state[btn.dataset.remove];
      adj.enabled = false;
      adj.value = 0;
      renderFields();
      update();
    });
  });
  paper.querySelectorAll('[data-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var adj = state[btn.dataset.toggle];
      adj.type = adj.type === 'percent' ? 'flat' : 'percent';
      update();
    });
  });

  // Logo
  logoInput.addEventListener('change', function () {
    var file = logoInput.files && logoInput.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      alert('Please choose an image under 2 MB.');
      logoInput.value = '';
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      state.logo = reader.result;
      renderLogo();
      persist();
    };
    reader.readAsDataURL(file);
    logoInput.value = '';
  });
  logoRemove.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    state.logo = null;
    renderLogo();
    persist();
  });

  // Currency
  CURRENCIES.forEach(function (c) {
    var opt = document.createElement('option');
    opt.value = c[0];
    opt.textContent = c[0] + ' (' + c[1] + ')';
    currencySelect.appendChild(opt);
  });
  currencySelect.addEventListener('change', function () {
    state.currency = currencySelect.value;
    update();
  });

  // Sidebar actions
  document.getElementById('download').addEventListener('click', function () {
    var prevTitle = document.title;
    document.title = (state.labels.title || 'Invoice') + ' ' + (state.number || '');
    renderPrint();
    window.print();
    document.title = prevTitle;
  });

  document.getElementById('save-default').addEventListener('click', function () {
    save(STORE_DEFAULT, {
      from: state.from,
      paymentTerms: state.paymentTerms,
      notes: state.notes,
      terms: state.terms,
      currency: state.currency,
      logo: state.logo,
      labels: state.labels,
      tax: state.tax,
      number: state.number
    });
    flash('Saved as default.');
  });

  document.getElementById('new-invoice').addEventListener('click', function () {
    if (!confirm('Start a new invoice? The current one will be cleared.')) return;
    var next = String(state.number).replace(/\d+(?!.*\d)/, function (d) {
      return String(parseInt(d, 10) + 1).padStart(d.length, '0');
    });
    var defaults = load(STORE_DEFAULT) || {};
    delete defaults.number;
    state = merge(blankInvoice(), defaults);
    state.number = next || '1';
    renderAll();
    flash('New invoice started.');
  });

  // Covers Ctrl+P and the browser menu as well as the Download button.
  window.addEventListener('beforeprint', renderPrint);

  renderAll();
})();
