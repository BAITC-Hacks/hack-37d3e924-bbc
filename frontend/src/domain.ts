import type {Result, Review} from './types.ts';
export function reviewOf(result:Result):Review {
  return structuredClone({participants:result.participants,tasks:result.tasks,summary:result.summary});
}
export function validateReview(review:Review, result:Result):string|null {
  const participants=new Set(review.participants.map(p=>p.id));
  const sources=new Set(result.segments.map(s=>s.id));
  const speakers=new Set(result.segments.map(s=>s.speaker_id));
  const assigned=review.participants.flatMap(p=>p.speaker_ids);
  if(new Set(assigned).size!==assigned.length || assigned.some(s=>!speakers.has(s))) return 'Один голос можно сопоставить только одному участнику.';
  for(const task of review.tasks){
    if(!task.text.trim()) return 'Укажите текст каждого поручения.';
    if(!task.source_segment_ids.length || task.source_segment_ids.some(s=>!sources.has(s))) return 'Выберите исходные реплики для каждого поручения.';
    if(task.assignee_id!==null && !participants.has(task.assignee_id)) return 'Выберите существующего участника.';
    if(task.due_date!==null){
      const date=new Date(task.due_date+'T00:00:00Z');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(task.due_date) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0,10)!==task.due_date) return 'Укажите действительную дату в формате YYYY-MM-DD.';
    }
    if((task.assignee_id===null || task.due_date===null) && !task.needs_review) return 'Поручение без исполнителя или срока требует проверки.';
  }
  return null;
}
