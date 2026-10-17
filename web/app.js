'use strict';

// Energy types a "fuel" item can use. Prices live in settings.prices.
const ENERGY = {
  diesel: { label: 'Diesel', unit: 'l/mil', price: 'kr/l' },
  petrol: { label: 'Petrol', unit: 'l/mil', price: 'kr/l' },
  el_home: { label: 'Electricity, home', unit: 'kWh/mil', price: 'kr/kWh' },
  el_public: { label: 'Electricity, public', unit: 'kWh/mil', price: 'kr/kWh' },
};

// Item types. Every cost of every car is one of these, converted to kr/month.
const TYPES = {
  fixed: { label: 'kr/month', defaults: { value: 0 } },
  per_year: { label: 'kr/year', defaults: { value: 0 } },
  one_time: { label: 'one-time, spread', defaults: { value: 0, months: 36 } },
  fuel: { label: 'fuel / energy', defaults: { energy: 'petrol', consumption: 0.5, share_pct: 100 } },
  capital: { label: 'money tied up (interest)', defaults: { amount: 0, rate_pct: 7, months: 36 } },
  depreciation: { label: 'depreciation (% per year)', defaults: { value_now: 0, rate_pct: 13, months: 36 } },
  excess_mileage: { label: 'excess mileage', defaults: { rate: 0, limit_per_year: 2000 } },
};

let data = null;
let etag = null;
let saveTimer = null;
let saving = false;
let costCells = [];   // { item, el }
let totalCells = [];  // { car, el }
let originCells = []; // { item, el }: the "auto" / "edited" badge of rows computed from the transactions
let bootCells = [];   // { car, el }: luggage cells, the largest one is highlighted
let budgetBoxes = []; // { car, el }: "how much repair cost can this car afford" boxes

// Equipment answers in the size/equipment table.
const FEATURE = { yes: 'yes', no: 'no', option: 'extra cost', unknown: '?' };
// How well the specs of a car are backed up.
const CHECKED = {
  official: 'manufacturer spec sheet',
  dealer: 'dealer listing for this trim',
  unverified: 'not verified',
};
const pendingDelete = new Set();
const showingHidden = new Set(); // ids of cars whose hidden costs are currently shown (view state, not saved)

// ---------- helpers ----------

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else if (k === 'checked') el.checked = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c);
  return el;
}

const num = x => Number(x) || 0;
const kr = x => Math.round(x).toLocaleString('sv-SE') + ' kr';
const signedKr = x => (x > 0 ? '+' : x < 0 ? '−' : '±') + Math.abs(Math.round(x)).toLocaleString('sv-SE') + ' kr';
const uid = prefix => prefix + '-' + Math.random().toString(36).slice(2, 8);

function setStatus(text, kind = '') {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = 'status ' + kind;
}

// ---------- cost model ----------

// Each money-tied-up row has its own interest rate; rows without one use the default in the settings.
const capitalRate = item => (item.rate_pct === undefined || item.rate_pct === null ? data.settings.return_rate_pct : item.rate_pct);

function monthly(item) {
  const s = data.settings;
  switch (item.type) {
    case 'fixed': return num(item.value);
    case 'per_year': return num(item.value) / 12;
    case 'one_time': return num(item.months) > 0 ? num(item.value) / num(item.months) : 0;
    case 'fuel': {
      const share = item.share_pct === undefined || item.share_pct === null ? 1 : num(item.share_pct) / 100;
      return num(item.consumption) * num(s.mil_per_year) * num(s.prices[item.energy]) * share / 12;
    }
    case 'capital': {
      // What the money would have grown to, compounded yearly, minus the money itself, spread over the months.
      const months = item.months === undefined || item.months === null ? 36 : num(item.months);
      if (months <= 0) return 0;
      const grown = num(item.amount) * Math.pow(1 + num(capitalRate(item)) / 100, months / 12);
      return (grown - num(item.amount)) / months;
    }
    case 'depreciation': {
      // The car keeps losing the same share of its value every year: value after = value now × (1 − rate)^years.
      const months = num(item.months);
      if (months <= 0) return 0;
      const valueAfter = num(item.value_now) * Math.pow(1 - num(item.rate_pct) / 100, months / 12);
      return (num(item.value_now) - valueAfter) / months;
    }
    case 'excess_mileage': return Math.max(0, num(s.mil_per_year) - num(item.limit_per_year)) * num(item.rate) / 12;
    default: return 0;
  }
}

