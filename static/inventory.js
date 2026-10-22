const el = id => document.getElementById(id);
const element = (tag, text, className) => {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
};
const statusNames = {REORDER:'Replenish', EXPEDITE_EXISTING:'Expedite incoming', INCOMING_COVERED:'Incoming covers need', NO_RECENT_SALES:'Review slow stock', SUFFICIENT:'Sufficient'};
let report;
let selected;
function amount(value, currency) {
  return value === null ? 'Not comparable / incomplete' : new Intl.NumberFormat('en', {style:'currency', currency}).format(value);
}
function selectProduct(item) {
  el('product-detail').hidden = false;
  selected = item;
  renderRows();
  el('detail-sku').textContent = item.sku + ' · ' + item.sellable_unit;
  el('detail-name').textContent = item.name;
  el('detail-status').textContent = statusNames[item.status];
  el('detail-reason').textContent = item.reason;
  el('detail-numbers').replaceChildren();
  for (const [label, value] of [['Days of stock', item.days_cover ?? 'No recent sales'], ['Proposed quantity', item.suggested_quantity], ['First projected shortage', item.first_shortage_date ?? 'None in horizon'], ['Overdue units excluded', item.overdue_quantity]]) {
    const card = element('div');
    card.append(element('span', label), element('strong', String(value)));
    el('detail-numbers').append(card);
  }
  el('detail-calculation').replaceChildren();
  for (const text of [
    `Available = ${item.on_hand} on hand − ${item.reserved} reserved = ${item.available} ${item.sellable_unit}.`,
    `Baseline = ${item.window_sales} sold / ${report.metadata.demand_window_days} calendar days = ${item.daily_sales.toFixed(2)} per day. ${item.window_returns} returned units are reported separately.`,
    `Reorder point = sales/day × (lead ${item.lead_days} + safety ${item.safety_days} days) = ${item.reorder_point.toFixed(1)} units.`,
    `Stock position = ${item.available} available + ${item.confirmed_incoming} confirmed incoming = ${item.stock_position}.`,
    `Target = sales/day × (lead ${item.lead_days} + safety ${item.safety_days} + review ${item.review_days} days) = ${item.target_stock.toFixed(1)} units. When triggered, the target gap is rounded up to a multiple of ${item.order_multiple}.`,
    'The daily projection receives confirmed deliveries before that day’s baseline sales. First shortage is the first negative projected balance. Overdue deliveries are excluded until reconfirmed.'
  ]) el('detail-calculation').append(element('p', text));
  el('quote-rows').replaceChildren();
  for (const quote of item.quotations) {
    const row = element('tr');
    const supplier = element('td');
    supplier.append(element('strong', quote.supplier), element('div', quote.quote_id + ' · ' + quote.sellable_unit));
    const cost = element('td', quote.economics ? amount(quote.economics.landed_cost, item.currency) : 'Unavailable');
    cost.append(element('small', `Quoted ${quote.currency}: ${quote.wholesale_price ?? 'unknown'} wholesale + ${quote.shipping_per_unit ?? 'unknown'} shipping + ${quote.duty_per_unit ?? 'unknown'} duty`));
    supplier.append(element('small', 'Valid through ' + quote.valid_until));
    const order = element('td', quote.order_quantity + ' / ' + amount(quote.order_cost, item.currency));
    const outcome = element('td');
    outcome.append(element('span', quote.quote_id === item.selected_quote_id ? 'Proposed for review' : quote.eligible ? 'Eligible alternative' : 'Needs clarification', 'badge'));
    for (const issue of quote.issues) outcome.append(element('div', issue, 'issue'));
    if (quote.economics) outcome.append(element('div', quote.economics.gross_margin_percent.toFixed(1) + '% gross margin'));
    row.append(supplier, cost, order, element('td', quote.arrival_date), outcome);
    el('quote-rows').append(row);
  }
  if (!item.quotations.length) {
    const cell = element('td', item.suggested_quantity ? 'No quotation available. Research and request comparable offers.' : 'No new sourcing required under the current baseline.');
    cell.colSpan = 5;
    const row = element('tr'); row.append(cell); el('quote-rows').append(row);
  }
  el('recommendation').textContent = item.recommendation;
  el('inquiry-download').hidden = item.suggested_quantity <= 0;
  el('inquiry-download').href = '/api/inventory/inquiry/' + encodeURIComponent(item.sku);
  el('handoff-research').hidden = item.suggested_quantity <= 0;
  el('handoff-json').textContent = JSON.stringify(item.handoff, null, 2);
}
function renderRows() {
  const filter = el('inventory-filter').value;
  const search = el('inventory-search').value.trim().toLowerCase();
  const rows = report.items.filter(item =>
    (filter === 'all' || (filter === 'action' ? ['REORDER','EXPEDITE_EXISTING'].includes(item.status) : item.status === filter)) &&
    (item.name + ' ' + item.sku).toLowerCase().includes(search));
  el('row-count').textContent = rows.length + ' OF ' + report.items.length + ' PRODUCTS';
  el('inventory-rows').replaceChildren();
  for (const item of rows) {
    const row = element('tr', undefined, selected?.sku === item.sku ? 'selected' : '');
    const title = element('td'); title.append(element('strong', item.name), element('small', item.sku + ' · ' + item.sellable_unit));
    const review = element('td');
    const button = element('button', 'Review ' + item.sku);
    button.type = 'button'; button.addEventListener('click', () => selectProduct(item));
    review.append(button, element('small', statusNames[item.status]));
    row.append(title, element('td', String(item.available)), element('td', item.daily_sales.toFixed(1)), element('td', String(item.confirmed_incoming)), element('td', String(item.suggested_quantity)), review);
    el('inventory-rows').append(row);
  }
  if (!rows.length) {const row = element('tr'); const cell = element('td', 'No products match this filter.'); cell.colSpan = 6; row.append(cell); el('inventory-rows').append(row);}
  return rows;
}
function applyFilters() {
  const rows = renderRows();
  el('product-detail').hidden = !rows.length;
  if (rows.length && !rows.some(item => item.sku === selected?.sku)) selectProduct(rows[0]);
}
async function initialise() {
  try {
    const response = await fetch('/api/inventory');
    report = await response.json();
    if (!response.ok) throw Error(report.error);
    const m = report.metadata;
    el('dataset-label').textContent = `SYNTHETIC DEMO · Snapshot ${m.as_of} · Sales ${m.history_start} to ${m.history_end} · No live inventory or supplier data.`;
    el('inventory-metrics').replaceChildren();
    for (const [label, value, note] of [['Products', report.summary.products, 'Whole fictional catalog'], ['Replenishment candidates', report.summary.reorder, 'Subject to review'], ['Covered by incoming', report.summary.incoming_covered, 'Avoid duplicate orders'], ['Quotation gaps', report.summary.quote_gaps, 'No eligible offer yet']]) {
      const card = element('div', undefined, 'metric'); card.append(element('span', label), element('strong', String(value)), element('small', note)); el('inventory-metrics').append(card);
    }
    el('baseline-description').textContent = `Baseline: average positive sales over the ${m.demand_window_days} calendar days ending ${m.history_end}. Demand is held constant through each product’s planning horizon.`;
    el('limitations').replaceChildren();
    for (const text of m.limitations) el('limitations').append(element('li', text));
    el('inventory-app').hidden = false;
    selectProduct(report.items[0]);
  } catch (error) {
    el('dataset-label').textContent = 'Synthetic data review unavailable.';
    el('load-error').hidden = false; el('load-error').textContent = error.message;
  }
}
el('inventory-filter').addEventListener('change', applyFilters);
el('inventory-search').addEventListener('input', applyFilters);
el('handoff-research').addEventListener('click', () => {
  const query = new URLSearchParams({product:selected.name + ', ' + selected.sellable_unit, vat:selected.vat_rate, margin:selected.target_margin, sku:selected.sku});
  window.location.href = '/?' + query.toString();
});
initialise();
