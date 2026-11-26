﻿import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { Link, Router as WouterRouter, useLocation } from 'wouter';
import LiveCurriculumAssistant from '@/components/live-curriculum-assistant';
import { logoutVerifiedDesigner } from '@/lib/live-assistant-api';
import { Activity, ArrowLeft, ArrowRight, BarChart3, Bell, BookMarked, BookOpen, Bot, Building2, Check, CheckCircle, CheckCircle2, ChevronDown, ChevronRight, CircleAlert, ClipboardCheck, Clock3, ExternalLink, Eye, FileCheck2, FileText, Filter, FolderKanban, GraduationCap, History, Inbox, Landmark, LayoutDashboard, Lightbulb, ListChecks, LockKeyhole, LogOut, Menu, MessageSquareText, Network, Pencil, Plus, RefreshCw, Save, Search, Send, Settings, ShieldCheck, SlidersHorizontal, Sparkles, Trash2, Upload, UserCog, Users, Video, X } from 'lucide-react';
import { mockService } from '@/lib/mock-services';
import { analyzerDocumentKey, submittedCurriculumDocuments } from '@/lib/analyzer-utils';
import ReviewerAnalyzerPage from '@/components/reviewer-analyzer';
const roles = {
    admin: { label: 'AICTE Admin', short: 'Admin', base: '/admin/dashboard', description: 'Authoritative governance and national oversight', icon: Landmark },
    reviewer: { label: 'Reviewer / Expert', short: 'Reviewer', base: '/reviewer/dashboard', description: 'Human review, evidence and final decisions', icon: ClipboardCheck },
    designer: { label: 'Curriculum Designer', short: 'Designer', base: '/designer/dashboard', description: 'Build, analyze and submit curriculum truth', icon: GraduationCap },
    institute: { label: 'Institute Representative', short: 'Institute', base: '/institute/dashboard', description: 'Published curricula, coordinators and feedback', icon: Building2 },
};
const permissions = {
    admin: ['documents.read', 'documents.create', 'documents.update', 'documents.delete', 'policies.read', 'policies.create', 'policies.update', 'institutes.read', 'institutes.create', 'users.manage', 'audit.read', 'curricula.read'],
    reviewer: ['curricula.read', 'reviews.read', 'reviews.decide', 'published.read', 'policies.read', 'policies.manage', 'analyzer.use'],
    designer: ['curricula.read', 'curricula.create', 'curricula.update', 'curricula.submit', 'ai.use', 'resources.use', 'comparison.use', 'changes.respond', 'published.read'],
    institute: ['published.read', 'courses.read', 'coordinator.assign', 'changes.create', 'feedback.create'],
};
const navByRole = {
    admin: [
        { label: 'Dashboard', href: '/admin/dashboard', icon: LayoutDashboard }, { label: 'Upload Document (PDF)', href: '/admin/documents', icon: Upload, permission: 'documents.read' },
        { label: 'Policies', href: '/admin/policies', icon: ShieldCheck, permission: 'policies.read' }, { label: 'Approved Institutes', href: '/admin/institutes', icon: Building2, permission: 'institutes.read' },
        { label: 'Curricula', href: '/admin/curricula', icon: BookOpen }, { label: 'Reviews', href: '/admin/reviews', icon: ClipboardCheck },
        { label: 'Users', href: '/admin/users', icon: Users, permission: 'users.manage' }, { label: 'Audit Logs', href: '/admin/audit-logs', icon: History, permission: 'audit.read' },
        { label: 'Settings', href: '/admin/settings', icon: Settings },
    ],
    reviewer: [
        { label: 'Dashboard', href: '/reviewer/dashboard', icon: LayoutDashboard }, { label: 'Pending Reviews', href: '/reviewer/reviews', icon: Inbox, permission: 'reviews.read' },
        { label: 'Curriculum Analyzer', href: '/reviewer/analyzer', icon: BarChart3, permission: 'analyzer.use' }, { label: 'Review History', href: '/reviewer/history', icon: History },
        { label: 'Change Requests', href: '/reviewer/changes', icon: RefreshCw },
        { label: 'Policies', href: '/reviewer/policies', icon: ShieldCheck, permission: 'policies.read' }, { label: 'Approved Curricula', href: '/reviewer/approved', icon: CheckCircle2, permission: 'published.read' },
        { label: 'Settings', href: '/reviewer/settings', icon: Settings },
    ],
    designer: [
        { label: 'Dashboard', href: '/designer/dashboard', icon: LayoutDashboard }, { label: 'My Curricula', href: '/designer/curricula', icon: FolderKanban },
        { label: 'Create Curriculum', href: '/designer/create', icon: Plus, permission: 'curricula.create' }, { label: 'AI Assistant', href: '/designer/assistant', icon: Bot, permission: 'ai.use' }, { label: 'Vaani', href: '/designer/virtual-assistant', icon: Video, permission: 'ai.use' },
        { label: 'Resource Assistant', href: '/designer/resources', icon: BookMarked, permission: 'resources.use' }, { label: 'Curriculum Comparison', href: '/designer/comparison', icon: Network, permission: 'comparison.use' },
        { label: 'Change Requests', href: '/designer/changes', icon: RefreshCw },
        { label: 'Improvement Tracker', href: '/designer/improvements', icon: Activity, permission: 'curricula.update' },
        { label: 'Published Curricula', href: '/designer/published', icon: CheckCircle2, permission: 'published.read' },
        { label: 'Settings', href: '/designer/settings', icon: Settings },
    ],
    institute: [
        { label: 'Dashboard', href: '/institute/dashboard', icon: LayoutDashboard }, { label: 'Portal Upload', href: '/institute/submit', icon: Upload }, { label: 'Available Curricula', href: '/institute/curricula', icon: BookOpen, permission: 'published.read' },
        { label: 'My Courses', href: '/institute/courses', icon: ListChecks, permission: 'courses.read' }, { label: 'Course Coordinators', href: '/institute/coordinators', icon: UserCog, permission: 'coordinator.assign' },
        { label: 'Change Requests', href: '/institute/changes', icon: RefreshCw, permission: 'changes.create' }, { label: 'Feedback', href: '/institute/feedback', icon: MessageSquareText, permission: 'feedback.create' },
        { label: 'Settings', href: '/institute/settings', icon: Settings },
    ],
};
function can(role, permission) {
    return !permission || permissions[role].includes(permission);
}
function roleFromPath(path) {
    if (path.startsWith('/admin/'))
        return 'admin';
    if (path.startsWith('/reviewer/'))
        return 'reviewer';
    if (path.startsWith('/designer/'))
        return 'designer';
    if (path.startsWith('/institute/'))
        return 'institute';
    return null;
}
function initials(name) { return name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase(); }
function App() {
    return <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Portal /></WouterRouter>;
}
function Portal() {
    const [location, setLocation] = useLocation();
    const [session, setSession] = useState(() => {
        const saved = localStorage.getItem('aicte-demo-session');
        return saved ? JSON.parse(saved) : null;
    });
    const [toast, setToast] = useState('');
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };
    const login = async (email, password) => {
        // The account recordâ€”not a client-selected roleâ€”determines the workspace.
        const next = await mockService.login(email, password);
        localStorage.setItem('aicte-demo-session', JSON.stringify(next));
        flushSync(() => setSession(next));
        setSidebarOpen(false);
        setLocation(roles[next.role].base);
    };
    const logout = async () => {
        try {
            if (session?.verified) await logoutVerifiedDesigner();
        } catch (failure) {
            notify(failure.message);
            return;
        }
        localStorage.removeItem('aicte-demo-session');
        setSession(null);
        setLocation('/login');
    };
    if (location === '/login' || location === '/signup' || location === '/forgot-password' || location === '/reset-password') {
        return <AuthPage mode={location.slice(1)} onLogin={login} />;
    }
    if (location === '/403')
        return <Unauthorized />;
    const expectedRole = roleFromPath(location);
    if (expectedRole && !session) {
        setLocation('/login');
        return null;
    }
    if (expectedRole && session && expectedRole !== session.role) {
        setLocation('/403');
        return null;
    }
    if (!expectedRole) {
        if (session)
            setLocation(roles[session.role].base);
        else
            setLocation('/login');
        return null;
    }
    return <AppShell session={session} role={expectedRole} path={location} open={sidebarOpen} setOpen={setSidebarOpen} onLogout={logout} notify={notify} toast={toast} />;
}
function AuthPage({ mode, onLogin }) {
    const [, setLocation] = useLocation();
    const [show, setShow] = useState(false);
    const [authError, setAuthError] = useState('');
    const [authLoading, setAuthLoading] = useState(false);
    const title = 'Curriculum truth, with a human in the loop.';
    const handleLogin = async event => {
        event.preventDefault();
        if (authLoading) return;
        const form = event.currentTarget;
        const email = form.elements.namedItem('email').value;
        const password = form.elements.namedItem('password').value;
        setAuthError(''); setAuthLoading(true);
        try { await onLogin(email, password); }
        catch (error) {
            setAuthError(error.status === 401 ? 'Incorrect email address or password.' : 'Sign-in is temporarily unavailable. Please try again.');
            setAuthLoading(false);
        }
    };
    if (mode !== 'login') return <div className="auth-wrap grain"><div className="surface" style={{ maxWidth: 520, padding: 36, textAlign: 'center' }}><div className="brand-mark" style={{ margin: '0 auto 18px' }}><LockKeyhole size={20} /></div><p className="eyebrow">Account support</p><h1 className="page-title" style={{ margin: '8px 0 12px' }}>{mode === 'signup' ? 'Request an account' : 'Password help'}</h1><p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>{mode === 'signup' ? 'Accounts are provisioned by an Admin. Ask your organization?s administrator to create and link your account.' : 'Online password recovery is not configured. Contact your organization?s administrator for help.'}</p><button className="btn btn-primary" style={{ marginTop: 22 }} onClick={() => setLocation('/login')} data-testid="button-auth-continue">Back to sign in</button></div></div>;
    return <div className="auth-wrap grain"><div className="auth-panel">
        <section className="auth-visual"><div><div style={{ display: 'flex', alignItems: 'center', gap: 11 }}><div className="brand-mark"><Landmark size={19} /></div><strong className="font-display">AICTE GOV</strong></div><div style={{ marginTop: 86 }}><p className="eyebrow" style={{ color: '#e7daf4' }}>National academic governance</p><h1 style={{ font: '700 42px/1.03 var(--app-font-display)', letterSpacing: '-.055em', margin: '12px 0 16px' }}>Easier way to manage curriculum.</h1><p style={{ color: 'rgba(255,255,255,.7)', maxWidth: 310, lineHeight: 1.7, fontSize: 13 }}>Authoritative sources. Visible evidence. Expert decisions. One shared record of curriculum truth.</p></div></div><div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'rgba(255,255,255,.68)', fontSize: 11 }}><ShieldCheck size={16} /> AI assistance never replaces human approval.</div></section>
        <section className="auth-form"><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 25 }}><div><p className="eyebrow">Sign in</p><h2 className="font-display" style={{ fontSize: 25, margin: '7px 0 0', letterSpacing: '-.035em' }}>{title}</h2></div><div className="brand-mark" style={{ background: '#f2eafa' }}><LockKeyhole size={19} /></div></div>
            <form onSubmit={handleLogin}><label className="label" htmlFor="login-email">Email address</label><input id="login-email" className="field" name="email" type="email" autoComplete="email" placeholder="name@organization.edu" required data-testid="input-login-email" /><label className="label" htmlFor="login-password" style={{ marginTop: 14 }}>Password</label><div style={{ position: 'relative' }}><input id="login-password" className="field" name="password" type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" required style={{ paddingRight: 44 }} data-testid="input-login-password" /><button type="button" className="btn btn-ghost icon-btn" aria-label={show ? 'Hide password' : 'Show password'} style={{ position: 'absolute', right: 2, top: 2, boxShadow: 'none' }} onClick={() => setShow(!show)} data-testid="button-show-password"><Eye size={16} /></button></div>{authError && <p className="auth-error" role="alert">{authError}</p>}<div style={{ display: 'flex', justifyContent: 'flex-end', margin: '12px 0 17px', fontSize: 11 }}><button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={() => setLocation('/forgot-password')} data-testid="link-forgot-password">Password help</button></div><p className="muted" style={{ fontSize: 11, lineHeight: 1.5 }}>Your account role determines the workspace you can access.</p><button className="btn btn-primary" style={{ width: '100%', marginTop: 20, minHeight: 44 }} disabled={authLoading} data-testid="button-login">{authLoading ? 'Signing in?' : 'Sign in'} <ArrowRight size={16} /></button><p className="muted" style={{ textAlign: 'center', fontSize: 11, marginTop: 18 }}>Need access? <button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={() => setLocation('/signup')} data-testid="link-signup">Request an account</button></p></form>
        </section>
    </div></div>;
}
function Unauthorized() {
    const [, setLocation] = useLocation();
    return <div className="auth-wrap grain"><div className="surface" style={{ maxWidth: 510, padding: 42, textAlign: 'center' }}><div className="brand-mark" style={{ margin: '0 auto 18px', background: '#f6d9d8', color: '#8e3c39' }}><CircleAlert size={22} /></div><p className="eyebrow">Access boundary</p><h1 className="page-title" style={{ margin: '8px 0 12px' }}>This workspace is not assigned to you.</h1><p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>Your account can only access the workspace assigned to its role. Return to sign in to use another account.</p><button className="btn btn-primary" style={{ marginTop: 22 }} onClick={() => setLocation('/login')} data-testid="button-unauthorized-login"><ArrowLeft size={15} /> Return to sign in</button></div></div>;
}
function AppShell({ session, role, path, open, setOpen, onLogout, notify, toast }) {
    const [menu, setMenu] = useState(false);
    const [, setLocation] = useLocation();
    const links = navByRole[role].filter((item) => can(role, item.permission));
    const primaryLinks = links.filter((item) => item.label !== 'Settings');
    const settingsLink = links.find((item) => item.label === 'Settings');
    const current = links.find((item) => path === item.href) ?? links.find((item) => path.startsWith(item.href)) ?? links[0];
    return <div className="app-shell grain"><aside className={`sidebar ${open ? 'open' : ''}`}><div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '0 10px 27px', minWidth: 0 }}><div className="brand-mark"><Landmark size={18} /></div><div style={{ minWidth: 0 }}><strong className="font-display" style={{ fontSize: 14 }}>AICTE</strong><div style={{ color: 'rgba(255,255,255,.5)', fontSize: 9, marginTop: 2 }}>GOVERNANCE PORTAL</div></div><button className="btn btn-ghost icon-btn" style={{ marginLeft: 'auto', color: '#fff', display: 'none' }} onClick={() => setOpen(false)}><X size={17} /></button></div><div className="sidebar-scroll">{primaryLinks.map((item) => <Link href={item.href} key={item.href} className={`nav-link ${current?.href === item.href ? 'active' : ''}`} onClick={() => setOpen(false)} data-testid={`link-nav-${item.label.toLowerCase().replaceAll(' ', '-')}`}><item.icon size={16} strokeWidth={1.8} /><span>{item.label}</span></Link>)}</div><div className="sidebar-footer"><div style={{ padding: '10px 13px', color: 'rgba(255,255,255,.6)', fontSize: 10, lineHeight: 1.5 }}>DEMO MODE<br /><span style={{ color: '#e7d6f7' }}>Local governance state</span></div>{settingsLink && <Link href={settingsLink.href} className={`nav-link ${current?.href === settingsLink.href ? 'active' : ''}`} onClick={() => setOpen(false)} data-testid="link-nav-settings"><Settings size={16} /><span>Settings</span></Link>}<button className="nav-link" onClick={onLogout} data-testid="button-logout"><LogOut size={16} /><span>Sign out</span></button></div></aside>{open && <button className="drawer-backdrop" onClick={() => setOpen(false)} aria-label="Close navigation" />}<main className="main-area"><header className="topbar"><div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><button className="btn icon-btn mobile-menu" onClick={() => setOpen(true)} data-testid="button-open-navigation"><Menu size={18} /></button><div className="breadcrumb muted" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}><span>Workspace</span><ChevronRight size={13} /><strong style={{ color: 'hsl(var(--foreground))' }}>{current?.label}</strong></div></div><div className="topbar-actions"><button className="btn icon-btn notification-button" onClick={() => setLocation(`${roles[role].base}/notifications`)} aria-label="Open notifications" data-testid="button-header-notifications"><Bell size={17} /></button><div style={{ position: 'relative' }}><button className="btn" style={{ padding: '4px 9px 4px 5px', gap: 8 }} onClick={() => setMenu(!menu)} data-testid="button-user-menu"><span className="brand-mark" style={{ width: 29, height: 29, borderRadius: 10, fontSize: 10, fontWeight: 700 }}>{initials(session.name)}</span><span style={{ textAlign: 'left', display: 'block' }}><strong style={{ display: 'block', fontSize: 11 }}>{session.name}</strong><small className="muted" style={{ fontSize: 9 }}>{roles[role].short}</small></span><ChevronDown size={14} /></button>{menu && <div className="surface" style={{ position: 'absolute', right: 0, top: 48, width: 230, padding: 10, zIndex: 40 }}><p className="eyebrow" style={{ padding: '4px 8px 8px' }}>Signed in workspace</p><div style={{ padding: '2px 8px 10px', fontSize: 12 }}><strong>{roles[role].label}</strong><span className="muted" style={{ display: 'block', fontSize: 10, marginTop: 3 }}>Role is assigned to your account.</span></div><button className="btn btn-ghost btn-danger" style={{ width: '100%', justifyContent: 'flex-start', marginTop: 4 }} onClick={onLogout} data-testid="button-menu-logout"><LogOut size={14} /> Sign out</button></div>}</div></div></header><PageContent role={role} path={path} notify={notify} /></main>{toast && <div className="toast-note" data-testid="status-toast"><CheckCircle size={15} style={{ verticalAlign: 'middle', marginRight: 7 }} />{toast}</div>}</div>;
}
function PageContent({ role, path, notify }) {
    if (path.endsWith('/dashboard'))
        return <Dashboard role={role} notify={notify} />;
    if (path === '/admin/documents')
        return <AdminDocuments notify={notify} />;
    if (path === '/admin/policies')
        return <PolicyManagement notify={notify} audience="admin" />;
    if (path === '/admin/institutes')
        return <AdminInstitutes notify={notify} />;
    if (path === '/admin/curricula')
        return <AdminCurricula notify={notify} />;
    if (path === '/admin/reviews')
        return <AdminReviews notify={notify} />;
    if (path === '/admin/users')
        return <AdminUsers notify={notify} />;
    if (path === '/admin/audit-logs')
        return <AuditLogs />;
    if (path.endsWith('/notifications'))
        return <Notifications notify={notify} />;
    if (path.endsWith('/settings'))
        return <SettingsPage notify={notify} />;
    if (path === '/reviewer/reviews')
        return <ReviewQueue notify={notify} />;
    if (path === '/reviewer/analyzer')
        return <ReviewerAnalyzerPage notify={notify} formatDate={formatDocumentDate} />;
    if (path === '/reviewer/policies')
        return <PolicyManagement notify={notify} audience="reviewer" />;
    if (path === '/reviewer/history' || path === '/reviewer/approved')
        return <ReviewSupportingPage path={path} />;
    if (path === '/reviewer/changes')
        return <DesignerChanges notify={notify} reviewer />;
    if (path === '/designer/curricula')
        return <DesignerCurricula notify={notify} />;
    if (path === '/designer/create')
        return <CreateWizard notify={notify} />;
    if (path === '/designer/virtual-assistant')
        return <LiveCurriculumAssistant />;
    if (path === '/designer/assistant')
        return <RagAssistantPage notify={notify} />;
    if (path === '/designer/resources')
        return <ResourcePage />;
    if (path === '/designer/comparison')
        return <ComparisonPage />;
    if (path.startsWith('/designer/analyzer'))
        return <Unauthorized />;
    if (path === '/reviewer/screener')
        return <Unauthorized />;
    if (path === '/designer/changes')
        return <DesignerChanges notify={notify} />;
    if (path === '/designer/improvements')
        return <ImprovementTracker notify={notify} />;
    if (path === '/designer/published')
        return <PublishedPage />;
    if (path === '/institute/curricula')
        return <InstituteCurricula />;
    if (path === '/institute/submit')
        return <InstituteSubmissionPortal notify={notify} />;
    if (path === '/institute/courses')
        return <InstituteCourses />;
    if (path === '/institute/coordinators')
        return <Coordinators notify={notify} />;
    if (path === '/institute/changes')
        return <ChangeRequests notify={notify} />;
    if (path === '/institute/feedback')
        return <Feedback notify={notify} />;
    return <Dashboard role={role} notify={notify} />;
}
function PageHeader({ eyebrow, title, detail, action }) {
    return <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 15, margin: '7px 0 25px' }}><div><p className="eyebrow">{eyebrow}</p><h1 className="page-title" style={{ margin: '7px 0 7px' }}>{title}</h1>{detail && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{detail}</p>}</div>{action}</div>;
}
function StatCard({ label, value, note, icon: Icon, tone = 'lavender' }) {
    return <div className="surface stat-card" data-testid={`stat-${label.toLowerCase().replaceAll(' ', '-')}`}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}><span className="eyebrow" style={{ letterSpacing: '.08em' }}>{label}</span><span className={`badge badge-${tone}`}><Icon size={14} /></span></div><div className="stat-value" style={{ marginTop: 16 }}>{value}</div><p className="muted" style={{ fontSize: 10, margin: '8px 0 0' }}>{note}</p></div>;
}
function SectionCard({ title, action, children, className = '' }) {
    return <section className={`surface ${className}`} style={{ padding: 20 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}><h2 className="font-display" style={{ fontSize: 15, margin: 0, letterSpacing: '-.02em' }}>{title}</h2>{action}</div>{children}</section>;
}
function StatusBadge({ status }) {
    const tone = status.includes('Approved') || status.includes('Published') || status === 'Active' || status === 'Accepted' ? 'green' : status.includes('Reject') || status.includes('Archived') ? 'red' : status.includes('Review') || status.includes('Submitted') || status.includes('Screening') || status.includes('Requested') || status === 'Pending' ? 'amber' : 'lavender';
    return <span className={`badge badge-${tone}`} data-testid={`status-${status.toLowerCase().replaceAll(' ', '-')}`}>{status}</span>;
}
function MiniBar({ value }) { return <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div className="progress" style={{ flex: 1 }}><span style={{ width: `${value}%` }} /></div><strong style={{ fontSize: 11, minWidth: 30 }}>{value}%</strong></div>; }
function Dashboard({ role, notify }) {
    const [stats, setStats] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try {
            let next = [];
            if (role === 'admin') {
                const [documents, institutions, users, submissions] = await Promise.all([
                    mockService.getDocuments(), mockService.getInstitutions(), mockService.getAdminUsers(), mockService.getAdminSubmissions(),
                ]);
                next = [
                    ['AICTE Documents', documents.length, 'Stored reference PDFs', FileText],
                    ['Institutions', institutions.length, 'Registered institutions', Building2],
                    ['User Accounts', users.length, 'Assigned workspace identities', Users],
                    ['Pending Reviews', submissions.filter(row => row.status === 'Pending').length, 'In the shared Reviewer Queue', ClipboardCheck],
                ];
            } else if (role === 'reviewer') {
                const [queue, history] = await Promise.all([mockService.getPendingSubmissions(), mockService.getReviewHistory()]);
                next = [
                    ['Pending Reviews', queue.length, 'Awaiting Reviewer action', Inbox],
                    ['Accepted', history.filter(row => row.status === 'Accepted').length, 'Recorded decisions', CheckCircle2],
                    ['Revision Required', history.filter(row => row.status === 'Revision Required').length, 'Returned for correction', RefreshCw],
                    ['Rejected', history.filter(row => row.status === 'Rejected').length, 'Preserved decision records', CircleAlert],
                ];
            } else if (role === 'designer') {
                const [documents, submissions, improvements, requests] = await Promise.all([
                    mockService.getDocuments(), mockService.getMySubmissions(), mockService.getImprovementHistory(), mockService.getChangeRequests(),
                ]);
                const activeFindings = improvements.reduce((sum, row) => sum + (row.latest_findings?.length || 0), 0);
                next = [
                    ['Uploaded Curricula', documents.length, 'Your indexed Designer PDFs', FolderKanban],
                    ['Pending Review', submissions.filter(row => row.status === 'Pending').length, 'Officially submitted versions', ClipboardCheck],
                    ['Outstanding Findings', activeFindings, 'From saved Analyzer reports', Lightbulb],
                    ['Open Change Requests', requests.filter(row => ['Pending Designer Action', 'In Progress', 'Reopened'].includes(row.status)).length, 'Reviewer feedback to address', RefreshCw],
                ];
            } else {
                const [prepared, submissions] = await Promise.all([mockService.getWorkflowCurricula(), mockService.getMySubmissions()]);
                next = [
                    ['Ready to Submit', prepared.length, 'Designer PDFs linked to this institution', Upload],
                    ['Submitted Versions', submissions.length, 'Stored submission history', BookOpen],
                    ['Pending Review', submissions.filter(row => row.status === 'Pending').length, 'In the shared Reviewer Queue', ClipboardCheck],
                    ['Revision Required', submissions.filter(row => row.status === 'Revision Required').length, 'Reviewer feedback available', RefreshCw],
                ];
            }
            setStats(next);
        } catch (e) { setError(e.message || 'Unable to load workspace summary.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, [role]);
    const config = {
        admin: { title: 'Governance overview', detail: 'Current records across documents, institutions, accounts, and submissions.' },
        reviewer: { title: 'Review desk', detail: 'Your shared queue of submitted curriculum versions and completed decisions.' },
        designer: { title: 'Design studio', detail: 'Your submitted curricula, analysis findings, and reviewer requests.' },
        institute: { title: 'Institute workspace', detail: 'Curricula and review activity linked to your institution.' },
    }[role];
    return <div className="content"><PageHeader eyebrow={roles[role].label} title={config.title} detail={config.detail} action={<button className="btn" onClick={() => void load()} disabled={loading} data-testid="button-refresh-dashboard"><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        <div className="stat-grid">{(loading && !stats.length ? [['Loading workspace', '?', 'Fetching current records', RefreshCw]] : stats).map(([label, value, note, Icon]) => <StatCard key={label} label={label} value={value} note={note} icon={Icon} />)}</div>
        <DashboardActions role={role} />
        <div style={{ display: 'grid', gridTemplateColumns: '1.25fr .75fr', gap: 16, marginTop: 17 }}>
            <SectionCard title={role === 'reviewer' ? 'Review queue' : role === 'designer' ? 'Curriculum movement' : role === 'institute' ? 'Recent submissions' : 'Recent governance activity'}><ActivityList role={role} /></SectionCard>
            <SectionCard title="Workflow status"><p className="muted" style={{ fontSize: 12 }}>{loading ? 'Updating from current workflow records.' : error ? 'Refresh to retry loading current records.' : 'Counts above reflect records available to your account.'}</p></SectionCard>
        </div>
        <div style={{ marginTop: 16 }}><SectionCard title="Curriculum register">{role === 'reviewer' ? <ReviewerDashboardQueue /> : <RecentWorkflowRecords role={role} />}</SectionCard></div>
    </div>;
}
function DashboardActions({ role }) {
    const [, setLocation] = useLocation();
    const actions = {
        admin: [
            ['Upload Document', 'Add an authoritative AICTE source to the governance registry.', Upload, '/admin/documents'],
            ['Approved Institutes', 'Review the institutes that can receive published curricula.', Building2, '/admin/institutes'],
        ],
        reviewer: [
            ['Manage Policies', 'Update, retire or remove the rules used during expert review.', ShieldCheck, '/reviewer/policies'],
            ['Open Review Queue', 'Review submitted curriculum versions and record decisions.', Inbox, '/reviewer/reviews'],
        ],
        designer: [
            ['Upload Curriculum PDF', 'Start the next governed curriculum version from a PDF.', Upload, '/designer/create'],
            ['Ask AI Assistant', 'Get evidence-backed help for outcomes, structure and coverage.', Bot, '/designer/assistant'],
            ['Vaani', 'Start a live curriculum consultation.', Video, '/designer/virtual-assistant'],
            ['Analyze Curriculum', 'Find problems and apply defined solutions before submission.', BarChart3, '/designer/analyzer'],
        ],
        institute: [
            ['Portal Upload', 'Submit a prepared institutional curriculum for Reviewer Compliance.', Upload, '/institute/submit'],
            ['Published Curricula', 'See only the programmes explicitly released to this institute.', BookOpen, '/institute/curricula'],
            ['Course Coordinators', 'Assign one active coordinator to each course and version.', UserCog, '/institute/coordinators'],
            ['Request Curriculum Change', 'Send evidence to the designer for next yearâ€™s version.', RefreshCw, '/institute/changes'],
        ],
    }[role];
    return <div className={`dashboard-actions dashboard-actions-${role}`}>{actions.map(([label, detail, Icon, href]) => <button className="surface dashboard-action" key={label} onClick={() => setLocation(href)} data-testid={`button-dashboard-${label.toLowerCase().replaceAll(' ', '-')}`}><span className="brand-mark"><Icon size={17} /></span><span><strong>{label}</strong><small>{detail}</small></span><ArrowRight size={15} className="action-arrow" /></button>)}</div>;
}
function ActivityList({ role }) {
    const [items, setItems] = useState([]);
    const [error, setError] = useState('');
    useEffect(() => {
        const load = role === 'reviewer' ? mockService.getPendingSubmissions()
            : role === 'admin' ? mockService.getAdminSubmissions()
                : mockService.getMySubmissions();
        load.then(rows => {
            const recent = rows.slice(0, 4).map(row => ({
                title: row.review_history?.length ? `Reviewer decision: ${row.review_history[row.review_history.length - 1].status}` : row.status === 'Pending' ? 'Pending compliance review' : 'Curriculum submission',
                curriculum: `${row.curriculum_name} · v${row.version}`,
                date: formatDocumentDate(row.review_history?.at(-1)?.decided_at || row.submitted_at),
            }));
            setItems(recent);
        }).catch(e => setError(e.message || 'Unable to load recent workflow activity.'));
    }, [role]);
    if (error) return <p className="muted" role="alert">{error}</p>;
    if (!items.length) return <p className="muted" style={{ fontSize: 12 }}>No recent workflow activity.</p>;
    return <div style={{ display: 'grid', gap: 6 }}>{items.map((item, index) => <div key={`${item.curriculum}-${index}`} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: index === items.length - 1 ? 0 : '1px solid hsl(var(--border))' }}><span className="brand-mark" style={{ width: 31, height: 31, borderRadius: 10, flexShrink: 0 }}><Activity size={14} /></span><div style={{ flex: 1 }}><strong style={{ display: 'block', fontSize: 12 }}>{item.title}</strong><span className="muted" style={{ fontSize: 11 }}>{item.curriculum}</span></div><span className="muted" style={{ fontSize: 10 }}>{item.date}</span></div>)}</div>;
}
function RecentWorkflowRecords({ role }) {
    const [rows, setRows] = useState([]);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        const load = role === 'admin' ? mockService.getAdminSubmissions() : mockService.getMySubmissions();
        load.then(setRows).catch(e => setError(e.message || 'Unable to load curriculum submissions.')).finally(() => setLoading(false));
    }, [role]);
    if (loading) return <p className="muted">Loading submissions…</p>;
    if (error) return <p className="muted" role="alert">{error}</p>;
    if (!rows.length) return <p className="muted" style={{ fontSize: 12 }}>No submission records are available yet.</p>;
    return <div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum</th>{role === 'admin' && <th>Institute</th>}<th>Version</th><th>Submitted</th><th>Status</th></tr></thead><tbody>{rows.slice(0, 5).map(row => <tr key={row.submission_id}><td><strong>{row.curriculum_name}</strong></td>{role === 'admin' && <td>{row.institute_name}</td>}<td>v{row.version}</td><td>{formatDocumentDate(row.submitted_at)}</td><td><StatusBadge status={row.status} /></td></tr>)}</tbody></table></div>;
}
function ReviewerDashboardQueue() {
    const [rows, setRows] = useState([]);
    const [error, setError] = useState('');
    useEffect(() => { mockService.getPendingSubmissions().then(setRows).catch(e => setError(e.message || 'Unable to load submissions.')); }, []);
    if (error) return <p className="muted" role="alert">{error}</p>;
    if (!rows.length) return <p className="muted" style={{ fontSize: 12 }}>No database submissions are pending review.</p>;
    return <div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum</th><th>Institute</th><th>Version</th><th>Submitted</th><th>Status</th></tr></thead><tbody>{rows.slice(0, 5).map(row => <tr key={row.submission_id}><td><strong>{row.curriculum_name}</strong></td><td>{row.institute_name}</td><td>{row.version}</td><td>{formatDocumentDate(row.submitted_at)}</td><td><StatusBadge status={row.status} /></td></tr>)}</tbody></table></div>;
}function CurriculumTable({ items, onAction }) {
    return <div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum</th><th>Institute</th><th>Version</th><th>Designer</th><th>Score</th><th>Status</th><th>Action</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} data-testid={`row-curriculum-${item.id}`}><td><strong>{item.name}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>{item.program}</span></td><td>Northstar Institute of Technology</td><td>{item.version}</td><td>{item.designer}</td><td><strong>{item.score}</strong><span className="muted">/100</span></td><td><StatusBadge status={item.status} /></td><td><button className="btn icon-btn" onClick={() => onAction(item)} data-testid={`button-view-curriculum-${item.id}`}><Eye size={15} /></button></td></tr>)}</tbody></table></div>;
}
function formatDocumentDate(value) {
    if (!value)
        return 'Not recorded';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Not recorded';
    let timeZone;
    try { timeZone = localStorage.getItem('aicte-timezone') || undefined; } catch { timeZone = undefined; }
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit', ...(timeZone ? { timeZone } : {}) });
}
function AdminDocuments({ notify }) {
    const [query, setQuery] = useState('');
    const [docs, setDocs] = useState([]);
    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const filtered = docs.filter(doc => (doc.filename || '').toLowerCase().includes(query.toLowerCase()));
    const refreshDocuments = async () => {
        setLoading(true); setError('');
        try { setDocs(await mockService.getDocuments()); }
        catch (e) { setError(e.message || 'Unable to load indexed documents.'); }
        finally { setLoading(false); }
    };
    const uploadPdf = async file => {
        if (!file) return;
        setUploading(true); setError('');
        try {
            const result = await mockService.uploadDocument(file);
            notify(`${result.filename} indexed into ${result.total_chunks} chunks.`);
            await refreshDocuments();
        } catch (e) { setError(e.message || 'Unable to index this PDF.'); }
        finally { setUploading(false); }
    };
    const removeDocument = async doc => {
        setError('');
        try {
            await mockService.deleteDocument(doc.filename, doc.document_id || '');
            await refreshDocuments();
            notify(`${doc.filename} was removed from the index.`);
        } catch (e) { setError(e.message || 'Unable to remove this indexed document.'); }
    };
    useEffect(() => { void refreshDocuments(); }, []);
    return <div className="content"><PageHeader eyebrow="Admin / Knowledge registry" title="Upload authoritative document" detail="Upload AICTE reference PDFs to index their contents for search and analysis." action={<label className={`btn btn-primary upload-button ${uploading ? 'disabled' : ''}`}><Upload size={15} /> {uploading ? 'Indexing PDF' : 'Upload PDF'}<input type="file" accept=".pdf,application/pdf" disabled={uploading} onChange={event => { void uploadPdf(event.target.files?.[0]); event.target.value = ''; }} data-testid="input-admin-document-pdf" /></label>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        <div className="surface" style={{ padding: 13, marginBottom: 15, display: 'flex', gap: 10 }}><input className="field" aria-label="Search indexed PDFs" placeholder="Search indexed PDFs" value={query} onChange={event => setQuery(event.target.value)} /><button className="btn" onClick={() => void refreshDocuments()} disabled={loading}><RefreshCw size={14} /> Refresh</button></div>
        <SectionCard title={loading ? 'Loading indexed documents' : `${filtered.length} indexed documents`}><div className="table-scroll"><table className="data-table"><thead><tr><th>Title</th><th>Chunks</th><th>Uploaded</th><th>Status</th><th>Actions</th></tr></thead><tbody>{filtered.map((doc, index) => <tr key={doc.document_id || doc.filename}><td><strong>{doc.filename}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>{doc.source_type || 'AICTE reference'}</span></td><td>{doc.total_chunks}</td><td>{formatDocumentDate(doc.uploaded_at)}</td><td><StatusBadge status={doc.status || 'Active'} /></td><td><button className="btn icon-btn" aria-label={`Details for ${doc.filename}`} onClick={() => setSelected(doc)} data-testid={`button-view-document-${index}`}><Eye size={14} /></button><button className="btn icon-btn" aria-label={`Delete ${doc.filename}`} onClick={() => void removeDocument(doc)} data-testid={`button-delete-document-${index}`}><Trash2 size={14} /></button></td></tr>)}{!loading && filtered.length === 0 && <tr><td colSpan="5" className="muted">No indexed PDFs found. Upload a reference PDF to make it searchable.</td></tr>}</tbody></table></div></SectionCard>
        {selected && <Modal title="Indexed document details" onClose={() => setSelected(null)}><dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '8px 14px', fontSize: 12 }}><dt className="muted">File</dt><dd>{selected.filename}</dd><dt className="muted">Document ID</dt><dd>{selected.document_id || 'Not recorded'}</dd><dt className="muted">Curriculum ID</dt><dd>{selected.curriculum_id || 'Not applicable'}</dd><dt className="muted">Programme</dt><dd>{selected.programme || 'Not recorded'}</dd><dt className="muted">Branch</dt><dd>{selected.branch || 'Not recorded'}</dd><dt className="muted">Version</dt><dd>{selected.version || 'Not recorded'}</dd><dt className="muted">Indexed chunks</dt><dd>{selected.total_chunks}</dd><dt className="muted">Uploaded</dt><dd>{formatDocumentDate(selected.uploaded_at)}</dd></dl></Modal>}
    </div>;
}
function PolicyManagement({ audience }) {
    const [criteria, setCriteria] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try { setCriteria(await mockService.getAnalyzerCriteria()); }
        catch (e) { setError(e.message || 'Unable to load configured Analyzer criteria.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const groups = [...new Set(criteria.map(item => item.criterion))].map(key => ({
        key, label: criteria.find(item => item.criterion === key)?.criterion_label || key,
        rows: criteria.filter(item => item.criterion === key),
    }));
    const prefix = audience === 'admin' ? 'Admin' : 'Reviewer / Expert';
    return <div className="content"><PageHeader eyebrow={`${prefix} / Governance rules`} title="Analyzer criteria" detail="The configured criteria used by curriculum scoring, with each rule?s stated basis and availability." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 22 }}>Loading configured criteria?</div> : !criteria.length ? <div className="surface" style={{ padding: 22 }}><p className="muted" style={{ margin: 0 }}>No Analyzer criteria are configured.</p></div> : <div style={{ display: 'grid', gap: 12 }}>{groups.map(group => <SectionCard key={group.key} title={group.label}><div style={{ display: 'grid', gap: 8 }}>{group.rows.map(row => <article key={row.check_id} className="surface" style={{ padding: 12 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 9 }}><strong style={{ fontSize: 12 }}>{row.title}</strong><span className="badge badge-slate">{row.basis === 'AICTE_MODEL_REFERENCE' ? 'AICTE model reference' : 'Analyzer-derived'}</span></div><p className="muted" style={{ fontSize: 11, margin: '7px 0' }}>{row.explanation}</p><div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}><span className="muted" style={{ fontSize: 10 }}>Configured comparison: {typeof row.expected === 'object' ? JSON.stringify(row.expected) : row.expected}</span><span className="muted" style={{ fontSize: 10 }}>Availability: {row.availability_policy}</span></div></article>)}</div></SectionCard>)}</div>}
    </div>;
}
function AdminInstitutes({ notify }) {
    const [institutes, setInstitutes] = useState([]);
    const [name, setName] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => { setLoading(true); try { setInstitutes(await mockService.getInstitutions()); setError(''); } catch (e) { setError(e.message || 'Unable to load institutions.'); } finally { setLoading(false); } };
    useEffect(() => { void load(); }, []);
    const add = async event => { event.preventDefault(); try { await mockService.createInstitution(name); setName(''); await load(); notify('Institution created. Assign Designer and Institute Representative accounts in Users & Roles.'); } catch (e) { setError(e.message || 'Unable to create institution.'); } };
    return <div className="content"><PageHeader eyebrow="Admin / Institution registry" title="Institutions" detail="Create trusted institutional records, then explicitly link Designer and Institute Representative accounts in Users & Roles." /><SectionCard title="Create institution"><form onSubmit={add} style={{ display: 'flex', gap: 9, maxWidth: 650 }}><input className="field" required value={name} onChange={e => setName(e.target.value)} placeholder="Official institution name" data-testid="input-institute-name" /><button className="btn btn-primary" data-testid="button-save-institute"><Plus size={14} /> Add institution</button></form></SectionCard>{error && <div className="surface" role="alert" style={{ padding: 12, marginTop: 12 }}>{error} <button className="btn" onClick={() => void load()}>Retry</button></div>}<div style={{ marginTop: 14 }}><SectionCard title={loading ? 'Loading institutions' : `${institutes.length} database institutions`}><div className="table-scroll"><table className="data-table"><thead><tr><th>Institution</th><th>Institution ID</th><th>Status</th></tr></thead><tbody>{institutes.map(item => <tr key={item.institute_id}><td><strong>{item.name}</strong></td><td>{item.institute_id}</td><td><StatusBadge status={item.status} /></td></tr>)}{!loading && institutes.length === 0 && <tr><td colSpan="3" className="muted">No institutions yet. Add an institution, then assign accounts in Users & Roles.</td></tr>}</tbody></table></div></SectionCard></div></div>;
}
function AdminCurricula({ notify }) {
    const tabs = ['All', 'Pending', 'Accepted', 'Revision Required', 'Rejected'];
    const [tab, setTab] = useState('All');
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => { setLoading(true); setError(''); try { setRows(await mockService.getAdminSubmissions()); } catch (e) { setError(e.message || 'Unable to load curriculum records.'); } finally { setLoading(false); } };
    useEffect(() => { void load(); }, []);
    const shown = tab === 'All' ? rows : rows.filter(item => item.status === tab);
    return <div className="content"><PageHeader eyebrow="Admin / Curriculum lifecycle" title="Curriculum register" detail="Submitted versions and review status from the workflow record." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} /><div className="surface" style={{ padding: 8, display: 'flex', gap: 5, overflowX: 'auto', marginBottom: 15 }}>{tabs.map((item) => <button key={item} className={`btn ${tab === item ? 'btn-primary' : 'btn-ghost'}`} style={{ whiteSpace: 'nowrap', padding: '0 11px' }} onClick={() => setTab(item)} data-testid={`tab-curriculum-${item.toLowerCase().replaceAll(' ', '-')}`}>{item}</button>)}</div>{error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}<SectionCard title={loading ? 'Loading submissions' : `${shown.length} curriculum submissions`}><div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum / ID</th><th>Institute</th><th>Version</th><th>Designer</th><th>Score</th><th>Status</th></tr></thead><tbody>{shown.map(item => <tr key={item.submission_id}><td><strong>{item.curriculum_name}</strong><span className="muted" style={{ display: 'block', marginTop: 3 }}>{item.curriculum_id}</span></td><td>{item.institute_name}</td><td>v{item.version}</td><td>{item.designer_name}</td><td>{item.latest_score == null ? 'Not analyzed' : `${item.latest_score}/100`}</td><td><StatusBadge status={item.status} /></td></tr>)}{!loading && !shown.length && <tr><td colSpan="6" className="muted">No submissions match this status.</td></tr>}</tbody></table></div></SectionCard></div>;
}
function AdminReviews({ notify }) {
    const [pending, setPending] = useState([]);
    const [decisions, setDecisions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => { setLoading(true); setError(''); try { const [rows, history] = await Promise.all([mockService.getAdminSubmissions(), mockService.getReviewHistory()]); setPending(rows.filter(row => row.status === 'Pending')); setDecisions(history); } catch (e) { setError(e.message || 'Unable to load review operations.'); } finally { setLoading(false); } };
    useEffect(() => { void load(); }, []);
    const statuses = decisions.reduce((counts, row) => { for (const review of row.review_history || []) counts[review.status] = (counts[review.status] || 0) + 1; return counts; }, {});
    const history = decisions.flatMap(row => (row.review_history || []).map((review, index) => ({ ...review, curriculum_name: row.curriculum_name, institute_name: row.institute_name, version: row.version, submission_id: row.submission_id, key: `${row.submission_id}-${review.review_id || index}` }))).sort((a, b) => new Date(b.decided_at || 0) - new Date(a.decided_at || 0));
    return <div className="content"><PageHeader eyebrow="Admin / Oversight" title="Review operations" detail="Current queue and recorded Reviewer decisions." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />{error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}<div className="stat-grid"><StatCard label="Open queue" value={loading ? '—' : pending.length} note="Pending submissions" icon={Inbox} /><StatCard label="Accepted" value={statuses.Accepted || 0} note="Recorded decisions" icon={CheckCircle2} tone="green" /><StatCard label="Revision required" value={statuses['Revision Required'] || 0} note="Returned to Designers" icon={RefreshCw} /><StatCard label="Rejected" value={statuses.Rejected || 0} note="Preserved review records" icon={CircleAlert} tone="amber" /></div><div style={{ marginTop: 17 }}><SectionCard title="Recent decisions">{loading ? <p className="muted">Loading decisions…</p> : history.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum</th><th>Institute</th><th>Reviewer</th><th>Decision</th><th>Date</th><th>Feedback</th></tr></thead><tbody>{history.map(row => <tr key={row.key}><td><strong>{row.curriculum_name}</strong><span className="muted" style={{ display: 'block', fontSize: 10 }}>v{row.version}</span></td><td>{row.institute_name}</td><td>{row.reviewer_name || row.reviewer_id || 'Reviewer'}</td><td><StatusBadge status={row.status} /></td><td>{formatDocumentDate(row.decided_at)}</td><td>{row.feedback || row.decision_justification || 'No additional feedback.'}</td></tr>)}</tbody></table></div> : <p className="muted" style={{ fontSize: 12 }}>No completed decisions have been recorded.</p>}</SectionCard></div></div>;
}
function InstituteSubmissionPortal({ notify }) {
    const [curricula, setCurricula] = useState([]);
    const [submissions, setSubmissions] = useState([]);
    const [eligible, setEligible] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState('');
    const load = async () => {
        setLoading(true);
        try {
            const [prepared, mine, readyToPublish] = await Promise.all([mockService.getWorkflowCurricula(), mockService.getMySubmissions(), mockService.getEligiblePublications()]);
            setCurricula(prepared);
            setSubmissions(mine);
            setEligible(readyToPublish);
            setError('');
        } catch (e) {
            setError(e.message || 'Unable to load institutional curricula.');
        } finally {
            setLoading(false);
        }
    };
    const publish = async item => {
        setBusy(`publish-${item.submission_id}`); setError('');
        try { await mockService.publishSubmission(item.submission_id); await load(); notify(`${item.curriculum_name} v${item.version} is now published.`); }
        catch (e) { setError(e.message || 'Unable to publish this accepted curriculum.'); }
        finally { setBusy(''); }
    };
    useEffect(() => { void load(); }, []);
    const submit = async item => {
        setBusy(item.document_id);
        setError('');
        try {
            await mockService.submitPreparedCurriculum({ curriculum_id: item.curriculum_id, document_id: item.document_id });
            await load();
            notify('The Designer?s PDF was submitted to the Reviewer Queue.');
        } catch (e) {
            setError(e.message || 'Submission failed.');
        } finally {
            setBusy('');
        }
    };
    return <div className="content">
        <PageHeader eyebrow="Institute Representative / Portal Upload" title="Submit curriculum" detail="Review a curriculum sent by a Designer linked to your institution, then submit that exact PDF version for review." action={<button className="btn" onClick={() => void load()}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12, color: '#8e3c39' }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 24 }}>Loading institution curricula?</div> : curricula.length === 0 ? <div className="surface" style={{ padding: 26 }}><h2 className="font-display" style={{ fontSize: 17 }}>No curricula waiting for your institution</h2><p className="muted" style={{ fontSize: 12 }}>A Designer linked to this institution must send a prepared curriculum here first.</p></div> : <div style={{ display: 'grid', gap: 11 }}>{curricula.map(item => <div className="surface" style={{ padding: 17 }} key={item.document_id}>
            <span className="eyebrow">{item.programme} {item.branch} ? Prepared version {item.version || '?'}</span>
            <h2 className="font-display" style={{ fontSize: 16, margin: '6px 0' }}>{item.filename}</h2>
            <p className="muted" style={{ fontSize: 10 }}>Curriculum ID: {item.curriculum_id} ? {item.total_chunks} indexed sections</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, alignItems: 'center' }}>
                <button className="btn" disabled={!item.original_available} onClick={async () => { try { const url = await mockService.getDraftDocument(item.curriculum_id, item.document_id); window.open(url, '_blank', 'noopener,noreferrer'); } catch (e) { setError(e.message); } }}><Eye size={14} /> View</button>
                <button className="btn btn-primary" disabled={!item.original_available || Boolean(busy)} onClick={() => void submit(item)}>{busy === item.document_id ? 'Submitting?' : 'Submit for review'}</button>
            </div>
        </div>)}</div>}
        <div style={{ marginTop: 18 }}><SectionCard title="Submission and feedback history">{submissions.length === 0 ? <p className="muted" style={{ fontSize: 12 }}>No submissions yet.</p> : <div style={{ display: 'grid', gap: 9 }}>{submissions.map(sub => <div className="surface" style={{ padding: 13 }} key={sub.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 9 }}><strong style={{ fontSize: 12 }}>{sub.curriculum_name} ? v{sub.version}</strong><StatusBadge status={sub.status} /></div><span className="muted" style={{ fontSize: 10 }}>{formatDocumentDate(sub.submitted_at)} ? {sub.submission_id}</span>{sub.review_history?.map(review => <p key={review.review_id} style={{ fontSize: 11, margin: '8px 0 0' }}><strong>{review.status}:</strong> {review.feedback || 'No additional feedback.'}</p>)}</div>)}</div>}</SectionCard></div>
        <div style={{ marginTop: 16 }}><SectionCard title="Accepted · ready to publish">{eligible.length ? <div style={{ display: 'grid', gap: 9 }}>{eligible.map(item => <div className="surface" style={{ padding: 13, display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }} key={item.submission_id}><div><strong style={{ fontSize: 12 }}>{item.curriculum_name} · v{item.version}</strong><p className="muted" style={{ fontSize: 10, margin: '5px 0 0' }}>Accepted {formatDocumentDate(item.review_history?.at(-1)?.decided_at)}</p></div><button className="btn btn-primary" disabled={Boolean(busy)} onClick={() => void publish(item)}>{busy === `publish-${item.submission_id}` ? 'Publishing…' : 'Publish curriculum'}</button></div>)}</div> : <p className="muted" style={{ fontSize: 12 }}>No accepted submissions are waiting for publication.</p>}</SectionCard></div>
    </div>;
}
function AdminUsers({ notify }) {
    const [users, setUsers] = useState([]);
    const [institutions, setInstitutions] = useState([]);
    const [error, setError] = useState('');
    const [institutionName, setInstitutionName] = useState('');
    const [newUser, setNewUser] = useState({ name: '', email: '', role: 'designer', password: '' });
    const reload = async () => {
        try { const [nextUsers, nextInstitutions] = await Promise.all([mockService.getAdminUsers(), mockService.getInstitutions()]); setUsers(nextUsers); setInstitutions(nextInstitutions); setError(''); }
        catch (e) { setError(e.message || 'Unable to load user records.'); }
    };
    useEffect(() => { void reload(); }, []);
    const assign = async (user, instituteId) => {
        try { await mockService.assignInstitution(user.user_id, instituteId); await reload(); notify('Institution link saved.'); }
        catch (e) { setError(e.message || 'Unable to update institution link.'); }
    };
    return <div className="content"><PageHeader eyebrow="Admin / Access control" title="Users & roles" detail="Account roles are stored in MongoDB. Institution links are set explicitly and are never inferred from organization labels." />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 15 }}>
            <SectionCard title="Create institution"><form onSubmit={async (e) => { e.preventDefault(); try { await mockService.createInstitution(institutionName); setInstitutionName(''); await reload(); notify('Institution created.'); } catch (err) { setError(err.message); } }}><label className="label">Institution name</label><input className="field" required value={institutionName} onChange={e => setInstitutionName(e.target.value)} /><button className="btn btn-primary" style={{ marginTop: 11 }}><Plus size={14} /> Create institution</button></form></SectionCard>
            <SectionCard title="Provision account"><form onSubmit={async (e) => { e.preventDefault(); try { await mockService.createUser(newUser); setNewUser({ name: '', email: '', role: 'designer', password: '' }); await reload(); notify('Account created. Link it to an institution when appropriate.'); } catch (err) { setError(err.message); } }}><div className="form-grid"><Field label="Name" value={newUser.name} onChange={e => setNewUser({ ...newUser, name: e.target.value })} required /><Field label="Email" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} type="email" required /><div><label className="label">Role</label><select className="select" value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}><option value="designer">Curriculum Designer</option><option value="institute">Institute Representative</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select></div><Field label="Temporary password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} type="password" minLength={8} required /></div><button className="btn btn-primary" style={{ marginTop: 11 }}><Plus size={14} /> Create account</button></form></SectionCard>
        </div>
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12, color: '#8e3c39' }}>{error} <button className="btn" onClick={() => void reload()}>Retry</button></div>}
        <SectionCard title={`${users.length} database identities`}><div className="table-scroll"><table className="data-table"><thead><tr><th>Name / Email</th><th>Role</th><th>Institution link</th><th>Account</th></tr></thead><tbody>{users.map(user => <tr key={user.user_id}><td><strong>{user.name}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>{user.email}</span></td><td><select className="select" value={user.role} onChange={async e => { try { await mockService.updateUser(user.user_id, { role: e.target.value }); await reload(); } catch (err) { setError(err.message); } }} aria-label={`Role for ${user.name}`}><option value="admin">Admin</option><option value="designer">Curriculum Designer</option><option value="reviewer">Reviewer</option><option value="institute">Institute Representative</option></select></td><td>{['designer', 'institute'].includes(user.role) ? <select className="select" value={user.institute_id || ''} onChange={e => void assign(user, e.target.value)} aria-label={`Institution for ${user.name}`}><option value="">Not linked</option>{institutions.map(inst => <option key={inst.institute_id} value={inst.institute_id}>{inst.name}</option>)}</select> : <span className="muted">Not required</span>}</td><td><button className={`btn ${user.status === 'Active' ? 'btn-ghost' : 'btn-primary'}`} onClick={async () => { try { await mockService.updateUser(user.user_id, { status: user.status === 'Active' ? 'Inactive' : 'Active' }); await reload(); } catch (err) { setError(err.message); } }}>{user.status === 'Active' ? 'Deactivate' : 'Activate'}</button></td></tr>)}{users.length === 0 && <tr><td colSpan="4" className="muted">Existing demo accounts migrate on first sign-in. Account provisioning and institution links are controlled here.</td></tr>}</tbody></table></div></SectionCard>
    </div>;
}
function AuditLogs() {
    const [events, setEvents] = useState([]);
    const [query, setQuery] = useState('');
    const [actionFilter, setActionFilter] = useState('All');
    const [expanded, setExpanded] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try { setEvents(await mockService.getAdminAuditEvents()); }
        catch (e) { setError(e.message || 'Unable to load recorded workflow activity.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const actions = ['All', ...new Set(events.map(event => event.action).filter(Boolean))];
    const shown = events.filter(event => {
        if (actionFilter !== 'All' && event.action !== actionFilter) return false;
        const text = [event.actor_name, event.institute_name, event.action, event.curriculum_name, event.curriculum_id, event.submission_id, event.details].join(' ').toLowerCase();
        return text.includes(query.trim().toLowerCase());
    });
    return <div className="content"><PageHeader eyebrow="Admin / Traceability" title="Workflow activity" detail="Submission, review, and publication events recorded in workflow history." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error} <button className="btn" onClick={() => void load()}>Retry</button></div>}
        <div className="surface" style={{ padding: 12, display: 'flex', gap: 9, flexWrap: 'wrap', marginBottom: 14 }}><input className="field" aria-label="Search workflow activity" placeholder="Search people, curriculum, or event" value={query} onChange={event => setQuery(event.target.value)} style={{ flex: '1 1 260px' }} /><select className="select" aria-label="Filter activity type" value={actionFilter} onChange={event => setActionFilter(event.target.value)} style={{ flex: '0 1 230px' }}>{actions.map(action => <option key={action}>{action}</option>)}</select></div>
        {loading ? <div className="surface" style={{ padding: 22 }}>Loading recorded activity…</div> : <SectionCard title={`${shown.length} recorded events`}><div className="table-scroll"><table className="data-table"><thead><tr><th>User</th><th>Institute</th><th>Action</th><th>Curriculum</th><th>Timestamp</th><th>Details</th></tr></thead><tbody>{shown.map(event => <><tr key={event.event_id}><td><strong>{event.actor_name}</strong></td><td>{event.institute_name}</td><td><StatusBadge status={event.action} /></td><td>{event.curriculum_name} <span className="muted">v{event.version}</span></td><td className="muted">{formatDocumentDate(event.created_at)}</td><td><button className="btn btn-ghost" onClick={() => setExpanded(expanded === event.event_id ? '' : event.event_id)} aria-expanded={expanded === event.event_id}><Eye size={14} /> {expanded === event.event_id ? 'Hide' : 'Inspect'}</button></td></tr>{expanded === event.event_id && <tr key={`${event.event_id}-details`}><td colSpan="6"><div className="surface" style={{ padding: 11 }}><p style={{ margin: '0 0 6px' }}>{event.details || 'No additional detail was recorded.'}</p>{event.decision_justification && <p className="muted" style={{ margin: '4px 0' }}><strong>Decision justification:</strong> {event.decision_justification}</p>}<span className="muted" style={{ fontSize: 10 }}>Submission {event.submission_id} · Curriculum ID {event.curriculum_id}</span></div></td></tr>}</>)}</tbody></table>{!shown.length && <p className="muted" style={{ padding: 12 }}>{events.length ? 'No events match these filters.' : 'No submission or review events have been recorded yet.'}</p>}</div></SectionCard>}
    </div>;
}
function ReviewQueue({ notify }) {
    const [queue, setQueue] = useState([]);
    const [selectedId, setSelectedId] = useState('');
    const [detail, setDetail] = useState(null);
    const [comment, setComment] = useState('');
    const [justification, setJustification] = useState('');
    const [documentUrl, setDocumentUrl] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [, setLocation] = useLocation();
    const load = async () => {
        setLoading(true); setError('');
        try { const rows = await mockService.getPendingSubmissions(); setQueue(rows); const id = rows.some(row => row.submission_id === selectedId) ? selectedId : rows[0]?.submission_id || ''; setSelectedId(id); setDetail(id ? await mockService.getSubmission(id) : null); }
        catch (e) { setError(e.message || 'Could not load the reviewer queue.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const select = async (id) => { setSelectedId(id); setDocumentUrl(''); try { setDetail(await mockService.getSubmission(id)); setError(''); } catch (e) { setError(e.message); } };
    const decide = async (decision) => {
        if (!detail) return;
        try { await mockService.decideSubmission(detail.submission_id, decision, comment, justification); setComment(''); setJustification(''); setDetail(null); await load(); notify(`Decision recorded: ${decision === 'accept' ? 'Accepted' : decision === 'review' ? 'Revision Required' : 'Rejected'}.`); }
        catch (e) { setError(e.message || 'Decision could not be saved.'); }
    };
    const analyzerReport = detail?.analyses?.[0]?.report;
    const recommendation = analyzerReport?.decision_support?.decision;
    const overrideRequired = decision => Boolean(recommendation && ({ accept: 'ACCEPT', review: 'REVISE', reject: 'REJECT' }[decision] !== recommendation));
    return <div className="content"><PageHeader eyebrow="Reviewer / Expert" title="Pending reviews" detail="Database submissions awaiting Reviewer Compliance." action={<button className="btn" onClick={() => void load()}><RefreshCw size={14} /> Refresh queue</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 13, marginBottom: 13, color: '#8e3c39' }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 28, textAlign: 'center' }}>Loading pending submissionsâ€¦</div> : queue.length === 0 ? <div className="surface" style={{ padding: 32, textAlign: 'center' }}><Inbox size={28} color="#7758aa" /><h2 className="font-display">No pending submissions</h2><p className="muted" style={{ fontSize: 12 }}>New portal uploads will appear here.</p></div> : <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: 16 }}>
            <SectionCard title={`Pending queue Â· ${queue.length}`}><div style={{ display: 'grid', gap: 9 }}>{queue.map(item => <button key={item.submission_id} onClick={() => void select(item.submission_id)} className="surface" style={{ textAlign: 'left', padding: 14, border: selectedId === item.submission_id ? '2px solid #9d7bc7' : undefined }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}><strong style={{ fontSize: 12 }}>{item.curriculum_name}</strong><StatusBadge status={item.status} /></div><p className="muted" style={{ fontSize: 10, margin: '6px 0' }}>{item.institute_name} Â· Version {item.version}</p><span className="muted" style={{ fontSize: 10 }}>ID {item.submission_id} Â· {formatDocumentDate(item.submitted_at)}</span></button>)}</div></SectionCard>
            <SectionCard title="Reviewer Compliance">{detail && <><span className="eyebrow">{detail.submission_id} Â· Version {detail.version}</span><h2 className="font-display" style={{ fontSize: 19, margin: '8px 0' }}>{detail.curriculum_name}</h2><p className="muted" style={{ fontSize: 11 }}>Curriculum {detail.curriculum_id} Â· Submitted {formatDocumentDate(detail.submitted_at)}</p>{detail.previous_versions?.length > 0 && <details className="surface" style={{ padding: 12, margin: '12px 0' }}><summary><strong>Earlier submitted versions</strong></summary>{detail.previous_versions.map(previous => <div key={previous.submission_id} style={{ paddingTop: 10 }}><span>v{previous.version} Â· {previous.status} Â· {formatDocumentDate(previous.submitted_at)}</span>{previous.analyses?.[0]?.report?.overall_score != null && <span> Â· analyzer score {previous.analyses[0].report.overall_score}</span>}</div>)}</details>}<div className="surface" style={{ padding: 12, margin: '14px 0' }}><strong style={{ fontSize: 12 }}>Submitted PDF</strong><div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}><button className="btn" onClick={async () => { try { if (documentUrl) URL.revokeObjectURL(documentUrl); setDocumentUrl(await mockService.getSubmissionDocument(detail.submission_id)); } catch (e) { setError(e.message); } }}><Eye size={14} /> Securely load document</button>{documentUrl && <a className="btn btn-primary" href={documentUrl} target="_blank" rel="noreferrer">Open PDF</a>}</div></div><button className="btn btn-primary" onClick={() => setLocation(`/reviewer/analyzer?submission_id=${encodeURIComponent(detail.submission_id)}`)}><BarChart3 size={14} /> Analyze this submission</button>{analyzerReport?.decision_support && <DecisionRecommendationPanel support={analyzerReport.decision_support} />}<label className="label" style={{ marginTop: 16 }}>Feedback for the institute and designer</label><textarea className="textarea" value={comment} onChange={e => setComment(e.target.value)} placeholder="Required for revision or rejection decisions." />{recommendation && <div style={{ marginTop: 10 }}><label className="label" htmlFor="decision-justification">Decision justification (required when it differs from {recommendation})</label><textarea id="decision-justification" className="textarea" value={justification} onChange={e => setJustification(e.target.value)} placeholder="Explain the reason for your decision." /></div>}<div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 11 }}><button className="btn btn-primary" disabled={!analyzerReport || Boolean(overrideRequired('accept') && !justification.trim())} onClick={() => void decide('accept')}><CheckCircle2 size={14} /> Accept</button><button className="btn" disabled={!comment.trim() || Boolean(overrideRequired('review') && !justification.trim())} onClick={() => void decide('review')}><RefreshCw size={14} /> Request revision</button><button className="btn btn-danger" disabled={!comment.trim() || Boolean(overrideRequired('reject') && !justification.trim())} onClick={() => void decide('reject')}><X size={14} /> Reject</button></div><p className="muted" style={{ fontSize: 10, lineHeight: 1.5 }}>Run the Analyzer before accepting. Revision and rejection require actionable feedback.</p></>}{!detail && <p className="muted">Select a pending submission.</p>}</SectionCard>
        </div>}
    </div>;
}
function ReviewSupportingPage({ path }) {
    const title = path.endsWith('history') ? 'Review history' : path.endsWith('policies') ? 'Reviewer policies' : 'Approved curricula';
    const [items, setItems] = useState([]);
    const [error, setError] = useState('');
    useEffect(() => { mockService.getReviewHistory().then(rows => setItems(path.endsWith('approved') ? rows.filter(row => ['Accepted', 'Published'].includes(row.status)) : rows)).catch(e => setError(e.message || 'Unable to load review history.')); }, [path]);
    return <div className="content"><PageHeader eyebrow="Reviewer / Expert" title={title} detail="Recorded decisions and feedback remain attached to each immutable submission version." />{error && <div className="surface" role="alert" style={{ padding: 12 }}>{error}</div>}<SectionCard title={path.endsWith('approved') ? 'Accepted submissions' : 'Completed review records'}>{items.length === 0 ? <p className="muted" style={{ fontSize: 12 }}>No completed review records.</p> : <div style={{ display: 'grid', gap: 9 }}>{items.map(item => <div className="surface" style={{ padding: 13 }} key={item.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 9 }}><strong style={{ fontSize: 12 }}>{item.curriculum_name} · v{item.version}</strong><StatusBadge status={item.status} /></div><p className="muted" style={{ fontSize: 10 }}>{item.institute_name} · {formatDocumentDate(item.submitted_at)} · {item.submission_id}</p>{item.review_history?.map(review => <p key={review.review_id} style={{ fontSize: 11, margin: '5px 0' }}><strong>{review.status}:</strong> {review.feedback || 'Accepted for publishing.'}</p>)}</div>)}</div>}</SectionCard></div>;
}
function DesignerCurricula({ notify }) {
    const [own, setOwn] = useState([]);
    const [submissions, setSubmissions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState('');
    const [, setLocation] = useLocation();
    const loadCurricula = async () => {
        setLoading(true);
        setError('');
        try {
            const [docs, history] = await Promise.all([mockService.getDocuments(), mockService.getMySubmissions()]);
            setOwn(submittedCurriculumDocuments(docs));
            setSubmissions(history);
        } catch (requestError) {
            setError(requestError.message || 'Unable to load your curricula.');
        } finally {
            setLoading(false);
        }
    };
    const handoffCurriculum = async item => {
        setBusy(item.document_id);
        try {
            const result = await mockService.handoffCurriculum(item.document_id);
            if (result?.handoff_status !== 'Ready for institute') {
                throw new Error('The server did not confirm that this curriculum was sent. Refresh and try again.');
            }
            // Reflect the persisted response immediately, then reload both sources of
            // truth so a refresh or a second browser session shows the same state.
            setOwn(current => current.map(draft => draft.document_id === item.document_id
                ? { ...draft, handoff_status: result.handoff_status }
                : draft));
            await loadCurricula();
            notify(`${item.filename} was sent to your Institute Representative.`);
        } catch (requestError) {
            notify(requestError.message || 'Unable to send this curriculum to your institution.');
        } finally {
            setBusy('');
        }
    };
    const removeCurriculum = async item => {
        try {
            await mockService.deleteDocument(item.filename, item.document_id);
            setOwn(current => current.filter(draft => draft.filename !== item.filename));
            notify(`${item.filename} and its stored PDF were deleted.`);
        } catch (requestError) {
            notify(requestError.message || 'Unable to delete this curriculum PDF.');
        }
    };
    useEffect(() => { void loadCurricula(); }, []);
    return <div className="content">
        <PageHeader eyebrow="Curriculum Designer" title="My curricula" detail="Prepare each PDF, then send it to your linked Institute Representative for review and submission." action={<button className="btn btn-primary" onClick={() => setLocation('/designer/create')} data-testid="button-create-curriculum"><Plus size={15} /> Create curriculum</button>} />
        {loading && <div className="surface" style={{ padding: 28, textAlign: 'center' }} data-testid="curricula-loading"><RefreshCw size={22} className="analyzer-spin" /><h2 className="font-display" style={{ fontSize: 17 }}>Loading your curricula</h2></div>}
        {!loading && error && <div className="surface" style={{ padding: 24 }} data-testid="curricula-error"><CircleAlert size={18} /><h2 className="font-display" style={{ fontSize: 17 }}>Could not load curricula</h2><p className="muted" style={{ fontSize: 12 }}>{error}</p><button className="btn" onClick={() => void loadCurricula()}><RefreshCw size={14} /> Retry</button></div>}
        {!loading && !error && own.length === 0 && <div className="surface" style={{ padding: 34, textAlign: 'center' }} data-testid="curricula-empty"><FileText size={28} color="#7758aa" /><h2 className="font-display" style={{ fontSize: 18 }}>No uploaded curricula yet</h2><p className="muted" style={{ fontSize: 12 }}>Create a curriculum and upload its PDF to prepare it for institutional submission.</p><button className="btn btn-primary" onClick={() => setLocation('/designer/create')}><Upload size={14} /> Upload curriculum PDF</button></div>}
        {!loading && !error && <div style={{ display: 'grid', gap: 13 }}>{own.map((item, i) => <div className="surface" style={{ padding: 19 }} key={analyzerDocumentKey(item)} data-testid={`card-designer-curriculum-${i}`}>
            {(() => {
                const relatedSubmissions = submissions.filter(sub => sub.curriculum_id === item.curriculum_id);
                const matchingSubmission = submissions.find(sub =>
                    [sub.prepared_document_id, sub.document_id].some(id => id != null && String(id) === String(item.document_id))
                );
                const handedOff = String(item.handoff_status || '').trim().toLowerCase() === 'ready for institute';
                const alreadySent = handedOff || Boolean(matchingSubmission);
                const visibleStatus = matchingSubmission?.status || (handedOff ? 'Sent to institute' : item.status || 'Draft');
                return <>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 15, alignItems: 'flex-start' }}><div><span className="eyebrow">{item.programme} {item.branch} ? v{item.version || 'Not set'}</span><h2 className="font-display" style={{ fontSize: 18, margin: '7px 0' }}>{item.filename}</h2><p className="muted" style={{ fontSize: 11, margin: 0 }}>Curriculum ID: {item.curriculum_id} ? {item.total_chunks} vector chunks ? Uploaded {formatDocumentDate(item.uploaded_at)}</p></div><StatusBadge status={visibleStatus} /></div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 17 }}>
                <button className="btn" onClick={async () => { try { const url = await mockService.getDraftDocument(item.curriculum_id, item.document_id); window.open(url, '_blank', 'noopener,noreferrer'); } catch (e) { notify(e.message); } }}><Eye size={14} /> View PDF</button>
                <button className="btn btn-primary" disabled={alreadySent || Boolean(busy)} onClick={() => void handoffCurriculum(item)} data-testid={`button-handoff-designer-curriculum-${i}`}>{busy === item.document_id ? 'Sending…' : alreadySent ? 'Sent to institute' : 'Submit to institute'}</button>
                {!alreadySent && <button className="btn icon-btn" aria-label={`Delete ${item.filename}`} title="Delete uploaded PDF" onClick={() => void removeCurriculum(item)} data-testid={`button-delete-designer-curriculum-${i}`}><Trash2 size={14} /></button>}
            </div>
            {relatedSubmissions.length > 0 && <section style={{ marginTop: 17, borderTop: '1px solid hsl(var(--border))', paddingTop: 13 }}><h3 className="font-display" style={{ fontSize: 14, margin: '0 0 10px' }}>Submission and reviewer feedback</h3>{relatedSubmissions.map(sub => <div className="surface" style={{ padding: 12, marginBottom: 9 }} key={sub.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong style={{ fontSize: 12 }}>Version {sub.version}</strong><StatusBadge status={sub.status} /></div><span className="muted" style={{ fontSize: 10 }}>Submitted {formatDocumentDate(sub.submitted_at)}</span>{(sub.review_history || []).map(review => { const requests = (sub.change_requests || []).filter(request => request.review_id === review.review_id); return <div key={review.review_id} className="surface" style={{ padding: 10, marginTop: 9 }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong style={{ fontSize: 11 }}>{review.status === 'Revision Required' ? 'Revision requested' : review.status === 'Rejected' ? 'Rejected' : review.status}</strong><span className="muted" style={{ fontSize: 10 }}>{formatDocumentDate(review.decided_at)}</span></div>{review.feedback && <p style={{ fontSize: 11, margin: '7px 0' }}>{review.feedback}</p>}{requests.map(request => <div key={request.request_id} style={{ borderTop: '1px solid hsl(var(--border))', paddingTop: 8, marginTop: 8 }}><strong style={{ fontSize: 11 }}>{request.issue}</strong><p className="muted" style={{ fontSize: 10, margin: '4px 0' }}>{request.explanation}</p><p style={{ fontSize: 10, margin: '4px 0' }}><strong>Required change:</strong> {request.required_corrective_action}</p><StatusBadge status={request.status} />{request.designer_response && <p style={{ fontSize: 10, margin: '6px 0 0' }}><strong>Your response:</strong> {request.designer_response}</p>}<button className="btn" style={{ marginTop: 8 }} onClick={() => { const nextVersion = Number(request.curriculum_version || sub.version || 1) + 1; const params = new URLSearchParams({ curriculum_id: sub.curriculum_id, version: `${nextVersion}.0`, request_id: request.request_id }); setLocation(`/designer/create?${params}`); }}>Prepare corrected version</button></div>)}{!requests.length && review.feedback && <button className="btn" style={{ marginTop: 7 }} onClick={() => { const params = new URLSearchParams({ curriculum_id: sub.curriculum_id, version: `${Number(sub.version || 1) + 1}.0` }); setLocation(`/designer/create?${params}`); }}>Prepare corrected version</button>}</div>; })}{(sub.institution_feedback || []).map(feedback => <div className="surface" style={{ padding: 9, marginTop: 8 }} key={feedback.feedback_id}><strong style={{ fontSize: 10 }}>{feedback.kind === 'change_request' ? 'Institution change request' : 'Institution feedback'} ? {feedback.category}</strong><p style={{ fontSize: 10, margin: '4px 0' }}>{feedback.observation}</p>{feedback.suggested_change && <p className="muted" style={{ fontSize: 10, margin: '4px 0' }}>Suggested change: {feedback.suggested_change}</p>}{feedback.kind === 'change_request' && <><StatusBadge status={feedback.status} />{feedback.designer_response && <p style={{ fontSize: 10 }}>Your response: {feedback.designer_response}</p>}<button className="btn" style={{ marginTop: 7 }} onClick={() => { const params = new URLSearchParams({ curriculum_id: sub.curriculum_id, version: `${Number(sub.version || 1) + 1}.0`, request_id: feedback.feedback_id }); setLocation(`/designer/create?${params}`); }}>Prepare corrected version</button></>}<span className="muted" style={{ display: 'block', fontSize: 9, marginTop: 5 }}>{formatDocumentDate(feedback.created_at)}</span></div>)}</div>)}</section>}
                </>;
            })()}
        </div>)}</div>}
        {submissions.length > 0 && <div style={{ marginTop: 18 }}><SectionCard title="Institution submission feedback">{submissions.map(sub => <div className="surface" style={{ padding: 12, marginBottom: 8 }} key={sub.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between' }}><strong style={{ fontSize: 12 }}>{sub.curriculum_name} ? v{sub.version}</strong><StatusBadge status={sub.status} /></div>{sub.review_history?.map(review => <p key={review.review_id} style={{ fontSize: 11, marginBottom: 0 }}><strong>{review.status}:</strong> {review.feedback || 'Accepted for publishing.'}</p>)}</div>)}</SectionCard></div>}
    </div>;
}
function CreateWizard({ notify }) {
    const [selectedPdf, setSelectedPdf] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const [details, setDetails] = useState(() => {
        const params = new URLSearchParams(window.location.search);
        return { curriculumId: params.get('curriculum_id') || '', programme: params.get('programme') || '', branch: params.get('branch') || '', academicYear: params.get('year') || '2026', version: params.get('version') || '1.0' };
    });
    const [, setLocation] = useLocation();
    const updateDetail = name => event => setDetails(current => ({ ...current, [name]: event.target.value }));
    const choosePdf = file => {
        if (!file) return;
        setError('');
        if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') { setError('Choose a PDF file.'); return; }
        if (file.size > 25 * 1024 * 1024) { setError('The PDF must be 25 MB or smaller.'); return; }
        const inferredId = file.name.replace(/\.pdf$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        setSelectedPdf(file);
        setDetails(current => ({ ...current, curriculumId: current.curriculumId.trim() || inferredId }));
    };
    const uploadCurriculum = async event => {
        event.preventDefault();
        if (!selectedPdf || !details.curriculumId.trim()) return;
        setUploading(true); setError('');
        try {
            const result = await mockService.uploadDocument(selectedPdf, {
                source_type: 'submitted_curriculum', programme: details.programme.trim(), branch: details.branch.trim(),
                curriculum_id: details.curriculumId.trim(), year: details.academicYear, version: details.version.trim(),
            });
            notify(`${result.filename} indexed into ${result.total_chunks} vector chunks.`);
            setLocation('/designer/curricula');
        } catch (e) { setError(e.message || 'Unable to upload the curriculum PDF.'); }
        finally { setUploading(false); }
    };
    const isRevision = new URLSearchParams(window.location.search).has('request_id');
    return <div className="content"><PageHeader eyebrow="Curriculum Designer" title={isRevision ? 'Prepare corrected version' : 'Upload curriculum'} detail="Upload the working PDF. Each distinct version is indexed and preserved for institutional handoff and review." />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        <form className="surface" style={{ maxWidth: 820, padding: 20 }} onSubmit={uploadCurriculum}>
            <div className="form-grid">
                <Field label="Curriculum ID" value={details.curriculumId} onChange={updateDetail('curriculumId')} placeholder="Use the same ID when preparing a correction" required />
                <Field label="Programme" value={details.programme} onChange={updateDetail('programme')} placeholder="For example, B.Tech" required />
                <Field label="Branch" value={details.branch} onChange={updateDetail('branch')} placeholder="For example, CSE" required />
                <Field label="Academic year" value={details.academicYear} onChange={updateDetail('academicYear')} type="number" required />
                <Field label="Version" value={details.version} onChange={updateDetail('version')} required />
                <div className="upload-field" style={{ gridColumn: '1 / -1' }}><div><label className="label">Curriculum PDF</label><span className="muted" style={{ fontSize: 11 }}>{selectedPdf ? `${selectedPdf.name} selected` : 'PDF only, up to 25 MB.'}</span></div><label className={`btn btn-primary upload-button ${uploading ? 'disabled' : ''}`}><Upload size={14} /> {selectedPdf ? 'Choose a different PDF' : 'Choose PDF'}<input type="file" accept=".pdf,application/pdf" disabled={uploading} onChange={event => { choosePdf(event.target.files?.[0]); event.target.value = ''; }} data-testid="input-curriculum-pdf" /></label></div>
            </div>
            {isRevision && <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>This correction will be saved as a new upload version. Previous submissions and reviewer feedback remain in the history.</p>}
            <button className="btn btn-primary" style={{ marginTop: 18 }} disabled={uploading || !selectedPdf || !details.curriculumId.trim() || !details.version.trim()} data-testid="button-upload-curriculum">{uploading ? <RefreshCw size={14} className="analyzer-spin" /> : <Upload size={14} />} {uploading ? 'Indexing PDF?' : 'Upload and index'}</button>
        </form>
    </div>;
}
function Field({ label, value, onChange, ...inputProps }) { return <div><label className="label">{label}</label><input className="field" {...(onChange ? { value, onChange } : { defaultValue: value })} {...inputProps} data-testid={`input-wizard-${label.toLowerCase().replaceAll(' ', '-')}`} /></div>; }
function AssistantPage({ notify }) {
    const [question, setQuestion] = useState('');
    const [answer, setAnswer] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const ask = async event => {
        event.preventDefault();
        if (!question.trim() || loading) return;
        setLoading(true); setError('');
        try { setAnswer(await mockService.askAssistant(question.trim())); }
        catch (requestError) { setError(requestError.message || 'Unable to query indexed documents.'); }
        finally { setLoading(false); }
    };
    const copyRecommendation = async () => {
        try { await navigator.clipboard.writeText(answer.answer); notify('Recommendation copied to clipboard.'); }
        catch { setError('Clipboard access is unavailable in this browser.'); }
    };
    const sources = answer?.sources || [];
    return <div className="content"><PageHeader eyebrow="Designer / Evidence assistant" title="AI assistant" detail="Ask a curriculum question and review the document excerpts returned by the indexed source search." /><div style={{ maxWidth: 980 }}><SectionCard title="Curriculum question"><div style={{ padding: 17, minHeight: 210, background: '#f9f5fd', borderRadius: 1, border: '1px solid #e1d6eb' }}>{loading ? <div className="muted" role="status">Searching indexed documents?</div> : answer ? <><span className="badge badge-slate">Your question</span><p style={{ fontSize: 13, lineHeight: 1.55 }}>{answer.question}</p><div style={{ marginTop: 17, padding: 14, borderRadius: '.8rem', background: '#f1e7fb', border: '1px solid #d8c6eb' }}><div style={{ color: '#73529e', fontSize: 10, fontWeight: 800, letterSpacing: '.08em' }}><Sparkles size={13} style={{ verticalAlign: 'middle', marginRight: 5 }} /> RESPONSE</div><p style={{ fontSize: 12, lineHeight: 1.65, marginBottom: 0 }}>{answer.answer}</p></div><button className="btn" style={{ marginTop: 12 }} onClick={() => void copyRecommendation()}><Check size={14} /> Copy response</button></> : <div style={{ textAlign: 'center', padding: '40px 10px' }}><Bot size={27} color="#8061ac" /><p style={{ fontSize: 13, margin: '12px 0 4px' }}>Ask a curriculum question</p></div>}</div><form onSubmit={ask} style={{ display: 'flex', gap: 8, marginTop: 13 }}><input className="field" value={question} onChange={event => setQuestion(event.target.value)} aria-label="Curriculum question" /><button className="btn btn-primary icon-btn" type="submit" disabled={loading || !question.trim()}><Send size={15} /></button></form>{error && <div className="surface" role="alert" style={{ padding: 12, marginTop: 10 }}>{error}</div>}</SectionCard><div style={{ marginTop: 16 }}><SectionCard title="Retrieved document evidence">{sources.length ? <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>{sources.map((source, index) => <SourceCard key={`${source.title}-${source.section}-${index}`} source={source} />)}</div> : <p className="muted" style={{ fontSize: 12 }}>{answer ? 'No source excerpts were returned for this answer.' : 'Source excerpts for your latest question will appear here.'}</p>}</SectionCard></div></div></div>;
}
function renderAnswerInline(text) {
    return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
}
function tableCells(line) {
    return line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
}
function isTableDivider(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}
function RagAnswer({ content }) {
    const lines = content.split('\n');
    const blocks = [];
    let index = 0;
    while (index < lines.length) {
        if (lines[index].includes('|') && isTableDivider(lines[index + 1] ?? '')) {
            const headers = tableCells(lines[index]);
            index += 2;
            const rows = [];
            while (index < lines.length && lines[index].includes('|')) {
                rows.push(tableCells(lines[index]));
                index += 1;
            }
            blocks.push(<div className="table-scroll" key={`table-${index}`}><table className="rag-answer-table"><thead><tr>{headers.map((header, cell) => <th key={cell}>{renderAnswerInline(header)}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, cell) => <td key={cell}>{renderAnswerInline(row[cell] ?? '')}</td>)}</tr>)}</tbody></table></div>);
            continue;
        }
        const line = lines[index].trim();
        if (line) {
            const isHeading = /^[A-Z][A-Z /&-]{2,}$/.test(line);
            blocks.push(<p className={isHeading ? 'rag-answer-heading' : undefined} key={`line-${index}`}>{renderAnswerInline(line)}</p>);
        }
        index += 1;
    }
    return <div className="rag-answer">{blocks}</div>;
}
function SourceCard({ source }) {
    return <article className="surface" style={{ padding: 13 }}><span className="eyebrow">{source.type || 'Retrieved document excerpt'}</span><strong style={{ display: 'block', fontSize: 12, marginTop: 7 }}>{source.title}</strong><span className="muted" style={{ fontSize: 10 }}>{source.section}</span><p style={{ fontSize: 11, lineHeight: 1.45, margin: '8px 0 0' }}>{source.detail}</p></article>;
}
function RagAssistantPage({ notify }) {
    const [question, setQuestion] = useState('');
    const [chats, setChats] = useState(() => {
        try { return JSON.parse(localStorage.getItem('aicte-assistant-chat-history')) ?? []; }
        catch { return []; }
    });
    const [activeChatId, setActiveChatId] = useState(null);
    const [loading, setLoading] = useState(false);
    const activeChat = chats.find((chat) => chat.id === activeChatId);
    const messages = activeChat?.messages ?? [];
    const sources = messages.at(-1)?.sources ?? [];
    useEffect(() => {
        localStorage.setItem('aicte-assistant-chat-history', JSON.stringify(chats));
    }, [chats]);
    const updateChat = (chatId, update) => {
        setChats((current) => current.map((chat) => chat.id === chatId ? { ...chat, ...update, updatedAt: Date.now() } : chat));
    };
    const startNewChat = () => {
        setActiveChatId(null);
        setQuestion('');
    };
    const ask = async (event) => {
        event.preventDefault();
        const text = question.trim();
        if (!text || loading)
            return;
        const history = messages.map(({ role, content }) => ({ role, content }));
        const chatId = activeChatId ?? `chat-${Date.now()}`;
        const nextMessages = [...messages, { role: 'user', content: text }];
        if (activeChatId)
            updateChat(chatId, { messages: nextMessages });
        else {
            setChats((current) => [{ id: chatId, title: text.slice(0, 58), messages: nextMessages, updatedAt: Date.now() }, ...current]);
            setActiveChatId(chatId);
        }
        setQuestion('');
        setLoading(true);
        try {
            const response = await mockService.askAssistant(text, history);
            setChats((current) => current.map((chat) => chat.id === chatId ? {
                ...chat,
                messages: [...chat.messages, { role: 'assistant', content: response.answer, sources: response.sources ?? [] }],
                updatedAt: Date.now(),
            } : chat));
        }
        catch (error) {
            notify(`Assistant unavailable: ${error.message}`);
        }
        finally {
            setLoading(false);
        }
    };
    return <div className="content">
        <PageHeader eyebrow="Designer / Evidence assistant" title="AI Assistant" detail="Ask against indexed AICTE PDFs stored in MongoDB Atlas Vector Search." />
        <div style={{ maxWidth: 980 }}>
            <SectionCard title="Conversation">
                <div className="rag-conversation" aria-live="polite">
                    {!messages.length && <div className="rag-empty"><Bot size={27} color="#8061ac" /><p>Start a grounded curriculum conversation</p><span>Ask about policies, course structure, outcomes, or assessment using the PDFs indexed by the Admin.</span></div>}
                    {messages.map((message, index) => <div className={`rag-message ${message.role}`} key={`${message.role}-${index}`}><span className="badge badge-slate">{message.role === 'user' ? 'You' : 'AI Assistant'}</span>{message.role === 'assistant' ? <RagAnswer content={message.content} /> : <p>{message.content}</p>}{message.role === 'assistant' && <button className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={async () => { try { await navigator.clipboard.writeText(message.content); notify('Response copied to clipboard.'); } catch { notify('Clipboard access is unavailable in this browser.'); } }} data-testid={`button-copy-ai-answer-${index}`}><Check size={14} /> Copy response</button>}</div>)}
                    {loading && <div className="rag-message assistant"><span className="badge badge-slate">AI Assistant</span><p className="muted">Searching indexed PDF vectors and preparing a grounded answerâ€¦</p></div>}
                </div>
                <form onSubmit={ask} style={{ display: 'flex', gap: 8, marginTop: 13 }}>
                    <input className="field" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question about the indexed curriculum documents." disabled={loading} data-testid="input-assistant-question" />
                    <button className="btn btn-primary icon-btn" aria-label="Send question" disabled={loading || !question.trim()} data-testid="button-ask-assistant"><Send size={15} /></button>
                </form>
            </SectionCard>
            <div style={{ marginTop: 16 }}>
                <SectionCard title="Chat history" action={<button className="btn" onClick={startNewChat} disabled={loading} data-testid="button-new-assistant-chat"><Plus size={14} /> New chat</button>}>
                    {chats.length ? <div className="chat-history-list" aria-label="Previous chats">
                        {chats.map((chat) => <button key={chat.id} type="button" className={`chat-history-item ${chat.id === activeChatId ? 'active' : ''}`} onClick={() => { setActiveChatId(chat.id); setQuestion(''); }} data-testid={`button-chat-history-${chat.id}`}>
                            <MessageSquareText size={15} /><span><strong>{chat.title}</strong><small>{chat.messages.length} messages Â· {new Date(chat.updatedAt).toLocaleDateString()}</small></span><ChevronRight size={15} />
                        </button>)}
                    </div> : <p className="muted" style={{ fontSize: 12, margin: 0 }}>Your completed conversations will appear here. Select one to continue where you left off.</p>}
                </SectionCard>
            </div>
            <div style={{ marginTop: 16 }}>
                <SectionCard title={sources.length ? 'Sources for the latest answer' : 'Sources will appear with the first answer'}>
                    {sources.length ? <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>{sources.map((source, index) => <SourceCard key={`${source.title}-${source.section}-${index}`} source={source} />)}</div> : <p className="muted" style={{ fontSize: 12, margin: 0 }}>The assistant only answers from chunks retrieved from the MongoDB Atlas vector collection.</p>}
                </SectionCard>
            </div>
        </div>
    </div>;
}
function ResourcePage() {
    const [subject, setSubject] = useState('');
    const [curriculumId, setCurriculumId] = useState('');
    const [curricula, setCurricula] = useState([]);
    const [filter, setFilter] = useState('All');
    const [results, setResults] = useState(null);
    const [saved, setSaved] = useState([]);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [initializing, setInitializing] = useState(true);
    const [error, setError] = useState('');
    useEffect(() => {
        Promise.all([mockService.getSavedResources(), mockService.getResourceSearchHistory()])
            .then(([resources, searches]) => { setSaved(resources); setHistory(searches); })
            .catch(e => setError(e.message || 'Unable to load saved resources.'))
            .finally(() => setInitializing(false));
        mockService.getDocuments()
            .then(documents => setCurricula(submittedCurriculumDocuments(documents)))
            .catch(e => setError(current => current || e.message || 'Unable to load your curriculum list.'));
    }, []);
    const search = async (value = subject) => {
        const query = value.trim();
        if (query.length < 2) { setError('Enter a subject with at least two characters.'); return; }
        setLoading(true); setError(''); setSubject(query);
        try {
            setResults(await mockService.searchResources(query));
            setHistory(await mockService.getResourceSearchHistory());
        } catch (e) {
            setError(e.message || 'Resource search failed.');
        } finally {
            setLoading(false);
        }
    };
    const filtered = (results?.resources || []).filter(resource => filter === 'All' || resource.resource_type.toLowerCase() === filter.toLowerCase().replace(/s$/, ''));
    const isSaved = resourceId => saved.some(item => item.resource_id === resourceId);
    const save = async resource => {
        try {
            const row = await mockService.saveResource({ ...resource, subject: results.subject, curriculum_id: curriculumId.trim() || null });
            setSaved(current => current.some(item => item.resource_id === row.resource_id) ? current : [row, ...current]);
        } catch (e) { setError(e.message || 'Unable to save this resource.'); }
    };
    const remove = async resourceId => {
        try { await mockService.removeSavedResource(resourceId); setSaved(current => current.filter(item => item.resource_id !== resourceId)); }
        catch (e) { setError(e.message || 'Unable to remove the saved resource.'); }
    };
    const card = (resource, savedCard = false) => <article className="surface" style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr auto', gap: 14 }} key={resource.resource_id}>
        <div><span className="eyebrow">{resource.resource_type} ? {resource.source}</span><h3 className="font-display" style={{ fontSize: 15, margin: '6px 0' }}>{resource.title}</h3><p className="muted" style={{ fontSize: 11, margin: '4px 0' }}>{resource.author || 'Author not listed'}{resource.publisher ? ` ? ${resource.publisher}` : ''}{resource.publication_year ? ` ? ${resource.publication_year}` : ''}</p>{resource.description && <p style={{ fontSize: 12, lineHeight: 1.5, margin: '8px 0' }}>{resource.description}</p>}{resource.topics?.length > 0 && <p className="muted" style={{ fontSize: 10, margin: '6px 0' }}>Topics: {resource.topics.join(' ? ')}</p>}<small className="muted">{resource.availability}</small></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, alignItems: 'stretch' }}><a className="btn" href={resource.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open source</a>{savedCard || isSaved(resource.resource_id) ? <button className="btn" onClick={() => void remove(resource.resource_id)}><Trash2 size={14} /> Remove saved</button> : <button className="btn btn-primary" onClick={() => void save(resource)}><BookMarked size={14} /> Save resource</button>}</div>
    </article>;
    return <div className="content">
        <PageHeader eyebrow="Designer / Resource assistant" title="Find learning resources" detail="Search live book, scholarly, repository, and video catalogs by subject." />
        <SectionCard title="Search by subject"><form onSubmit={event => { event.preventDefault(); void search(); }} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 9, alignItems: 'end' }}><div><label className="label" htmlFor="resource-subject">Enter subject name</label><input id="resource-subject" className="field" value={subject} onChange={event => setSubject(event.target.value)} placeholder="Artificial Intelligence, Data Structures?" data-testid="input-resource-subject" /></div><div><label className="label" htmlFor="resource-curriculum">Associate saved resources (optional)</label><select id="resource-curriculum" className="select" value={curriculumId} onChange={event => setCurriculumId(event.target.value)}><option value="">Subject only</option>{[...new Map(curricula.map(item => [item.curriculum_id, item])).values()].map(item => <option key={item.curriculum_id} value={item.curriculum_id}>{item.curriculum_id} ? {item.filename}</option>)}</select></div><button className="btn btn-primary" type="submit" disabled={loading || initializing || subject.trim().length < 2}><Search size={14} /> {loading ? 'Searching?' : 'Search'}</button></form>{history.length > 0 && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 12 }}><span className="eyebrow" style={{ alignSelf: 'center' }}>Recent searches</span>{history.slice(0, 8).map(item => <button className="btn btn-ghost" key={`${item.subject}-${item.searched_at}`} onClick={() => void search(item.subject)}>{item.subject}</button>)}</div>}</SectionCard>
        {error && <div className="surface" role="alert" style={{ padding: 12, marginTop: 12 }}>{error}</div>}
        {results?.source_errors?.length > 0 && <div className="surface" role="status" style={{ padding: 12, marginTop: 12 }}>{results.source_errors.map(item => item.message).join(' ')}</div>}
        {results && <div style={{ marginTop: 15 }}><div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 10 }}>{['All', 'Books', 'Research Papers', 'Articles', 'Videos', 'Practical Resources'].map(item => <button key={item} className={`btn ${filter === item ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setFilter(item)}>{item}</button>)}</div>{loading ? <div className="surface" style={{ padding: 20 }}>Searching resource catalogs?</div> : filtered.length ? <div style={{ display: 'grid', gap: 9 }}>{filtered.map(resource => card(resource))}</div> : <div className="surface" style={{ padding: 20 }}><p className="muted" style={{ margin: 0 }}>No resources of this type were returned for ?{results.subject}?. Try another filter or search term.</p></div>}</div>}
        <div style={{ marginTop: 18 }}><SectionCard title={`Saved resources${saved.length ? ` ? ${saved.length}` : ''}`}>{initializing ? <p className="muted">Loading saved resources?</p> : saved.length ? <div style={{ display: 'grid', gap: 9 }}>{saved.map(item => card(item, true))}</div> : <p className="muted" style={{ fontSize: 12 }}>Resources you save will appear here for this Designer account.</p>}</SectionCard></div>
    </div>;
}
function ComparisonPage() {
    const [items, setItems] = useState([]);
    const [curriculumId, setCurriculumId] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try {
            const rows = await mockService.getImprovementHistory();
            setItems(rows);
            setCurriculumId(current => rows.some(row => row.curriculum_id === current) ? current : rows[0]?.curriculum_id || '');
        } catch (e) { setError(e.message || 'Unable to load stored curriculum analyses.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const item = items.find(row => row.curriculum_id === curriculumId);
    const versions = item?.versions || [];
    const maxScore = Math.max(1, ...versions.map(row => Number(row.score) || 0));
    return <div className="content"><PageHeader eyebrow="Designer / Version comparison" title="Curriculum comparison" detail="Compare analyzer scores and findings from saved submission versions." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading stored analyses…</div> : !items.length ? <div className="surface" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>Version comparison appears after a Reviewer analyzes submitted curricula.</p></div> : <>
            <div className="surface" style={{ padding: 9, display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>{items.map(row => <button key={row.curriculum_id} className={`btn ${row.curriculum_id === curriculumId ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setCurriculumId(row.curriculum_id)}>{row.curriculum_name}</button>)}</div>
            {item && <SectionCard title={`${item.curriculum_name} · saved analyzer history`}>
                {versions.length > 1 && <div className="version-score-chart" aria-label="Stored analyzer score by submitted version">{versions.map(row => <div className="version-score-column" key={row.submission_id}><div className="version-score-value">{row.score == null ? '—' : row.score}</div><div className="version-score-bar"><span style={{ height: `${Math.max(0, Math.min(100, ((Number(row.score) || 0) / maxScore) * 100))}%` }} /></div><strong>v{row.version}</strong></div>)}</div>}
                <div className="table-scroll"><table className="data-table"><thead><tr><th>Version</th><th>Analysis date</th><th>Score</th><th>Change</th><th>Resolved findings</th><th>Open findings</th><th>New findings</th></tr></thead><tbody>{versions.map((row, index) => { const prior = versions[index - 1]; const delta = prior?.score != null && row.score != null ? Number((row.score - prior.score).toFixed(2)) : null; const findings = row.finding_snapshot || []; return <tr key={row.submission_id}><td>v{row.version}</td><td>{formatDocumentDate(row.analyzed_at)}</td><td>{row.score == null ? 'Not evaluated' : row.score}</td><td>{delta == null ? 'Baseline' : `${delta > 0 ? '+' : ''}${delta}`}</td><td>{findings.filter(finding => finding.status === 'Resolved').length}</td><td>{findings.filter(finding => ['Open', 'In Progress', 'Reopened', 'Newly Detected'].includes(finding.status)).length}</td><td>{findings.filter(finding => finding.status === 'Newly Detected').length}</td></tr>; })}</tbody></table></div>
                {versions.length === 1 && <p className="muted" style={{ fontSize: 11 }}>One analyzed version is stored; comparison will appear when another version is analyzed.</p>}
            </SectionCard>}
        </>}
    </div>;
}
function displayAnalyzerValue(value) {
    if (value == null || value === '')
        return 'Not available';
    if (typeof value === 'object')
        return JSON.stringify(value, null, 2);
    return String(value);
}