// Hidden costs stay in cars.json (with their tick state) but are neither shown nor counted.
const carTotal = car => car.items.filter(i => i.enabled && !i.hidden).reduce((sum, i) => sum + monthly(i), 0);
const perMil = car => carTotal(car) * 12 / Math.max(1, num(data.settings.mil_per_year));
const defaultCar = () => data.cars.find(c => c.default) || data.cars[0];

// ---------- inputs ----------

function numberInput(obj, key, title) {
  return h('input', {
    type: 'number', step: 'any', title, value: obj[key] ?? '',
    oninput: e => {
      obj[key] = e.target.value === '' ? null : Number(e.target.value);
      if (obj.auto) obj.auto = false;  // the user owns this value now; build_v40.py leaves it alone
      changed();
    },
  });
}

function textInput(obj, key, cls, placeholder) {
  return h('input', {
    type: 'text', class: cls, placeholder, value: obj[key] ?? '',
    oninput: e => { obj[key] = e.target.value; changed(); },
  });
}

function changed() {
  updateNumbers();
  scheduleSave();
}

// ---------- rendering ----------

function render() {
  costCells = [];
  totalCells = [];
  originCells = [];
  budgetBoxes = [];
  renderSettings();
  renderSpecs();
  const cars = document.getElementById('cars');
  cars.replaceChildren(...data.cars.map(renderCar));
  updateNumbers();
}

function renderSettings() {
  const s = data.settings;
  const priceInputs = Object.entries(ENERGY).map(([key, e]) =>
    h('label', {}, `${e.label} (${e.price})`, numberInput(s.prices, key)));
  document.getElementById('settings').replaceChildren(
    h('h2', {}, 'Assumptions for all cars'),
    h('div', { class: 'settings-grid' },
      h('label', {}, 'Driving (mil/year)', numberInput(s, 'mil_per_year')),
      h('label', {}, 'Default interest (%/year)', numberInput(s, 'return_rate_pct', 'Used by money-tied-up rows that have no rate of their own')),
      ...priceInputs),
    s.prices_note ? h('p', { class: 'note' }, s.prices_note) : null,
  );
}

// ---------- size and equipment ----------

function specNumber(car, key, title, width) {
  const specs = car.specs;
  return h('input', {
    type: 'number', step: 'any', title, placeholder: '–', value: specs[key] ?? '', style: width ? `width:${width}px` : null,
    oninput: e => {
      specs[key] = e.target.value === '' ? null : Number(e.target.value);
      if (key.startsWith('boot')) markBestBoot();
      scheduleSave();
    },
  });
}

function specText(car, key, placeholder, width) {
  const specs = car.specs;
  return h('input', {
    type: 'text', placeholder, value: specs[key] ?? '', style: `width:${width}px`,
    oninput: e => { specs[key] = e.target.value; scheduleSave(); },
  });
}

function featureSelect(car, key) {
  const specs = car.specs;
  const select = h('select', {
    class: 'feature ' + (specs[key] || 'unknown'),
    onchange: e => { specs[key] = e.target.value; select.className = 'feature ' + e.target.value; scheduleSave(); },
  }, Object.entries(FEATURE).map(([k, label]) =>
    h('option', { value: k, selected: (specs[key] || 'unknown') === k }, label)));
  return select;
}

function markBestBoot() {
  for (const key of ['boot_l', 'boot_roof_l']) {
    const cells = bootCells.filter(cell => cell.key === key);
    const best = Math.max(0, ...cells.map(({ car }) => num(car.specs[key])));
    for (const { car, el } of cells) el.classList.toggle('best', best > 0 && num(car.specs[key]) === best);
  }
}

