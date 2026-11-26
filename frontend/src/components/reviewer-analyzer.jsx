import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'wouter';
import {
  ArrowLeft, ArrowUpRight, BarChart3, BookOpen, BriefcaseBusiness, Check, CheckCircle2,
  ChevronDown, CircleAlert, ClipboardCheck, FileText, GraduationCap, History, Layers3,
  ListChecks, RefreshCw, ShieldCheck, Sparkles, X,
} from 'lucide-react';
import { mockService } from '@/lib/mock-services';
import {
  coverageCalculation, criterionCalculation, criterionScoreLabel,
  documentScopeLabel, hasLowEvaluationCoverage, isPartialCurriculum, overallScoreLabel,
} from '@/lib/analyzer-utils';
import {
  checkPresentation, evidenceEntries, evidencePreview, readableLabel, severityLevels, versionComparison,
} from '@/lib/reviewer-analyzer';
import './reviewer-analyzer.css';

const sections = [
  ['overview', 'Overview', BarChart3], ['findings', 'Priority findings', CircleAlert],
  ['decision', 'Decision support', ClipboardCheck], ['history', 'History', History],
];
const criterionIcons = {
  structure: Layers3, compliance: ShieldCheck, industry_relevance: BriefcaseBusiness,
  learning_outcomes: GraduationCap, assessment: ListChecks, resources: BookOpen, skill_coverage: Sparkles,
};
const severityTones = { CRITICAL: 'red', HIGH: 'orange', MEDIUM: 'amber', LOW: 'purple' };
const recommendationLabels = {
  ACCEPT: ['Recommend acceptance', 'green'], REVISE: ['Recommend revision', 'amber'],
  REJECT: ['Recommend rejection', 'red'], INSUFFICIENT_EVIDENCE: ['Manual review required', 'slate'],
};

export function ReviewerAnalyzerPicker() {
  const [queue, setQueue] = useState(null);
  const [error, setError] = useState('');
  const [, setLocation] = useLocation();

  async function load() {
    setError('');
    setQueue(null);
    try { setQueue(await mockService.getPendingSubmissions()); }
    catch (failure) { setError(failure.message || 'Unable to load submissions.'); }
  }

  useEffect(() => { void load(); }, []);

  return <div className="content reviewer-analyzer">
    <header className="ra-header"><div><p className="eyebrow">Reviewer / Analysis</p><h1 className="page-title">Choose a submission</h1></div></header>
    {error ? <Notice alert title="Unable to load submissions" detail={error} retry={load} />
      : !queue ? <Notice loading title="Loading pending submissions" />
        : !queue.length ? <Notice title="No pending submissions" detail="Submissions ready for review will appear here." />
          : <div className="ra-stack">{queue.map((item) => <button
            className="ra-picker-row" key={item.submission_id}
            onClick={() => setLocation(`/reviewer/analyzer?submission_id=${encodeURIComponent(item.submission_id)}`)}>
            <FileText aria-hidden="true" size={20} /><span><strong>{item.curriculum_name}</strong>
              <small>{[item.institute_name, `Version ${item.version}`].filter(Boolean).join(' · ')}</small></span>
            <ArrowUpRight aria-hidden="true" size={17} />
          </button>)}</div>}
  </div>;
}

