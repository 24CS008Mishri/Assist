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
  assert.match(appSource, /Evaluated score \(quality\)/);
  assert.match(appSource, /Evaluation coverage \(evidence completeness\)/);
  assert.match(appSource, /Required checks receive zero marks/);
  assert.match(appSource, /SCOPE DEPENDENT/);
  assert.match(appSource, /Missing reliable evidence for this check receives zero marks/);
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
  assert.match(appSource, /mockService\.analyzeSubmission\(submissionId\)/);
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
  assert.match(appSource, /DecisionRecommendationPanel support=\{report\.decision_support\}/);
  assert.match(appSource, /reason\.aicte_evidence/);
  assert.match(appSource, /reason\.curriculum_evidence/);
  assert.match(appSource, /overrideRequired\('accept'\)/);
  assert.match(serviceSource, /justification/);
  assert.match(appSource, /submission-version-comparison/);
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
  const comparison = appSource.slice(appSource.indexOf('function ComparisonPage'), appSource.indexOf('function Analyzer'));
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
  assert.match(appSource, /analyzer-aicte-reference-unavailable/);
  assert.match(appSource, /AICTE Reference: Unavailable/);
  assert.match(appSource, /AICTE-based score: Not Evaluable/);
  assert.match(appSource, /aicte_reference_available === false/);
  assert.match(appSource, /AICTE-based recommendations are unavailable/);
});