function renderSpecs() {
  bootCells = [];
  for (const car of data.cars) car.specs = car.specs || {};  // only saved once something is edited
  const head = ['Car', 'Power (hp)', 'kW', 'Gearbox', 'Gears', 'Range, electric (km)', 'Luggage to the cover (l)',
    'Luggage to the roof (l)', 'Seats folded (l)',
    'Length × width × height (mm)', 'Rear camera', 'Sensors front', 'Sensors rear', 'Adaptive cruise'];
  const rows = data.cars.map(car => {
    const bootCell = h('td', { class: 'boot', title: 'Luggage space with the seats up, up to the luggage cover' },
      specNumber(car, 'boot_l', 'Luggage up to the luggage cover, seats up (l)', 58));
    const roofCell = h('td', { class: 'boot', title: 'Luggage space with the seats up, up to the roof' },
      specNumber(car, 'boot_roof_l', 'Luggage up to the roof, seats up (l)', 58));
    bootCells.push({ car, el: bootCell, key: 'boot_l' }, { car, el: roofCell, key: 'boot_roof_l' });
    return h('tr', {},
      h('th', { scope: 'row' }, car.name || '(unnamed)', h('div', { class: 'type' }, car.kind || '')),
      h('td', {}, specNumber(car, 'power_hp', 'Power in hp', 54)),
      h('td', {}, specNumber(car, 'power_kw', 'Power in kW', 48)),
      h('td', {}, specText(car, 'gearbox', 'e.g. 7-speed auto', 100)),
      h('td', {}, specNumber(car, 'gears', 'Number of gears (empty for electric/CVT)', 46)),
      h('td', {}, specNumber(car, 'range_km', 'Electric range in km (WLTP), only for electric cars', 54)),
      bootCell,
      roofCell,
      h('td', {}, specNumber(car, 'boot_max_l', 'Luggage with the rear seats folded (l)', 58)),
      h('td', { class: 'dims' }, specNumber(car, 'length_mm', 'Length (mm)', 58), ' × ',
        specNumber(car, 'width_mm', 'Width (mm)', 58), ' × ', specNumber(car, 'height_mm', 'Height (mm)', 58)),
      h('td', {}, featureSelect(car, 'rear_camera')),
      h('td', {}, featureSelect(car, 'parking_front')),
      h('td', {}, featureSelect(car, 'parking_rear')),
      h('td', {}, featureSelect(car, 'adaptive_cruise')));
  });

  const sources = data.cars.map(car => h('div', { class: 'spec-source' },
    h('strong', {}, car.name || '(unnamed)'), ' ',
    h('select', {
      class: 'checked ' + (car.specs.checked || 'unverified'), title: 'How well these specs are backed up',
      onchange: e => { car.specs.checked = e.target.value; e.target.className = 'checked ' + e.target.value; scheduleSave(); },
    }, Object.entries(CHECKED).map(([k, label]) =>
      h('option', { value: k, selected: (car.specs.checked || 'unverified') === k }, label))),
    h('textarea', {
      rows: 2, placeholder: 'Where do these specs come from? Anything unverified?', value: car.specs.source ?? '',
      oninput: e => { car.specs.source = e.target.value; scheduleSave(); },
    })));

  document.getElementById('specs').replaceChildren(
    h('h2', {}, 'Size & equipment'),
    h('div', { class: 'table-wrap' }, h('table', { class: 'specs' },
      h('thead', {}, h('tr', {}, head.map(text => h('th', {}, text)))),
      h('tbody', {}, rows))),
    h('p', { class: 'note' }, 'Every cell can be edited. Both luggage columns are with the seats up: up to the luggage ' +
      'cover, and up to the roof (without the cover). A number is only comparable if its source note says which it is. ' +
      'The largest in each column is highlighted. "?" or an empty cell means not known yet.'),
    h('details', {}, h('summary', {}, 'Sources and how sure each car is'), sources),
  );
  markBestBoot();
}

function renderSummary() {
  const def = defaultCar();
  const base = def ? carTotal(def) : 0;
  const rows = [...data.cars].sort((a, b) => carTotal(a) - carTotal(b));
  const max = Math.max(1, ...rows.map(carTotal));
  document.getElementById('summary').replaceChildren(
    h('h2', {}, 'Comparison (ticked costs only)'),
    h('div', { class: 'table-wrap' }, h('table', { class: 'summary' },
      h('thead', {}, h('tr', {},
        h('th', {}, 'Car'), h('th', {}, 'kr/month'), h('th', {}, 'kr/mil'), h('th', {}, 'kr/year'),
        h('th', {}, `vs ${def ? def.name : ''}`), h('th', {}, ''))),
      h('tbody', {}, rows.map(car => {
        const total = carTotal(car);
        const diff = total - base;
        return h('tr', {},
          h('td', {}, car.name || '(unnamed)', ' ', h('span', { class: 'muted' }, car.kind || '')),
          h('td', {}, kr(total)),
          h('td', {}, perMil(car).toFixed(1)),
          h('td', {}, kr(total * 12)),
          h('td', { class: car === def ? 'muted' : diff < 0 ? 'cheaper' : 'dearer' },
            car === def ? 'default' : signedKr(diff)),
          h('td', { class: 'barcell' },
            h('div', { class: car === def ? 'bar default' : 'bar', style: `width:${(total / max) * 100}%` })));
      })))),
  );
}