export default function ReviewerAnalyzer({ submissionId, notify, formatDate }) {
  const [submission, setSubmission] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState(null);
  const [historyState, setHistoryState] = useState('idle');
  const historyRequest = useRef(0);
  const [selectedCriterion, setSelectedCriterion] = useState(null);

  async function refreshHistory() {
    const request = ++historyRequest.current;
    setHistoryState('loading');
    try {
      const updated = await mockService.getSubmission(submissionId);
      if (request !== historyRequest.current) return;
      setSubmission(updated);
      setHistoryState('ready');
    } catch {
      if (request === historyRequest.current) setHistoryState('error');
    }
  }

  async function analyze(announce = false) {
    setBusy(true);
    setError(null);
    setSelectedCriterion(null);
    try {
      if (!submission) setSubmission(await mockService.getSubmission(submissionId));
      const result = await mockService.analyzeSubmission(submissionId);
      setReport(result);
      if (announce) notify('Analysis saved to this submission version.');
      void refreshHistory();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void analyze(); }, []);

  const errorTitles = { 404: 'Curriculum not found', 409: 'Submission cannot be analyzed', 422: 'Invalid curriculum metadata' };
  const checks = (report?.criteria || []).flatMap((criterion) => (criterion.checks || []).map((check) => ({
    ...check, criterion: criterion.criterion, criterionLabel: criterion.label,
  })));

  return <div className="content reviewer-analyzer">
    <header className="ra-header">
      <div><Link href="/reviewer/reviews" className="ra-back"><ArrowLeft size={15} aria-hidden="true" /> Reviewer Queue</Link>
        <h1 className="page-title">Curriculum Analyzer</h1></div>
      <button className="btn btn-primary" disabled={busy} onClick={() => void analyze(true)} data-testid="button-recalculate-analyzer">
        <RefreshCw size={15} className={busy ? 'analyzer-spin' : undefined} aria-hidden="true" /> {busy ? 'Analyzing…' : 'Recalculate'}
      </button>
    </header>
    {busy && <Notice loading title={report ? 'Recalculating report' : 'Analyzing curriculum'} testId="analyzer-loading"
      detail={report ? 'The last completed report is shown below.' : 'Evaluating the submitted version and its supporting evidence.'} />}
    {error && <Notice alert title={errorTitles[error.status] || 'Analysis unavailable'} detail={error.message}
      testId={{ 404: 'analyzer-not-found', 409: 'analyzer-ambiguous', 422: 'analyzer-invalid-metadata' }[error.status] || 'analyzer-error'} retry={analyze} />}
    {report && <>
      <nav className="ra-nav" aria-label="Analysis sections">
        {sections.map(([id, label, Icon]) => <a key={id} href={`#analyzer-${id}`} onClick={(event) => {
          event.preventDefault();
          const section = document.getElementById(`analyzer-${id}`);
          section.focus({ preventScroll: true });
          section.scrollIntoView({ block: 'start' });
        }}><Icon size={15} aria-hidden="true" />{label}</a>)}
      </nav>
      <section className="ra-section ra-overview" id="analyzer-overview" tabIndex={-1} aria-label="Curriculum health overview">
        <HealthReport report={report} submission={submission} checkCount={checks.length} />
        <div className="ra-section-heading"><h2>Criterion scores</h2><span>Select a criterion to review its checks</span></div>
        <div className="ra-criteria">
          {(report.criteria || []).map((criterion) => <ScoreTile key={criterion.criterion} criterion={criterion}
            onClick={() => setSelectedCriterion(criterion)} />)}
        </div>
        {report.overall_evaluation_coverage === 0 && <Notice title="Insufficient evidence" testId="analyzer-insufficient"
          detail="Open a criterion to see which checks could be evaluated and which were excluded." />}
      </section>
      <PriorityFindings key={submissionId} report={report} checks={checks} />
      <section className="ra-section" id="analyzer-decision" tabIndex={-1} aria-labelledby="analyzer-decision-title">
        <DecisionSupport report={report} checks={checks} />
        <FinalDecision submissionId={submissionId} recommendation={report.decision_support?.decision} notify={notify} disabled={busy} />
      </section>
      <AnalysisHistory submission={submission} formatDate={formatDate} historyState={historyState} retry={refreshHistory} />
    </>}
    {selectedCriterion && <CriterionDialog criterion={selectedCriterion} report={report}
      onClose={() => setSelectedCriterion(null)} />}
  </div>;
}

function Notice({ title, detail, loading, alert, testId, retry }) {
  const Icon = loading ? RefreshCw : CircleAlert;
  return <div className="ra-notice" data-testid={testId}>
    <div className="ra-notice-message" role={alert ? 'alert' : 'status'}>
      <Icon size={19} className={loading ? 'analyzer-spin' : undefined} aria-hidden="true" />
      <div><strong>{title}</strong>{detail && <p>{detail}</p>}</div>
    </div>
    {retry && <button className="btn" onClick={() => void retry()}>Retry</button>}
  </div>;
}

