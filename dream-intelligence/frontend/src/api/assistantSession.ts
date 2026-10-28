import type { AssistantMessage, PlanFields, PlanProposal } from './planAssistant';

const key = 'dsih.plan-assistant.session.v1';
export interface AssistantSession {
  messages: AssistantMessage[]; proposal: PlanProposal | null; draft: PlanFields | null;
  input: string; topicText: string; websiteText: string;
}
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(row => typeof row === 'string');
function fields(value: unknown): value is PlanFields {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<PlanFields>;
  return typeof row.name === 'string' && typeof row.purpose === 'string' && strings(row.topics) && strings(row.websites);
}
export function readAssistantSession(): AssistantSession | null {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(key) ?? 'null');
    if (!value || !Array.isArray(value.messages) || value.messages.length > 24
      || !value.messages.every((row: AssistantMessage) => row && ['user','assistant'].includes(row.role)
        && typeof row.content === 'string' && row.content.length <= 3000)
      || !['input','topicText','websiteText'].every(name => typeof value[name] === 'string')
      || value.draft !== null && !fields(value.draft)) return null;
    if (value.proposal !== null) {
      const row = value.proposal;
      if (!row || !['needs_details','draft_ready'].includes(row.status) || typeof row.message !== 'string'
        || !strings(row.questions) || row.plan !== null && !fields(row.plan)
        || !Array.isArray(row.sources) || !row.sources.every((source: {url:unknown;name:unknown;scope:unknown}) =>
          source && [source.url,source.name,source.scope].every(part => typeof part === 'string'))
        || row.deferred_sources && (!Array.isArray(row.deferred_sources) || !row.deferred_sources.every(
          (source: {name:unknown;reason:unknown}) => source && typeof source.name === 'string' && typeof source.reason === 'string'))) return null;
    }
    // A refresh during a pending reply must not revive a superseded ready draft.
    if (value.messages.at(-1)?.role === 'user') value.proposal = null;
    return value as AssistantSession;
  } catch { return null; }
}
export function saveAssistantSession(value: AssistantSession) {
  try {
    if (!value.messages.length && !value.draft && !value.input) { clearAssistantSession(); return; }
    const messages = value.messages.length > 24 ? [value.messages[0], ...value.messages.slice(-23)] : value.messages;
    window.sessionStorage.setItem(key, JSON.stringify({ ...value, messages }));
  } catch { /* Browser storage is optional; failure must not block planning. */ }
}
export function clearAssistantSession() {
  try { window.sessionStorage.removeItem(key); } catch { /* Storage may be disabled. */ }
}