function DecisionRecommendationPanel({ support }) {
    if (!support) return null;
    const title = support.decision === 'INSUFFICIENT_EVIDENCE'
        ? 'Insufficient Evidence — Manual Review Required'
        : `Recommended: ${support.decision}`;
    const badgeClass = support.decision === 'ACCEPT' ? 'badge-green' : support.decision === 'REJECT' ? 'badge-red' : 'badge-amber';
    return <section className="surface" style={{ padding: 16, margin: '14px 0' }} data-testid="decision-support-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}><h2 className="font-display" style={{ fontSize: 17, margin: 0 }}>Reviewer decision support</h2><span className={`badge ${badgeClass}`}>{title}</span></div>
        <p style={{ fontSize: 12, lineHeight: 1.6 }}>{support.summary}</p>
        <p className="muted" style={{ fontSize: 10 }}>Advisory evidence summary. The Reviewer makes and records the final decision.</p>
        {support.reasons?.length > 0 ? <div style={{ display: 'grid', gap: 9 }}>{support.reasons.map((reason, index) => <article className="surface" style={{ padding: 11 }} key={`${reason.finding_id}-${index}`}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}><strong style={{ fontSize: 12 }}>{reason.title}</strong><span className="badge badge-amber">{reason.severity}</span><span className="muted" style={{ fontSize: 10 }}>{reason.criterion} · {reason.rule_type}</span></div>
            <p style={{ fontSize: 11, margin: '7px 0' }}>{reason.explanation}</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 9 }}><div><span className="eyebrow">Expected</span><p style={{ fontSize: 11, margin: '4px 0' }}>{displayAnalyzerValue(reason.expected)}</p></div><div><span className="eyebrow">Observed</span><p style={{ fontSize: 11, margin: '4px 0' }}>{displayAnalyzerValue(reason.actual)}</p></div><div><span className="eyebrow">Recommended correction</span><p style={{ fontSize: 11, margin: '4px 0' }}>{reason.recommended_action}</p></div></div>
            {[...(reason.curriculum_evidence || []).map(row => ({ ...row, kind: 'Curriculum evidence' })), ...(reason.aicte_evidence || []).map(row => ({ ...row, kind: 'AICTE reference' }))].map((row, rowIndex) => <p key={`${row.kind}-${rowIndex}`} className="muted" style={{ fontSize: 10, margin: '7px 0 0' }}><strong>{row.kind}{row.page_number != null ? ` · p. ${row.page_number}` : ''}:</strong> {row.excerpt}</p>)}
        </article>)}</div> : <p className="muted" style={{ fontSize: 11 }}>No failed or partial findings were returned. Confirm evidence and policy manually.</p>}
    </section>;
}