function HealthReport({ submission, report, checkCount }) {
  const unavailable = report.aicte_reference_available === false;
  const partial = isPartialCurriculum(report);
  const coverage = report.overall_evaluation_coverage;
  const score = unavailable || report.overall_score == null ? null : report.overall_score;
  const evidenceLabel = unavailable ? 'AICTE reference unavailable' : report.aicte_reference_available === true
    ? 'AICTE reference available' : 'AICTE availability unreported';

  return <div className="ra-hero" data-testid="analyzer-summary">
    <div className="ra-hero-main">
      <div>
        <p className="eyebrow">Curriculum health report</p>
        <h2>{submission?.curriculum_name || 'Submitted curriculum'}</h2>
        <p className="ra-hero-file">{[submission?.version != null && `Version ${submission.version}`, submission?.document_filename].filter(Boolean).join(' · ')}</p>
        <div className="ra-hero-facts">
          <div data-testid="analyzer-document-scope"><span>Document scope</span><strong>{readableLabel(documentScopeLabel(report.document_scope))}</strong></div>
          <div data-testid="analyzer-evaluation-coverage"><span>{unavailable ? 'Curriculum-only coverage' : 'Evaluation coverage'}</span><strong>{coverage == null ? 'Unavailable' : `${coverage}%`}</strong></div>
          <div><span>Evidence</span><strong>{evidenceLabel}</strong></div>
        </div>
      </div>
      <div className="ra-hero-score">
        <span>{overallScoreLabel(report)}</span>
        <strong data-testid="analyzer-overall-score" className={score == null ? 'ra-hero-unscored' : undefined}>{score == null ? 'Not evaluable' : `${score}%`}</strong>
        {coverage != null && <progress value={coverage} max="100" aria-label="Evaluation coverage" />}
        {(report.low_coverage || (coverage != null && hasLowEvaluationCoverage(coverage))) && <Tag tone="amber">Limited coverage</Tag>}
      </div>
    </div>
    <div className="ra-hero-footer">
      <span>{checkCount} checks{report.scoring_version && ` · Scoring ${report.scoring_version}`}</span>
      {(report.scope_reason || unavailable) && <details>
        <summary>Scope and evidence details <ChevronDown size={14} aria-hidden="true" /></summary>
        {partial && <p data-testid="analyzer-partial-warning">This score covers the evaluable parts of a partial curriculum.</p>}
        {report.scope_reason && <p>{report.scope_reason}</p>}
        {unavailable && <p data-testid="analyzer-aicte-reference-unavailable">{report.aicte_reference_message || 'Official AICTE reference evidence is unavailable.'}</p>}
      </details>}
    </div>
  </div>;
}

function Tag({ tone = 'slate', children }) {
  return <span className={`ra-tag ra-tag-${tone}`}>{children}</span>;
}

function ScoreTile({ criterion, onClick }) {
  const Icon = criterionIcons[criterion.criterion] || ListChecks;
  const limited = criterion.low_coverage || hasLowEvaluationCoverage(criterion.evaluation_coverage);
  return <button className={`ra-score-tile ra-criterion-${criterion.criterion}`} onClick={onClick}
    data-testid={`card-analyzer-criterion-${criterion.criterion}`} aria-haspopup="dialog">
    <span className="ra-tile-top"><span className="ra-tile-icon"><Icon aria-hidden="true" size={18} /></span><ArrowUpRight size={15} aria-hidden="true" /></span>
    <span className="ra-tile-label">{criterion.label}</span>
    <strong className={criterion.score == null ? 'ra-tile-unscored' : undefined}>{criterionScoreLabel(criterion)}</strong>
    <span className="ra-tile-coverage">Coverage {criterion.evaluation_coverage}%{limited && ' · Limited evidence'}</span>
  </button>;
}

