import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Render the actual component without a browser, network, or production writes.
const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../src/pages/ResearchResults.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
} }).outputText;
const exports = {};
new Function('require', 'exports', compiled)(require, exports);
const { ResearchResults } = exports;
const item = (id, title, date) => ({ id, title, published_at: date, source: 'Test', url: `https://example.com/${id}` });
const run = { id: 1, plan_id: 1, status: 'COMPLETED', errors: [], received: 3, matched: 3, inserted: 3,
  items: [item(1, 'Old article', '2026-10-20T00:00:00Z'), item(2, 'Unknown article', null),
    item(3, 'Newest article', '2026-10-23T01:00:00Z')],
  summary: { overview: 'Overview', findings: [], limitations: 'Evidence only', sections: [
    { category: '模型与版本', summary: 'A real group synthesis', key_points: ['Shared trend'],
      suggested_action: 'Verify the sources', item_ids: [2, 1, 3] },
  ] },
};
const render = value => renderToStaticMarkup(React.createElement(ResearchResults, { run: value }));

test('groups show synthesis and order by publication, with undated evidence last', () => {
  const html = render(run);
  assert.ok(html.indexOf('Newest article') < html.indexOf('Old article'));
  assert.ok(html.indexOf('Old article') < html.indexOf('Unknown article'));
  assert.ok(html.includes('发布时间未知'));
  assert.ok(html.includes('A real group synthesis') && html.includes('Shared trend'));
  assert.ok(html.includes('2026/10/23 09:00'));
});
test('legacy results show pending classification without inventing an agent summary', () => {
  const html = render({ ...run, summary: { ...run.summary, sections: [] } });
  assert.ok(html.includes('待归类资讯'));
  assert.ok(html.includes('分析已有结果'));
  assert.ok(!html.includes('AGENT 综合分析'));
});
test('regions themselves are ordered by their newest evidence', () => {
  const base = run.summary.sections[0];
  const value = { ...run, summary: { ...run.summary, sections: [
    { ...base, category: 'Old region', item_ids: [1, 2] },
    { ...base, category: 'Newest region', item_ids: [3] },
  ] } };
  const html = render(value);
  assert.ok(html.indexOf('Newest region') < html.indexOf('Old region'));
});

test('empty selection distinguishes failure from a successful search with no matches',()=>{
  const empty={...run,status:'NO_MATCHES',summary:null,items:[],received:30,matched:0};
  const noMatch=render(empty);
  assert.ok(noMatch.includes('获取了 30 条候选')&&noMatch.includes('当前话题和目的'));
  const failure=render({...empty,status:'FAILED',errors:[{reason:'WeiboTopicSelectionFailed'}]});
  assert.ok(failure.includes('话题筛选未完成')&&!failure.includes('未筛出与当前话题'));
});
