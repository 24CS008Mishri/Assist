import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';


const appSource = readFileSync(new URL('../src/app.jsx', import.meta.url), 'utf8');
const analyzerSource = readFileSync(new URL('../src/components/reviewer-analyzer.jsx', import.meta.url), 'utf8');
const serviceSource = readFileSync(
  new URL('../src/lib/mock-services.js', import.meta.url),
  'utf8',
);
const utilitySource = readFileSync(
  new URL('../src/lib/analyzer-utils.js', import.meta.url),
  'utf8',
);


test('criterion cards are populated from the analyze endpoint response', () => {
  assert.match(serviceSource, /\/api\/workflow\/submissions\/.*\/analyze/);
  assert.match(analyzerSource, /setReport\(result\)/);
  assert.match(analyzerSource, /report\.criteria \|\| \[\]\)\.map/);
  assert.match(analyzerSource, /<ScoreTile[^>]+criterion=\{criterion\}/);
  assert.match(analyzerSource, /onClick=\{onClick\}/);
});

test('live issue cards use backend issues and no hardcoded analyzer values', () => {
  assert.match(analyzerSource, /report\.issues \|\| \[\]/);
  assert.match(analyzerSource, /issue\.why_it_matters/);
  assert.match(analyzerSource, /issue\.recommended_solution/);
  assert.doesNotMatch(analyzerSource, /\['Structure', 89\]|Resource quality is uneven/);
});

test('unavailable LLM issues retain deterministic scoring presentation', () => {
  assert.match(analyzerSource, /report\.issues_available/);
  assert.match(analyzerSource, /Priority recommendations unavailable/);
  assert.match(analyzerSource, /criterion scores and deterministic checks below are still available/);
});

test('modal exposes score, coverage, evidence, and not-evaluable exclusion', () => {
  assert.match(analyzerSource, /criterionCalculation\(criterion\)/);
  assert.match(analyzerSource, /coverageCalculation\(criterion\)/);
  assert.match(analyzerSource, /showModal\(\)/);
  assert.match(analyzerSource, /Missing evidence can yield zero marks on required checks/);
  assert.match(analyzerSource, /check\.availability_policy/);
  assert.match(analyzerSource, /Excluded from score/);
  assert.match(analyzerSource, /check\.obtained_marks/);
  assert.match(analyzerSource, /check\.maximum_marks/);
});

test('scope and score presentation distinguishes partial and full curricula', () => {
  assert.match(analyzerSource, /Document scope/);
  assert.match(analyzerSource, /documentScopeLabel\(report\.document_scope\)/);
  assert.match(analyzerSource, /overallScoreLabel\(report\)/);
  assert.match(utilitySource, /Evaluable Score/);
  assert.match(utilitySource, /Overall Score/);
  assert.match(analyzerSource, /evaluable parts of a partial curriculum/);
  assert.match(analyzerSource, /Limited coverage/);
  assert.match(analyzerSource, /criterionScoreLabel\(criterion\)/);
});

test('issue cards retain severity, related checks, evidence, and locations', () => {
  assert.match(analyzerSource, /issue\.severity/);
  assert.match(analyzerSource, /issue\.problem/);
  assert.match(analyzerSource, /issue\.related_check_ids/);
  assert.match(analyzerSource, /item\.page_number/);
  assert.match(analyzerSource, /Read original excerpt/);
  assert.match(analyzerSource, /<blockquote>\{item\.excerpt\}<\/blockquote>/);
});