function renderCar(car) {
  const deleting = pendingDelete.has(car.id);
  const totalEl = h('div', { class: 'total' });
  totalCells.push({ car, el: totalEl });

  const typeSelect = h('select', {}, Object.entries(TYPES).map(([k, t]) => h('option', { value: k }, t.label)));
  const addItem = () => {
    const type = typeSelect.value;
    car.items.push({ id: uid('item'), name: 'New cost', type, enabled: true, ...structuredClone(TYPES[type].defaults) });
    render();
    scheduleSave();
  };

  return h('article', { class: 'panel car' },
    h('div', { class: 'car-head' },
      textInput(car, 'name', 'name', 'Car name'),
      car.default ? h('span', { class: 'badge' }, 'default') : null,
      h('select', {
        onchange: e => { car.kind = e.target.value; changed(); },
      }, ['own', 'lease', 'buy'].map(k => h('option', { value: k, selected: car.kind === k }, k))),
      h('button', { type: 'button', onclick: () => duplicateCar(car) }, 'Duplicate'),
      car.default ? null : h('button', {
        type: 'button', class: 'danger',
        onclick: () => deleting ? deleteCar(car) : askDelete(car),
      }, deleting ? 'Click again to delete' : 'Delete')),
    h('textarea', {
      rows: 1, placeholder: 'Notes (quote, dealer, contract length…)', value: car.notes ?? '',
      oninput: e => { car.notes = e.target.value; scheduleSave(); },
    }),
    car.basis ? h('div', { class: 'note' }, `Averages from ${car.basis}.`) : null,
    h('table', { class: 'items' }, h('tbody', {},
      car.items.filter(item => !item.hidden || showingHidden.has(car.id)).flatMap(item => renderItem(car, item)))),
    hiddenToggle(car),
    repairBudget(car),
    h('div', { class: 'car-foot' },
      h('div', {}, typeSelect, ' ', h('button', { type: 'button', onclick: addItem }, '+ Add cost')),
      totalEl),
  );
}

function renderItem(car, item) {
  const costEl = h('td', { class: 'cost' });
  costCells.push({ item, el: costEl });
  const row = h('tr', {
    class: 'item-row' + (item.enabled ? '' : ' off') + (item.hidden ? ' hidden-row' : ''),
  },
    h('td', {}, h('input', {
      type: 'checkbox', checked: !!item.enabled, title: 'Include this cost',
      onchange: e => {
        item.enabled = e.target.checked;
        if (item.enabled && item.group) {
          // Either/or: e.g. repairs as all-period vs last-12-month average must not be counted twice.
          car.items.forEach(other => { if (other !== item && other.group === item.group) other.enabled = false; });
          render();
        } else {
          row.classList.toggle('off', !item.enabled);
        }
        changed();
      },
    })),
    h('td', {}, textInput(item, 'name', 'name'), h('div', { class: 'type' },
      item.group ? `either/or (${item.group})` : '', originCell(item),
      // The description stays in the data; it is only shown when hovering the ⓘ.
      item.note ? h('span', { class: 'info', title: item.note }, ' ⓘ') : null)),
    h('td', { class: 'params' }, renderParams(item)),
    costEl,
    h('td', { class: 'actions' },
      h('button', {
        type: 'button', class: 'small',
        title: item.hidden ? 'Show this cost again and count it' : 'Hide this cost: not shown and not counted, but kept in the data',
        onclick: () => { item.hidden = !item.hidden; render(); scheduleSave(); },
      }, item.hidden ? 'unhide' : 'hide'),
      ' ',
      h('button', {
        type: 'button', class: 'icon danger', title: 'Delete this cost permanently',
        onclick: () => { car.items.splice(car.items.indexOf(item), 1); render(); scheduleSave(); },
      }, '×')),
  );
  return [row];
}