function PriorityFindings({ report, checks }) {
  const [severity, setSeverity] = useState('all');
  const issues = report.issues || [];
  const available = report.issues_available;
  const byId = new Map(checks.map((check) => [check.check_id, check]));
  const counts = Object.fromEntries(severityLevels.map((level) => [level, issues.filter((issue) => issue.severity === level).length]));
  const visible = severity === 'all' ? issues : issues.filter((issue) => issue.severity === severity);

  return <section className="ra-section" id="analyzer-findings" tabIndex={-1} aria-labelledby="analyzer-findings-title">
    <div className="ra-section-heading"><h2 id="analyzer-findings-title">Priority findings</h2>{available && <span>{issues.length} findings</span>}</div>
    {!available ? <Notice title="Priority recommendations unavailable" testId="analyzer-issues-unavailable"
      detail={report.issues_error || 'The criterion scores and deterministic checks below are still available.'} />
      : !issues.length ? <Notice title="No priority findings were generated" testId="analyzer-no-issues" />
        : <>
          <div className="ra-filters" role="group" aria-label="Filter findings by severity">
            <button type="button" aria-pressed={severity === 'all'} onClick={() => setSeverity('all')}>All <span>{issues.length}</span></button>
            {severityLevels.map((level) => <button type="button" key={level} aria-pressed={severity === level}
              onClick={() => setSeverity(level)}><span className={`ra-dot ra-tag-${severityTones[level]}`} />{readableLabel(level)} <span>{counts[level]}</span></button>)}
          </div>
          <div className="ra-stack" data-testid="analyzer-live-issues">
            {visible.length ? visible.map((issue) => <FindingRow key={issue.issue_id} issue={issue}
              checks={(issue.related_check_ids || []).map((id) => byId.get(id)).filter(Boolean)} report={report} />)
              : <Notice title={`No ${severity.toLowerCase()} findings`} />}
          </div>
        </>}
  </section>;
}

function FindingRow({ issue, checks, report }) {
  const criterion = report.criteria?.find((entry) => entry.criterion === issue.criterion);
  const firstCheck = checks[0];
  const description = firstCheck?.deduction_reason || issue.why_it_matters;
  const count = issue.related_check_ids?.length;
  return <details className={`ra-row ra-finding ra-finding-${severityTones[issue.severity] || 'purple'}`} data-testid={`analyzer-issue-${issue.issue_id}`}>
    <summary className="ra-row-summary">
      <CircleAlert className="ra-finding-icon" size={17} aria-hidden="true" />
      <span className="ra-row-copy"><strong>{issue.problem}</strong>
        <span>{criterion?.label || readableLabel(issue.criterion)}{count > 0 && ` · ${count} related ${count === 1 ? 'check' : 'checks'}`}</span>
        {description && <span className="ra-preview">{description}</span>}
      </span>
      <Tag tone={severityTones[issue.severity]}>{readableLabel(issue.severity)}</Tag><Caret />
    </summary>
    <div className="ra-row-body">
      <div className="ra-facts">
        <Fact label="Why it matters" value={issue.why_it_matters} />
        <Fact label="Recommended correction" value={issue.recommended_solution} />
      </div>
      {checks.map((check) => <CheckRow key={check.check_id} check={check} report={report} />)}
      <EvidenceList entries={checkEvidence(issue)} />
    </div>
  </details>;
}

function DecisionSupport({ report, checks }) {
  const support = report.decision_support;
  const reasons = new Map((support?.reasons || []).map((reason) => [reason.finding_id, reason]));
  const mandatory = checks.filter((check) => check.rule_type === 'AICTE_MANDATORY');
  const reviewChecks = checks.filter((check) => check.status !== 'pass' && check.rule_type !== 'AICTE_MANDATORY');
  const satisfied = checks.filter((check) => check.status === 'pass' && check.rule_type !== 'AICTE_MANDATORY');
  const [label, tone] = recommendationLabels[support?.decision] || ['Recommendation unavailable', 'slate'];
  return <>
    <div className="ra-section-heading"><h2 id="analyzer-decision-title">Reviewer decision support</h2></div>
    <div className="ra-recommendation" data-testid="decision-support-panel">
      <div className="ra-recommendation-icon"><ClipboardCheck size={22} aria-hidden="true" /></div>
      <div><Tag tone={tone}>{label}</Tag>{support?.summary && <p>{support.summary}</p>}
        <small>The Reviewer records the final decision.</small></div>
    </div>
    <div className="ra-stack ra-decision-checks">
      <div data-testid="mandatory-requirement-status">
        {mandatory.length > 0 ? <CheckGroup title="Configured mandatory checks" checks={mandatory} report={report} reasons={reasons} initiallyOpen />
          : <p className="ra-muted">Confirm applicable mandatory requirements during manual review.</p>}
      </div>
      <CheckGroup title="Checks to review" checks={reviewChecks} report={report} reasons={reasons} initiallyOpen />
      <CheckGroup title="Satisfied checks" checks={satisfied} report={report} reasons={reasons} />
      {(support?.reasons || []).filter((reason) => !checks.some((check) => check.check_id === reason.finding_id)).map((reason) =>
        <CheckRow key={reason.finding_id} report={report} check={{ ...reason, check_id: reason.finding_id }} reason={reason} />)}
    </div>
  </>;
}