test('analyzer renders loading, empty, not-found, insufficient, and API error states', () => {
  for (const state of [
    'analyzer-loading',
    'No pending submissions',
    'analyzer-not-found',
    'analyzer-ambiguous',
    'analyzer-invalid-metadata',
    'analyzer-insufficient',
    'analyzer-error',
  ]) {
    assert.match(analyzerSource, new RegExp(state));
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

test('designer curricula remain private and the role no longer opens Analyzer', () => {
  const curriculaSource = appSource.slice(
    appSource.indexOf('function DesignerCurricula'),
    appSource.indexOf('function CreateWizard'),
  );
  assert.match(curriculaSource, /mockService\.getDocuments\(\)/);
  assert.match(curriculaSource, /submittedCurriculumDocuments/);
  assert.match(curriculaSource, /getMySubmissions\(\)/);
  assert.match(curriculaSource, /getDraftDocument\(item\.curriculum_id, item\.document_id\)/);
  assert.doesNotMatch(curriculaSource, /Analyze curriculum/);
  assert.doesNotMatch(curriculaSource, /designer === 'Ananya Iyer'/);
});

test('reviewer analyzer is bound to an official submission ID', () => {
  assert.match(appSource, /path === '\/reviewer\/analyzer'/);
  assert.match(appSource, /submission_id/);
  assert.match(analyzerSource, /mockService\.analyzeSubmission\(submissionId\)/);
  assert.match(appSource, /path\.startsWith\('\/designer\/analyzer'\)[\s\S]*?Unauthorized/);
});

test('Reviewer Queue and Institute Portal use workflow APIs rather than demo submissions', () => {
  const queue = appSource.slice(appSource.indexOf('function ReviewQueue'), appSource.indexOf('function ReviewSupportingPage'));
  const portal = appSource.slice(appSource.indexOf('function InstituteSubmissionPortal'), appSource.indexOf('function AdminUsers'));
  assert.match(queue, /mockService\.getPendingSubmissions\(\)/);
  assert.match(queue, /mockService\.decideSubmission/);
  assert.doesNotMatch(queue, /mockCurricula/);
  assert.match(portal, /mockService\.getWorkflowCurricula\(\)/);
  assert.match(portal, /mockService\.submitPreparedCurriculum/);
  assert.match(portal, /review_history/);
});

test('reviewer decision support is evidence based and records justified overrides', () => {
  assert.match(analyzerSource, /const support = report\.decision_support/);
  assert.match(analyzerSource, /record\?\.aicte_evidence/);
  assert.match(analyzerSource, /record\?\.curriculum_evidence/);
  assert.match(analyzerSource, /recommendation !== matches && !justification\.trim\(\)/);
  assert.match(appSource, /overrideRequired\('accept'\)/);
  assert.match(serviceSource, /justification/);
  assert.match(analyzerSource, /submission-version-comparison/);
});

test('designer curriculum cards show database review requests linked to that curriculum', () => {
  const dashboard = appSource.slice(appSource.indexOf('function DesignerCurricula'), appSource.indexOf('function CreateWizard'));
  assert.match(dashboard, /sub\.curriculum_id === item\.curriculum_id/);
  assert.match(dashboard, /sub\.change_requests/);
  assert.match(dashboard, /Prepare corrected version/);
  assert.match(dashboard, /review\.feedback/);
  assert.match(dashboard, /handoff_status\s*\|\|\s*''\)\.trim\(\)\.toLowerCase\(\)\s*===\s*'ready for institute'/);
  assert.match(dashboard, /disabled=\{alreadySent \|\| Boolean\(busy\)\}/);
  assert.match(dashboard, /result\?\.handoff_status !== 'Ready for institute'/);
});

test('resource search and notifications use persistent workflow APIs', () => {
  const resourcePage = appSource.slice(appSource.indexOf('function ResourcePage'), appSource.indexOf('function ComparisonPage'));
  const notificationPage = appSource.slice(appSource.indexOf('function Notifications'), appSource.indexOf('function SettingsPage'));
  assert.match(resourcePage, /mockService\.searchResources/);
  assert.match(resourcePage, /mockService\.saveResource/);
  assert.match(resourcePage, /mockService\.getDocuments\(\)/);
  assert.match(resourcePage, /<select id="resource-curriculum"/);
  assert.match(resourcePage, /submittedCurriculumDocuments\(documents\)/);
  assert.match(notificationPage, /mockService\.getNotifications/);
  assert.match(notificationPage, /mockService\.markAllNotificationsRead/);
});

test('accepted submissions require institution publication before appearing as published', () => {
  assert.match(serviceSource, /getEligiblePublications\(\)/);
  assert.match(serviceSource, /publishSubmission\(submissionId\)/);
  assert.match(appSource, /mockService\.publishSubmission/);
  assert.match(appSource, /function PublishedCurriculaPage/);
  assert.match(appSource, /mockService\.getPublishedCurricula\(\)/);
});

test('institution change requests and delivery feedback save against published versions', () => {
  assert.match(serviceSource, /submitInstituteFeedback/);
  assert.match(appSource, /kind: 'change_request'/);
  assert.match(appSource, /kind: 'feedback'/);
  assert.match(appSource, /Prepare corrected version/);
});

test('role dashboards load counts and submission records from workflow services', () => {
  const dashboard = appSource.slice(appSource.indexOf('function Dashboard('), appSource.indexOf('function DashboardActions'));
  assert.match(dashboard, /mockService\.getAdminSubmissions/);
  assert.match(dashboard, /mockService\.getPendingSubmissions/);
  assert.match(dashboard, /mockService\.getImprovementHistory/);
  assert.match(dashboard, /mockService\.getWorkflowCurricula/);
});

test('admin activity and criteria pages read actual workflow and analyzer configuration', () => {
  const activity = appSource.slice(appSource.indexOf('function AuditLogs'), appSource.indexOf('function ReviewQueue'));
  const policies = appSource.slice(appSource.indexOf('function PolicyManagement'), appSource.indexOf('function AdminInstitutes'));
  assert.match(activity, /mockService\.getAdminAuditEvents/);
  assert.match(activity, /actionFilter/);
  assert.match(activity, /aria-expanded/);
  assert.match(policies, /mockService\.getAnalyzerCriteria/);
  assert.match(policies, /availability_policy/);
  assert.match(serviceSource, /\/api\/workflow\/admin\/audit-events/);
  assert.match(serviceSource, /\/api\/analyzer\/criteria/);
});

test('comparison and account settings use persisted records and preferences', () => {
  const comparison = appSource.slice(appSource.indexOf('function ComparisonPage'), appSource.indexOf('function displayAnalyzerValue'));
  const settings = appSource.slice(appSource.indexOf('function SettingsPage'), appSource.indexOf('function Modal'));
  assert.match(comparison, /mockService\.getImprovementHistory/);
  assert.doesNotMatch(comparison, /Reference Curriculum A|B\.Tech Artificial Intelligence v2\.1/);
  assert.match(settings, /mockService\.getAccountProfile/);
  assert.match(settings, /mockService\.updateAccountPreferences/);
  assert.match(serviceSource, /\/api\/workflow\/account\/me\/preferences/);
});

test('assistant source evidence is live and actions do not claim to modify an unsaved draft', () => {
  const assistant = appSource.slice(appSource.indexOf('function AssistantPage'), appSource.indexOf('function RagAssistantPage'));
  assert.match(assistant, /answer\?\.sources/);
  assert.match(assistant, /Copy response/);
  assert.doesNotMatch(assistant, /sourceCards|Apply to draft/);
  assert.doesNotMatch(serviceSource, /analyzerScoreHistory|mockCurricula|mockChanges/);
});

test('course views use published curricula and account support never reports fake success', () => {
  const courses = appSource.slice(appSource.indexOf('function InstituteCourses'), appSource.indexOf('function Coordinators'));
  const coordinators = appSource.slice(appSource.indexOf('function Coordinators'), appSource.indexOf('function ChangeRequests'));
  const auth = appSource.slice(appSource.indexOf('function AuthPage'), appSource.indexOf('function Unauthorized'));
  assert.match(courses, /mockService\.getPublishedCurricula/);
  assert.match(courses, /getPublishedCurriculumStructure/);
  assert.doesNotMatch(courses, /Dr\. Kavya|Prof\. Nikhil|CSE201/);
  assert.match(coordinators, /No faculty directory or coordinator assignment records/);
  assert.match(auth, /Accounts are provisioned by an Admin/);
  assert.match(auth, /Online password recovery is not configured/);
  assert.doesNotMatch(auth, /secure reset link has been sent|Workspace ready/);
});

test('obsolete Screener and Designer Analyzer navigation are removed', () => {
  const navigation = appSource.slice(appSource.indexOf('const navByRole'), appSource.indexOf('function can('));
  const reviewerNav = navigation.slice(navigation.indexOf('reviewer: ['), navigation.indexOf('designer: ['));
  const designerNav = navigation.slice(navigation.indexOf('designer: ['), navigation.indexOf('institute: ['));
  assert.doesNotMatch(reviewerNav, /screener/i);
  assert.match(reviewerNav, /\/reviewer\/analyzer/);
  assert.doesNotMatch(designerNav, /analyzer/i);
});

test('missing uploaded AICTE references have an explicit non-scoring state', () => {
  assert.match(analyzerSource, /analyzer-aicte-reference-unavailable/);
  assert.match(analyzerSource, /AICTE reference unavailable/);
  assert.match(analyzerSource, /unavailable \|\| report\.overall_score == null/);
  assert.match(analyzerSource, /aicte_reference_available === false/);
});
