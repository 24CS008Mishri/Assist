import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';


const appSource = readFileSync(new URL('../src/app.jsx', import.meta.url), 'utf8');
const serviceSource = readFileSync(
  new URL('../src/lib/mock-services.js', import.meta.url),
  'utf8',
);
const utilitySource = readFileSync(
  new URL('../src/lib/analyzer-utils.js', import.meta.url),
  'utf8',
);


test('criterion cards are populated from the analyze endpoint response', () => {
  assert.match(serviceSource, /\/api\/analyzer\/analyze\//);
  assert.match(appSource, /mockService\.analyzeCurriculum/);
  assert.match(appSource, /setReport\(result\)/);
  assert.match(appSource, /criteria\.map\(\(criterion\)/);
  assert.match(appSource, /criterion=\{criterion\}/);
  assert.match(appSource, /function AnalyzerScoreTile\(\{ criterion, onClick \}\)/);
  assert.match(appSource, /onClick=\{onClick\}/);
});

test('live issue cards use backend issues and no hardcoded analyzer values', () => {
  assert.match(appSource, /report\.issues\.map\(\(issue\)/);
  assert.match(appSource, /issue\.why_it_matters/);
  assert.match(appSource, /issue\.recommended_solution/);
  const liveAnalyzer = appSource.slice(
    appSource.indexOf('function Analyzer({ notify })'),
    appSource.indexOf('function DesignerChanges'),
  );
  assert.doesNotMatch(liveAnalyzer, /\['Structure', 89\]/);
  assert.doesNotMatch(liveAnalyzer, /Resource quality is uneven/);
});

test('unavailable LLM issues retain deterministic scoring presentation', () => {
  assert.match(appSource, /if \(!report\.issues_available\)/);
  assert.match(appSource, /AI recommendations are temporarily unavailable/);
  assert.match(appSource, /deterministic scores and evidence are still available/);
});

test('modal exposes score, coverage, evidence, and not-evaluable exclusion', () => {
  assert.match(appSource, /criterionCalculation\(criterion\)/);
  assert.match(appSource, /coverageCalculation\(criterion\)/);
  assert.match(appSource, /AICTE Evidence/);
  assert.match(appSource, /Curriculum Evidence/);
  assert.match(appSource, /Excluded from score/);
  assert.match(appSource, /it is not a failure/);
  assert.match(appSource, /This check was excluded from scoring because sufficient evidence was not available/);
  assert.match(appSource, /does not represent the complete B\.Tech CSE programme/);
  assert.match(appSource, /Obtained marks/);
  assert.match(appSource, /Maximum marks/);
});

test('scope and score presentation distinguishes partial and full curricula', () => {
  assert.match(appSource, /Document Scope/);
  assert.match(appSource, /documentScopeLabel\(report\.document_scope\)/);
  assert.match(appSource, /overallScoreLabel\(report\)/);
  assert.match(utilitySource, /Evaluable Score/);
  assert.match(utilitySource, /Overall Score/);
  assert.match(appSource, /Partial curriculum analyzed/);
  assert.match(appSource, /Based on.*evaluation coverage/);
  assert.match(appSource, /Limited evaluation coverage/);
  assert.match(appSource, /criterionScoreLabel\(criterion\)/);
});

test('issue cards retain severity, related checks, evidence, and locations', () => {
  assert.match(appSource, /issue\.severity/);
  assert.match(appSource, /issue\.problem/);
  assert.match(appSource, /issue\.related_check_ids/);
  assert.match(appSource, /item\.page_number/);
  assert.match(appSource, /item\.chunk_index/);
});

test('analyzer renders loading, empty, not-found, insufficient, and API error states', () => {
  for (const state of [
    'analyzer-loading',
    'analyzer-empty',
    'analyzer-not-found',
    'analyzer-ambiguous',
    'analyzer-invalid-metadata',
    'analyzer-insufficient',
    'analyzer-error',
  ]) {
    assert.match(appSource, new RegExp(state));
  }
});

test('existing demo session forwards only its registry user ID', () => {
  assert.match(serviceSource, /function currentDemoUserId\(\)/);
  assert.match(serviceSource, /localStorage\.getItem\('aicte-demo-session'\)/);
  assert.match(serviceSource, /headers\.set\('X-Demo-User-Id', demoUserId\)/);
  assert.doesNotMatch(serviceSource, /headers\.set\('X-Demo-User-Id', 'u3'\)/);
});

test('designer create upload classifies PDFs for the private curriculum store', () => {
  assert.match(appSource, /mockService\.uploadDocument\(selectedPdf/);
  assert.match(appSource, /source_type: 'submitted_curriculum'/);
  assert.match(appSource, /curriculum_id: details\.curriculumId/);
  assert.match(appSource, /setLocation\('\/designer\/curricula'\)/);
  assert.match(serviceSource, /Object\.entries\(metadata\)/);
  assert.match(serviceSource, /body\.append\(key, String\(value\)\.trim\(\)\)/);
});

test('my curricula loads owned documents and every card opens its analyzer selection', () => {
  const curriculaSource = appSource.slice(
    appSource.indexOf('function DesignerCurricula'),
    appSource.indexOf('function CreateWizard'),
  );
  assert.match(curriculaSource, /mockService\.getDocuments\(\)/);
  assert.match(curriculaSource, /submittedCurriculumDocuments/);
  assert.match(curriculaSource, /analyzerDocumentHref\(item\)/);
  assert.match(curriculaSource, /Analyze curriculum/);
  assert.doesNotMatch(curriculaSource, /designer === 'Ananya Iyer'/);
});

test('analyzer honors the curriculum and document selected by a card', () => {
  assert.match(appSource, /path\.startsWith\('\/designer\/analyzer'\)/);
  assert.match(appSource, /requestedAnalyzerDocument\(available, window\.location\.search\)/);
});

test('missing uploaded AICTE references have an explicit non-scoring state', () => {
  assert.match(appSource, /analyzer-aicte-reference-unavailable/);
  assert.match(appSource, /AICTE Reference: Unavailable/);
  assert.match(appSource, /AICTE-based score: Not Evaluable/);
  assert.match(appSource, /aicte_reference_available === false/);
  assert.match(appSource, /AICTE-based recommendations are unavailable/);
});
