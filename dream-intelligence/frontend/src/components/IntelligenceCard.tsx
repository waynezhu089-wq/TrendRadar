import { useState } from 'react';
import type { FeedbackValue, Intelligence } from '../api/intelligence';

const options: { value: FeedbackValue; label: string }[] = [
  { value: 'useful', label: '👍 有价值' },
  { value: 'not_useful', label: '👎 没价值' },
  { value: 'watch', label: '⭐ 继续跟踪' },
];

export function IntelligenceCard({ item, onFeedback }: {
  item: Intelligence;
  onFeedback: (itemId: number, feedback: FeedbackValue) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function choose(feedback: FeedbackValue) {
    setSaving(true);
    setError('');
    try {
      await onFeedback(item.id, feedback);
    } catch {
      setError('保存反馈失败，请重试。');
    } finally {
      setSaving(false);
    }
  }

  return <article className="card">
    <div className="labels"><span>{item.category.replaceAll('_', ' ')}</span>{item.source_type === 'mock' && <span>MOCK DATA</span>}</div>
    <h2>{item.title}</h2>
    <p>{item.summary}</p>
    <h3>Why it matters</h3><p>{item.why_it_matters}</p>
    <div className="scores"><span>Priority <strong>{item.priority}</strong></span><span>Dream Stream Relevance <strong>{item.dreamstream_relevance}</strong></span></div>
    <p className="tags">{item.tags.join(' · ')}</p>
    <div className="feedback-actions" aria-label="反馈">
      {options.map(option => <button key={option.value} type="button"
        aria-pressed={item.feedback === option.value} disabled={saving}
        onClick={() => void choose(option.value)}>{option.label}</button>)}
    </div>
    {error && <p className="feedback-error" role="alert">{error}</p>}
    <footer>{item.source} · {item.analyzer_version}{item.published_at && <> · <time dateTime={item.published_at}>{item.published_at.replace('T', ' ')}</time></>}</footer>
  </article>;
}
