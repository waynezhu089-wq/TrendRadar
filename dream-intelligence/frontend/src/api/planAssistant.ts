import type { ResearchPlan } from './research';

export type PlanFields = Omit<ResearchPlan, 'id' | 'created_at'>;
export interface AssistantMessage { role: 'user' | 'assistant'; content: string }
export interface PlanProposal {
  status: 'needs_details' | 'draft_ready'; message: string; questions: string[];
  plan: PlanFields | null; sources: { url: string; name: string; scope: string }[];
  deferred_sources?: { name: string; reason: string }[];
}
export interface CreatedPlan { plan: ResearchPlan; created: boolean }
const base = 'http://127.0.0.1:8000/api/v1/research-plan-assistant';

export function conversationForRequest(messages: AssistantMessage[]): AssistantMessage[] {
  if (!messages.length) return [];
  const first = messages[0];
  const tail: AssistantMessage[] = [];
  let budget = 12000 - first.content.length;
  for (let index = messages.length - 1; index > 0 && tail.length < 9; index--) {
    if (messages[index].content.length > budget) break;
    tail.unshift(messages[index]); budget -= messages[index].content.length;
  }
  return [first, ...tail];
}

export async function draftPlan(messages: AssistantMessage[], currentDraft: PlanFields | null): Promise<PlanProposal> {
  const response = await fetch(`${base}/draft`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: conversationForRequest(messages), current_draft: currentDraft }) });
  if (!response.ok) throw new Error(response.status === 503 ? '尚未配置助手使用的模型，请检查本机模型配置。'
    : response.status === 409 ? '助手正在处理另一条需求，请稍后重试。'
    : response.status === 422 ? '这段对话太长或内容未通过校验，请缩短需求后重试。'
    : '助手暂时未能整理好方案，尚未创建任何项目。可以重试。');
  return response.json();
}

export async function confirmPlan(plan: PlanFields): Promise<CreatedPlan> {
  const response = await fetch(`${base}/create`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan, confirmed: true }) });
  if (!response.ok) throw new Error(response.status === 422
    ? '草案内容未通过校验：请检查话题数量、公开网址和至少 10 字的目的。'
    : '方案尚未保存成功，请稍后重试。草案已保留。');
  return response.json();
}
