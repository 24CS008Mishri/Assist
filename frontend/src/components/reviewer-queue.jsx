import { useEffect, useState } from 'react';
import { Link } from 'wouter';
import { ArrowUpRight, BarChart3, CheckCircle2, ChevronDown, CircleAlert, Eye, FileText, History, Inbox, RefreshCw, X } from 'lucide-react';
import { mockService } from '@/lib/mock-services';
import './reviewer-queue.css';

const actions = [
  { value: 'accept', recommendation: 'ACCEPT', label: 'Accept', result: 'Accepted', icon: CheckCircle2, style: 'btn-primary' },
  { value: 'review', recommendation: 'REVISE', label: 'Request revision', result: 'Revision Required', icon: RefreshCw, style: '' },
  { value: 'reject', recommendation: 'REJECT', label: 'Reject', result: 'Rejected', icon: X, style: 'btn-danger' },
];

export default function ReviewQueue({ notify, formatDate }) {
  const [queue, setQueue] = useState(null);
  const [selectedId, setSelectedId] = useState('');
  const [refreshing, setRefreshing] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);

  async function load() {
    setRefreshing(true);
    setError('');
    try {
      const rows = await mockService.getPendingSubmissions();
      setQueue(rows);
      setSelectedId((current) => rows.some((row) => row.submission_id === current) ? current : rows[0]?.submission_id || '');
      setRevision((current) => current + 1);
    } catch (failure) {
      setError(failure.message || 'Could not load the reviewer queue.');
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => { void load(); }, []);
  const selected = queue?.find((item) => item.submission_id === selectedId);

  return <div className="content reviewer-queue">
    <header className="rq-page-header">
      <div><p className="eyebrow">Reviewer / Expert</p><h1 className="page-title">Pending reviews</h1></div>
      <button type="button" className="btn" disabled={refreshing} onClick={() => void load()}>
        <RefreshCw size={15} aria-hidden="true" /> {refreshing ? 'Refreshing…' : 'Refresh queue'}
      </button>
    </header>
    {error && <QueueNotice error>{error}</QueueNotice>}
    {!queue && refreshing && <QueueNotice>Loading pending submissions…</QueueNotice>}
    {queue?.length === 0 && <QueueNotice icon={Inbox}>No pending submissions</QueueNotice>}
    {queue?.length > 0 && <div className="rq-layout">
      <section className="rq-panel rq-list" aria-labelledby="pending-queue-title">
        <div className="rq-panel-heading"><h2 id="pending-queue-title">Pending queue</h2><span className="rq-count">{queue.length}</span></div>
        <ul>{queue.map((item) => <li key={item.submission_id}>
          <button type="button" className="rq-item" aria-pressed={selectedId === item.submission_id} onClick={() => setSelectedId(item.submission_id)}>
            <FileText size={19} aria-hidden="true" />
            <span><strong>{item.curriculum_name}</strong><small>{submissionLabel(item)}</small></span>
            <ChevronDown size={16} aria-hidden="true" />
          </button>
        </li>)}</ul>
      </section>
      {selected && <SubmissionReview key={selectedId} submission={selected} revision={revision} formatDate={formatDate}
        onRecorded={(result) => { notify(`Decision recorded: ${result}.`); void load(); }} />}
    </div>}
  </div>;
}

function submissionLabel(submission) {
  return [submission.institute_name, submission.version != null && `Version ${submission.version}`].filter(Boolean).join(' · ');
}

function QueueNotice({ children, error, icon: Icon = CircleAlert }) {
  return <div className={`rq-notice${error ? ' rq-error' : ''}`} role={error ? 'alert' : 'status'}>
    <Icon size={18} aria-hidden="true" />{children}
  </div>;
}

