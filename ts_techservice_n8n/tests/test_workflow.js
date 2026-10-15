const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/techservice_email_teams.json'), 'utf8'));
const byName = Object.fromEntries(workflow.nodes.map(node => [node.name, node]));
const compatible = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/techservice_email_teams_v2.json'), 'utf8'));
assert.deepEqual(compatible, workflow);
assert.equal(workflow.active, false);
assert.equal(byName['Email Channel'].typeVersion, 2.2);
assert.equal(byName['TechService Webhook'].parameters.authentication, 'headerAuth');
for (const [name, outputs] of Object.entries(workflow.connections)) {
  assert(byName[name]);
  for (const branch of outputs.main) for (const edge of branch) assert(byName[edge.node]);
}
for (const node of workflow.nodes) {
  if (node.type.endsWith('.httpRequest')) {
    assert.equal(node.typeVersion, 4.2);
    assert.equal(node.retryOnFail, false);
    assert(!node.credentials); // Choose the actual sender after import.
  }
  for (const value of Object.values(node.parameters)) {
    if (typeof value === 'string' && value.startsWith('={{')) {
      new Function('$json', '$', 'return (' + value.slice(3, -2) + ')');
    }
  }
}
assert.equal(workflow.connections['Prepare Notification'].main[0][0].node, 'Email Channel');
assert.equal(workflow.connections['Email Channel'].main[0][0].node, 'Send Email with PDF');
assert.equal(workflow.connections['Email Channel'].main[1][0].node, 'Teams Sender');
for (const node of workflow.nodes.filter(node => !node.type.endsWith('.stickyNote') && !node.type.endsWith('.webhook'))) {
  assert(Object.values(workflow.connections).some(output => output.main.some(branch => branch.some(edge => edge.node === node.name))), `Disconnected node: ${node.name}`);
}
const executeCode = (name, json, lookup = {}) => new Function('$input', '$', byName[name].parameters.jsCode)(
  {first: () => ({json})}, name => ({first: () => ({json: lookup[name]})}),
);
const payload = {
  event_id: 'quote:1:email', channel: 'email', event_type: 'quotation_sent',
  recipient: 'sale@example.com', subject: 'Quotation Q01',
  body: 'Fault: <motor>\nSecond line', record_url: 'https://service.example.com/web#id=1&model=sale.order',
  attachment: {name: 'Q01.pdf', content_base64: Buffer.from('PDF sample').toString('base64')},
};
const result = executeCode('Prepare Notification', {body: payload})[0].json;
assert.equal(result.mail_payload.message.toRecipients[0].emailAddress.address, payload.recipient);
assert.equal(result.mail_payload.message.attachments[0].contentBytes, payload.attachment.content_base64);
assert.equal(result.mail_payload.message.body.contentType, 'Text');
assert(result.content.includes('Second line'));
assert.throws(() => executeCode('Prepare Notification', {body: {...payload, recipient: 'bad address'}}));
assert.throws(() => executeCode('Prepare Notification', {body: {...payload, channel: 'zalo'}}));
assert.throws(() => executeCode('Prepare Notification', {body: {...payload, event_id: ''}}));
assert.throws(() => executeCode('Prepare Notification', {body: {...payload, attachment: {name: 'large.pdf', content_base64: 'a'.repeat(4000001)}}}));
const chat = executeCode('Build Private Chat', {value: [{id: 'sale-id', userType: 'Member'}]}, {'Teams Sender': {id: 'sender-id'}})[0].json;
assert.equal(chat.chat_payload.chatType, 'oneOnOne');
assert.equal(chat.chat_payload.members.length, 2);
assert(chat.chat_payload.members[1]['user@odata.bind'].includes('sale-id'));
assert.throws(() => executeCode('Build Private Chat', {value: []}, {'Teams Sender': {id: 'sender-id'}}));
assert.throws(() => executeCode('Build Private Chat', {value: [{id: 'sender-id'}]}, {'Teams Sender': {id: 'sender-id'}}));
assert.throws(() => executeCode('Build Private Chat', {value: [{id: 'sale-id'}, {id: 'other-id'}]}, {'Teams Sender': {id: 'sender-id'}}));
const filterExpression = byName['Resolve Sale for Teams'].parameters.queryParameters.parameters.find(p => p.name === '$filter').value;
const filter = new Function('$', 'return (' + filterExpression.slice(3, -2) + ')')(() => ({first: () => ({json: {recipient: "o'sale@example.com"}})}));
assert(filter.includes("o''sale@example.com"));
console.log('PASS: routing, expressions, PDF email payload, invalid inputs, private chat resolution, escaped Graph filter');
