"""Build the importable n8n workflow without credentials or live executions."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# Keep this export compatible with the editor that renders IF 2.3 and
# HTTP Request 4.5 as unknown nodes. Do not use the MCP catalogue's latest
# versions as evidence of what a separately deployed editor supports.
HTTP_REQUEST_VERSION = 4.2
IF_VERSION = 2.2


def node(name, kind, version, params, x, y, **extra):
    return {
        'id': str(uuid5(NAMESPACE_URL, 'ts-techservice-n8n/' + name)),
        'name': name, 'type': 'n8n-nodes-base.' + kind,
        'typeVersion': version, 'position': [x, y], 'parameters': params, **extra,
    }


def graph(name, url, x, y, body=None, method='GET', **params):
    config = {
        'method': method, 'url': url,
        'authentication': 'genericCredentialType', 'genericAuthType': 'oAuth2Api',
        'options': {'timeout': 25000}, **params,
    }
    if body is not None:
        config.update(sendBody=True, contentType='json', specifyBody='json', jsonBody=body)
    return node(name, 'httpRequest', HTTP_REQUEST_VERSION, config, x, y, retryOnFail=False)


prepare = r"""
const input = $input.first().json.body;
if (!input || !['email', 'teams'].includes(input.channel)) throw new Error('Invalid channel');
if (!['quotation_sent', 'quotation_reminder', 'ticket_alert'].includes(input.event_type)) throw new Error('Invalid event type');
for (const key of ['event_id', 'recipient', 'subject', 'body', 'record_url']) {
  if (typeof input[key] !== 'string' || !input[key].trim()) throw new Error('Missing field: ' + key);
}
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.recipient)) throw new Error('Invalid recipient');
if (!input.record_url.startsWith('https://')) throw new Error('Record URL must use HTTPS');
const content = input.body + '\n\nMở TechService: ' + input.record_url;
const message = {
  subject: input.subject,
  body: {contentType: 'Text', content},
  toRecipients: [{emailAddress: {address: input.recipient}}],
};
if (input.attachment) {
  const file = input.attachment;
  if (typeof file.content_base64 !== 'string' || !file.name) throw new Error('Invalid PDF attachment');
  if (file.content_base64.length > 4000000) throw new Error('PDF exceeds inline Graph attachment limit');
  message.attachments = [{
    '@odata.type': '#microsoft.graph.fileAttachment', name: file.name,
    contentType: 'application/pdf', contentBytes: file.content_base64,
  }];
}
return [{json: {...input, content, mail_payload: {message, saveToSentItems: true}}}];
""".strip()

members = r"""
const sender = $('Teams Sender').first().json;
const users = $input.first().json.value || [];
if (!sender.id || users.length !== 1 || !users[0].id) throw new Error('Cannot uniquely resolve Teams recipient');
const recipient = users[0];
if (sender.id === recipient.id) throw new Error('Use a sending account different from the sale recipient');
if (recipient.userType === 'Guest') throw new Error('This workflow is configured for internal DAT users');
const member = id => ({
  '@odata.type': '#microsoft.graph.aadUserConversationMember', roles: ['owner'],
  'user@odata.bind': "https://graph.microsoft.com/v1.0/users('" + id + "')",
});
return [{json: {chat_payload: {chatType: 'oneOnOne', members: [member(sender.id), member(recipient.id)]}}}];
""".strip()

nodes = [
    node('Configuration', 'stickyNote', 1, {
        'content': '## TechService → Email + Teams riêng\n1. Webhook: chọn Header Auth, tên header X-TechService-Token.\n2. Tất cả node Microsoft Graph: chọn cùng OAuth2 credential (delegated user).\nScopes: User.Read User.ReadBasic.All Mail.Send Chat.Create ChatMessage.Send offline_access.\n3. Publish rồi nhập Production URL + token vào Odoo.\nMỗi event chỉ gửi một kênh; Odoo theo dõi hai kênh độc lập.\nKhông bật Retry On Fail cho node gửi. Nếu timeout, kiểm tra execution trước khi gửi lại.\nPhản hồi sale được ghi trên Odoo; reply Teams/email tự do chưa được đọc tự động.',
        'height': 370, 'width': 580,
    }, 20, -450),
    node('TechService Webhook', 'webhook', 2.1, {
        'httpMethod': 'POST', 'path': 'techservice-notifications',
        'authentication': 'headerAuth', 'responseMode': 'responseNode', 'options': {},
    }, 0, 0, webhookId='ts-techservice-notifications'),
    node('Prepare Notification', 'code', 2, {'mode': 'runOnceForAllItems', 'language': 'javaScript', 'jsCode': prepare}, 240, 0),
    node('Email Channel', 'if', IF_VERSION, {
        'conditions': {
            'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
            'conditions': [{'id': 'email-channel', 'leftValue': '={{ $json.channel }}', 'rightValue': 'email',
                            'operator': {'type': 'string', 'operation': 'equals'}}], 'combinator': 'and',
        }, 'options': {},
    }, 480, 0),
    graph('Send Email with PDF', 'https://graph.microsoft.com/v1.0/me/sendMail', 760, -140,
          method='POST', body='={{ $json.mail_payload }}',
          options={'timeout': 25000, 'response': {'response': {'fullResponse': True, 'responseFormat': 'text'}}}),
    graph('Teams Sender', 'https://graph.microsoft.com/v1.0/me?$select=id,userPrincipalName', 760, 140),
    graph('Resolve Sale for Teams', 'https://graph.microsoft.com/v1.0/users', 1000, 140,
          sendQuery=True, queryParameters={'parameters': [
              {'name': '$select', 'value': 'id,mail,userPrincipalName,userType'},
              {'name': '$filter', 'value': "={{ \"userPrincipalName eq '\" + $('Prepare Notification').first().json.recipient.replace(/'/g, \"''\") + \"' or mail eq '\" + $('Prepare Notification').first().json.recipient.replace(/'/g, \"''\") + \"'\" }}"},
          ]}),
    node('Build Private Chat', 'code', 2, {'mode': 'runOnceForAllItems', 'language': 'javaScript', 'jsCode': members}, 1240, 140),
    graph('Create or Reuse Private Chat', 'https://graph.microsoft.com/v1.0/chats', 1480, 140,
          method='POST', body='={{ $json.chat_payload }}'),
    graph('Send Teams Message', "={{ 'https://graph.microsoft.com/v1.0/chats/' + encodeURIComponent($json.id) + '/messages' }}", 1720, 140,
          method='POST', body="={{ {body: {contentType: 'text', content: $('Prepare Notification').first().json.content}} }}"),
    node('Acknowledge Delivery', 'respondToWebhook', 1.5, {
        'respondWith': 'json',
        'responseBody': "={{ {delivered: true, event_id: $('Prepare Notification').first().json.event_id, channel: $('Prepare Notification').first().json.channel} }}",
        'options': {'responseCode': 200},
    }, 1980, 0),
]

connections = {}


def connect(source, destination, output=0):
    outputs = connections.setdefault(source, {'main': [[]]})['main']
    while len(outputs) <= output:
        outputs.append([])
    outputs[output].append({'node': destination, 'type': 'main', 'index': 0})


connect('TechService Webhook', 'Prepare Notification')
connect('Prepare Notification', 'Email Channel')
connect('Email Channel', 'Send Email with PDF')
connect('Email Channel', 'Teams Sender', 1)
connect('Send Email with PDF', 'Acknowledge Delivery')
connect('Teams Sender', 'Resolve Sale for Teams')
connect('Resolve Sale for Teams', 'Build Private Chat')
connect('Build Private Chat', 'Create or Reuse Private Chat')
connect('Create or Reuse Private Chat', 'Send Teams Message')
connect('Send Teams Message', 'Acknowledge Delivery')

workflow = {
    'name': 'DAT - TechService - Email + Private Teams - Compatible v2',
    'nodes': nodes, 'connections': connections, 'active': False,
    'settings': {'executionOrder': 'v1', 'timezone': 'Asia/Bangkok', 'executionTimeout': 120},
    'pinData': {}, 'tags': [],
}

if __name__ == '__main__':
    content = json.dumps(workflow, ensure_ascii=False, indent=2) + '\n'
    for filename in ('techservice_email_teams.json', 'techservice_email_teams_v2.json'):
        destination = Path(__file__).with_name(filename)
        destination.write_text(content, encoding='utf-8')
        print(destination)