function CheckGroup({ title, checks, report, reasons, initiallyOpen }) {
  if (!checks.length) return null;
  const rows = checks.map((check) => <CheckRow key={check.check_id} check={check} report={report} reason={reasons.get(check.check_id)} />);
  return <details className="ra-row ra-group" open={initiallyOpen}><summary className="ra-row-summary">
    <ListChecks size={17} aria-hidden="true" /><strong>{title}</strong><Tag>{checks.length}</Tag><Caret />
  </summary><div className="ra-row-body ra-stack">
    {rows.slice(0, 4)}
    {rows.length > 4 && <details className="ra-more-checks"><summary>Show {rows.length - 4} more <Caret /></summary>
      <div className="ra-stack">{rows.slice(4)}</div></details>}
  </div></details>;
}

function CheckRow({ check, report, reason }) {
  const presentation = checkPresentation(report, check);
  const observation = check.deduction_reason || reason?.explanation;
  const evidence = evidenceEntries(...evidenceGroups(check), ...evidenceGroups(reason));
  const StatusIcon = check.status === 'pass' ? CheckCircle2 : CircleAlert;
  return <details className="ra-row ra-check" data-testid={`analyzer-check-${check.check_id}`}>
    <summary className="ra-row-summary"><StatusIcon size={16} aria-hidden="true" />
      <span className="ra-row-copy"><strong>{check.title}</strong>
        {check.criterionLabel && <span>{check.criterionLabel}</span>}
        {observation && <span className="ra-preview">{observation}</span>}
      </span>
      <span className="ra-row-tags"><Tag tone={presentation.tone}>{presentation.label}</Tag>
        {reason?.severity && !['Missing evidence', 'Manual verification'].includes(presentation.label) &&
          <Tag tone={severityTones[reason.severity]}>{readableLabel(reason.severity)}</Tag>}</span><Caret />
    </summary>
    <div className="ra-row-body">
      <div className="ra-check-meta">
        {check.rule_type && <Tag>{ruleLabel(check.rule_type)}</Tag>}
        {check.availability_policy && <Tag>{readableLabel(check.availability_policy)}</Tag>}
        {check.maximum_marks != null && <Tag>{check.status === 'not_evaluable' ? `Excluded from score · ${check.maximum_marks} possible marks` : `${check.obtained_marks ?? '—'} / ${check.maximum_marks} marks`}</Tag>}
      </div>
      <div className="ra-facts">
        <Fact label="Expected requirement" value={check.expected ?? reason?.expected} />
        <Fact label="Observed curriculum information" value={check.actual ?? reason?.actual} />
        {observation && <Fact label="Check observation" value={observation} />}
        {reason?.recommended_action && <Fact label="Recommended action" value={reason.recommended_action} />}
      </div>
      {check.status === 'not_evaluable' && <p className="ra-muted">Excluded from evaluable marks. Verify the requirement manually if it applies.</p>}
      <EvidenceList entries={evidence} />
    </div>
  </details>;
}

function ruleLabel(rule) {
  return { AICTE_MANDATORY: 'Mandatory AICTE rule', AICTE_MODEL_REFERENCE: 'AICTE model reference',
    ANALYZER_DERIVED: 'Analyzer check' }[rule] || readableLabel(rule);
}

function Fact({ label, value }) {
  return <div className="ra-fact"><h4>{label}</h4><ObservedValue value={value} /></div>;
}

