export const LOW_EVALUATION_COVERAGE_THRESHOLD = 50;

export function analyzerDocumentKey(document) {
  return document.document_id || `${document.curriculum_id}:${document.filename}`;
}

export function analyzerDocumentHref(document) {
  const params = new URLSearchParams({ curriculum_id: document.curriculum_id });
  if (document.document_id) params.set('document_id', document.document_id);
  return `/designer/analyzer?${params.toString()}`;
}

export function requestedAnalyzerDocument(documents, search = '') {
  const params = new URLSearchParams(search);
  const curriculumId = params.get('curriculum_id');
  const documentId = params.get('document_id');
  if (!curriculumId && !documentId) return null;
  return (documents || []).find((document) => (
    (!curriculumId || document.curriculum_id === curriculumId)
    && (!documentId || document.document_id === documentId)
  )) || null;
}

export function submittedCurriculumDocuments(documents) {
  return (documents || []).filter(
    (document) => document.source_type === 'submitted_curriculum' && document.curriculum_id,
  );
}

export function hasLowEvaluationCoverage(coverage) {
  return Number(coverage || 0) < LOW_EVALUATION_COVERAGE_THRESHOLD;
}

export function isPartialCurriculum(report) {
  return report?.document_scope === 'PARTIAL_CURRICULUM';
}

export function documentScopeLabel(scope) {
  return {
    PARTIAL_CURRICULUM: 'PARTIAL CURRICULUM',
    FULL_CURRICULUM: 'FULL CURRICULUM',
  }[scope] || 'SCOPE UNAVAILABLE';
}

export function overallScoreLabel(report) {
  if (report?.aicte_reference_available === false) return 'AICTE-based Score';
  return isPartialCurriculum(report) ? 'Evaluable Score' : 'Overall Score';
}

export function criterionScoreLabel(criterion) {
  return criterion?.score == null ? 'Not Evaluable' : `${criterion.score}%`;
}

export function isPartialScopeExclusion(report, check) {
  return isPartialCurriculum(report)
    && check?.status === 'not_evaluable'
    && String(check?.deduction_reason || '').toLowerCase().includes('partial curriculum document');
}

export function criterionCalculation(criterion) {
  if (criterion?.score == null || !criterion?.evaluable_maximum_marks) {
    return 'No evaluable checks; criterion score is not available.';
  }
  return `${criterion.obtained_marks} / ${criterion.evaluable_maximum_marks} × 100 = ${criterion.score}%`;
}

export function coverageCalculation(criterion) {
  const configured = criterion?.configured_maximum_marks || 0;
  if (!configured) return 'Evaluation coverage is not available.';
  return `${criterion.evaluable_maximum_marks} / ${configured} × 100 = ${criterion.evaluation_coverage}%`;
}

export function checkStatusLabel(status) {
  return {
    pass: 'PASS',
    partial: 'PARTIAL',
    fail: 'FAIL',
    not_evaluable: 'NOT EVALUABLE',
  }[status] || String(status || '').toUpperCase();
}