// For a car with repair items (group "repairs"): how much repairs + service per year it can afford and still cost
// no more than each other car, given everything else that is ticked. Not an item, since it would be circular.
function repairBudget(car) {
  if (!car.items.some(i => i.group === 'repairs')) return null;
  const el = h('div', { class: 'budget' });
  budgetBoxes.push({ car, el });
  fillBudget(car, el);
  return el;
}

function fillBudget(car, el) {
  const repairItems = car.items.filter(i => i.group === 'repairs');
  const others = data.cars.filter(c => c !== car);
  const base = car.items.filter(i => i.enabled && !i.hidden && i.group !== 'repairs')
    .reduce((sum, i) => sum + monthly(i), 0);
  el.replaceChildren(
    h('div', { class: 'budget-title' }, 'Repairs & service this car can afford (everything else as ticked above)'),
    h('table', {}, h('tbody', {}, others.map(other => {
      const room = carTotal(other) - base;
      return h('tr', {},
        h('td', {}, `to cost the same as ${other.name || '(unnamed)'} (${kr(carTotal(other))}/month)`),
        h('td', { class: room < 0 ? 'dearer' : 'cheaper' }, room < 0
          ? `already ${kr(-room * 12)}/year dearer before any repairs`
          : `up to ${kr(room * 12)}/year (${kr(room)}/month)`));
    }))),
    h('div', { class: 'note' }, 'For comparison, your own history: ' +
      repairItems.map(i => `${i.name.replace(/^Repairs & service \(?/, '').replace(/\)$/, '')} ${kr(monthly(i) * 12)}/year`)
        .join(', ') + '.'),
  );
}

function hiddenToggle(car) {
  const hidden = car.items.filter(i => i.hidden);
  if (!hidden.length) return null;
  const showing = showingHidden.has(car.id);
  return h('div', { class: 'hidden-toggle note' },
    `${hidden.length} hidden ${hidden.length === 1 ? 'cost is' : 'costs are'} not counted. `,
    h('button', {
      type: 'button', class: 'link',
      onclick: () => { showing ? showingHidden.delete(car.id) : showingHidden.add(car.id); render(); },
    }, showing ? 'Hide them again' : 'Show hidden'));
}

// Rows computed from the transactions (build_v40.py) are "auto"; after a manual edit they are "edited".
function originCell(item) {
  if (item.auto === undefined) return null;
  const el = h('span', { class: 'origin' });
  originCells.push({ item, el });
  el.dataset.state = String(item.auto);
  fillOrigin(item, el);
  return el;
}

function fillOrigin(item, el) {
  if (item.auto) {
    el.replaceChildren(h('span', { class: 'badge auto', title: 'Computed from the transaction data. ' +
      'build_v40.py updates it when new transactions are added.' }, 'auto'));
    return;
  }
  el.replaceChildren(
    h('span', { class: 'badge edited', title: 'You changed this value, so build_v40.py no longer updates it.' },
      'edited'),
    item.auto_value === undefined ? null : h('button', {
      type: 'button', class: 'link', title: 'Go back to the value computed from the transactions',
      onclick: () => { item.value = item.auto_value; item.auto = true; render(); scheduleSave(); },
    }, `↺ use data value (${kr(item.auto_value)})`),
  );
}