function ObservedValue({ value }) {
  if (value == null || value === '') return <p>Unavailable</p>;
  if (typeof value === 'boolean') return <p>{value ? 'Yes' : 'No'}</p>;
  if (typeof value !== 'object') {
    const content = String(value);
    return content.length > 240 || content.split('\n').length > 3
      ? <details className="ra-long-text"><summary>Read full text <Caret /></summary><p>{content}</p></details>
      : <p>{content}</p>;
  }
  const isArray = Array.isArray(value);
  const entries = Object.entries(value);
  if (!entries.length) return <p>{isArray ? 'No items recorded' : 'No details recorded'}</p>;
  const list = <ul className="ra-data-list">{entries.map(([key, item]) => <li key={key}>
    {!isArray && <strong>{readableLabel(key)}</strong>}<ObservedValue value={item} />
  </li>)}</ul>;
  return entries.length > 4 ? <details className="ra-long-text"><summary>View {entries.length} {isArray ? 'entries' : 'details'} <Caret /></summary>{list}</details> : list;
}

function evidenceGroups(record) {
  return [{ label: 'Curriculum evidence', evidence: record?.curriculum_evidence },
    { label: 'AICTE reference', evidence: record?.aicte_evidence }];
}

function checkEvidence(record) {
  return evidenceEntries(...evidenceGroups(record));
}

function EvidenceList({ entries }) {
  if (!entries.length) return null;
  return <details className="ra-evidence"><summary><BookOpen size={16} aria-hidden="true" /> Evidence and references <Tag>{entries.length}</Tag><Caret /></summary>
    <div className="ra-evidence-list">{entries.map((item) => {
      const preview = evidencePreview(item.excerpt);
      return <article className="ra-citation" key={item.key}>
        <span className="ra-citation-label">{item.label}{item.page_number != null && ` · Page ${item.page_number}`}</span>
        <strong>{item.source || (item.label === 'AICTE reference' ? 'AICTE source' : 'Submitted curriculum')}</strong>
        {item.heading && <span>{item.heading}</span>}
        {preview && <p className="ra-citation-preview">“{preview}”</p>}
        {item.excerpt && <details className="ra-long-text"><summary>Read original excerpt <Caret /></summary>
          <blockquote>{item.excerpt}</blockquote>
          {item.chunk_index != null && <small className="ra-muted">Source chunk {item.chunk_index}</small>}
        </details>}
      </article>;
    })}</div>
  </details>;
}

function Caret() {
  return <ChevronDown className="ra-caret" size={17} aria-hidden="true" />;
}

function CriterionDialog({ criterion, report, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    const modal = dialog.current;
    const trigger = document.activeElement;
    modal.showModal();
    return () => {
      modal.close();
      trigger?.focus();
    };
  }, []);
  return <dialog className="ra-dialog reviewer-analyzer" ref={dialog} aria-labelledby="ra-criterion-title" onClose={onClose}>
    <header><div><p className="eyebrow">Criterion details</p><h2 id="ra-criterion-title">{criterion.label} · {criterionScoreLabel(criterion)}</h2></div>
      <button className="btn icon-btn" aria-label="Close criterion details" onClick={() => dialog.current.close()}><X size={19} /></button></header>
    <div className="ra-dialog-body">
      <div className="ra-facts">
        <Fact label="Evaluated score (quality)" value={criterionCalculation(criterion)} />
        <Fact label="Evaluation coverage (evidence completeness)" value={coverageCalculation(criterion)} />
      </div>
      <p className="ra-muted">Missing evidence can yield zero marks on required checks. Scope exclusions are removed from evaluable marks.</p>
      <div className="ra-stack">{(criterion.checks || []).map((check) => <CheckRow key={check.check_id} check={check} report={report} />)}</div>
    </div>
  </dialog>;
}