function DesignerChanges({ notify, reviewer = false }) {
    const [requests, setRequests] = useState([]);
    const [statusFilter, setStatusFilter] = useState('All');
    const [curriculumFilter, setCurriculumFilter] = useState('All');
    const [responses, setResponses] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState('');
    const [, setLocation] = useLocation();
    const load = async () => {
        setLoading(true); setError('');
        try { setRequests(await mockService.getChangeRequests()); }
        catch (e) { setError(e.message || 'Unable to load review requests.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const curriculumOptions = [...new Map(requests.map(item => [item.curriculum_id, item.curriculum_name])).entries()];
    const visible = requests.filter(item => (statusFilter === 'All' || item.status === statusFilter) && (curriculumFilter === 'All' || item.curriculum_id === curriculumFilter));
    const update = async item => {
        setBusy(item.request_id); setError('');
        try {
            const result = await mockService.updateChangeRequest(item.submission_id, item.review_id, item.request_id, { status: 'In Progress', response: responses[item.request_id] || '' });
            setRequests(current => current.map(row => row.request_id === item.request_id ? { ...row, ...result } : row));
            setResponses(current => ({ ...current, [item.request_id]: '' }));
            notify('Response saved to this review request.');
        } catch (e) { setError(e.message || 'Unable to save your response.'); }
        finally { setBusy(''); }
    };
    const openRevision = item => {
        const version = Number(item.curriculum_version || 1) + 1;
        const query = new URLSearchParams({ curriculum_id: item.curriculum_id, version: `${version}.0`, request_id: item.request_id });
        setLocation(`/designer/create?${query}`);
    };
    const statuses = ['Pending Designer Action', 'In Progress', 'Resubmitted', 'Under Re-review', 'Resolved', 'Reopened', 'Closed'];
    return <div className="content">
        <PageHeader eyebrow={reviewer ? 'Reviewer / Follow-up' : 'Designer / Next version inputs'} title="Change requests" detail={reviewer ? 'Track whether requested corrections have been addressed in a new submitted version.' : 'Review feedback, record your response, and prepare a corrected version.'} action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        <div className="surface" style={{ display: 'flex', flexWrap: 'wrap', gap: 9, padding: 12, marginBottom: 12 }}><label><span className="label">Curriculum</span><select className="select" value={curriculumFilter} onChange={event => setCurriculumFilter(event.target.value)}><option value="All">All curricula</option>{curriculumOptions.map(([id, name]) => <option key={id} value={id}>{name} ? {id}</option>)}</select></label><label><span className="label">Status</span><select className="select" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option>All</option>{statuses.map(status => <option key={status}>{status}</option>)}</select></label></div>
        {loading ? <div className="surface" style={{ padding: 22 }}>Loading change requests?</div> : !visible.length ? <div className="surface" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>No requests match these filters.</p></div> : <div style={{ display: 'grid', gap: 11 }}>{visible.map(item => <article className="surface" style={{ padding: 17 }} key={item.request_id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}><div><span className="eyebrow">{item.decision_type === 'reject' ? 'REJECTION RECORD' : 'REVISION REQUEST'} ? {item.priority} priority</span><h3 className="font-display" style={{ fontSize: 16, margin: '6px 0' }}>{item.curriculum_name}</h3><p className="muted" style={{ fontSize: 10, margin: 0 }}>Curriculum {item.curriculum_id} ? submission v{item.curriculum_version} ? {formatDocumentDate(item.decision_date)}</p></div><StatusBadge status={item.status} /></div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12, marginTop: 12 }}><div><span className="eyebrow">Finding</span><p style={{ fontSize: 12 }}>{item.issue}</p></div><div><span className="eyebrow">{item.source === 'Institute Representative' ? 'Institution explanation' : 'Reviewer explanation'}</span><p style={{ fontSize: 12 }}>{item.explanation || item.reviewer_feedback}</p></div><div><span className="eyebrow">Required correction</span><p style={{ fontSize: 12 }}>{item.required_corrective_action}</p></div></div>
            {item.supporting_evidence?.length > 0 && <details style={{ marginTop: 8 }}><summary className="btn btn-ghost" style={{ width: 'fit-content' }}>View evidence ({item.supporting_evidence.length})</summary><div style={{ display: 'grid', gap: 6, marginTop: 8 }}>{item.supporting_evidence.map((evidence, index) => <p className="surface" style={{ padding: 9, fontSize: 11, margin: 0 }} key={index}>{evidence.excerpt}{evidence.page_number != null ? ` ? Page ${evidence.page_number}` : ''}</p>)}</div></details>}
            {item.designer_response && <div className="surface" style={{ padding: 10, marginTop: 10 }}><span className="eyebrow">Designer response</span><p style={{ fontSize: 12, marginBottom: 0 }}>{item.designer_response}</p></div>}
            {item.resubmission_submission_id && <p className="muted" style={{ fontSize: 10 }}>Resubmitted as {item.resubmission_submission_id}</p>}
            {!reviewer && ['Pending Designer Action', 'In Progress', 'Reopened'].includes(item.status) && <div style={{ marginTop: 12 }}><label className="label" htmlFor={`response-${item.request_id}`}>Your response</label><textarea id={`response-${item.request_id}`} className="textarea" value={responses[item.request_id] ?? item.designer_response ?? ''} onChange={event => setResponses(current => ({ ...current, [item.request_id]: event.target.value }))} placeholder="Describe the correction you are making." /><div style={{ display: 'flex', gap: 8, marginTop: 8 }}><button className="btn btn-primary" disabled={!responses[item.request_id]?.trim() || Boolean(busy)} onClick={() => void update(item)}>{busy === item.request_id ? 'Saving?' : 'Save response / mark in progress'}</button>{item.decision_type !== 'reject' && <button className="btn" onClick={() => openRevision(item)}>Prepare revision</button>}</div></div>}
        </article>)}</div>}
    </div>;
}
function ImprovementTracker({ notify }) {
    const [items, setItems] = useState([]);
    const [curriculumId, setCurriculumId] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const load = async (announce = false) => {
        setLoading(true); setError('');
        try {
            const rows = await mockService.getImprovementHistory();
            setItems(rows);
            setCurriculumId(current => rows.some(row => row.curriculum_id === current) ? current : rows[0]?.curriculum_id || '');
            if (announce) notify('Improvement history refreshed from saved analyzer reports.');
        } catch (e) { setError(e.message || 'Unable to load analyzer history.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    useEffect(() => {
        const refresh = () => mockService.getImprovementHistory().then(setItems).catch(e => setError(e.message || 'Unable to refresh analyzer history.'));
        const interval = window.setInterval(refresh, 30000);
        window.addEventListener('focus', refresh);
        return () => { window.clearInterval(interval); window.removeEventListener('focus', refresh); };
    }, []);
    const item = items.find(row => row.curriculum_id === curriculumId);
    const versions = item?.versions || [];
    const latest = versions[versions.length - 1];
    const previous = versions.length > 1 ? versions[versions.length - 2] : null;
    const delta = latest?.score != null && previous?.score != null ? Number((latest.score - previous.score).toFixed(2)) : null;
    const formatScore = score => score == null ? 'Not evaluated' : `${score}`;
    return <div className="content">
        <PageHeader eyebrow="Designer / Continuous improvement" title="Improvement tracker" detail="Compare analyzer reports, findings, and reviewer decisions saved for each submitted version." action={<button className="btn" onClick={() => void load(true)} disabled={loading} data-testid="button-refresh-improvement"><RefreshCw size={14} /> Refresh history</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 24 }}>Loading saved analyzer history?</div> : !items.length ? <div className="surface" style={{ padding: 28 }} data-testid="improvement-empty"><h2 className="font-display" style={{ fontSize: 17 }}>No analyzed submissions yet</h2><p className="muted" style={{ fontSize: 12 }}>Scores and finding changes will appear after a Reviewer runs the Analyzer on a submitted version.</p></div> : <>
            <div className="surface" style={{ padding: 9, display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>{items.map(row => <button key={row.curriculum_id} className={`btn ${row.curriculum_id === curriculumId ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setCurriculumId(row.curriculum_id)}>{row.curriculum_name}</button>)}</div>
            {item && <>
                <div className="improvement-summary"><div className="surface improvement-score-card"><span className="eyebrow">Latest analyzer score</span><strong>{formatScore(item.latest_score)}{item.latest_score != null && <small>/100</small>}</strong><span className="muted">Version {latest?.version} ? {latest?.analyzed_at ? formatDocumentDate(latest.analyzed_at) : 'Date unavailable'}</span></div><div className="surface improvement-score-card positive"><span className="eyebrow">Total score change</span><strong>{item.total_improvement == null ? 'Not available' : `${item.total_improvement > 0 ? '+' : ''}${item.total_improvement}`}<small>{item.total_improvement == null ? '' : ' points'}</small></strong><span className="muted">Since version {versions[0]?.version}</span></div><div className="surface improvement-score-card"><span className="eyebrow">Last version change</span><strong>{delta == null ? 'Baseline' : `${delta > 0 ? '+' : ''}${delta}`}<small>{delta == null ? '' : ' points'}</small></strong><span className="muted">{previous ? `Since version ${previous.version}` : 'One analyzed version available'}</span></div></div>
                <div className="stat-grid" style={{ marginTop: 12 }}><StatCard label="Resolved findings" value={item.resolved_findings.length} note="In the latest analyzed version" icon={CheckCircle2} /><StatCard label="Outstanding findings" value={item.latest_findings.length} note="Still open or reopened" icon={CircleAlert} /><StatCard label="New findings" value={item.new_findings.length} note="First seen in latest version" icon={Plus} /><StatCard label="Reopened findings" value={item.reopened_findings.length} note="Returned after earlier resolution" icon={RefreshCw} /></div>
                <SectionCard title={`${item.curriculum_name} ? analyzed version history`}>
                    {versions.length > 1 && <div className="version-score-chart" aria-label="Stored analyzer score by submitted version">{versions.map(row => <div className="version-score-column" key={row.submission_id}><div className="version-score-value">{row.score == null ? '?' : row.score}</div><div className="version-score-bar"><span style={{ height: `${Math.max(0, Math.min(100, Number(row.score) || 0))}%` }} /></div><strong>v{row.version}</strong></div>)}</div>}
                    <div className="table-scroll"><table className="data-table"><thead><tr><th>Version</th><th>Score</th><th>Change</th><th>Resolved</th><th>Remaining</th><th>Analysis date</th><th>Review status</th></tr></thead><tbody>{versions.map((row, index) => { const before = index ? versions[index - 1] : null; const change = before?.score != null && row.score != null ? Number((row.score - before.score).toFixed(2)) : null; const open = (row.finding_snapshot || []).filter(f => ['Open', 'Reopened', 'Newly Detected', 'In Progress'].includes(f.status)).length; const resolved = (row.finding_snapshot || []).filter(f => f.status === 'Resolved').length; return <tr key={row.submission_id}><td><strong>v{row.version}</strong></td><td>{formatScore(row.score)}</td><td>{change == null ? 'Baseline' : `${change > 0 ? '+' : ''}${change}`}</td><td>{resolved}</td><td>{open}</td><td>{formatDocumentDate(row.analyzed_at)}</td><td><StatusBadge status={row.status} /></td></tr>; })}</tbody></table></div>
                </SectionCard>
                <div style={{ marginTop: 14 }}><SectionCard title="Reviewer decisions and feedback">{versions.flatMap(row => (row.review_history || []).map(review => ({ ...review, version: row.version, submission_id: row.submission_id }))).length ? <div style={{ display: 'grid', gap: 8 }}>{versions.flatMap(row => (row.review_history || []).map(review => ({ ...review, version: row.version, submission_id: row.submission_id }))).map((review, index) => <div className="surface" style={{ padding: 11 }} key={`${review.submission_id}-${review.review_id || index}`}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong style={{ fontSize: 11 }}>v{review.version} · {review.status}</strong><span className="muted" style={{ fontSize: 10 }}>{formatDocumentDate(review.decided_at)}</span></div><p style={{ fontSize: 11, margin: '6px 0 0' }}>{review.feedback || 'No additional reviewer feedback.'}</p>{review.decision_justification && <p className="muted" style={{ fontSize: 10, margin: '5px 0 0' }}>Decision justification: {review.decision_justification}</p>}</div>)}</div> : <p className="muted" style={{ fontSize: 12 }}>No reviewer decisions are stored for these analyzed versions.</p>}</SectionCard></div>
                <div style={{ marginTop: 14 }}><SectionCard title="Latest finding status">{item.latest_findings.length || item.resolved_findings.length ? <div style={{ display: 'grid', gap: 8 }}>{[...item.latest_findings, ...item.resolved_findings].map(finding => <div className="surface" style={{ padding: 12 }} key={`${finding.finding_id}-${finding.status}`}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 9 }}><strong style={{ fontSize: 12 }}>{finding.original_issue}</strong><StatusBadge status={finding.status} /></div><p className="muted" style={{ fontSize: 10, marginBottom: 0 }}>Finding {finding.finding_id} ? First seen v{finding.first_detected_version}{finding.resolved_in_version ? ` ? Resolved v${finding.resolved_in_version}` : ''}</p>{finding.resolution_evidence?.map((evidence, index) => <p key={index} style={{ fontSize: 11, marginBottom: 0 }}>{evidence.excerpt}</p>)}</div>)}</div> : <p className="muted" style={{ fontSize: 12 }}>No failed or partial checks were recorded in the latest report.</p>}</SectionCard></div>
            </>}
        </>}
    </div>;
}
function PublishedPage() { return <PublishedCurriculaPage audience="Designer" />; }
function InstituteCurricula() { return <PublishedCurriculaPage audience="Institute" />; }
function PublishedCurriculaPage({ audience }) {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [expanded, setExpanded] = useState('');
    const [, setLocation] = useLocation();
    const load = async () => { setLoading(true); setError(''); try { setItems(await mockService.getPublishedCurricula()); } catch (e) { setError(e.message || 'Unable to load published curricula.'); } finally { setLoading(false); } };
    useEffect(() => { void load(); }, []);
    const openPdf = async item => { try { const url = await mockService.getSubmissionDocument(item.submission_id); window.open(url, '_blank', 'noopener,noreferrer'); } catch (e) { setError(e.message || 'Unable to open the published PDF.'); } };
    return <div className="content"><PageHeader eyebrow={`${audience} / Published curricula`} title={audience === 'Institute' ? 'Available curricula' : 'Published curricula'} detail="Only versions explicitly published by the Institute Representative appear here." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />{error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}{loading ? <div className="surface" style={{ padding: 22 }}>Loading published curricula…</div> : !items.length ? <div className="surface" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>No curricula have been published to this workspace.</p></div> : <div style={{ display: 'grid', gap: 10 }}>{items.map(item => <article className="surface" style={{ padding: 17 }} key={item.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}><div><h2 className="font-display" style={{ fontSize: 16, margin: '0 0 6px' }}>{item.curriculum_name}</h2><p className="muted" style={{ fontSize: 11, margin: 0 }}>Version {item.version} · Published {formatDocumentDate(item.published_at)}</p></div><StatusBadge status="Published" /></div><div style={{ display: 'flex', gap: 8, marginTop: 12 }}><button className="btn" onClick={() => void openPdf(item)}><Eye size={14} /> View PDF</button><button className="btn" onClick={() => setExpanded(expanded === item.curriculum_id ? '' : item.curriculum_id)}><History size={14} /> {expanded === item.curriculum_id ? 'Hide history' : 'Version history'}</button>{audience === 'Institute' && <button className="btn" onClick={() => setLocation('/institute/courses')}>View courses</button>}</div>{expanded === item.curriculum_id && <div className="surface" style={{ padding: 10, marginTop: 10 }}><strong style={{ fontSize: 11 }}>Published versions</strong><p className="muted" style={{ fontSize: 10, margin: '5px 0 0' }}>{items.filter(version => version.curriculum_id === item.curriculum_id).map(version => `v${version.version} · ${formatDocumentDate(version.published_at)}`).join(' | ')}</p></div>}</article>)}</div>}</div>;
}
function InstituteCourses() {
    const [items, setItems] = useState([]);
    const [structures, setStructures] = useState({});
    const [expanded, setExpanded] = useState('');
    const [loading, setLoading] = useState(true);
    const [loadingId, setLoadingId] = useState('');
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try { setItems(await mockService.getPublishedCurricula()); }
        catch (e) { setError(e.message || 'Unable to load published curriculum outlines.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const showCourses = async item => {
        if (expanded === item.submission_id) { setExpanded(''); return; }
        setExpanded(item.submission_id);
        if (structures[item.submission_id]) return;
        setLoadingId(item.submission_id); setError('');
        try {
            const structure = await mockService.getPublishedCurriculumStructure(item.submission_id);
            setStructures(current => ({ ...current, [item.submission_id]: structure }));
        } catch (e) { setError(e.message || 'Unable to extract courses from this published PDF.'); }
        finally { setLoadingId(''); }
    };
    const openPdf = async item => {
        try { const url = await mockService.getSubmissionDocument(item.submission_id); window.open(url, '_blank', 'noopener,noreferrer'); }
        catch (e) { setError(e.message || 'Unable to open the published curriculum PDF.'); }
    };
    return <div className="content"><PageHeader eyebrow="Institute / Published courses" title="My courses" detail="Course outlines are extracted from curricula published to your institution." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading published curricula?</div> : !items.length ? <div className="surface" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>No published curriculum is available to this institution yet.</p></div> : <div style={{ display: 'grid', gap: 10 }}>{items.map(item => {
            const structure = structures[item.submission_id];
            const courses = [...(structure?.courses || []), ...(structure?.professional_electives || []), ...(structure?.open_electives || []), ...(structure?.projects || []), ...(structure?.internships || []), ...(structure?.mandatory_courses || [])];
            return <article className="surface" style={{ padding: 16 }} key={item.submission_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}><div><h2 className="font-display" style={{ fontSize: 15, margin: '0 0 5px' }}>{item.curriculum_name}</h2><span className="muted" style={{ fontSize: 11 }}>Version {item.version} ? Published {formatDocumentDate(item.published_at)}</span></div><StatusBadge status="Published" /></div><div style={{ display: 'flex', gap: 8, marginTop: 11 }}><button className="btn" onClick={() => void openPdf(item)}><Eye size={14} /> Open PDF</button><button className="btn" onClick={() => void showCourses(item)} disabled={loadingId === item.submission_id}><BookOpen size={14} /> {loadingId === item.submission_id ? 'Extracting?' : expanded === item.submission_id ? 'Hide course outline' : 'View course outline'}</button></div>{expanded === item.submission_id && <div className="surface" style={{ padding: 11, marginTop: 10 }}>{loadingId === item.submission_id ? <p className="muted">Extracting course details from this version?</p> : structure && (courses.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Course</th><th>Code</th><th>Semester</th><th>Category</th><th>Credits</th></tr></thead><tbody>{courses.map((course, index) => <tr key={`${course.course_code || course.course_title}-${index}`}><td>{course.course_title}</td><td>{course.course_code || '?'}</td><td>{course.semester || '?'}</td><td>{course.category || '?'}</td><td>{course.credits ?? '?'}</td></tr>)}</tbody></table></div> : <p className="muted" style={{ margin: 0 }}>No courses could be extracted from this PDF version. Open the original to review its contents.</p>)}</div>}</article>;
        })}</div>}
    </div>;
}
function Coordinators() {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    useEffect(() => {
        mockService.getAccountProfile().then(setProfile).catch(e => setError(e.message || 'Unable to load institution details.')).finally(() => setLoading(false));
    }, []);
    return <div className="content"><PageHeader eyebrow="Institute / Delivery ownership" title="Course coordinators" detail="Coordinator assignments are not configured in this workspace." />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading institution details?</div> : <SectionCard title="Coordinator directory"><p className="muted" style={{ fontSize: 12, margin: 0 }}>No faculty directory or coordinator assignment records are available for {profile?.institute_name || 'this institution'}. No names or assignments are shown until they are provided through a supported account workflow.</p></SectionCard>}
    </div>;
}
function ChangeRequests({ notify }) {
    const [curricula, setCurricula] = useState([]);
    const [submissionId, setSubmissionId] = useState('');
    const [category, setCategory] = useState('Course coverage');
    const [observation, setObservation] = useState('');
    const [suggestion, setSuggestion] = useState('');
    const [priority, setPriority] = useState('Medium');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try {
            const rows = await mockService.getPublishedCurricula();
            setCurricula(rows);
            setSubmissionId(current => rows.some(row => row.submission_id === current) ? current : rows[0]?.submission_id || '');
        } catch (e) { setError(e.message || 'Unable to load published curricula.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const requests = curricula.flatMap(item => (item.institution_feedback || []).filter(row => row.kind === 'change_request').map(row => ({ ...row, ...item })));
    const submit = async event => {
        event.preventDefault(); setSaving(true); setError('');
        try {
            await mockService.submitInstituteFeedback(submissionId, { kind: 'change_request', category, observation, suggested_change: suggestion, priority });
            setObservation(''); setSuggestion(''); await load(); notify('Change request saved for the Designer.');
        } catch (e) { setError(e.message || 'Unable to save this change request.'); }
        finally { setSaving(false); }
    };
    return <div className="content"><PageHeader eyebrow="Institute / Curriculum feedback loop" title="Change requests" detail="Send evidence-based requests for a published version. The Designer sees them in the matching curriculum." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading published curricula...</div> : <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <SectionCard title="Request a curriculum change">{curricula.length ? <form onSubmit={submit}>
                <label className="label" htmlFor="change-curriculum">Published curriculum</label><select id="change-curriculum" className="select" required value={submissionId} onChange={e => setSubmissionId(e.target.value)}>{curricula.map(item => <option key={item.submission_id} value={item.submission_id}>{item.curriculum_name} ? v{item.version}</option>)}</select>
                <label className="label" style={{ marginTop: 12 }}>Category</label><select className="select" value={category} onChange={e => setCategory(e.target.value)}><option>Course coverage</option><option>Assessment design</option><option>Learning outcomes</option><option>Practical resources</option><option>Other</option></select>
                <label className="label" style={{ marginTop: 12 }}>Observation and evidence</label><textarea className="textarea" required value={observation} onChange={e => setObservation(e.target.value)} placeholder="Describe what should change and why." />
                <label className="label" style={{ marginTop: 12 }}>Suggested change</label><textarea className="textarea" required value={suggestion} onChange={e => setSuggestion(e.target.value)} placeholder="Describe a practical correction." />
                <label className="label" style={{ marginTop: 12 }}>Priority</label><select className="select" value={priority} onChange={e => setPriority(e.target.value)}><option>High</option><option>Medium</option><option>Low</option></select>
                <button className="btn btn-primary" style={{ width: '100%', marginTop: 15 }} disabled={saving || !submissionId}><Send size={14} /> {saving ? 'Saving...' : 'Submit change request'}</button>
            </form> : <p className="muted" style={{ fontSize: 12 }}>Publish an accepted curriculum before submitting an institutional change request.</p>}</SectionCard>
            <SectionCard title="Submitted requests">{requests.length ? <div style={{ display: 'grid', gap: 8 }}>{requests.map(item => <div className="surface" style={{ padding: 11 }} key={item.feedback_id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong style={{ fontSize: 12 }}>{item.curriculum_name} ? v{item.version}</strong><StatusBadge status={item.status} /></div><p style={{ fontSize: 11 }}>{item.observation}</p><p className="muted" style={{ fontSize: 10, marginBottom: 0 }}>Suggested change: {item.suggested_change}</p></div>)}</div> : <p className="muted" style={{ fontSize: 12 }}>No institutional change requests have been submitted.</p>}</SectionCard>
        </div>}
    </div>;
}
function Feedback({ notify }) {
    const [curricula, setCurricula] = useState([]);
    const [submissionId, setSubmissionId] = useState('');
    const [category, setCategory] = useState('Course coverage');
    const [observation, setObservation] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try {
            const rows = await mockService.getPublishedCurricula();
            setCurricula(rows);
            setSubmissionId(current => rows.some(row => row.submission_id === current) ? current : rows[0]?.submission_id || '');
        } catch (e) { setError(e.message || 'Unable to load published curricula.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const feedback = curricula.flatMap(item => (item.institution_feedback || []).filter(row => row.kind === 'feedback').map(row => ({ ...row, ...item })));
    const submit = async event => {
        event.preventDefault(); setSaving(true); setError('');
        try {
            await mockService.submitInstituteFeedback(submissionId, { kind: 'feedback', category, observation });
            setObservation(''); await load(); notify('Feedback saved for this published curriculum.');
        } catch (e) { setError(e.message || 'Unable to save feedback.'); }
        finally { setSaving(false); }
    };
    return <div className="content"><PageHeader eyebrow="Institute / Delivery feedback" title="Feedback" detail="Share delivery observations with the Designer of a published curriculum." action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading published curricula...</div> : <div style={{ maxWidth: 760 }}>
            <SectionCard title="Share delivery feedback">{curricula.length ? <form onSubmit={submit}>
                <label className="label" htmlFor="feedback-curriculum">Curriculum</label><select id="feedback-curriculum" className="select" required value={submissionId} onChange={e => setSubmissionId(e.target.value)}>{curricula.map(item => <option key={item.submission_id} value={item.submission_id}>{item.curriculum_name} ? v{item.version}</option>)}</select>
                <label className="label" style={{ marginTop: 12 }}>Feedback category</label><select className="select" value={category} onChange={e => setCategory(e.target.value)}><option>Course coverage</option><option>Assessment design</option><option>Resources</option><option>Learning outcomes</option><option>Other</option></select>
                <label className="label" style={{ marginTop: 12 }}>Your observation</label><textarea className="textarea" required value={observation} onChange={e => setObservation(e.target.value)} placeholder="Describe the delivery experience and supporting evidence." />
                <button className="btn btn-primary" style={{ marginTop: 15 }} disabled={saving || !submissionId}><Send size={14} /> {saving ? 'Saving...' : 'Share feedback'}</button>
            </form> : <p className="muted" style={{ fontSize: 12 }}>Feedback is available after a curriculum has been published.</p>}</SectionCard>
            <div style={{ marginTop: 14 }}><SectionCard title="Recent feedback">{feedback.length ? <div style={{ display: 'grid', gap: 8 }}>{feedback.map(item => <div className="surface" style={{ padding: 11 }} key={item.feedback_id}><strong style={{ fontSize: 12 }}>{item.curriculum_name} ? v{item.version} ? {item.category}</strong><p style={{ fontSize: 11, marginBottom: 0 }}>{item.observation}</p><span className="muted" style={{ fontSize: 10 }}>{formatDocumentDate(item.created_at)}</span></div>)}</div> : <p className="muted" style={{ fontSize: 12 }}>No delivery feedback recorded yet.</p>}</SectionCard></div>
        </div>}
    </div>;
}
function Notifications({ notify }) {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [, setLocation] = useLocation();
    const load = () => mockService.getNotifications().then(setItems).catch(e => setError(e.message || 'Unable to load notifications.')).finally(() => setLoading(false));
    useEffect(() => { void load(); }, []);
    const markAllRead = async () => {
        try { await mockService.markAllNotificationsRead(); await load(); notify('Notifications marked as read.'); }
        catch (e) { setError(e.message || 'Unable to update notifications.'); }
    };
    const open = async item => {
        try {
            if (!item.read) await mockService.markNotificationRead(item.notification_id);
            await load();
            const role = roleFromPath(window.location.pathname);
            setLocation(role === 'reviewer' ? '/reviewer/reviews' : role === 'designer' ? '/designer/curricula' : role === 'institute' ? '/institute/submit' : '/admin/reviews');
        } catch (e) { setError(e.message || 'Unable to open this notification.'); }
    };
    return <div className="content"><PageHeader eyebrow="Workspace" title="Notifications" action={<button className="btn" onClick={() => void markAllRead()} disabled={loading || !items.some(item => !item.read)} data-testid="button-mark-all-read"><Check size={14} /> Mark all read</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 10 }}>{error} <button className="btn" onClick={() => { setLoading(true); void load(); }}>Retry</button></div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading notifications…</div> : items.length === 0 ? <div className="surface" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>No workflow notifications yet.</p></div> : <div style={{ display: 'grid', gap: 9 }}>{items.map(item => <button key={item.notification_id} className="surface" style={{ textAlign: 'left', padding: 16, display: 'flex', gap: 13, alignItems: 'flex-start', borderLeft: !item.read ? '3px solid #9070bf' : undefined }} onClick={() => void open(item)}><span className="brand-mark" style={{ width: 32, height: 32, borderRadius: 10, flexShrink: 0 }}><Bell size={14} /></span><span style={{ flex: 1 }}><strong style={{ display: 'block', fontSize: 12 }}>{item.title}</strong><span className="muted" style={{ display: 'block', fontSize: 11, marginTop: 5 }}>{item.message}</span><span className="muted" style={{ display: 'block', fontSize: 10, marginTop: 9 }}>{formatDocumentDate(item.created_at)}</span></span>{!item.read && <span className="badge badge-lavender">New</span>}</button>)}</div>}
    </div>;
}
function SettingsPage({ notify }) {
    const [profile, setProfile] = useState(null);
    const [timezone, setTimezone] = useState('Asia/Kolkata');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const load = async () => {
        setLoading(true); setError('');
        try {
            const result = await mockService.getAccountProfile();
            setProfile(result);
            const zone = result.preferences?.timezone || 'Asia/Kolkata';
            setTimezone(zone); localStorage.setItem('aicte-timezone', zone);
        } catch (e) { setError(e.message || 'Unable to load account settings.'); }
        finally { setLoading(false); }
    };
    useEffect(() => { void load(); }, []);
    const save = async () => {
        setSaving(true); setError('');
        try {
            const result = await mockService.updateAccountPreferences({ timezone });
            setProfile(result);
            const zone = result.preferences?.timezone || timezone;
            setTimezone(zone); localStorage.setItem('aicte-timezone', zone);
            notify('Time zone preference saved.');
        } catch (e) { setError(e.message || 'Unable to save the time zone.'); }
        finally { setSaving(false); }
    };
    return <div className="content"><PageHeader eyebrow="Workspace / Preferences" title="Settings" action={<button className="btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</button>} />
        {error && <div className="surface" role="alert" style={{ padding: 12, marginBottom: 12 }}>{error}</div>}
        {loading ? <div className="surface" style={{ padding: 20 }}>Loading account settings?</div> : profile && <div style={{ maxWidth: 760, display: 'grid', gap: 14 }}>
            <SectionCard title="Account"><div className="form-grid"><div><span className="label">Name</span><p>{profile.name}</p></div><div><span className="label">Email</span><p>{profile.email}</p></div><div><span className="label">Role</span><p>{profile.role}</p></div><div><span className="label">Institution</span><p>{profile.institute_name || 'Not linked'}</p></div></div></SectionCard>
            <SectionCard title="Workspace preferences"><label className="label" htmlFor="settings-timezone">Time zone</label><select id="settings-timezone" className="select" value={timezone} onChange={event => setTimezone(event.target.value)}><option value="Asia/Kolkata">Asia/Kolkata</option><option value="UTC">UTC</option><option value="Europe/London">Europe/London</option><option value="America/New_York">America/New_York</option></select><p className="muted" style={{ fontSize: 11 }}>Dates throughout the workspace use this time zone.</p><button className="btn btn-primary" style={{ marginTop: 12 }} onClick={() => void save()} disabled={saving}><Save size={14} /> {saving ? 'Saving?' : 'Save time zone'}</button></SectionCard>
        </div>}
    </div>;
}
function Modal({ title, onClose, children, wide = false }) {
    return <div style={{ position: 'fixed', inset: 0, zIndex: 45, background: 'rgba(43,28,59,.35)', display: 'grid', placeItems: 'center', padding: 18 }}><div className="surface" style={{ width: wide ? 'min(900px, 100%)' : 'min(520px, 100%)', maxHeight: '90dvh', overflowY: 'auto', padding: 23 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}><h2 className="font-display" style={{ fontSize: 19, margin: 0 }}>{title}</h2><button className="btn icon-btn" onClick={onClose} data-testid="button-close-modal"><X size={16} /></button></div>{children}</div></div>;
}
export default App;
