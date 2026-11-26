import assert from 'node:assert/strict';
import test from 'node:test';
import { checkPresentation, evidenceEntries, evidencePreview, versionComparison } from '../src/lib/reviewer-analyzer.js';

test('zero marks for missing evidence and unverified compliance get separate labels', () => {
  const mandatory = { status: 'fail', rule_type: 'AICTE_MANDATORY', obtained_marks: 0 };
  const cited = { ...mandatory, curriculum_evidence: [{}], aicte_evidence: [{}] };
  assert.equal(checkPresentation({}, mandatory).label, 'Manual verification');
  assert.equal(checkPresentation({}, cited).label, 'Confirmed compliance issue');
  assert.equal(checkPresentation({}, { ...cited,
    deduction_reason: 'Required check failed: reliable evidence was not extracted; zero marks awarded.',
  }).label, 'Missing evidence');
  assert.equal(checkPresentation({}, { status: 'not_evaluable' }).label, 'Not evaluable');
  assert.equal(checkPresentation({ document_scope: 'PARTIAL_CURRICULUM' }, {
    status: 'not_evaluable', deduction_reason: 'Excluded for a partial curriculum document',
  }).label, 'Outside document scope');
  assert.equal(checkPresentation({}, { status: 'pass' }).label, 'Satisfied');
});

test('evidence previews retain conditions and merged sources keep original excerpts', () => {
  const item = { source: 'Policy.pdf', page_number: 4, chunk_index: 5,
    excerpt: 'A lab is required  only where the course includes a practical component.' };
  const group = { label: 'AICTE reference', evidence: [item] };
  const [citation, second] = evidenceEntries(group, group);
  assert.equal(second, undefined);
  assert.equal(citation.excerpt, item.excerpt);
  assert.equal(citation.page_number, 4);
  assert.equal(evidencePreview(citation.excerpt), 'A lab is required only where the course includes a practical component.');
  assert.equal(evidencePreview('Credits | Classroom | Lab'), '');
  assert.equal(evidencePreview('A'.repeat(200) + '.'), '');
});

test('version comparison uses saved finding states and compares only matching scoring scopes', () => {
  const scope = { document_scope: 'FULL_CURRICULUM', scoring_version: '3' };
  const submission = {
    previous_versions: [{ version: 2, analyses: [] }, { version: 1, analyses: [{ report: { ...scope, overall_score: 0 } }] }],
    analyses: [{ report: { ...scope, overall_score: 48.2 }, finding_snapshot: [
      { finding_id: 'open-no-evidence', status: 'Open' }, { finding_id: 'resolved', status: 'Resolved' },
      { finding_id: 'new', status: 'Newly Detected' }, { finding_id: 'reopened', status: 'Reopened' },
    ] }],
  };
  const comparison = versionComparison(submission);
  assert.equal(comparison.previousVersion, 1);
  assert.equal(comparison.prior, 0);
  assert.equal(comparison.delta, 48.2);
  assert.deepEqual(comparison.changes.map(({ findings }) => findings.map((row) => row.finding_id)), [['resolved'], ['new'], ['reopened']]);
  submission.analyses[0].report.document_scope = 'PARTIAL_CURRICULUM';
  assert.equal(versionComparison(submission).delta, null);
  delete submission.analyses[0].finding_snapshot;
  assert.equal(versionComparison(submission).changes, null);
});