function AnalysisHistory({ submission, formatDate, historyState, retry }) {
  const saved = submission?.analyses || [];
  const older = submission?.previous_versions || [];
  const comparison = submission && versionComparison(submission);
  return <section className="ra-section" id="analyzer-history" tabIndex={-1} aria-labelledby="analyzer-history-title">
    <div className="ra-section-heading"><h2 id="analyzer-history-title">Version comparison and analysis history</h2></div>
    {historyState === 'loading' && <Notice loading title="Refreshing saved analysis history" />}
    {historyState === 'error' && <Notice alert title="Saved history could not be refreshed" retry={retry} />}
    <div className="ra-stack">
      <div className="ra-panel" data-testid="submission-version-comparison">
        <h3>Version comparison</h3>
        {comparison ? <VersionComparison comparison={comparison} version={submission.version} />
          : <p className="ra-muted">{historyState === 'ready' ? 'Comparison is available once two submitted versions have saved analyses.' : 'Waiting for saved version data.'}</p>}
      </div>
      <div className="ra-panel">
        <h3>Saved analysis runs</h3>
        {!saved.length && !older.length && historyState === 'ready' && <p className="ra-muted">No saved analyses are available.</p>}
        <div className="ra-stack">
          {saved.map((run, index) => <SavedRun key={run.analysis_id} run={run} formatDate={formatDate} latest={index === 0} />)}
          {older.map((entry) => <details key={entry.submission_id} className="ra-row ra-group">
            <summary className="ra-row-summary"><History size={16} aria-hidden="true" /><strong>Version {entry.version}</strong>
              <Tag>{entry.analyses?.length || 0} saved runs</Tag><Caret /></summary>
            <div className="ra-row-body ra-stack">{entry.analyses?.length
              ? entry.analyses.map((run) => <SavedRun key={run.analysis_id} run={run} formatDate={formatDate} />)
              : <p className="ra-muted">This version has no saved analysis.</p>}</div>
          </details>)}
        </div>
      </div>
    </div>
  </section>;
}

function VersionComparison({ comparison, version }) {
  const { previousVersion, prior, current, delta, changes } = comparison;
  return <>
    <dl className="ra-comparison-metrics">
      <div><dt>Previous · v{previousVersion}</dt><dd>{scoreText(prior)}</dd></div>
      <div><dt>Current · v{version}</dt><dd>{scoreText(current)}</dd></div>
      <div><dt>Score change</dt><dd>{delta == null ? 'Unavailable' : `${delta > 0 ? '+' : ''}${delta} pts`}</dd></div>
    </dl>
    {delta == null && <p className="ra-muted">Score change requires evaluable scores with the same document scope and scoring version.</p>}
    {changes ? <div className="ra-change-grid">{changes.map(({ status, findings }) => <details className="ra-row ra-group" key={status}>
      <summary className="ra-row-summary"><strong>{status === 'Newly Detected' ? 'New findings' : status}</strong><Tag>{findings.length}</Tag><Caret /></summary>
      <div className="ra-row-body ra-stack">{findings.length ? findings.map((finding) => <SavedFinding key={finding.finding_id} finding={finding} />)
        : <p className="ra-muted">No findings in this category.</p>}</div>
    </details>)}</div> : <p className="ra-muted">The saved analysis has no finding snapshot.</p>}
  </>;
}

function scoreText(score) {
  return score == null ? 'Not evaluable' : `${score}%`;
}

