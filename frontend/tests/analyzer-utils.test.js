import assert from 'node:assert/strict';
import test from 'node:test';

import {
  analyzerDocumentHref,
  checkStatusLabel,
  coverageCalculation,
  criterionScoreLabel,
  criterionCalculation,
  documentScopeLabel,
  hasLowEvaluationCoverage,
  isPartialCurriculum,
  isPartialScopeExclusion,
  overallScoreLabel,
  requestedAnalyzerDocument,
  submittedCurriculumDocuments,
} from '../src/lib/analyzer-utils.js';


test('only analyzable submitted curricula are offered to the cards', () => {
  const documents = submittedCurriculumDocuments([
    { source_type: 'aicte_reference', curriculum_id: null },
    { source_type: 'submitted_curriculum', curriculum_id: null },
    { source_type: 'submitted_curriculum', curriculum_id: 'xyz-cse-2026' },
  ]);
  assert.equal(documents.length, 1);
  assert.equal(documents[0].curriculum_id, 'xyz-cse-2026');
});

test('curriculum cards link to and select the exact uploaded document', () => {
  const documents = [
    { curriculum_id: 'same-curriculum', document_id: 'doc-1', filename: 'first.pdf' },
    { curriculum_id: 'same-curriculum', document_id: 'doc-2', filename: 'second.pdf' },
  ];
  const href = analyzerDocumentHref(documents[1]);
  assert.equal(
    href,
    '/designer/analyzer?curriculum_id=same-curriculum&document_id=doc-2',
  );
  assert.equal(requestedAnalyzerDocument(documents, href.split('?')[1]), documents[1]);
});

test('modal score and coverage calculations use backend marks', () => {
  const criterion = {
    score: 80,
    obtained_marks: 60,
    evaluable_maximum_marks: 75,
    configured_maximum_marks: 100,
    evaluation_coverage: 75,
  };
  assert.equal(criterionCalculation(criterion), '60 / 75 × 100 = 80%');
  assert.equal(coverageCalculation(criterion), '75 / 100 × 100 = 75%');
});

test('not-evaluable calculation and low-coverage threshold are explicit', () => {
  assert.equal(
    criterionCalculation({ score: null, evaluable_maximum_marks: 0 }),
    'No evaluable checks; criterion score is not available.',
  );
  assert.equal(checkStatusLabel('not_evaluable'), 'NOT EVALUABLE');
  assert.equal(hasLowEvaluationCoverage(49.99), true);
  assert.equal(hasLowEvaluationCoverage(50), false);
});

test('partial and full curriculum score labels are scope safe', () => {
  const partial = { document_scope: 'PARTIAL_CURRICULUM' };
  const full = { document_scope: 'FULL_CURRICULUM' };
  assert.equal(isPartialCurriculum(partial), true);
  assert.equal(isPartialCurriculum(full), false);
  assert.equal(documentScopeLabel(partial.document_scope), 'PARTIAL CURRICULUM');
  assert.equal(documentScopeLabel(full.document_scope), 'FULL CURRICULUM');
  assert.equal(overallScoreLabel(partial), 'Evaluable Score');
  assert.equal(overallScoreLabel(full), 'Overall Score');
  assert.equal(
    overallScoreLabel({ ...full, aicte_reference_available: false }),
    'AICTE-based Score',
  );
});

test('null criterion and partial-scope exclusion messaging are distinguishable', () => {
  assert.equal(criterionScoreLabel({ score: null }), 'Not Evaluable');
  assert.equal(criterionScoreLabel({ score: 82 }), '82%');
  assert.equal(
    isPartialScopeExclusion(
      { document_scope: 'PARTIAL_CURRICULUM' },
      {
        status: 'not_evaluable',
        deduction_reason: 'Not evaluable from a partial curriculum document.',
      },
    ),
    true,
  );
  assert.equal(
    isPartialScopeExclusion(
      { document_scope: 'FULL_CURRICULUM' },
      {
        status: 'not_evaluable',
        deduction_reason: 'Not evaluable: evidence unavailable.',
      },
    ),
    false,
  );
});