function renderParams(item) {
  const unit = text => h('span', {}, text);
  switch (item.type) {
    case 'fixed': return [numberInput(item, 'value'), unit('kr/month')];
    case 'per_year': return [numberInput(item, 'value'), unit('kr/year')];
    case 'one_time': return [numberInput(item, 'value'), unit('kr over'), numberInput(item, 'months'), unit('months')];
    case 'capital':
      return [numberInput(item, 'amount', 'Money tied up (kr)'), unit('kr at'),
        numberInput(item, 'rate_pct', `Interest per year (empty = default ${num(data.settings.return_rate_pct)} %)`),
        unit('% per year, compounded over'), numberInput(item, 'months', 'Number of months the money is tied up'),
        unit('months')];
    case 'depreciation':
      return [numberInput(item, 'value_now'), unit('kr now, loses'), numberInput(item, 'rate_pct'),
        unit('%/year, over'), numberInput(item, 'months'), unit('months')];
    case 'excess_mileage':
      return [numberInput(item, 'rate'), unit('kr/mil over'), numberInput(item, 'limit_per_year'), unit('mil/year')];
    case 'fuel': {
      const energy = ENERGY[item.energy] ?? ENERGY.petrol;
      return [
        h('select', {
          onchange: e => { item.energy = e.target.value; render(); scheduleSave(); },
        }, Object.entries(ENERGY).map(([k, e]) => h('option', { value: k, selected: item.energy === k }, e.label))),
        ' ', numberInput(item, 'consumption', 'Consumption per mil (10 km)'), unit(energy.unit),
        numberInput(item, 'share_pct', 'Share of the driving'), unit('%'),
      ];
    }
    default: return [unit('unknown type')];
  }
}

function updateNumbers() {
  for (const { item, el } of costCells) el.textContent = kr(monthly(item));
  for (const { car, el } of budgetBoxes) fillBudget(car, el);
  for (const { item, el } of originCells) {
    if (el.dataset.state !== String(item.auto)) { el.dataset.state = String(item.auto); fillOrigin(item, el); }
  }
  for (const { car, el } of totalCells) {
    el.replaceChildren(kr(carTotal(car)) + '/month ', h('span', { class: 'muted' }, `${perMil(car).toFixed(1)} kr/mil`));
  }
  renderSummary();
}

// ---------- car actions ----------

function duplicateCar(car) {
  const copy = structuredClone(car);
  copy.id = uid('car');
  copy.name = `${car.name} (copy)`;
  copy.default = false;
  delete copy.basis;
  copy.items.forEach(i => { i.id = uid('item'); delete i.auto; });
  data.cars.splice(data.cars.indexOf(car) + 1, 0, copy);
  render();
  scheduleSave();
}

function askDelete(car) {
  pendingDelete.add(car.id);
  render();
  setTimeout(() => { if (pendingDelete.delete(car.id)) render(); }, 4000);
}

function deleteCar(car) {
  pendingDelete.delete(car.id);
  data.cars.splice(data.cars.indexOf(car), 1);
  render();
  scheduleSave();
}

// A new car starts with the cost rows in settings.new_car_template (copied, with fresh ids), so only the
// numbers need filling in. Without a template it starts empty.
function addCar() {
  const template = data.settings.new_car_template || [];
  data.cars.push({
    id: uid('car'), name: 'New car', kind: 'lease', notes: '',
    items: template.map(item => ({ ...structuredClone(item), id: uid('item') })),
  });
  render();
  scheduleSave();
}

// ---------- loading and saving ----------

function scheduleSave() {
  setStatus('Unsaved changes…');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 500);
}

async function save() {
  saveTimer = null;
  if (saving) { scheduleSave(); return; }
  saving = true;
  try {
    const res = await fetch('/api/data', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': etag },
      body: JSON.stringify(data),
    });
    if (res.status === 409) {
      etag = res.headers.get('ETag');
      data = await res.json();
      render();
      setStatus('cars.json was changed outside the app, so it was reloaded. Your last edit was not saved.', 'warn');
      return;
    }
    if (!res.ok) throw new Error(await res.text());
    etag = res.headers.get('ETag');
    setStatus('Saved', 'ok');
  } catch (err) {
    setStatus('Could not save: ' + err.message, 'error');
  } finally {
    saving = false;
  }
}

async function load(quiet = false) {
  const res = await fetch('/api/data', { cache: 'no-store' });
  const tag = res.headers.get('ETag');
  if (quiet && (tag === etag || saveTimer || saving)) return;
  data = await res.json();
  etag = tag;
  render();
  if (quiet) setStatus('Reloaded: cars.json was changed outside the app.', 'ok');
}

// Pick up cars added to cars.json outside the app (e.g. by Claude) without a manual refresh.
window.addEventListener('focus', () => load(true).catch(() => {}));
setInterval(() => { if (!document.hidden) load(true).catch(() => {}); }, 5000);

document.getElementById('add-car').addEventListener('click', addCar);
load().catch(err => setStatus('Could not load data: ' + err.message, 'error'));