function SavedRun({ run, formatDate, latest }) {
  const [expanded, setExpanded] = useState(false);
  const report = run.report;
  const snapshot = run.finding_snapshot || [];
  return <details className="ra-row ra-group" onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className="ra-row-summary"><History size={16} aria-hidden="true" />
      <span className="ra-row-copy"><strong>{formatDate(run.created_at)}</strong>{latest && <span>Latest saved run</span>}</span>
      <Tag>{scoreText(report?.overall_score)}</Tag><Caret />
    </summary>
    {expanded && <div className="ra-row-body ra-stack">
      {report && <div className="ra-check-meta">
        <Tag>{readableLabel(documentScopeLabel(report.document_scope))}</Tag>
        {report.overall_evaluation_coverage != null && <Tag>{report.overall_evaluation_coverage}% coverage</Tag>}
        {report.scoring_version && <Tag>Scoring {report.scoring_version}</Tag>}
      </div>}
      {report?.decision_support?.summary && <Fact label="Saved recommendation" value={report.decision_support.summary} />}
      {report?.criteria?.length > 0 && <details className="ra-row ra-group"><summary className="ra-row-summary"><strong>Saved criterion scores and checks</strong><Caret /></summary>
        <div className="ra-row-body ra-stack">{report.criteria.map((criterion) => <details className="ra-row ra-group" key={criterion.criterion}>
          <summary className="ra-row-summary"><strong>{criterion.label}</strong><Tag>{criterionScoreLabel(criterion)}</Tag><Caret /></summary>
          <div className="ra-row-body ra-stack">
            <div className="ra-facts"><Fact label="Score calculation" value={criterionCalculation(criterion)} />
              <Fact label="Coverage calculation" value={coverageCalculation(criterion)} /></div>
            {(criterion.checks || []).map((check) => <CheckRow key={check.check_id} report={report} check={check} />)}
          </div>
        </details>)}</div>
      </details>}
      {snapshot.length > 0 && <details className="ra-row ra-group"><summary className="ra-row-summary"><strong>Saved finding status</strong><Tag>{snapshot.length}</Tag><Caret /></summary>
        <div className="ra-row-body ra-stack">{snapshot.map((finding) => <SavedFinding key={finding.finding_id} finding={finding} />)}</div>
      </details>}
      {report?.issues?.length > 0 && <details className="ra-row ra-group"><summary className="ra-row-summary"><strong>Saved priority findings</strong><Tag>{report.issues.length}</Tag><Caret /></summary>
        <div className="ra-row-body ra-stack">{report.issues.map((issue) => <FindingRow key={issue.issue_id} issue={issue} report={report} checks={[]} />)}</div>
      </details>}
    </div>}
  </details>;
}

function SavedFinding({ finding }) {
  const evidence = evidenceEntries({ label: 'Resolution evidence', evidence: finding.resolution_evidence }, ...evidenceGroups(finding));
  return <div className="ra-saved-finding">
    <div><strong>{finding.original_issue || 'Saved finding'}</strong> <Tag>{finding.status}</Tag></div>
    {finding.first_detected_version != null && <small>First detected in v{finding.first_detected_version}
      {finding.resolved_in_version != null && ` · Resolved in v${finding.resolved_in_version}`}</small>}
    <EvidenceList entries={evidence} />
  </div>;
}

function FinalDecision({ submissionId, recommendation, notify, disabled }) {
  const [feedback, setFeedback] = useState('');
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [, setLocation] = useLocation();
  const actions = [
    ['accept', 'Accept', 'ACCEPT', 'btn-primary', Check, 'Accepted'],
    ['review', 'Request revision', 'REVISE', '', RefreshCw, 'Revision requested'],
    ['reject', 'Reject', 'REJECT', 'btn-danger', X, 'Rejected'],
  ];

  async function decide(action, result) {
    setSaving(true);
    setError('');
    try {
      await mockService.decideSubmission(submissionId, action, feedback, justification);
      notify(`Decision recorded: ${result}.`);
      setLocation('/reviewer/reviews');
    } catch (failure) {
      setError(failure.message || 'Decision could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  return <details className="ra-row ra-group ra-final-decision">
    <summary className="ra-row-summary"><ClipboardCheck size={18} aria-hidden="true" /><strong>Record final Reviewer decision</strong><Caret /></summary>
    <div className="ra-row-body">
      {error && <Notice alert title="Could not save decision" detail={error} />}
      <label className="label" htmlFor="analyzer-final-feedback">Reviewer feedback</label>
      <textarea id="analyzer-final-feedback" className="textarea" value={feedback} onChange={(event) => setFeedback(event.target.value)}
        placeholder="Required for revision or rejection." />
      {recommendation && <><label className="label" htmlFor="analyzer-final-justification">Justification for overriding the recommendation</label>
        <textarea id="analyzer-final-justification" className="textarea" value={justification} onChange={(event) => setJustification(event.target.value)} /></>}
      <div className="ra-actions">{actions.map(([action, label, matches, style, Icon, result]) => <button key={action} className={`btn ${style}`}
        disabled={disabled || saving || (action !== 'accept' && !feedback.trim()) || Boolean(recommendation && recommendation !== matches && !justification.trim())}
        onClick={() => void decide(action, result)}><Icon size={15} aria-hidden="true" /> {label}</button>)}</div>
    </div>
  </details>;
}
