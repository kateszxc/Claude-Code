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
    return { subtotal: subtotal, total: total, balance: total - num(state.amountPaid) };
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

    // Hide empty optional blocks when printing.
    paper.querySelectorAll('.party, .meta-row, .block').forEach(function (el) {
      var f = el.querySelector('.field');
      el.classList.toggle('empty-print', !f.value.trim());
    });

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

  window.addEventListener('beforeprint', function () {
    paper.querySelectorAll('textarea').forEach(autosize);
  });

  renderAll();
})();
