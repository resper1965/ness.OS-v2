const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const document = {};
let click;
let request;
const toolbar = { on: (_event, _selector, handler) => { click = handler; } };
const button = {
  data: () => 'suggest',
  html: (value) => value === undefined ? 'Sugerir' : button,
  prop: () => button,
};
function $(arg) {
  if (arg === document) return { ready: (fn) => fn() };
  if (arg === button) return button;
  if (arg.startsWith('<div')) return toolbar;
  if (arg === 'input[name=_glpi_csrf_token]') return { val: () => 'csrf-test' };
  if (arg === '.timeline-buttons') {
    return { length: 1, first: () => ({ before: () => {} }) };
  }
  return { length: 0 };
}
$.ajax = (options) => { request = options; };

const source = fs.readFileSync(path.join(__dirname, '../public/js/nessai.js'), 'utf8');
vm.runInNewContext(source, {
  document,
  window: { location: { href: 'https://glpi.test/front/ticket.form.php?id=41', pathname: '/front/ticket.form.php' } },
  CFG_GLPI: { root_doc: '' },
  $,
  Date,
});
assert.equal(typeof click, 'function');
click.call(button, { preventDefault() {} });
assert.equal(request.headers?.['X-Glpi-Csrf-Token'], 'csrf-test');
console.log('PASS: AJAX request carries the GLPI CSRF header');