function SubmissionReview({ submission, revision, formatDate, onRecorded }) {
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [retry, setRetry] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);
  const [decisionError, setDecisionError] = useState('');
  const [documentRequested, setDocumentRequested] = useState(false);
  const [documentUrl, setDocumentUrl] = useState('');
  const [documentError, setDocumentError] = useState('');
  const submissionId = submission.submission_id;

  useEffect(() => {
    let active = true;
    setDetail(null);
    setDetailError('');
    mockService.getSubmission(submissionId).then((result) => {
      if (active) setDetail(result);
    }).catch((failure) => {
      if (active) setDetailError(failure.message || 'Could not load this submission.');
    });
    return () => { active = false; };
  }, [submissionId, revision, retry]);

  useEffect(() => {
    if (!documentRequested) return;
    let active = true;
    let url;
    mockService.getSubmissionDocument(submissionId).then((result) => {
      if (!active) {
        URL.revokeObjectURL(result);
        return;
      }
      url = result;
      setDocumentUrl(url);
    }).catch((failure) => {
      if (!active) return;
      setDocumentError(failure.message || 'Could not load the submitted PDF.');
      setDocumentRequested(false);
    });
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentRequested, submissionId]);

  const report = detail?.analyses?.[0]?.report;
  const recommendation = report?.decision_support?.decision;
  const analyzerHref = `/reviewer/analyzer?submission_id=${encodeURIComponent(submissionId)}`;

  async function decide(action) {
    setSaving(true);
    setDecisionError('');
    try {
      await mockService.decideSubmission(submissionId, action.value, feedback, justification);
      setFeedback('');
      setJustification('');
      setDetail(null);
      onRecorded(action.result);
    } catch (failure) {
      setDecisionError(failure.message || 'Decision could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  return <section className="rq-panel rq-compliance" aria-labelledby="reviewer-compliance-title">
    <header className="rq-submission-header">
      <div><h2 className="eyebrow" id="reviewer-compliance-title">Reviewer Compliance</h2>
        <h3>{submission.curriculum_name}</h3><p>{submissionLabel(submission)} · {formatDate(submission.submitted_at)}</p></div>
      <span className="rq-status">{submission.status}</span>
    </header>
    <div className="rq-content">
      <div className="rq-resources">
        <div className="rq-resource">
          <FileText size={20} aria-hidden="true" />
          <div><h4>Submitted PDF</h4><p>{detail?.document_filename || submission.document_filename || submission.curriculum_name}</p></div>
          {documentUrl ? <a className="btn" href={documentUrl} target="_blank" rel="noreferrer">Open PDF <ArrowUpRight size={14} aria-hidden="true" /></a>
            : <button type="button" className="btn" disabled={documentRequested} onClick={() => { setDocumentError(''); setDocumentRequested(true); }}>
              <Eye size={15} aria-hidden="true" /> {documentRequested ? 'Loading PDF…' : 'Load PDF'}
            </button>}
          {documentError && <QueueNotice error>{documentError}</QueueNotice>}
        </div>
        <div className="rq-resource">
          <BarChart3 size={20} aria-hidden="true" />
          <div><h4>Curriculum Analyzer</h4><p>{report ? 'Analysis saved' : detail ? 'Analysis required for acceptance' : 'Review scores and evidence'}</p></div>
          <Link className="btn btn-primary" href={analyzerHref}>Analyze submission <ArrowUpRight size={14} aria-hidden="true" /></Link>
        </div>
      </div>
      {detailError && <><QueueNotice error>{detailError}</QueueNotice><button className="btn" type="button" onClick={() => setRetry((current) => current + 1)}>Retry submission details</button></>}
      {!detail && !detailError && <QueueNotice>Loading submission details…</QueueNotice>}
      {detail && <>
        <details className="rq-history"><summary><History size={16} aria-hidden="true" /> Submission details and earlier versions <ChevronDown size={16} aria-hidden="true" /></summary>
          <div className="rq-history-content">
            <dl><div><dt>Submission ID</dt><dd>{submissionId}</dd></div><div><dt>Curriculum ID</dt><dd>{detail.curriculum_id}</dd></div></dl>
            {detail.previous_versions?.length > 0 && <ul>{detail.previous_versions.map((version) => {
              const score = version.analyses?.[0]?.report?.overall_score;
              return <li key={version.submission_id}><strong>Version {version.version}</strong><span>{version.status} · {formatDate(version.submitted_at)}</span>{score != null && <span>Analyzer score {score}%</span>}</li>;
            })}</ul>}
          </div>
        </details>
        <section className="rq-decision" aria-labelledby="record-review-title">
          <h4 id="record-review-title">Record your review</h4>
          {decisionError && <QueueNotice error>{decisionError}</QueueNotice>}
          <label className="label" htmlFor="review-queue-feedback">Feedback for the institute and designer</label>
          <textarea id="review-queue-feedback" className="textarea" value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Required for revision or rejection." />
          {recommendation && <><label className="label" htmlFor="review-queue-justification">Justification when overriding the saved recommendation</label>
            <textarea id="review-queue-justification" className="textarea" value={justification} onChange={(event) => setJustification(event.target.value)} /></>}
          <div className="rq-actions">{actions.map((action) => <button type="button" key={action.value} className={`btn ${action.style}`}
            disabled={saving || (action.value === 'accept' ? !report : !feedback.trim()) || Boolean(recommendation && recommendation !== action.recommendation && !justification.trim())}
            onClick={() => void decide(action)}><action.icon size={15} aria-hidden="true" /> {action.label}</button>)}</div>
          {saving && <p role="status">Saving review…</p>}
        </section>
      </>}
    </div>
  </section>;
}
