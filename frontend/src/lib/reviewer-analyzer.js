import { isPartialScopeExclusion } from './analyzer-utils.js';

export const severityLevels = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export function readableLabel(value) {
  const words = String(value ?? '').replaceAll('_', ' ').trim();
  return words ? words.toLowerCase().replace(/^./, (letter) => letter.toUpperCase()) : '';
}

export function checkPresentation(report, check) {
  const reason = check.deduction_reason || check.explanation || '';
  if (check.status === 'pass') return { label: 'Satisfied', tone: 'green' };
  if (isPartialScopeExclusion(report, check)) return { label: 'Outside document scope', tone: 'slate' };
  if (/reliable evidence was not extracted|official AICTE reference.*unavailable|absence cannot be distinguished/i.test(reason)) {
    return { label: 'Missing evidence', tone: 'amber' };
  }
  if (check.status === 'not_evaluable') return { label: 'Not evaluable', tone: 'slate' };
  if (check.status === 'fail' && check.rule_type === 'AICTE_MANDATORY') {
    return check.curriculum_evidence?.length && check.aicte_evidence?.length
      ? { label: 'Confirmed compliance issue', tone: 'red' }
      : { label: 'Manual verification', tone: 'amber' };
  }
  if (check.status === 'fail') return { label: 'Check failed', tone: 'red' };
  if (check.status === 'partial') return { label: 'Partially satisfied', tone: 'amber' };
  return { label: 'Manual verification', tone: 'amber' };
}

export function evidenceEntries(...groups) {
  const entries = new Map();
  for (const { label, evidence } of groups) {
    for (const item of evidence || []) {
      const key = JSON.stringify([label, item.source, item.page_number, item.chunk_index, item.heading, item.excerpt]);
      entries.set(key, { ...item, label, key });
    }
  }
  return [...entries.values()];
}

// Use only a self-contained quotation for the preview. The full excerpt is always available.
export function evidencePreview(excerpt) {
  const clean = String(excerpt || '').trim().replace(/\s+/g, ' ');
  if (!clean || clean.length > 180 || !/[.!?।]$/.test(clean) || clean.includes('|')) return '';
  return clean;
}

export function versionComparison(submission) {
  const previous = (submission.previous_versions || []).find((version) => version.analyses?.length);
  const currentRun = submission.analyses?.[0];
  const previousRun = previous?.analyses[0];
  if (!currentRun || !previousRun) return null;

  const prior = previousRun.report?.overall_score;
  const current = currentRun.report?.overall_score;
  const scoresComparable = prior != null && current != null
    && previousRun.report.document_scope === currentRun.report.document_scope
    && previousRun.report.scoring_version === currentRun.report.scoring_version;
  const changes = Array.isArray(currentRun.finding_snapshot)
    ? ['Resolved', 'Newly Detected', 'Reopened'].map((status) => ({
      status,
      findings: currentRun.finding_snapshot.filter((finding) => finding.status === status),
    }))
    : null;
  return {
    previousVersion: previous.version,
    prior,
    current,
    delta: scoresComparable ? Number((current - prior).toFixed(2)) : null,
    changes,
  };
}
