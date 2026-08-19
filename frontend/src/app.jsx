import { useEffect, useState } from 'react';
import { Link, Router as WouterRouter, useLocation } from 'wouter';
import { Activity, ArrowLeft, ArrowRight, BarChart3, Bell, BookMarked, BookOpen, Bot, Building2, Check, CheckCircle, CheckCircle2, ChevronDown, ChevronRight, CircleAlert, ClipboardCheck, Clock3, ExternalLink, Eye, FileCheck2, FileText, Filter, FolderKanban, GraduationCap, History, Inbox, Landmark, LayoutDashboard, Lightbulb, ListChecks, LockKeyhole, LogOut, Menu, MessageSquareText, Network, Pencil, Plus, RefreshCw, Save, Search, Send, Settings, ShieldCheck, SlidersHorizontal, Sparkles, Trash2, Upload, UserCog, Users, X } from 'lucide-react';
import { analyzerScoreHistory, mockChanges, mockCurricula, mockService, mockUsers, sourceCards } from '@/lib/mock-services';
import { analyzerDocumentHref, analyzerDocumentKey, checkStatusLabel, coverageCalculation, criterionCalculation, criterionScoreLabel, documentScopeLabel, hasLowEvaluationCoverage, isPartialCurriculum, isPartialScopeExclusion, overallScoreLabel, requestedAnalyzerDocument, submittedCurriculumDocuments } from '@/lib/analyzer-utils';
const roles = {
    admin: { label: 'AICTE Admin', short: 'Admin', base: '/admin/dashboard', description: 'Authoritative governance and national oversight', icon: Landmark },
    reviewer: { label: 'Reviewer / Expert', short: 'Reviewer', base: '/reviewer/dashboard', description: 'Human review, evidence and final decisions', icon: ClipboardCheck },
    designer: { label: 'Curriculum Designer', short: 'Designer', base: '/designer/dashboard', description: 'Build, analyze and submit curriculum truth', icon: GraduationCap },
    institute: { label: 'Institute Representative', short: 'Institute', base: '/institute/dashboard', description: 'Published curricula, coordinators and feedback', icon: Building2 },
};
const permissions = {
    admin: ['documents.read', 'documents.create', 'documents.update', 'documents.delete', 'policies.read', 'policies.create', 'policies.update', 'institutes.read', 'institutes.create', 'users.manage', 'audit.read', 'curricula.read'],
    reviewer: ['curricula.read', 'reviews.read', 'reviews.decide', 'screening.read', 'published.read', 'policies.read', 'policies.manage'],
    designer: ['curricula.read', 'curricula.create', 'curricula.update', 'curricula.submit', 'ai.use', 'resources.use', 'comparison.use', 'analyzer.use', 'changes.respond', 'published.read'],
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
        { label: 'Curriculum Screener', href: '/reviewer/screener', icon: SlidersHorizontal, permission: 'screening.read' }, { label: 'Review History', href: '/reviewer/history', icon: History },
        { label: 'Policies', href: '/reviewer/policies', icon: ShieldCheck, permission: 'policies.read' }, { label: 'Approved Curricula', href: '/reviewer/approved', icon: CheckCircle2, permission: 'published.read' },
        { label: 'Settings', href: '/reviewer/settings', icon: Settings },
    ],
    designer: [
        { label: 'Dashboard', href: '/designer/dashboard', icon: LayoutDashboard }, { label: 'My Curricula', href: '/designer/curricula', icon: FolderKanban },
        { label: 'Create Curriculum', href: '/designer/create', icon: Plus, permission: 'curricula.create' }, { label: 'AI Assistant', href: '/designer/assistant', icon: Bot, permission: 'ai.use' },
        { label: 'Resource Assistant', href: '/designer/resources', icon: BookMarked, permission: 'resources.use' }, { label: 'Curriculum Comparison', href: '/designer/comparison', icon: Network, permission: 'comparison.use' },
        { label: 'Curriculum Analyzer', href: '/designer/analyzer', icon: BarChart3, permission: 'analyzer.use' }, { label: 'Change Requests', href: '/designer/changes', icon: RefreshCw },
        { label: 'Improvement Tracker', href: '/designer/improvements', icon: Activity, permission: 'curricula.update' },
        { label: 'Published Curricula', href: '/designer/published', icon: CheckCircle2, permission: 'published.read' },
        { label: 'Settings', href: '/designer/settings', icon: Settings },
    ],
    institute: [
        { label: 'Dashboard', href: '/institute/dashboard', icon: LayoutDashboard }, { label: 'Available Curricula', href: '/institute/curricula', icon: BookOpen, permission: 'published.read' },
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
        // The account record—not a client-selected role—determines the workspace.
        const next = await mockService.login(email, password);
        localStorage.setItem('aicte-demo-session', JSON.stringify(next));
        setSession(next);
        setSidebarOpen(false);
        setLocation(roles[next.role].base);
    };
    const logout = () => { localStorage.removeItem('aicte-demo-session'); setSession(null); setLocation('/login'); };
    if (location === '/login' || location === '/signup' || location === '/forgot-password' || location === '/reset-password') {
        return <AuthPage mode={location.slice(1)} onLogin={login}/>;
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
    return <AppShell session={session} role={expectedRole} path={location} open={sidebarOpen} setOpen={setSidebarOpen} onLogout={logout} notify={notify} toast={toast}/>;
}
function AuthPage({ mode, onLogin }) {
    const [, setLocation] = useLocation();
    const [show, setShow] = useState(false);
    const [authError, setAuthError] = useState('');
    const [submitted, setSubmitted] = useState(false);
    const [emailSent, setEmailSent] = useState(false);
    const title = mode === 'signup' ? 'Create a governed workspace' : mode === 'forgot-password' ? 'Recover access' : mode === 'reset-password' ? 'Set a new password' : 'Curriculum truth, with a human in the loop.';
    if (submitted || emailSent)
        return <div className="auth-wrap grain"><div className="surface" style={{ maxWidth: 520, padding: 42, textAlign: 'center' }}><div className="brand-mark" style={{ margin: '0 auto 18px' }}><Check size={21}/></div><p className="eyebrow">Request recorded</p><h1 className="page-title" style={{ margin: '8px 0 12px' }}>{mode === 'forgot-password' ? 'Check your inbox' : 'Workspace ready'}</h1><p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>{mode === 'forgot-password' ? 'A secure reset link has been sent to the address provided. This demo accepts any email.' : 'Your demo account is configured. Please sign in using your work email.'}</p><button className="btn btn-primary" style={{ marginTop: 22 }} onClick={() => setLocation('/login')} data-testid="button-auth-continue">Continue to sign in</button></div></div>;
    return <div className="auth-wrap grain"><div className="auth-panel">
    <section className="auth-visual"><div><div style={{ display: 'flex', alignItems: 'center', gap: 11 }}><div className="brand-mark"><Landmark size={19}/></div><strong className="font-display">AICTE / MCI GOV</strong></div><div style={{ marginTop: 86 }}><p className="eyebrow" style={{ color: '#e7daf4' }}>National academic governance</p><h1 style={{ font: '700 42px/1.03 var(--app-font-display)', letterSpacing: '-.055em', margin: '12px 0 16px' }}>A calmer way to steward curriculum.</h1><p style={{ color: 'rgba(255,255,255,.7)', maxWidth: 310, lineHeight: 1.7, fontSize: 13 }}>Authoritative sources. Visible evidence. Expert decisions. One shared record of curriculum truth.</p></div></div><div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'rgba(255,255,255,.68)', fontSize: 11 }}><ShieldCheck size={16}/> AI assistance never replaces human approval.</div></section>
    <section className="auth-form"><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 25 }}><div><p className="eyebrow">Demo access portal</p><h2 className="font-display" style={{ fontSize: 25, margin: '7px 0 0', letterSpacing: '-.035em' }}>{title}</h2></div><div className="brand-mark" style={{ background: '#f2eafa' }}><LockKeyhole size={19}/></div></div>
      {mode === 'login' && <form onSubmit={async (event) => { event.preventDefault(); setAuthError(''); try { await onLogin(event.currentTarget.elements.namedItem('email').value, event.currentTarget.elements.namedItem('password').value); } catch { setAuthError('Incorrect email address or password.'); } }}><label className="label">Email address</label><input className="field" name="email" type="email" autoComplete="email" placeholder="name@organization.edu" required data-testid="input-login-email"/><label className="label" style={{ marginTop: 14 }}>Password</label><div style={{ position: 'relative' }}><input className="field" name="password" type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" required style={{ paddingRight: 44 }} data-testid="input-login-password"/><button type="button" className="btn btn-ghost icon-btn" aria-label={show ? 'Hide password' : 'Show password'} style={{ position: 'absolute', right: 2, top: 2, boxShadow: 'none' }} onClick={() => setShow(!show)} data-testid="button-show-password"><Eye size={16}/></button></div>{authError && <p className="auth-error" role="alert">{authError}</p>}<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '12px 0 17px', fontSize: 11 }}><label style={{ display: 'flex', gap: 7, alignItems: 'center' }}><input type="checkbox" defaultChecked/> Remember this device</label><button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={() => setLocation('/forgot-password')} data-testid="link-forgot-password">Forgot password?</button></div><p className="muted" style={{ fontSize: 11, lineHeight: 1.5 }}>Your email identifies your assigned role and opens only that workspace.</p><button className="btn btn-primary" style={{ width: '100%', marginTop: 20, minHeight: 44 }} data-testid="button-login">Sign in <ArrowRight size={16}/></button><p className="muted" style={{ textAlign: 'center', fontSize: 11, marginTop: 18 }}>New to the portal? <button type="button" className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={() => setLocation('/signup')} data-testid="link-signup">Create an account</button></p></form>}
      {mode === 'signup' && <form onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; if (form.elements.namedItem('password').value !== form.elements.namedItem('confirmPassword').value) { form.elements.namedItem('confirmPassword').setCustomValidity('Passwords do not match'); form.reportValidity(); return; } setSubmitted(true); }} onInput={(event) => event.currentTarget.elements.namedItem('confirmPassword')?.setCustomValidity('')}><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}><div><label className="label">Full name</label><input className="field" autoComplete="name" required data-testid="input-signup-name"/></div><div><label className="label">Organization</label><input className="field" autoComplete="organization" required data-testid="input-signup-organization"/></div></div><label className="label" style={{ marginTop: 13 }}>Work email</label><input className="field" type="email" autoComplete="email" placeholder="name@organization.edu" required data-testid="input-signup-email"/><label className="label" style={{ marginTop: 13 }}>Password</label><input className="field" name="password" type={show ? 'text' : 'password'} autoComplete="new-password" minLength={8} placeholder="At least 8 characters" required data-testid="input-signup-password"/><label className="label" style={{ marginTop: 13 }}>Confirm password</label><input className="field" name="confirmPassword" type={show ? 'text' : 'password'} autoComplete="new-password" placeholder="Re-enter your password" required data-testid="input-signup-confirm-password"/><p className="muted" style={{ fontSize: 11, lineHeight: 1.5, margin: '16px 0' }}>Your workspace role is assigned by an administrator after account approval.</p><label style={{ display: 'flex', gap: 7, alignItems: 'center', fontSize: 11, margin: '15px 0' }}><input type="checkbox" required data-testid="checkbox-signup-terms"/> I agree to the governance workspace terms.</label><button className="btn btn-primary" style={{ width: '100%' }} data-testid="button-create-account">Request account <ArrowRight size={16}/></button><button type="button" className="btn btn-ghost" style={{ width: '100%', marginTop: 6 }} onClick={() => setLocation('/login')} data-testid="link-back-login">Back to sign in</button></form>}
      {mode === 'forgot-password' && <form onSubmit={(event) => { event.preventDefault(); setEmailSent(true); }}><p className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>Enter your work email and we will send a secure link to reset your access.</p><label className="label" style={{ marginTop: 20 }}>Work email</label><input className="field" type="email" required data-testid="input-forgot-email"/><button className="btn btn-primary" style={{ width: '100%', marginTop: 20 }} data-testid="button-send-reset">Send reset link <Send size={15}/></button><button type="button" className="btn btn-ghost" style={{ width: '100%', marginTop: 7 }} onClick={() => setLocation('/login')} data-testid="link-back-login">Return to sign in</button></form>}
      {mode === 'reset-password' && <form onSubmit={(event) => { event.preventDefault(); setSubmitted(true); }}><label className="label">New password</label><input className="field" type="password" minLength={8} required data-testid="input-reset-password"/><label className="label" style={{ marginTop: 14 }}>Confirm password</label><input className="field" type="password" minLength={8} required data-testid="input-reset-confirm"/><button className="btn btn-primary" style={{ width: '100%', marginTop: 22 }} data-testid="button-reset-password">Update password <Check size={15}/></button></form>}
    </section>
  </div></div>;
}
function Unauthorized() {
    const [, setLocation] = useLocation();
    return <div className="auth-wrap grain"><div className="surface" style={{ maxWidth: 510, padding: 42, textAlign: 'center' }}><div className="brand-mark" style={{ margin: '0 auto 18px', background: '#f6d9d8', color: '#8e3c39' }}><CircleAlert size={22}/></div><p className="eyebrow">Access boundary</p><h1 className="page-title" style={{ margin: '8px 0 12px' }}>This workspace is not assigned to you.</h1><p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>Your account can only access the workspace assigned to its role. Return to sign in to use another account.</p><button className="btn btn-primary" style={{ marginTop: 22 }} onClick={() => setLocation('/login')} data-testid="button-unauthorized-login"><ArrowLeft size={15}/> Return to sign in</button></div></div>;
}
function AppShell({ session, role, path, open, setOpen, onLogout, notify, toast }) {
    const [menu, setMenu] = useState(false);
    const links = navByRole[role].filter((item) => can(role, item.permission));
    const primaryLinks = links.filter((item) => item.label !== 'Settings');
    const settingsLink = links.find((item) => item.label === 'Settings');
    const current = links.find((item) => path === item.href) ?? links.find((item) => path.startsWith(item.href)) ?? links[0];
    return <div className="app-shell grain"><aside className={`sidebar ${open ? 'open' : ''}`}><div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '0 10px 27px', minWidth: 0 }}><div className="brand-mark"><Landmark size={18}/></div><div style={{ minWidth: 0 }}><strong className="font-display" style={{ fontSize: 14 }}>AICTE / MCI</strong><div style={{ color: 'rgba(255,255,255,.5)', fontSize: 9, marginTop: 2 }}>GOVERNANCE PORTAL</div></div><button className="btn btn-ghost icon-btn" style={{ marginLeft: 'auto', color: '#fff', display: 'none' }} onClick={() => setOpen(false)}><X size={17}/></button></div><div className="sidebar-scroll">{primaryLinks.map((item) => <Link href={item.href} key={item.href} className={`nav-link ${current?.href === item.href ? 'active' : ''}`} onClick={() => setOpen(false)} data-testid={`link-nav-${item.label.toLowerCase().replaceAll(' ', '-')}`}><item.icon size={16} strokeWidth={1.8}/><span>{item.label}</span></Link>)}</div><div className="sidebar-footer"><div style={{ padding: '10px 13px', color: 'rgba(255,255,255,.6)', fontSize: 10, lineHeight: 1.5 }}>DEMO MODE<br /><span style={{ color: '#e7d6f7' }}>Local governance state</span></div>{settingsLink && <Link href={settingsLink.href} className={`nav-link ${current?.href === settingsLink.href ? 'active' : ''}`} onClick={() => setOpen(false)} data-testid="link-nav-settings"><Settings size={16}/><span>Settings</span></Link>}<button className="nav-link" onClick={onLogout} data-testid="button-logout"><LogOut size={16}/><span>Sign out</span></button></div></aside>{open && <button className="drawer-backdrop" onClick={() => setOpen(false)} aria-label="Close navigation"/>}<main className="main-area"><header className="topbar"><div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><button className="btn icon-btn mobile-menu" onClick={() => setOpen(true)} data-testid="button-open-navigation"><Menu size={18}/></button><div className="breadcrumb muted" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}><span>Workspace</span><ChevronRight size={13}/><strong style={{ color: 'hsl(var(--foreground))' }}>{current?.label}</strong></div></div><div className="topbar-actions"><button className="btn icon-btn notification-button" onClick={() => notify('No new alerts. You are up to date.')} aria-label="Open notifications" data-testid="button-header-notifications"><Bell size={17}/><span className="notification-dot"/></button><div style={{ position: 'relative' }}><button className="btn" style={{ padding: '4px 9px 4px 5px', gap: 8 }} onClick={() => setMenu(!menu)} data-testid="button-user-menu"><span className="brand-mark" style={{ width: 29, height: 29, borderRadius: 10, fontSize: 10, fontWeight: 700 }}>{initials(session.name)}</span><span style={{ textAlign: 'left', display: 'block' }}><strong style={{ display: 'block', fontSize: 11 }}>{session.name}</strong><small className="muted" style={{ fontSize: 9 }}>{roles[role].short}</small></span><ChevronDown size={14}/></button>{menu && <div className="surface" style={{ position: 'absolute', right: 0, top: 48, width: 230, padding: 10, zIndex: 40 }}><p className="eyebrow" style={{ padding: '4px 8px 8px' }}>Signed in workspace</p><div style={{ padding: '2px 8px 10px', fontSize: 12 }}><strong>{roles[role].label}</strong><span className="muted" style={{ display: 'block', fontSize: 10, marginTop: 3 }}>Role is assigned to your account.</span></div><button className="btn btn-ghost btn-danger" style={{ width: '100%', justifyContent: 'flex-start', marginTop: 4 }} onClick={onLogout} data-testid="button-menu-logout"><LogOut size={14}/> Sign out</button></div>}</div></div></header><PageContent role={role} path={path} notify={notify}/></main>{toast && <div className="toast-note" data-testid="status-toast"><CheckCircle size={15} style={{ verticalAlign: 'middle', marginRight: 7 }}/>{toast}</div>}</div>;
}
function PageContent({ role, path, notify }) {
    if (path.endsWith('/dashboard'))
        return <Dashboard role={role} notify={notify}/>;
    if (path === '/admin/documents')
        return <AdminDocuments notify={notify}/>;
    if (path === '/admin/policies')
        return <PolicyManagement notify={notify} audience="admin"/>;
    if (path === '/admin/institutes')
        return <AdminInstitutes notify={notify}/>;
    if (path === '/admin/curricula')
        return <AdminCurricula notify={notify}/>;
    if (path === '/admin/reviews')
        return <AdminReviews notify={notify}/>;
    if (path === '/admin/users')
        return <AdminUsers notify={notify}/>;
    if (path === '/admin/audit-logs')
        return <AuditLogs />;
    if (path.endsWith('/notifications'))
        return <Notifications notify={notify}/>;
    if (path.endsWith('/settings'))
        return <SettingsPage notify={notify}/>;
    if (path === '/reviewer/reviews')
        return <ReviewQueue notify={notify}/>;
    if (path === '/reviewer/screener')
        return <Screener notify={notify}/>;
    if (path === '/reviewer/policies')
        return <PolicyManagement notify={notify} audience="reviewer"/>;
    if (path === '/reviewer/history' || path === '/reviewer/approved')
        return <ReviewSupportingPage path={path}/>;
    if (path === '/designer/curricula')
        return <DesignerCurricula notify={notify}/>;
    if (path === '/designer/create')
        return <CreateWizard notify={notify}/>;
    if (path === '/designer/assistant')
        return <RagAssistantPage notify={notify}/>;
    if (path === '/designer/resources')
        return <ResourcePage />;
    if (path === '/designer/comparison')
        return <ComparisonPage />;
    if (path.startsWith('/designer/analyzer'))
        return <Analyzer notify={notify}/>;
    if (path === '/designer/changes')
        return <DesignerChanges notify={notify}/>;
    if (path === '/designer/improvements')
        return <ImprovementTracker notify={notify}/>;
    if (path === '/designer/published')
        return <PublishedPage />;
    if (path === '/institute/curricula')
        return <InstituteCurricula />;
    if (path === '/institute/courses')
        return <InstituteCourses />;
    if (path === '/institute/coordinators')
        return <Coordinators notify={notify}/>;
    if (path === '/institute/changes')
        return <ChangeRequests notify={notify}/>;
    if (path === '/institute/feedback')
        return <Feedback notify={notify}/>;
    return <Dashboard role={role} notify={notify}/>;
}
function PageHeader({ eyebrow, title, detail, action }) {
    return <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 15, margin: '7px 0 25px' }}><div><p className="eyebrow">{eyebrow}</p><h1 className="page-title" style={{ margin: '7px 0 7px' }}>{title}</h1>{detail && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{detail}</p>}</div>{action}</div>;
}
function StatCard({ label, value, note, icon: Icon, tone = 'lavender' }) {
    return <div className="surface stat-card" data-testid={`stat-${label.toLowerCase().replaceAll(' ', '-')}`}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}><span className="eyebrow" style={{ letterSpacing: '.08em' }}>{label}</span><span className={`badge badge-${tone}`}><Icon size={14}/></span></div><div className="stat-value" style={{ marginTop: 16 }}>{value}</div><p className="muted" style={{ fontSize: 10, margin: '8px 0 0' }}>{note}</p></div>;
}
function SectionCard({ title, action, children, className = '' }) {
    return <section className={`surface ${className}`} style={{ padding: 20 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}><h2 className="font-display" style={{ fontSize: 15, margin: 0, letterSpacing: '-.02em' }}>{title}</h2>{action}</div>{children}</section>;
}
function StatusBadge({ status }) {
    const tone = status.includes('Approved') || status.includes('Published') || status === 'Active' || status === 'Accepted' ? 'green' : status.includes('Reject') || status.includes('Archived') ? 'red' : status.includes('Review') || status.includes('Submitted') || status.includes('Screening') || status.includes('Requested') || status === 'Pending' ? 'amber' : 'lavender';
    return <span className={`badge badge-${tone}`} data-testid={`status-${status.toLowerCase().replaceAll(' ', '-')}`}>{status}</span>;
}
function MiniBar({ value }) { return <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div className="progress" style={{ flex: 1 }}><span style={{ width: `${value}%` }}/></div><strong style={{ fontSize: 11, minWidth: 30 }}>{value}%</strong></div>; }
function Dashboard({ role, notify }) {
    const config = {
        admin: { title: 'Governance overview', detail: 'A live view of documents, institutions, curriculum movement and review health.', stats: [['Approved Institutes', '4,850', '+86 this quarter', Building2], ['AICTE Documents', '320', '12 awaiting metadata', FileText], ['Active Policies', '85', '3 revised this month', ShieldCheck], ['Pending Reviews', '24', '8 high priority', ClipboardCheck]] },
        reviewer: { title: 'Review desk', detail: 'Your queue of curriculum decisions, evidence and upcoming panel work.', stats: [['Pending Reviews', '12', '3 due this week', Inbox], ['Approved', '45', '91% first-pass clarity', CheckCircle2], ['Rejected', '5', 'Across 54 decisions', CircleAlert], ['Changes Requested', '8', '4 awaiting response', RefreshCw]] },
        designer: { title: 'Design studio', detail: 'Curriculum work in motion, with evidence-backed recommendations in view.', stats: [['Draft Curricula', '3', '1 edited today', FolderKanban], ['Under Review', '2', 'B.Tech AI is active', ClipboardCheck], ['Priority Improvements', '3', 'Analyzer findings', Lightbulb], ['Published', '4', 'Across 2 programs', CheckCircle2]] },
        institute: { title: 'Institute workspace', detail: 'Published curriculum access and the people responsible for delivery.', stats: [['Published Curricula', '12', '4 recently updated', BookOpen], ['Assigned Courses', '8', 'Across 3 programs', ListChecks], ['Active Coordinators', '8', 'One per course version', UserCog], ['Pending Changes', '3', '2 high priority', RefreshCw]] },
    }[role];
    return <div className="content"><PageHeader eyebrow={roles[role].label} title={config.title} detail={config.detail} action={<button className="btn" onClick={() => notify('Workspace data refreshed from local demo state.')} data-testid="button-refresh-dashboard"><RefreshCw size={14}/> Refresh state</button>}/><div className="stat-grid">{config.stats.map(([label, value, note, Icon]) => <StatCard key={label} label={label} value={value} note={note} icon={Icon}/>)}</div><DashboardActions role={role}/><div style={{ display: 'grid', gridTemplateColumns: '1.25fr .75fr', gap: 16, marginTop: 17 }}><SectionCard title={role === 'reviewer' ? 'Review queue' : role === 'designer' ? 'Curriculum movement' : role === 'institute' ? 'Recently published' : 'Recent governance activity'} action={<button className="btn btn-ghost" onClick={() => notify('Opening the full activity register.')} data-testid="button-view-activity">View all <ArrowRight size={14}/></button>}><ActivityList role={role}/></SectionCard><SectionCard title={role === 'admin' ? 'Review health' : role === 'reviewer' ? 'Upcoming reviews' : role === 'designer' ? 'AI recommendations' : 'Delivery pulse'}><div style={{ display: 'grid', gap: 16 }}>{(role === 'designer' ? [['High priority improvements', 3], ['Medium priority improvements', 5], ['Missing topic areas', 2]] : role === 'reviewer' ? [['Ready for decision', 7], ['Evidence requested', 3], ['Panel this week', 2]] : role === 'institute' ? [['Courses with active owners', 100], ['Feedback this quarter', 68], ['Published visibility', 100]] : [['Screening pass rate', 91], ['Reviews within SLA', 78], ['Policy coverage', 96]]).map(([label, value]) => <div key={label}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 7 }}><span>{label}</span><strong>{value}{role === 'admin' || role === 'institute' ? '%' : ''}</strong></div><MiniBar value={Number(value) > 10 ? Number(value) : Number(value) * 20}/></div>)}</div></SectionCard></div><div style={{ marginTop: 16 }}><SectionCard title="Curriculum register"><CurriculumTable items={mockCurricula.slice(0, role === 'admin' ? 4 : 3)} onAction={() => notify('Curriculum detail opened in the governed workspace.')}/></SectionCard></div></div>;
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
            ['Open Curriculum Screener', 'Inspect evidence, then approve, reject or request changes.', SlidersHorizontal, '/reviewer/screener'],
        ],
        designer: [
            ['Upload Curriculum PDF', 'Start the next governed curriculum version from a PDF.', Upload, '/designer/create'],
            ['Ask AI Assistant', 'Get evidence-backed help for outcomes, structure and coverage.', Bot, '/designer/assistant'],
            ['Analyze Curriculum', 'Find problems and apply defined solutions before submission.', BarChart3, '/designer/analyzer'],
        ],
        institute: [
            ['Published Curricula', 'See only the programmes explicitly released to this institute.', BookOpen, '/institute/curricula'],
            ['Course Coordinators', 'Assign one active coordinator to each course and version.', UserCog, '/institute/coordinators'],
            ['Request Curriculum Change', 'Send evidence to the designer for next year’s version.', RefreshCw, '/institute/changes'],
        ],
    }[role];
    return <div className={`dashboard-actions dashboard-actions-${role}`}>{actions.map(([label, detail, Icon, href]) => <button className="surface dashboard-action" key={label} onClick={() => setLocation(href)} data-testid={`button-dashboard-${label.toLowerCase().replaceAll(' ', '-')}`}><span className="brand-mark"><Icon size={17}/></span><span><strong>{label}</strong><small>{detail}</small></span><ArrowRight size={15} className="action-arrow"/></button>)}</div>;
}
function ActivityList({ role }) {
    const items = role === 'admin' ? [['Document uploaded', 'AICTE Model Curriculum Guidelines 2026', '14 min ago'], ['Policy updated', 'Credit distribution policy · v3.2', '1 hr ago'], ['Institute added', 'Northstar Institute of Technology', '3 hrs ago'], ['Curriculum submitted', 'B.Tech Artificial Intelligence · v2.1', 'Yesterday']] : role === 'reviewer' ? [['Ready for review', 'B.Tech Artificial Intelligence · v2.0', 'Today'], ['Decision recorded', 'B.Tech CSE · v1.4 approved', 'Yesterday'], ['Evidence requested', 'B.Tech ECE · v1.1', '2 days ago']] : role === 'designer' ? [['Under review', 'B.Tech Artificial Intelligence · v2.1', 'Today'], ['Changes requested', 'B.Tech ECE · v1.1', 'Yesterday'], ['Recommendation added', 'DBMS · outcome mapping', '2 days ago']] : [['Updated', 'B.Tech CSE · 2026–27', 'Today'], ['Coordinator assigned', 'Data Structures · v4.0', 'Yesterday'], ['Change request', 'DBMS · CR-1018', '3 days ago']];
    return <div style={{ display: 'grid', gap: 6 }}>{items.map(([action, entity, time], index) => <div key={entity} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: index === items.length - 1 ? 0 : '1px solid hsl(var(--border))' }}><span className="brand-mark" style={{ width: 31, height: 31, borderRadius: 10, flexShrink: 0 }}><Activity size={14}/></span><div style={{ flex: 1 }}><strong style={{ display: 'block', fontSize: 12 }}>{action}</strong><span className="muted" style={{ fontSize: 11 }}>{entity}</span></div><span className="muted" style={{ fontSize: 10 }}>{time}</span></div>)}</div>;
}
function CurriculumTable({ items, onAction }) {
    return <div className="table-scroll"><table className="data-table"><thead><tr><th>Curriculum</th><th>Institute</th><th>Version</th><th>Designer</th><th>Score</th><th>Status</th><th>Action</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} data-testid={`row-curriculum-${item.id}`}><td><strong>{item.name}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>{item.program}</span></td><td>Northstar Institute of Technology</td><td>{item.version}</td><td>{item.designer}</td><td><strong>{item.score}</strong><span className="muted">/100</span></td><td><StatusBadge status={item.status}/></td><td><button className="btn icon-btn" onClick={() => onAction(item)} data-testid={`button-view-curriculum-${item.id}`}><Eye size={15}/></button></td></tr>)}</tbody></table></div>;
}
function formatDocumentDate(value) {
    if (!value)
        return 'Not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' });
}
function AdminDocuments({ notify }) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [docs, setDocs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const filtered = docs.filter((doc) => doc.filename.toLowerCase().includes(query.toLowerCase()));
    const refreshDocuments = async () => {
        setLoading(true);
        try {
            setDocs(await mockService.getDocuments());
        }
        catch (error) {
            notify(error.message);
        }
        finally {
            setLoading(false);
        }
    };
    const uploadPdf = async (file) => {
        if (!file)
            return;
        setUploading(true);
        try {
            const result = await mockService.uploadDocument(file);
            notify(`${result.filename} indexed into ${result.total_chunks} chunks.`);
            await refreshDocuments();
        }
        catch (error) {
            notify(error.message);
        }
        finally {
            setUploading(false);
        }
    };
    const removeDocument = async (filename) => {
        try {
            await mockService.deleteDocument(filename);
            setDocs(docs.filter((doc) => doc.filename !== filename));
            notify(`${filename} removed from the vector index.`);
        }
        catch (error) {
            notify(error.message);
        }
    };
    useEffect(() => {
        refreshDocuments();
    }, []);
    return <div className="content"><PageHeader eyebrow="Admin / Knowledge registry" title="Upload authoritative document" detail="Add AICTE source PDFs. They are chunked with a recursive character splitter, embedded with Hugging Face, and stored in MongoDB Atlas Vector Search." action={<div style={{ display: 'flex', gap: 8 }}><label className={`btn btn-primary upload-button ${uploading ? 'disabled' : ''}`}><Upload size={15}/> {uploading ? 'Indexing PDF' : 'Upload PDF'}<input type="file" accept=".pdf,application/pdf" disabled={uploading} onChange={(e) => { uploadPdf(e.target.files?.[0]); e.target.value = ''; }} data-testid="input-admin-document-pdf"/></label><button className="btn" onClick={() => setOpen(true)} data-testid="button-add-document"><Plus size={15}/> Add metadata</button></div>}/><div className="surface" style={{ padding: 13, marginBottom: 15, display: 'flex', gap: 10 }}><div style={{ position: 'relative', flex: 1 }}><Search size={15} className="muted" style={{ position: 'absolute', top: 12, left: 12 }}/><input className="field" style={{ paddingLeft: 36 }} placeholder="Search indexed PDFs" value={query} onChange={(e) => setQuery(e.target.value)} data-testid="input-search-documents"/></div><button className="btn" onClick={refreshDocuments} data-testid="button-filter-documents"><RefreshCw size={14}/> Refresh</button></div><SectionCard title={loading ? 'Loading indexed documents' : `${filtered.length} documents in vector registry`}><div className="table-scroll"><table className="data-table"><thead><tr><th>Title</th><th>Storage</th><th>Chunks</th><th>Uploaded</th><th>Status</th><th>Actions</th></tr></thead><tbody>{filtered.map((doc, i) => <tr key={doc.filename}><td><strong>{doc.filename}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>MongoDB Atlas Vector Search</span></td><td>PDF embeddings</td><td>{doc.total_chunks}</td><td>{formatDocumentDate(doc.uploaded_at)}</td><td><StatusBadge status={doc.status || 'Active'}/></td><td><button className="btn icon-btn" onClick={() => notify(`${doc.filename} has ${doc.total_chunks} searchable chunks.`)} data-testid={`button-view-document-${i}`}><Eye size={14}/></button><button className="btn icon-btn" onClick={() => removeDocument(doc.filename)} data-testid={`button-archive-document-${i}`}><ArchiveIcon /></button></td></tr>)}{!loading && filtered.length === 0 && <tr><td colSpan="6"><span className="muted">No indexed PDFs found. Upload an authoritative PDF to power the assistant.</span></td></tr>}</tbody></table></div></SectionCard>{open && <Modal title="Add authoritative document" onClose={() => setOpen(false)}><label className="label">Document title</label><input className="field" defaultValue="AICTE Model Curriculum Guidelines 2026" data-testid="input-document-title"/><label className="label" style={{ marginTop: 13 }}>Document type</label><select className="select" data-testid="select-document-type"><option>Model Curriculum</option><option>Guidelines</option><option>Circular</option><option>Policy</option></select><label className="label" style={{ marginTop: 13 }}>PDF file</label><label className="btn upload-button" style={{ width: '100%' }}><Upload size={14}/> Choose PDF<input type="file" accept=".pdf,application/pdf" onChange={(e) => uploadPdf(e.target.files?.[0])} data-testid="input-document-modal-pdf"/></label><label className="label" style={{ marginTop: 13 }}>Description</label><textarea className="textarea" defaultValue="Authoritative reference for 2026 curriculum design and review." data-testid="textarea-document-description"/><button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} onClick={() => { setOpen(false); notify('Metadata saved. Upload the PDF selector indexes content automatically.'); }} data-testid="button-save-document"><Upload size={15}/> Save metadata</button></Modal>}</div>;
}
function ArchiveIcon() { return <Trash2 size={14}/>; }
function PolicyManagement({ notify, audience }) {
    const [open, setOpen] = useState(false);
    const [policies, setPolicies] = useState([
        ['Credit Distribution & Workload', 'Academic structure', 'v3.2', 'Active', 'All B.Tech programmes', 'Northstar Institute of Technology'],
        ['Outcome Based Education Standard', 'Learning outcomes', 'v2.4', 'Active', 'Technical programmes', 'Crescent Valley University'],
        ['Practical & Industry Exposure', 'Assessment', 'v1.8', 'Active', 'AI, CSE, ECE', 'Eastern Technical College'],
        ['Model Curriculum Retirement', 'Governance', 'v1.0', 'Draft', '2026 cohort', 'Harbor School of Engineering'],
    ]);
    const prefix = audience === 'admin' ? 'Admin' : 'Reviewer / Expert';
    const mutatePolicy = (index, action) => {
        if (action === 'deleted')
            setPolicies(policies.filter((_, itemIndex) => itemIndex !== index));
        notify(action === 'deleted' ? 'Policy removed from the governed register.' : `Policy ${policies[index][0]} updated.`);
    };
    return <div className="content"><PageHeader eyebrow={`${prefix} / Governance rules`} title="Policy management" detail="Update, retire or remove the rules used to make defensible curriculum decisions." action={<button className="btn btn-primary" onClick={() => setOpen(true)} data-testid={`button-${audience}-add-policy`}><Plus size={15}/> Create policy</button>}/><div className="policy-note surface"><ShieldCheck size={18}/><span><strong>Policy authority</strong><small>{audience === 'reviewer' ? 'Reviewer / Expert edits are recorded for the active review cycle.' : 'AICTE policies are the authoritative source for screening and curriculum design.'}</small></span></div><div style={{ display: 'grid', gap: 12, marginTop: 14 }}>{policies.map((policy, index) => <div className="surface policy-row" key={policy[0]} data-testid={`card-${audience}-policy-${index}`}><div><span className="eyebrow">{policy[1]}</span><h3 className="font-display" style={{ fontSize: 15, margin: '6px 0' }}>{policy[0]}</h3><span className="muted" style={{ display: 'block', fontSize: 11 }}>{policy[4]}</span><span className="muted" style={{ display: 'block', marginTop: 4, fontSize: 10 }}>Institute: {policy[5]}</span></div><div><span className="muted" style={{ fontSize: 10 }}>Current version</span><strong style={{ display: 'block', marginTop: 4 }}>{policy[2]}</strong></div><StatusBadge status={policy[3]}/><div className="policy-actions"><button className="btn icon-btn" onClick={() => mutatePolicy(index, 'updated')} aria-label={`Update ${policy[0]}`} data-testid={`button-update-${audience}-policy-${index}`}><Pencil size={14}/></button><button className="btn icon-btn btn-danger" onClick={() => mutatePolicy(index, 'deleted')} aria-label={`Delete ${policy[0]}`} data-testid={`button-delete-${audience}-policy-${index}`}><Trash2 size={14}/></button></div></div>)}</div>{open && <Modal title="Create policy" onClose={() => setOpen(false)}><label className="label">Policy title</label><input className="field" required data-testid={`input-${audience}-policy-title`}/><label className="label" style={{ marginTop: 13 }}>Category</label><select className="select"><option>Academic structure</option><option>Learning outcomes</option><option>Assessment</option></select><label className="label" style={{ marginTop: 13 }}>Requirements and rules</label><textarea className="textarea" data-testid={`textarea-${audience}-policy-rules`}/><button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} onClick={() => { setOpen(false); notify('New policy saved as Draft for review.'); }} data-testid={`button-save-${audience}-policy`}><Save size={15}/> Save policy</button></Modal>}</div>;
}
function AdminInstitutes({ notify }) {
    const [open, setOpen] = useState(false);
    const [institutes, setInstitutes] = useState([['Northstar Institute of Technology', 'INST-0421', 'Pune, Maharashtra', '8 programmes', 'Approved'], ['Crescent Valley University', 'INST-0317', 'Bengaluru, Karnataka', '12 programmes', 'Approved'], ['Eastern Technical College', 'INST-0188', 'Bhubaneswar, Odisha', '6 programmes', 'Approved'], ['Harbor School of Engineering', 'INST-0592', 'Kochi, Kerala', '4 programmes', 'Pending']]);
    return <div className="content"><PageHeader eyebrow="Admin / National network" title="Approved institutes" detail="Visibility boundaries for published curriculum and institutional delivery." action={<button className="btn btn-primary" onClick={() => setOpen(true)} data-testid="button-add-institute"><Plus size={15}/> Add institute</button>}/><SectionCard title={`${institutes.length} institutes`} action={<button className="btn"><Filter size={14}/> Filter</button>}><div className="table-scroll"><table className="data-table"><thead><tr><th>Institute</th><th>Institute ID</th><th>Location</th><th>Programs</th><th>Status</th><th>Action</th></tr></thead><tbody>{institutes.map((item, index) => <tr key={item[1]}><td><strong>{item[0]}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>Representative: {index === 0 ? 'Rohan Kulkarni' : index === 1 ? 'Priya Shah' : 'Institute representative assigned'}</span><span className="muted" style={{ display: 'block', marginTop: 3 }}>Curriculum designer: {index === 0 ? 'Ananya Iyer' : 'Design cell assigned'}</span></td><td>{item[1]}</td><td>{item[2]}</td><td>{item[3]}</td><td><StatusBadge status={item[4]}/></td><td><button className="btn icon-btn" onClick={() => notify(`${item[0]} detail opened with representative and curriculum designer.`)} data-testid={`button-view-institute-${index}`}><Eye size={14}/></button></td></tr>)}</tbody></table></div></SectionCard>{open && <Modal title="Add approved institute" onClose={() => setOpen(false)}><label className="label">Institute name</label><input className="field" data-testid="input-institute-name"/><label className="label" style={{ marginTop: 13 }}>Institute ID</label><input className="field" placeholder="INST-0000" data-testid="input-institute-id"/><label className="label" style={{ marginTop: 13 }}>Location</label><input className="field" data-testid="input-institute-location"/><button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} onClick={() => { setOpen(false); notify('Institute added to the approved network.'); }} data-testid="button-save-institute"><Save size={15}/> Add institute</button></Modal>}</div>;
}
function AdminCurricula({ notify }) {
    const tabs = ['All', 'Draft', 'Submitted', 'Screening', 'Under Review', 'Approved', 'Rejected', 'Changes Requested', 'Published', 'Archived'];
    const [tab, setTab] = useState('All');
    const shown = tab === 'All' ? mockCurricula : mockCurricula.filter((item) => item.status === tab);
    return <div className="content"><PageHeader eyebrow="Admin / Curriculum lifecycle" title="Curriculum register" detail="Every version, handoff and human decision in one governed trail."/><div className="surface" style={{ padding: 8, display: 'flex', gap: 5, overflowX: 'auto', marginBottom: 15 }}>{tabs.map((item) => <button key={item} className={`btn ${tab === item ? 'btn-primary' : 'btn-ghost'}`} style={{ whiteSpace: 'nowrap', padding: '0 11px' }} onClick={() => setTab(item)} data-testid={`tab-curriculum-${item.toLowerCase().replaceAll(' ', '-')}`}>{item}</button>)}</div><SectionCard title={`${shown.length} curriculum records`}><CurriculumTable items={shown} onAction={(item) => notify(`${item.name} v${item.version} is ${item.status}.`)}/></SectionCard></div>;
}
function AdminReviews({ notify }) {
    return <div className="content"><PageHeader eyebrow="Admin / Oversight" title="Review operations" detail="Queue health and decision integrity across the national review panel."/><div className="stat-grid"><StatCard label="Open queue" value="24" note="12 reviewers active" icon={Inbox}/><StatCard label="Median decision time" value="4.6d" note="Down 0.8d this month" icon={Clock3} tone="peach"/><StatCard label="First-pass approval" value="68%" note="Across 2026 submissions" icon={CheckCircle2} tone="green"/><StatCard label="Escalations" value="2" note="Require admin attention" icon={CircleAlert} tone="amber"/></div><div style={{ marginTop: 17 }}><SectionCard title="Recent decisions"><table className="data-table"><thead><tr><th>Curriculum</th><th>Institute</th><th>Reviewer</th><th>Decision</th><th>Date</th><th>Notes</th></tr></thead><tbody>{[['B.Tech CSE', 'Northstar Institute of Technology', 'Dr. Arvind Rao', 'Approved', '04 Mar 2026', 'Strong outcomes mapping'], ['B.Tech ECE', 'Crescent Valley University', 'Dr. S. Kulkarni', 'Changes Requested', '02 Mar 2026', 'Assessment balance'], ['B.Tech AI', 'Eastern Technical College', 'Dr. Arvind Rao', 'Under Review', 'Today', 'Evidence review in progress']].map((row, i) => <tr key={row[0]}><td><strong>{row[0]}</strong></td><td>{row[1]}</td><td>{row[2]}</td><td><StatusBadge status={row[3]}/></td><td>{row[4]}</td><td><button className="btn btn-ghost" onClick={() => notify(`Decision notes: ${row[5]}.`)} data-testid={`button-review-note-${i}`}>View note <ChevronRight size={14}/></button></td></tr>)}</tbody></table></SectionCard></div></div>;
}
function AdminUsers({ notify }) {
    const [users, setUsers] = useState(mockUsers);
    return <div className="content"><PageHeader eyebrow="Admin / Access control" title="Users & roles" detail="Role assignment is the boundary around every workspace and action." action={<button className="btn btn-primary" onClick={() => notify('Invite flow opened.')} data-testid="button-invite-user"><Plus size={15}/> Invite user</button>}/><SectionCard title={`${users.length} governed identities`}><table className="data-table"><thead><tr><th>Name</th><th>Institute</th><th>Organization</th><th>Role</th><th>Status</th><th>Last active</th><th>Action</th></tr></thead><tbody>{users.map((user, i) => <tr key={user.id}><td><strong>{user.name}</strong><span className="muted" style={{ display: 'block', marginTop: 4 }}>{user.email}</span></td><td>{user.role === 'admin' || user.role === 'reviewer' ? 'National panel' : user.organization}</td><td>{user.organization}</td><td>{roles[user.role].label}</td><td><StatusBadge status={user.status}/></td><td>{i === 0 ? 'Just now' : `${i + 1}h ago`}</td><td><button className="btn icon-btn" onClick={() => { setUsers(users.map((item) => item.id === user.id ? { ...item, status: item.status === 'Active' ? 'Inactive' : 'Active' } : item)); notify(`${user.name} status updated.`); }} data-testid={`button-toggle-user-${user.id}`}><UserCog size={14}/></button></td></tr>)}</tbody></table></SectionCard></div>;
}
function AuditLogs() {
    const logs = [['Meera Nair', 'Policy updated', 'Credit Distribution · v3.2', 'Northstar Institute of Technology', 'Today · 09:42'], ['Dr. Arvind Rao', 'Curriculum approved', 'B.Tech CSE · v1.4', 'Northstar Institute of Technology', 'Yesterday · 16:08'], ['Meera Nair', 'Institute added', 'Northstar Institute', 'Northstar Institute of Technology', 'Yesterday · 11:25'], ['Rohan Kulkarni', 'Course coordinator assigned', 'Data Structures · v4.0', 'Northstar Institute of Technology', '04 Mar · 15:18'], ['Ananya Iyer', 'Document uploaded', 'AICTE Guidelines 2026', 'Crescent Valley University', '04 Mar · 10:02']];
    return <div className="content"><PageHeader eyebrow="Admin / Traceability" title="Audit logs" detail="Governance events are recorded with actor, institute, entity and timestamp." action={<button className="btn"><Filter size={14}/> Filter logs</button>}/><SectionCard title="Immutable activity register"><table className="data-table"><thead><tr><th>User</th><th>Institute</th><th>Action</th><th>Entity</th><th>Timestamp</th><th>Details</th></tr></thead><tbody>{logs.map((log, i) => <tr key={i}><td><strong>{log[0]}</strong></td><td>{log[3]}</td><td>{log[1]}</td><td>{log[2]}</td><td className="muted">{log[4]}</td><td><button className="btn btn-ghost" data-testid={`button-log-detail-${i}`}><Eye size={14}/> Inspect</button></td></tr>)}</tbody></table></SectionCard></div>;
}
function ReviewQueue({ notify }) {
    const [selected, setSelected] = useState('c1');
    const [comment, setComment] = useState('');
    const queue = mockCurricula.filter((item) => item.status === 'Under Review' || item.status === 'Changes Requested');
    const current = [...queue, { ...mockCurricula[3], status: 'Submitted' }].find((item) => item.id === selected) ?? queue[0];
    return <div className="content"><PageHeader eyebrow="Reviewer / Expert" title="Pending reviews" detail="AI screening prepares the record. You make the final academic decision." action={<button className="btn"><Filter size={14}/> Filter queue</button>}/><div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 16 }}><SectionCard title="Review queue"><div style={{ display: 'grid', gap: 10 }}>{[...queue, { ...mockCurricula[3], status: 'Submitted' }].map((item) => <button key={item.id} onClick={() => setSelected(item.id)} className="surface" style={{ textAlign: 'left', padding: 16, border: selected === item.id ? '2px solid #9d7bc7' : undefined, boxShadow: selected === item.id ? 'var(--shadow-inset)' : undefined }} data-testid={`card-pending-review-${item.id}`}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}><div><strong style={{ fontSize: 13 }}>{item.name}</strong><p className="muted" style={{ fontSize: 11, margin: '5px 0' }}>Version {item.version} · {item.designer} · Northstar Institute of Technology</p></div><StatusBadge status={item.status}/></div><div style={{ marginTop: 12 }}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 5 }}><span className="muted">AI screening score</span><strong>{item.score}/100</strong></div><MiniBar value={item.score}/></div><div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 10 }}><span className="muted">Submitted {item.submitted}</span><span className={`badge ${item.score < 80 ? 'badge-red' : 'badge-lavender'}`}>{item.score < 80 ? 'Priority' : 'Standard'}</span></div></button>)}</div></SectionCard><SectionCard title="Selected curriculum documents"><p className="muted" style={{ fontSize: 12, lineHeight: 1.6 }}><strong style={{ color: 'hsl(var(--foreground))' }}>{current?.name} · v{current?.version}</strong><br />Institute: Northstar Institute of Technology · Designer: {current?.designer}</p><div className="surface" style={{ padding: 13, marginTop: 13, display: 'grid', gap: 9 }}><strong style={{ fontSize: 12 }}>Submitted documents</strong>{['Curriculum structure and credit matrix.pdf', 'Course outcomes and assessment mapping.pdf', 'Faculty and resource plan.pdf'].map((doc) => <div key={doc} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', fontSize: 11 }}><span>{doc}</span><button className="btn icon-btn" onClick={() => notify(`Opened ${doc}.`)} data-testid={`button-open-review-document-${doc.slice(0, 8)}`}><Eye size={14}/></button></div>)}</div><div style={{ display: 'grid', gap: 9, margin: '18px 0' }}><button className="btn btn-primary" onClick={() => notify('Approved by human reviewer. AI recommendations remain advisory.')} data-testid="button-approve-review"><CheckCircle2 size={15}/> Approve curriculum</button><button className="btn" onClick={() => notify('Changes requested with reviewer comments.')} data-testid="button-request-changes"><RefreshCw size={15}/> Request changes</button><button className="btn btn-danger" onClick={() => notify('Curriculum rejected with a recorded decision.')} data-testid="button-reject-review"><X size={15}/> Reject</button></div><label className="label">Reviewer comments</label><textarea className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Record the reason for this decision..." data-testid="textarea-review-comments"/><button className="btn" style={{ marginTop: 9 }} onClick={() => notify('Reviewer comment saved to the selected curriculum.')} data-testid="button-save-review-comment"><MessageSquareText size={14}/> Save comment</button><div style={{ padding: 12, borderRadius: '.85rem', marginTop: 13, background: '#f8f0e9', border: '1px solid #ecd8ca', fontSize: 11, lineHeight: 1.55 }}><strong style={{ display: 'block', marginBottom: 4 }}>Human review reminder</strong>The AI provides recommendations. The Reviewer makes the final decision.</div></SectionCard></div></div>;
}
function ScoreTile({ label, value }) {
    return <div className="surface" style={{ padding: 14 }}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 9 }}><span>{label}</span><strong>{value}%</strong></div><MiniBar value={value}/></div>;
}
function SourceCard({ source }) {
    return <div style={{ padding: 13, borderRadius: '.9rem', border: '1px solid #ddd1eb', background: '#f9f5fd' }} data-testid={`card-source-${source.section.replaceAll(' ', '-').toLowerCase()}`}><div style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#6b4c9c', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.08em' }}><FileCheck2 size={14}/> {source.type}</div><strong style={{ display: 'block', fontSize: 12, marginTop: 7 }}>{source.title}</strong><span className="muted" style={{ fontSize: 10 }}>{source.section}</span><p style={{ fontSize: 11, lineHeight: 1.45, margin: '8px 0 10px' }}>{source.detail}</p><button className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#6b4c9c' }} data-testid="button-view-source"><ExternalLink size={13}/> View source</button></div>;
}
function Screener({ notify }) {
    const [issues, setIssues] = useState([true, true, false]);
    const issueData = [['HIGH', 'Credit distribution issue', 'Semester 4 contains 28 credits.', 'The distribution conflicts with the applicable curriculum policy.', 'Redistribute credits across semesters.'], ['MEDIUM', 'Learning outcome mapping is thin', 'CO3 is mapped to one assessment only.', 'A single assessment does not demonstrate progressive mastery.', 'Add a practical evaluation and map CO3 explicitly.'], ['LOW', 'Resource metadata incomplete', 'Three reading links have no publication year.', 'Evidence quality is harder to audit without bibliographic context.', 'Complete source metadata before submission.']];
    return <div className="content"><PageHeader eyebrow="Reviewer / AI-assisted screening" title="Curriculum screener" detail="AI recommendations are advisory; the human reviewer remains the final authority." action={<button className="btn btn-primary" onClick={() => notify('Screening report regenerated from the current curriculum version.')} data-testid="button-run-screening"><RefreshCw size={14}/> Run screening</button>}/><div className="surface soft-gradient" style={{ padding: 20, color: '#34224e', marginBottom: 16 }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 18, alignItems: 'center' }}><div><p className="eyebrow" style={{ color: '#5e4276' }}>Screening report · v2.1</p><h2 className="font-display" style={{ margin: '7px 0 5px', fontSize: 20 }}>B.Tech Artificial Intelligence</h2><p style={{ margin: 0, fontSize: 11 }}>Institute: Northstar Institute of Technology · Prepared by the curriculum screener · 06 Mar 2026</p></div><div style={{ textAlign: 'right' }}><strong className="font-display" style={{ fontSize: 43, letterSpacing: '-.08em' }}>82</strong><span style={{ display: 'block', fontSize: 10 }}>OVERALL / 100</span></div></div></div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 17 }}><ScoreTile label="AICTE compliance" value={91}/><ScoreTile label="Structure" value={88}/><ScoreTile label="Learning outcomes" value={76}/><ScoreTile label="Assessment" value={80}/><ScoreTile label="Course coverage" value={85}/><ScoreTile label="Resource quality" value={78}/></div><div style={{ display: 'grid', gap: 13 }}>{issueData.map((item, i) => issues[i] && <div className="surface" style={{ padding: 19 }} key={item[1]} data-testid={`card-screening-issue-${i}`}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}><div><span className={`badge ${item[0] === 'HIGH' ? 'badge-red' : item[0] === 'MEDIUM' ? 'badge-amber' : 'badge-lavender'}`}>{item[0]}</span><h3 className="font-display" style={{ fontSize: 15, margin: '10px 0 0' }}>{item[1]}</h3></div><button className="btn icon-btn" onClick={() => setIssues(issues.map((active, index) => index === i ? false : active))} data-testid={`button-dismiss-issue-${i}`}><X size={14}/></button></div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 13, marginTop: 16 }}><div><span className="eyebrow">Problem / evidence</span><p style={{ fontSize: 11, lineHeight: 1.5 }}>{item[2]}</p></div><div><span className="eyebrow">Why</span><p style={{ fontSize: 11, lineHeight: 1.5 }}>{item[3]}</p></div><div><span className="eyebrow">Recommended solution</span><p style={{ fontSize: 11, lineHeight: 1.5 }}>{item[4]}</p></div></div><div style={{ display: 'flex', gap: 8, marginTop: 12 }}><button className="btn btn-ghost" onClick={() => notify('Comment field ready.')} data-testid={`button-comment-issue-${i}`}><MessageSquareText size={14}/> Add reviewer comment</button></div></div>)}</div><div style={{ marginTop: 17 }}><SectionCard title="Official evidence used by this report"><div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 11 }}>{sourceCards.map((source) => <SourceCard key={source.section} source={source}/>)}</div></SectionCard></div></div>;
}
function ReviewSupportingPage({ path }) {
    const title = path.endsWith('history') ? 'Review history' : path.endsWith('policies') ? 'Reviewer policies' : 'Approved curricula';
    return <div className="content"><PageHeader eyebrow="Reviewer / Expert" title={title} detail="A clear record of evidence, decisions and applicable governance context."/><SectionCard title={title === 'Approved curricula' ? 'Published to the national catalogue' : 'Recent records'}><CurriculumTable items={mockCurricula} onAction={() => undefined}/></SectionCard></div>;
}
function DesignerCurricula({ notify }) {
    const [own, setOwn] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [, setLocation] = useLocation();
    const loadCurricula = async () => {
        setLoading(true);
        setError('');
        try {
            setOwn(submittedCurriculumDocuments(await mockService.getDocuments()));
        }
        catch (requestError) {
            setError(requestError.message || 'Unable to load your curricula.');
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        void loadCurricula();
    }, []);
    return <div className="content"><PageHeader eyebrow="Curriculum Designer" title="My curricula" detail="Your uploaded curricula are stored in the private Designer document store and are ready for analysis." action={<button className="btn btn-primary" onClick={() => setLocation('/designer/create')} data-testid="button-create-curriculum"><Plus size={15}/> Create curriculum</button>}/>{loading && <div className="surface" style={{ padding: 28, textAlign: 'center' }} data-testid="curricula-loading"><RefreshCw size={22} className="analyzer-spin"/><h2 className="font-display" style={{ fontSize: 17 }}>Loading your curricula</h2></div>}{!loading && error && <div className="surface" style={{ padding: 24 }} data-testid="curricula-error"><CircleAlert size={18}/><h2 className="font-display" style={{ fontSize: 17 }}>Could not load curricula</h2><p className="muted" style={{ fontSize: 12 }}>{error}</p><button className="btn" onClick={() => void loadCurricula()}><RefreshCw size={14}/> Retry</button></div>}{!loading && !error && own.length === 0 && <div className="surface" style={{ padding: 34, textAlign: 'center' }} data-testid="curricula-empty"><FileText size={28} color="#7758aa"/><h2 className="font-display" style={{ fontSize: 18 }}>No uploaded curricula yet</h2><p className="muted" style={{ fontSize: 12 }}>Create a B.Tech CSE curriculum and upload its PDF to index it for analysis.</p><button className="btn btn-primary" onClick={() => setLocation('/designer/create')}><Upload size={14}/> Upload curriculum PDF</button></div>}{!loading && !error && <div style={{ display: 'grid', gap: 13 }}>{own.map((item, i) => <div className="surface" style={{ padding: 19 }} key={analyzerDocumentKey(item)} data-testid={`card-designer-curriculum-${i}`}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 15, alignItems: 'flex-start' }}><div><span className="eyebrow">{item.programme} {item.branch} · v{item.version || 'Not set'}</span><h2 className="font-display" style={{ fontSize: 18, margin: '7px 0' }}>{item.filename}</h2><p className="muted" style={{ fontSize: 11, margin: 0 }}>Curriculum ID: {item.curriculum_id} · {item.total_chunks} vector chunks · Uploaded {formatDocumentDate(item.uploaded_at)}</p></div><StatusBadge status={item.status || 'Active'}/></div><div style={{ display: 'flex', gap: 8, marginTop: 17 }}><button className="btn btn-primary" onClick={() => setLocation(analyzerDocumentHref(item))} data-testid={`button-analyze-own-curriculum-${i}`}><BarChart3 size={14}/> Analyze curriculum</button></div></div>)}</div>}</div>;
}
function CreateWizard({ notify }) {
    const [step, setStep] = useState(0);
    const [saved, setSaved] = useState(false);
    const [selectedPdf, setSelectedPdf] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [details, setDetails] = useState({
        curriculumId: '',
        academicYear: '2026',
        version: '1.0',
    });
    const [, setLocation] = useLocation();
    const updateDetail = (name) => (event) => setDetails((current) => ({ ...current, [name]: event.target.value }));
    const choosePdf = (file) => {
        if (!file)
            return;
        if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
            notify('Only PDF files can be uploaded.');
            return;
        }
        if (file.size > 25 * 1024 * 1024) {
            notify('The curriculum PDF must be 25 MB or smaller.');
            return;
        }
        const inferredId = file.name.replace(/\.pdf$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        setSelectedPdf(file);
        setDetails((current) => ({
            ...current,
            curriculumId: current.curriculumId.trim() || inferredId,
        }));
    };
    const uploadCurriculum = async () => {
        if (!selectedPdf) {
            notify('Choose a curriculum PDF before continuing.');
            return;
        }
        if (!details.curriculumId.trim()) {
            notify('Curriculum ID is required.');
            return;
        }
        setUploading(true);
        try {
            const result = await mockService.uploadDocument(selectedPdf, {
                source_type: 'submitted_curriculum',
                programme: 'B.Tech',
                branch: 'CSE',
                curriculum_id: details.curriculumId,
                year: details.academicYear,
                version: details.version,
            });
            notify(`${result.filename} indexed into ${result.total_chunks} vector chunks.`);
            setLocation('/designer/curricula');
        }
        catch (requestError) {
            notify(requestError.message || 'Unable to upload the curriculum PDF.');
        }
        finally {
            setUploading(false);
        }
    };
    const steps = ['Basic information', 'Semester structure', 'Courses', 'Learning outcomes', 'Modules', 'Assessment', 'Resources', 'Review', 'Submit'];
    const content = [
        <div className="form-grid" key="basic"><div className="upload-field" style={{ gridColumn: '1 / -1' }}><div><label className="label">Curriculum PDF</label><span className="muted" style={{ fontSize: 11 }}>{selectedPdf ? `${selectedPdf.name} selected` : 'Upload the working curriculum source. PDF only, up to 25 MB.'}</span></div><label className={`btn btn-primary upload-button ${uploading ? 'disabled' : ''}`}><Upload size={14}/> {selectedPdf ? 'Change PDF' : 'Choose PDF'}<input type="file" accept=".pdf,application/pdf" disabled={uploading} onChange={(event) => { choosePdf(event.target.files?.[0]); event.target.value = ''; }} data-testid="input-curriculum-pdf"/></label></div><Field label="Curriculum ID" value={details.curriculumId} onChange={updateDetail('curriculumId')} placeholder="e.g. institute-cse-2026" required/><Field label="Programme" value="B.Tech" readOnly/><Field label="Degree" value="Bachelor of Technology" readOnly/><Field label="Branch" value="CSE" readOnly/><Field label="Academic year" value={details.academicYear} onChange={updateDetail('academicYear')} type="number" required/><Field label="Version" value={details.version} onChange={updateDetail('version')}/><Field label="Duration" value="4 years / 8 semesters" readOnly/><div style={{ gridColumn: '1 / -1' }}><label className="label">Description</label><textarea className="textarea" defaultValue="B.Tech CSE curriculum submitted for evidence-based analysis against official AICTE references." data-testid="textarea-curriculum-description"/></div></div>,
        <div key="semesters"><div className="surface" style={{ padding: 15, marginBottom: 10 }}><div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Semester 1</strong><span className="badge badge-green">24 credits · valid</span></div><p className="muted" style={{ fontSize: 11 }}>Mathematics I · Programming Fundamentals · Physics · Engineering Graphics</p></div><div className="surface" style={{ padding: 15 }}><div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Semester 2</strong><span className="badge badge-amber">22 credits · review</span></div><p className="muted" style={{ fontSize: 11 }}>Data Structures · DBMS · Discrete Mathematics · Communication Skills</p></div><button className="btn" style={{ marginTop: 12 }} onClick={() => notify('New semester added to draft.')} data-testid="button-add-semester"><Plus size={14}/> Add semester</button></div>,
        <div key="courses"><EditableRow code="AI201" name="Machine Learning" credits="4"/><EditableRow code="AI202" name="Deep Learning" credits="4"/><EditableRow code="CS204" name="Database Management Systems" credits="4"/><button className="btn" style={{ marginTop: 9 }} onClick={() => notify('Course editor opened.')} data-testid="button-add-course"><Plus size={14}/> Add course</button></div>,
        <div key="outcomes"><p className="muted" style={{ fontSize: 12 }}>Define measurable outcomes and map them to assessments. AI suggestions remain clearly advisory.</p>{['CO1 · Explain core learning paradigms and data preparation choices.', 'CO2 · Implement and evaluate supervised learning pipelines.', 'CO3 · Analyze model behaviour, fairness and operational risk.'].map((outcome, i) => <div className="surface" style={{ padding: 14, marginTop: 9, display: 'flex', gap: 12 }} key={outcome}><span className="badge badge-lavender">CO{i + 1}</span><span style={{ fontSize: 12 }}>{outcome}</span></div>)}<button className="btn" style={{ marginTop: 12 }} onClick={() => notify('AI suggestion added as a draft outcome.')} data-testid="button-ai-outcome"><Sparkles size={14}/> Suggest outcome</button></div>,
        <StructureEditor label="Module structure" detail="Course → Module → Topic → Learning outcome" key="modules"/>,
        <StructureEditor label="Assessment plan" detail="Exams · assignments · quizzes · labs · projects" key="assessment"/>,
        <StructureEditor label="Resource set" detail="Books · research papers · videos · practical references" key="resources"/>,
        <div key="review" className="surface" style={{ padding: 17 }}><span className="eyebrow">Ready for review</span><h3 className="font-display" style={{ fontSize: 18, margin: '8px 0' }}>B.Tech Artificial Intelligence · v2.2</h3><p className="muted" style={{ fontSize: 12, lineHeight: 1.6 }}>8 semesters · 162 credits · 34 courses · 12 outcomes. One validation warning remains in Semester 2 workload.</p><div style={{ display: 'flex', alignItems: 'center', gap: 9, marginTop: 14 }}><CircleAlert size={15} color="#a2732c"/><span style={{ fontSize: 11 }}>Review warning before submission</span></div></div>,
        <div key="submit" style={{ textAlign: 'center', padding: 25 }}><div className="brand-mark" style={{ margin: '0 auto 12px' }}><Send size={20}/></div><h3 className="font-display" style={{ fontSize: 19 }}>Submit to AI screening and human review?</h3><p className="muted" style={{ fontSize: 12, maxWidth: 400, margin: '8px auto 17px', lineHeight: 1.6 }}>The reviewer remains the final decision-maker. You can continue editing while this version is Draft.</p><button className="btn btn-primary" onClick={() => { setSaved(true); notify('Curriculum submitted. Reviewer queue updated.'); }} data-testid="button-submit-curriculum"><Send size={14}/> Submit curriculum</button></div>,
    ];
    return <div className="content"><PageHeader eyebrow="Curriculum Designer / Builder" title="Create curriculum" detail="Upload a B.Tech CSE curriculum PDF to index it in your private Designer store." action={<span className="badge badge-lavender">Designer-owned</span>}/>{saved ? <div className="surface" style={{ padding: 40, textAlign: 'center' }}><CheckCircle2 size={34} color="#50865d"/><h2 className="font-display" style={{ margin: '12px 0 5px' }}>Submitted for screening</h2><p className="muted" style={{ fontSize: 12 }}>B.Tech CSE v{details.version} is now in the governed review workflow.</p></div> : <div className="surface" style={{ padding: 21 }}><div style={{ display: 'flex', gap: 7, overflowX: 'auto', paddingBottom: 18, marginBottom: 18, borderBottom: '1px solid hsl(var(--border))' }}>{steps.map((item, i) => <button key={item} className={`btn ${i === step ? 'btn-primary' : 'btn-ghost'}`} style={{ whiteSpace: 'nowrap', padding: '0 10px' }} onClick={() => setStep(i)} data-testid={`button-wizard-step-${i}`}><span style={{ opacity: .7 }}>{i + 1}</span> {item}</button>)}</div><div style={{ minHeight: 260 }}>{content[step]}</div><div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, paddingTop: 16, borderTop: '1px solid hsl(var(--border))' }}><button className="btn" disabled={step === 0 || uploading} onClick={() => setStep(Math.max(0, step - 1))} data-testid="button-wizard-back"><ArrowLeft size={14}/> Back</button>{step === 0 ? <button className="btn btn-primary" disabled={uploading || !selectedPdf} onClick={() => void uploadCurriculum()} data-testid="button-upload-curriculum">{uploading ? <RefreshCw size={14} className="analyzer-spin"/> : <Upload size={14}/>} {uploading ? 'Indexing PDF' : 'Upload curriculum'}</button> : <button className="btn btn-primary" disabled={step === steps.length - 1} onClick={() => setStep(Math.min(steps.length - 1, step + 1))} data-testid="button-wizard-next">Continue <ArrowRight size={14}/></button>}</div></div>}</div>;
}
function Field({ label, value, onChange, ...inputProps }) { return <div><label className="label">{label}</label><input className="field" {...(onChange ? { value, onChange } : { defaultValue: value })} {...inputProps} data-testid={`input-wizard-${label.toLowerCase().replaceAll(' ', '-')}`}/></div>; }
function EditableRow({ code, name, credits }) { return <div className="surface" style={{ padding: 13, display: 'grid', gridTemplateColumns: '.7fr 1.8fr .5fr auto', gap: 10, alignItems: 'center', marginBottom: 9 }}><span className="badge badge-lavender">{code}</span><strong style={{ fontSize: 12 }}>{name}</strong><span className="muted" style={{ fontSize: 11 }}>{credits} credits</span><button className="btn icon-btn" data-testid={`button-edit-course-${code}`}><Pencil size={14}/></button></div>; }
function StructureEditor({ label, detail }) { return <div className="surface" style={{ padding: 19 }}><span className="eyebrow">{label}</span><h3 className="font-display" style={{ fontSize: 18, margin: '7px 0' }}>{detail}</h3><div style={{ display: 'grid', gap: 8, marginTop: 16 }}>{['Core concepts and vocabulary', 'Applied lab / case study', 'Reflection and assessment checkpoint'].map((item, i) => <div key={item} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: 10, borderRadius: '.75rem', background: '#f6f1fa', fontSize: 12 }}><span className="badge badge-lavender">{i + 1}</span>{item}<Pencil size={13} style={{ marginLeft: 'auto' }}/></div>)}</div><button className="btn" style={{ marginTop: 14 }} data-testid={`button-add-${label.toLowerCase().replaceAll(' ', '-')}`}><Plus size={14}/> Add item</button></div>; }
function AssistantPage({ notify }) {
    const [question, setQuestion] = useState('What learning outcomes should I define for a DBMS course?');
    const [answer, setAnswer] = useState(null);
    const [loading, setLoading] = useState(false);
    const ask = async (event) => {
        event.preventDefault();
        if (!question.trim())
            return;
        setLoading(true);
        try {
            setAnswer(await mockService.askAssistant(question));
        }
        catch (error) {
            notify(error.message);
        }
        finally {
            setLoading(false);
        }
    };
    const sources = answer?.sources?.length ? answer.sources : sourceCards.slice(0, 2);
    return <div className="content"><PageHeader eyebrow="Designer / Evidence assistant" title="AI assistant" detail="Ask against AICTE sources and curriculum context, not an unrestricted chat model."/><div style={{ maxWidth: 980 }}><SectionCard title="Relevant official documents"><div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>{sourceCards.slice(0, 2).map((source) => <SourceCard key={source.section} source={source}/>)}</div></SectionCard><div style={{ marginTop: 16 }}><SectionCard title="Curriculum question"><div style={{ padding: 17, minHeight: 250, background: '#f9f5fd', borderRadius: 1, border: '1px solid #e1d6ef' }}>{loading ? <div className="muted" style={{ fontSize: 12 }}>Reading official sources and preparing a recommendation…</div> : answer ? <><span className="badge badge-slate">Your question</span><p style={{ fontSize: 13, lineHeight: 1.55 }}>{answer.question}</p><div style={{ marginTop: 17, padding: 14, borderRadius: '.8rem', background: '#f1e7fb', border: '1px solid #d8c6eb' }}><div style={{ color: '#73529e', fontSize: 10, fontWeight: 800, letterSpacing: '.08em' }}><Sparkles size={13} style={{ verticalAlign: 'middle', marginRight: 5 }}/> AI RECOMMENDATION</div><p style={{ fontSize: 12, lineHeight: 1.65, marginBottom: 0 }}>{answer.answer}</p></div><div style={{ display: 'flex', gap: 8, marginTop: 14 }}><button className="btn" onClick={() => notify('Recommendation copied into the outcome draft.')} data-testid="button-apply-ai-answer"><Check size={14}/> Apply to draft</button><button className="btn btn-ghost" onClick={() => setAnswer(null)} data-testid="button-new-question">New question</button></div></> : <div style={{ textAlign: 'center', padding: '50px 10px' }}><Bot size={27} color="#8061ac"/><p style={{ fontSize: 13, margin: '12px 0 4px' }}>Ask a curriculum question</p><span className="muted" style={{ fontSize: 11 }}>Responses carry official source references.</span></div>}</div><form onSubmit={ask} style={{ display: 'flex', gap: 8, marginTop: 13 }}><input className="field" value={question} onChange={(e) => setQuestion(e.target.value)} data-testid="input-assistant-question"/><button className="btn btn-primary icon-btn" data-testid="button-ask-assistant"><Send size={15}/></button></form></SectionCard></div></div></div>;
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
        <PageHeader eyebrow="Designer / Evidence assistant" title="AI Assistant" detail="Ask against indexed AICTE PDFs stored in MongoDB Atlas Vector Search."/>
        <div style={{ maxWidth: 980 }}>
            <SectionCard title="Conversation">
                <div className="rag-conversation" aria-live="polite">
                    {!messages.length && <div className="rag-empty"><Bot size={27} color="#8061ac"/><p>Start a grounded curriculum conversation</p><span>Ask about policies, course structure, outcomes, or assessment using the PDFs indexed by the Admin.</span></div>}
                    {messages.map((message, index) => <div className={`rag-message ${message.role}`} key={`${message.role}-${index}`}><span className="badge badge-slate">{message.role === 'user' ? 'You' : 'AI Assistant'}</span>{message.role === 'assistant' ? <RagAnswer content={message.content}/> : <p>{message.content}</p>}{message.role === 'assistant' && <button className="btn btn-ghost" style={{ padding: 0, minHeight: 0, color: '#7758aa' }} onClick={() => notify('Recommendation copied into the curriculum draft.')} data-testid={`button-apply-ai-answer-${index}`}><Check size={14}/> Apply to draft</button>}</div>)}
                    {loading && <div className="rag-message assistant"><span className="badge badge-slate">AI Assistant</span><p className="muted">Searching indexed PDF vectors and preparing a grounded answer…</p></div>}
                </div>
                <form onSubmit={ask} style={{ display: 'flex', gap: 8, marginTop: 13 }}>
                    <input className="field" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question about the indexed curriculum documents…" disabled={loading} data-testid="input-assistant-question"/>
                    <button className="btn btn-primary icon-btn" aria-label="Send question" disabled={loading || !question.trim()} data-testid="button-ask-assistant"><Send size={15}/></button>
                </form>
            </SectionCard>
            <div style={{ marginTop: 16 }}>
                <SectionCard title="Chat history" action={<button className="btn" onClick={startNewChat} disabled={loading} data-testid="button-new-assistant-chat"><Plus size={14}/> New chat</button>}>
                    {chats.length ? <div className="chat-history-list" aria-label="Previous chats">
                        {chats.map((chat) => <button key={chat.id} type="button" className={`chat-history-item ${chat.id === activeChatId ? 'active' : ''}`} onClick={() => { setActiveChatId(chat.id); setQuestion(''); }} data-testid={`button-chat-history-${chat.id}`}>
                            <MessageSquareText size={15}/><span><strong>{chat.title}</strong><small>{chat.messages.length} messages · {new Date(chat.updatedAt).toLocaleDateString()}</small></span><ChevronRight size={15}/>
                        </button>)}
                    </div> : <p className="muted" style={{ fontSize: 12, margin: 0 }}>Your completed conversations will appear here. Select one to continue where you left off.</p>}
                </SectionCard>
            </div>
            <div style={{ marginTop: 16 }}>
                <SectionCard title={sources.length ? 'Sources for the latest answer' : 'Sources will appear with the first answer'}>
                    {sources.length ? <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>{sources.map((source, index) => <SourceCard key={`${source.title}-${source.section}-${index}`} source={source}/>)}</div> : <p className="muted" style={{ fontSize: 12, margin: 0 }}>The assistant only answers from chunks retrieved from the MongoDB Atlas vector collection.</p>}
                </SectionCard>
            </div>
        </div>
    </div>;
}
function ResourcePage() {
    const [filter, setFilter] = useState('All');
    const resources = [['Deep Learning', 'Book', 'Ian Goodfellow · Neural Networks & Learning Representations', 'Backpropagation · optimization · CNN'], ['Practical CNN Lab', 'Practical resource', 'A guided image classification exercise with a clear evaluation rubric.', 'CNN · regularization · metrics'], ['Representation Learning Review', 'Research paper', 'A concise survey for the Neural Networks module.', 'Embeddings · transfer learning · evaluation'], ['Visualizing Model Training', 'Video', 'Short lecture with annotated training curves.', 'Optimization · diagnostics']];
    return <div className="content"><PageHeader eyebrow="Designer / Resource assistant" title="Recommended resources" detail="Context-aware recommendations for B.Tech AI · Deep Learning · Neural Networks." action={<select className="select" style={{ width: 145 }} value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="select-resource-filter"><option>All</option><option>Book</option><option>Research paper</option><option>Video</option><option>Practical resource</option></select>}/><div style={{ display: 'grid', gap: 11 }}>{resources.filter((item) => filter === 'All' || item[1] === filter).map((item) => <div className="surface" style={{ padding: 17, display: 'grid', gridTemplateColumns: '1fr .8fr auto', gap: 16, alignItems: 'center' }} key={item[0]}><div><span className="eyebrow">{item[1]}</span><h3 className="font-display" style={{ fontSize: 15, margin: '6px 0' }}>{item[0]}</h3><p className="muted" style={{ fontSize: 11, margin: 0 }}>{item[2]}</p></div><div><span className="eyebrow">Covered topics</span><p style={{ fontSize: 11, lineHeight: 1.5, marginBottom: 0 }}>{item[3]}</p></div><button className="btn" data-testid={`button-save-resource-${item[0].replaceAll(' ', '-')}`}><BookMarked size={14}/> Save</button></div>)}</div></div>;
}
function ComparisonPage() {
    const rows = [['Core AI', 'Strong', 'Good', 'Strong', 'Your outcomes need one more progressive assessment example.'], ['Machine Learning', 'Strong', 'Strong', 'Good', 'No material gap in this category.'], ['Deep Learning', 'Good', 'Partial', 'Strong', 'Reference B includes a stronger advanced vision and representation-learning sequence.'], ['Generative AI', 'Partial', 'Missing', 'Good', 'Add responsible generative AI, evaluation and safety coverage.'], ['MLOps', 'Missing', 'Partial', 'Good', 'Reference curricula include deployment, monitoring and model governance studios.'], ['Industry Project', 'Good', 'Strong', 'Strong', 'Add a larger client-style project with delivery evidence.'], ['Practical Hours', 'Partial', 'Good', 'Strong', 'Increase lab and project hours to match the stronger reference set.']];
    return <div className="content"><PageHeader eyebrow="Designer / Anonymous benchmarks" title="Curriculum comparison" detail="Reference curricula are anonymized by design. No institute identity or private metadata is exposed."/><SectionCard title="B.Tech Artificial Intelligence v2.1 compared with approved reference sets"><table className="data-table"><thead><tr><th>Category</th><th>Your curriculum</th><th>Reference Curriculum A</th><th>Reference Curriculum B</th><th>What is missing</th></tr></thead><tbody>{rows.map((row) => <tr key={row[0]}><td><strong>{row[0]}</strong></td>{row.slice(1, 4).map((cell, i) => <td key={i}><span className={`badge ${cell === 'Strong' ? 'badge-green' : cell === 'Good' ? 'badge-lavender' : cell === 'Partial' ? 'badge-amber' : 'badge-red'}`}>{cell}</span></td>)}<td><span className="muted" style={{ fontSize: 11, lineHeight: 1.4 }}>{row[4]}</span></td></tr>)}</tbody></table></SectionCard><div style={{ marginTop: 16 }}><SectionCard title="Recommended improvement"><div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}><div><span className="eyebrow">Problem</span><p style={{ fontSize: 12 }}>MLOps is missing from the current map.</p></div><div><span className="eyebrow">Evidence</span><p style={{ fontSize: 12 }}>Reference sets include deployment and monitoring outcomes.</p></div><div><span className="eyebrow">Why</span><p style={{ fontSize: 12 }}>Graduates need a bridge from model building to operation.</p></div><div><span className="eyebrow">Suggested revision</span><p style={{ fontSize: 12, color: '#694a98' }}>Add a 2-credit model operations studio.</p></div></div></SectionCard></div></div>;
}
function LegacyAnalyzerMock({ notify }) {
    const [active, setActive] = useState([true, true, true]);
    const issues = [['HIGH', 'Resource quality is uneven', '64% of sources have complete bibliographic metadata.', 'Students and reviewers cannot reliably audit the source set.', 'Complete metadata and replace two undated links.'], ['MEDIUM', 'Industry relevance can be stronger', 'No dedicated MLOps or deployment studio appears in the map.', 'The programme ends at model training rather than delivery.', 'Add a model operations studio in Semester 7.'], ['LOW', 'Assessment balance', 'Practical evaluation is 12% of the total plan.', 'The stated hands-on outcomes deserve a stronger assessment signal.', 'Increase lab and project weighting by 4%.']];
    return <div className="content"><PageHeader eyebrow="Designer / Curriculum health report" title="Curriculum analyzer" detail="A decision aid for the designer — not an approval authority." action={<button className="btn btn-primary" onClick={() => notify('Health report recalculated.')} data-testid="button-recalculate-analyzer"><RefreshCw size={14}/> Recalculate</button>}/><div className="surface soft-gradient" style={{ padding: 22, marginBottom: 16 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><div><p className="eyebrow">Curriculum health report</p><h2 className="font-display" style={{ fontSize: 21, margin: '6px 0' }}>B.Tech Artificial Intelligence · v2.0</h2><span style={{ fontSize: 11 }}>6 dimensions · 24 evidence checks</span></div><div style={{ textAlign: 'center' }}><strong className="font-display" style={{ fontSize: 44, letterSpacing: '-.08em' }}>78</strong><div style={{ fontSize: 10 }}>OVERALL / 100</div></div></div></div><div className="stat-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>{[['Structure', 89], ['Compliance', 91], ['Industry relevance', 68], ['Learning outcomes', 72], ['Assessment', 75], ['Resources', 64], ['Skill coverage', 79]].map(([label, value]) => <ScoreTile key={label} label={label} value={value}/>)}</div><div style={{ display: 'grid', gap: 12, marginTop: 17 }}>{issues.map((issue, i) => active[i] && <div className="surface" style={{ padding: 18 }} key={issue[1]}><div style={{ display: 'flex', justifyContent: 'space-between' }}><div><span className={`badge ${issue[0] === 'HIGH' ? 'badge-red' : issue[0] === 'MEDIUM' ? 'badge-amber' : 'badge-lavender'}`}>{issue[0]}</span><h3 className="font-display" style={{ fontSize: 15, margin: '8px 0' }}>{issue[1]}</h3></div><button className="btn icon-btn" onClick={() => setActive(active.map((item, index) => index === i ? false : item))} data-testid={`button-dismiss-analyzer-${i}`}><X size={14}/></button></div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 13 }}><div><span className="eyebrow">Problem</span><p style={{ fontSize: 11 }}>{issue[1]}</p></div><div><span className="eyebrow">Evidence</span><p style={{ fontSize: 11 }}>{issue[2]}</p></div><div><span className="eyebrow">Why it matters</span><p style={{ fontSize: 11 }}>{issue[3]}</p></div><div><span className="eyebrow">Recommended solution</span><p style={{ fontSize: 11 }}>{issue[4]}</p></div></div><div style={{ display: 'flex', gap: 8, marginTop: 11 }}><button className="btn btn-primary" onClick={() => notify('Suggestion applied to the draft plan.')} data-testid={`button-apply-analyzer-${i}`}><Check size={14}/> Apply suggestion</button><button className="btn" onClick={() => notify('Manual editor opened for this finding.')} data-testid={`button-edit-analyzer-${i}`}><Pencil size={14}/> Edit manually</button></div></div>)}</div></div>;
}
function Analyzer({ notify }) {
    const [documents, setDocuments] = useState([]);
    const [selectedKey, setSelectedKey] = useState('');
    const [report, setReport] = useState(null);
    const [selectedCriterion, setSelectedCriterion] = useState(null);
    const [state, setState] = useState('loading');
    const [error, setError] = useState('');

    const analyze = async (requestedDocument = null, announce = false) => {
        setState('loading');
        setError('');
        setSelectedCriterion(null);
        try {
            let available = documents;
            if (!available.length) {
                available = submittedCurriculumDocuments(await mockService.getDocuments());
                setDocuments(available);
            }
            const target = requestedDocument
                || (!selectedKey && requestedAnalyzerDocument(available, window.location.search))
                || available.find((item) => analyzerDocumentKey(item) === selectedKey)
                || available[0];
            if (!target) {
                setReport(null);
                setState('empty');
                return;
            }
            setSelectedKey(analyzerDocumentKey(target));
            const result = await mockService.analyzeCurriculum(target.curriculum_id, target.document_id);
            setReport(result);
            setState('ready');
            if (announce)
                notify('Curriculum health report recalculated from backend evidence.');
        }
        catch (requestError) {
            setReport(null);
            setError(requestError.message || 'Unable to analyze this curriculum.');
            setState({ 404: 'not-found', 409: 'ambiguous', 422: 'invalid-metadata' }[requestError.status] || 'error');
        }
    };

    useEffect(() => {
        void analyze();
    }, []);

    const selectedDocument = documents.find((item) => analyzerDocumentKey(item) === selectedKey);
    const criteria = report?.criteria || [];
    const checkCount = criteria.reduce((total, criterion) => total + (criterion.checks?.length || 0), 0);
    const aicteReferenceUnavailable = report?.aicte_reference_available === false;
    const overallScore = aicteReferenceUnavailable ? 'Not Evaluable' : report?.overall_score == null ? '—' : report.overall_score;
    const partialCurriculum = isPartialCurriculum(report);

    return <div className="content">
        <PageHeader
            eyebrow="Designer / Curriculum health report"
            title="Curriculum analyzer"
            detail="Deterministic B.Tech CSE scores with check-level AICTE and curriculum evidence."
            action={<button className="btn btn-primary" disabled={state === 'loading'} onClick={() => void analyze(null, true)} data-testid="button-recalculate-analyzer"><RefreshCw size={14}/> {state === 'loading' ? 'Analyzing' : 'Recalculate'}</button>}
        />
        {documents.length > 1 && <div className="surface" style={{ padding: 13, marginBottom: 15 }}>
            <label className="label" htmlFor="analyzer-curriculum">Submitted curriculum</label>
            <select id="analyzer-curriculum" className="select" value={selectedKey} onChange={(event) => {
                const next = documents.find((item) => analyzerDocumentKey(item) === event.target.value);
                if (next)
                    void analyze(next);
            }} data-testid="select-analyzer-curriculum">
                {documents.map((document) => <option value={analyzerDocumentKey(document)} key={analyzerDocumentKey(document)}>{document.filename} · {document.curriculum_id}</option>)}
            </select>
        </div>}
        {state === 'loading' && <div className="surface" style={{ padding: 28, textAlign: 'center' }} data-testid="analyzer-loading"><RefreshCw size={22} className="analyzer-spin"/><h2 className="font-display" style={{ fontSize: 17 }}>Analyzing curriculum</h2><p className="muted" style={{ fontSize: 12 }}>Extracting the submitted curriculum and evaluating deterministic checks…</p></div>}
        {state === 'empty' && <AnalyzerState title="No submitted curriculum found" detail="Upload a PDF classified as submitted_curriculum with a curriculum_id before running the analyzer." testId="analyzer-empty"/>}
        {state === 'not-found' && <AnalyzerState title="Curriculum not found" detail={error} testId="analyzer-not-found" onRetry={() => void analyze()}/>}
        {state === 'ambiguous' && <AnalyzerState title="Ambiguous curriculum selection" detail={error} testId="analyzer-ambiguous" onRetry={() => void analyze()}/>}
        {state === 'invalid-metadata' && <AnalyzerState title="Invalid curriculum metadata" detail={error} testId="analyzer-invalid-metadata" onRetry={() => void analyze()}/>}
        {state === 'error' && <AnalyzerState title="Analyzer API error" detail={error} testId="analyzer-error" onRetry={() => void analyze()}/>}
        {state === 'ready' && report && <>
            {aicteReferenceUnavailable && <div className="surface analyzer-issues-unavailable" style={{ margin: '0 0 16px' }} data-testid="analyzer-aicte-reference-unavailable"><CircleAlert size={20}/><div><strong>AICTE Reference: Unavailable</strong><span>{report.aicte_reference_message || 'Official AICTE reference documents are not currently available. AICTE-based compliance evaluation cannot be completed.'}</span><span>Curriculum extraction: Available · AICTE evidence: Unavailable · AICTE-based score: Not Evaluable</span></div></div>}
            <div className="surface soft-gradient" style={{ padding: 22, marginBottom: 16 }} data-testid="analyzer-summary">
                <div className="analyzer-summary-grid">
                    <div>
                        <p className="eyebrow">Curriculum health report · {report.scoring_version}</p>
                        <h2 className="font-display" style={{ fontSize: 21, margin: '6px 0' }}>{selectedDocument?.filename || report.curriculum_id}</h2>
                        <span style={{ fontSize: 11 }}>B.Tech CSE · {criteria.length} criteria · {checkCount} evidence checks</span>
                        <div className="analyzer-scope" data-testid="analyzer-document-scope">
                            <span className="eyebrow">Document Scope</span>
                            <strong>{documentScopeLabel(report.document_scope)}</strong>
                            <p>{report.scope_reason || 'Document scope explanation is unavailable.'}</p>
                        </div>
                    </div>
                    <div className="analyzer-overall">
                        <span className="eyebrow">{overallScoreLabel(report)}</span>
                        <strong className="font-display" style={aicteReferenceUnavailable ? { fontSize: 23, letterSpacing: '-.03em' } : undefined} data-testid="analyzer-overall-score">{report.overall_score == null ? overallScore : `${overallScore}%`}</strong>
                        <div className="muted" data-testid="analyzer-evaluation-coverage">{aicteReferenceUnavailable ? `Curriculum-only evaluation coverage: ${report.overall_evaluation_coverage}%` : partialCurriculum ? `Based on ${report.overall_evaluation_coverage}% evaluation coverage` : `Evaluation Coverage: ${report.overall_evaluation_coverage}%`}</div>
                        {(report.low_coverage || hasLowEvaluationCoverage(report.overall_evaluation_coverage)) && <span className="badge badge-amber" style={{ marginTop: 7 }}>Limited evaluation coverage</span>}
                    </div>
                </div>
                {partialCurriculum && <div className="analyzer-scope-warning" data-testid="analyzer-partial-warning"><CircleAlert size={17}/><span><strong>Partial curriculum analyzed.</strong> The score reflects only the criteria that could be evaluated from the submitted document.</span></div>}
            </div>
            {report.overall_evaluation_coverage === 0 && <AnalyzerState title="Insufficient evidence" detail="The curriculum was found, but no checks had reliable extracted inputs. Open a criterion to see which checks were excluded." testId="analyzer-insufficient"/>}
            <div className="stat-grid analyzer-score-grid">
                {criteria.map((criterion) => <AnalyzerScoreTile key={criterion.criterion} criterion={criterion} onClick={() => setSelectedCriterion(criterion)}/>) }
            </div>
            <AnalyzerIssues report={report}/>
        </>}
        {selectedCriterion && report && <AnalyzerCriterionModal criterion={selectedCriterion} report={report} onClose={() => setSelectedCriterion(null)}/>}
    </div>;
}

function AnalyzerState({ title, detail, testId, onRetry }) {
    return <div className="surface" style={{ padding: 25, textAlign: 'center', marginBottom: 16 }} data-testid={testId}><CircleAlert size={23} color="#8b6a30"/><h2 className="font-display" style={{ fontSize: 17, margin: '10px 0 5px' }}>{title}</h2><p className="muted" style={{ fontSize: 12, margin: '0 auto', maxWidth: 620 }}>{detail}</p>{onRetry && <button className="btn" style={{ marginTop: 14 }} onClick={onRetry}><RefreshCw size={14}/> Retry</button>}</div>;
}

function AnalyzerIssues({ report }) {
    if (!report.issues_available)
        return <div className="surface analyzer-issues-unavailable" data-testid="analyzer-issues-unavailable"><CircleAlert size={18}/><div><strong>{report.aicte_reference_available === false ? 'AICTE-based recommendations are unavailable.' : 'AI recommendations are temporarily unavailable.'}</strong><span>{report.issues_error || 'Your deterministic scores and evidence are still available.'}</span></div></div>;
    if (!report.issues?.length)
        return <div className="surface analyzer-no-issues" data-testid="analyzer-no-issues"><CheckCircle2 size={18}/><div><strong>No priority recommendations generated</strong><span>No failed or partial checks were selected for an issue card.</span></div></div>;
    return <section className="analyzer-issues" data-testid="analyzer-live-issues">
        <div className="analyzer-issues-heading"><div><p className="eyebrow">Advisory recommendations</p><h2 className="font-display">Priority findings</h2></div><span className="badge badge-lavender">{report.issues.length} generated</span></div>
        <div style={{ display: 'grid', gap: 12 }}>
            {report.issues.map((issue) => <AnalyzerIssueCard issue={issue} key={issue.issue_id}/>) }
        </div>
    </section>;
}

function AnalyzerIssueCard({ issue }) {
    const severityTone = {
        CRITICAL: 'badge-red',
        HIGH: 'badge-red',
        MEDIUM: 'badge-amber',
        LOW: 'badge-lavender',
    };
    const evidence = [...(issue.curriculum_evidence || []), ...(issue.aicte_evidence || [])].slice(0, 3);
    return <article className="surface analyzer-issue-card" data-testid={`analyzer-issue-${issue.issue_id}`}>
        <div className="analyzer-issue-title">
            <div><span className={`badge ${severityTone[issue.severity] || 'badge-lavender'}`}>{issue.severity}</span><span className="eyebrow" style={{ marginLeft: 8 }}>Problem</span><h3 className="font-display">{issue.problem}</h3></div>
            <span className="badge badge-slate">{issue.criterion.replaceAll('_', ' ')}</span>
        </div>
        <div className="analyzer-issue-grid">
            <div><span className="eyebrow">Evidence / related criterion</span>{evidence.length ? evidence.map((item, index) => <div className="analyzer-issue-evidence" key={`${item.source || 'curriculum'}-${item.page_number}-${item.chunk_index}-${index}`}><p>{item.excerpt}</p><small>{item.source || 'Submitted curriculum'} · {item.page_number != null ? `Page ${item.page_number}` : 'Page unavailable'} · {item.chunk_index != null ? `Chunk ${item.chunk_index}` : 'Chunk unavailable'}</small></div>) : <p>The recommendation is grounded in the related deterministic checks.</p>}<small>{(issue.related_check_ids || []).join(' · ')}</small></div>
            <div><span className="eyebrow">Why it matters</span><p>{issue.why_it_matters}</p></div>
            <div><span className="eyebrow">Recommended solution</span><p>{issue.recommended_solution}</p></div>
        </div>
    </article>;
}

function AnalyzerScoreTile({ criterion, onClick }) {
    const score = criterionScoreLabel(criterion);
    const limited = criterion.low_coverage || hasLowEvaluationCoverage(criterion.evaluation_coverage);
    return <button className="surface analyzer-score-tile" onClick={onClick} data-testid={`card-analyzer-criterion-${criterion.criterion}`} aria-label={`Open ${criterion.label} score evidence`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}><span>{criterion.label}</span><strong className={criterion.score == null ? 'analyzer-not-evaluable-score' : ''}>{score}</strong></div>
        {criterion.score == null ? <div className="analyzer-excluded-bar">Excluded from scoring</div> : <MiniBar value={criterion.score}/>}
        <span className="muted" style={{ display: 'block', fontSize: 10, marginTop: 9 }}>Evaluation coverage: {criterion.evaluation_coverage}%</span>
        {limited && <span className="badge badge-amber" style={{ marginTop: 7 }}>Limited evidence</span>}
    </button>;
}

function displayAnalyzerValue(value) {
    if (value == null || value === '')
        return 'Not available';
    if (typeof value === 'object')
        return JSON.stringify(value, null, 2);
    return String(value);
}

function AnalyzerEvidenceList({ title, evidence, official = false }) {
    return <div className="analyzer-evidence-group"><span className="eyebrow">{title}</span>{evidence?.length ? evidence.map((item, index) => <div className="analyzer-evidence" key={`${item.source || 'curriculum'}-${item.page_number}-${item.chunk_index}-${index}`}>
        {official && <strong>{item.source}</strong>}
        {item.heading && <span>{item.heading}</span>}
        <p>{item.excerpt}</p>
        <small>{item.page_number != null ? `Page ${item.page_number}` : 'Page unavailable'} · {item.chunk_index != null ? `Chunk ${item.chunk_index}` : 'Chunk unavailable'}</small>
    </div>) : <p className="muted" style={{ fontSize: 11 }}>No evidence excerpt is available for this check.</p>}</div>;
}

function AnalyzerCriterionModal({ criterion, report, onClose }) {
    const score = criterionScoreLabel(criterion);
    const statusTone = { pass: 'badge-green', partial: 'badge-amber', fail: 'badge-red', not_evaluable: 'badge-slate' };
    return <Modal title={`${criterion.label.toUpperCase()} — ${score}`} onClose={onClose} wide>
        <div className="analyzer-modal-summary">
            <div><span className="eyebrow">Score calculation</span><strong>{criterionCalculation(criterion)}</strong></div>
            <div><span className="eyebrow">Evaluation coverage</span><strong>{coverageCalculation(criterion)}</strong></div>
        </div>
        {(criterion.low_coverage || hasLowEvaluationCoverage(criterion.evaluation_coverage)) && <div className="analyzer-limited-note"><CircleAlert size={15}/><span><strong>Limited evidence.</strong> Fewer than half of this criterion’s possible check marks were evaluable.</span></div>}
        <div className="analyzer-check-list">
            {(criterion.checks || []).map((check) => <section className={`analyzer-check analyzer-check-${check.status}`} key={check.check_id} data-testid={`analyzer-check-${check.check_id}`}>
                <div className="analyzer-check-heading">
                    <div><span className={`badge ${statusTone[check.status]}`}>{checkStatusLabel(check.status)}</span><h3 className="font-display">{check.title}</h3></div>
                    <strong>{check.status === 'not_evaluable' ? 'Excluded from score' : `${check.obtained_marks} / ${check.maximum_marks}`}</strong>
                </div>
                <span className="badge badge-lavender">{check.rule_type.replaceAll('_', ' ')}</span>
                <div className="analyzer-check-marks">
                    <div><span className="eyebrow">Obtained marks</span><strong>{check.status === 'not_evaluable' ? 'Not scored' : check.obtained_marks}</strong></div>
                    <div><span className="eyebrow">Maximum marks</span><strong>{check.maximum_marks}</strong></div>
                </div>
                <div className="analyzer-expected-grid">
                    <div><span className="eyebrow">Expected</span><pre>{displayAnalyzerValue(check.expected)}</pre></div>
                    <div><span className="eyebrow">Actual curriculum value</span><pre>{displayAnalyzerValue(check.actual)}</pre></div>
                </div>
                <div className="analyzer-reason"><span className="eyebrow">Deduction reason</span><p>{check.deduction_reason}</p></div>
                {check.status === 'not_evaluable' && <div className="analyzer-not-evaluable-note" data-testid={`analyzer-not-evaluable-${check.check_id}`}><strong>This check was excluded from scoring because sufficient evidence was not available.</strong><span>It was excluded from both obtained and maximum evaluable marks; it is not a failure.</span>{isPartialScopeExclusion(report, check) && <span>Not evaluated because the submitted document does not represent the complete B.Tech CSE programme.</span>}</div>}
                <div className="analyzer-evidence-grid">
                    <AnalyzerEvidenceList title="AICTE Evidence" evidence={check.aicte_evidence} official/>
                    <AnalyzerEvidenceList title="Curriculum Evidence" evidence={check.curriculum_evidence}/>
                </div>
            </section>)}
        </div>
        <div className="surface inset-surface analyzer-modal-total" data-testid="analyzer-modal-calculation">
            <div><span>Obtained evaluable marks</span><strong>{criterion.obtained_marks}</strong></div>
            <div><span>Evaluable maximum marks</span><strong>{criterion.evaluable_maximum_marks}</strong></div>
            <div><span>Total possible marks</span><strong>{criterion.configured_maximum_marks}</strong></div>
            <p><strong>Criterion score:</strong> {criterionCalculation(criterion)}</p>
            <p><strong>Evaluation coverage:</strong> {coverageCalculation(criterion)}</p>
        </div>
    </Modal>;
}

function DesignerChanges({ notify }) {
    const [changes, setChanges] = useState(mockChanges);
    return <div className="content"><PageHeader eyebrow="Designer / Next version inputs" title="Change requests" detail="Accepting a request informs the next curriculum version. It never edits a published version directly."/><div style={{ display: 'grid', gap: 12 }}>{changes.map((change) => <div className="surface" style={{ padding: 19 }} key={change.id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><div><span className="eyebrow">CHANGE REQUEST #{change.id}</span><h3 className="font-display" style={{ fontSize: 17, margin: '7px 0' }}>{change.course}</h3></div><div style={{ display: 'flex', gap: 7 }}><span className={`badge ${change.priority === 'High' ? 'badge-red' : 'badge-amber'}`}>{change.priority} priority</span><StatusBadge status={change.status}/></div></div><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 15, marginTop: 13 }}><div><span className="eyebrow">Issue</span><p style={{ fontSize: 12 }}>{change.issue}</p></div><div><span className="eyebrow">Suggested change</span><p style={{ fontSize: 12 }}>{change.suggestion}</p></div><div><span className="eyebrow">Reason / evidence</span><p style={{ fontSize: 12 }}>{change.reason}</p></div></div><div style={{ display: 'flex', gap: 8, marginTop: 8 }}><button className="btn btn-primary" onClick={() => { setChanges(changes.map((item) => item.id === change.id ? { ...item, status: 'Included in Next Version' } : item)); notify(`${change.id} added to the next version backlog.`); }} data-testid={`button-accept-change-${change.id}`}><Check size={14}/> Add to next version</button><button className="btn" onClick={() => notify('Discussion note opened.')} data-testid={`button-discuss-change-${change.id}`}><MessageSquareText size={14}/> Discuss</button></div></div>)}</div></div>;
}
function ImprovementTracker({ notify }) {
    const [curriculumId, setCurriculumId] = useState(analyzerScoreHistory[0].curriculumId);
    const item = analyzerScoreHistory.find((record) => record.curriculumId === curriculumId) ?? analyzerScoreHistory[0];
    const first = item.versions[0];
    const latest = item.versions[item.versions.length - 1];
    const improvement = latest.score - first.score;
    const previous = item.versions[item.versions.length - 2];
    const recentChange = latest.score - previous.score;
    return <div className="content"><PageHeader eyebrow="Designer / Continuous improvement" title="Improvement tracker" detail="Compare every analyzed curriculum version and see the score improvement created by completed revisions." action={<button className="btn" onClick={() => notify('Analyzer score history refreshed.')} data-testid="button-refresh-improvement"><RefreshCw size={14}/> Refresh history</button>}/><div className="surface" style={{ padding: 8, display: 'flex', gap: 5, overflowX: 'auto', marginBottom: 15 }}>{analyzerScoreHistory.map((record) => <button key={record.curriculumId} className={`btn ${record.curriculumId === curriculumId ? 'btn-primary' : 'btn-ghost'}`} style={{ whiteSpace: 'nowrap', padding: '0 12px' }} onClick={() => setCurriculumId(record.curriculumId)} data-testid={`tab-improvement-${record.curriculumId}`}>{record.name}</button>)}</div><div className="improvement-summary"><div className="surface improvement-score-card"><span className="eyebrow">Latest analyzer score</span><strong>{latest.score}<small>/100</small></strong><span className="muted">v{latest.version} · {latest.analyzedOn}</span></div><div className="surface improvement-score-card positive"><span className="eyebrow">Total improvement</span><strong>+{improvement}<small> points</small></strong><span className="muted">From v{first.version} ({first.score}) to v{latest.version}</span></div><div className="surface improvement-score-card"><span className="eyebrow">Last version change</span><strong>{recentChange > 0 ? '+' : ''}{recentChange}<small> points</small></strong><span className="muted">Since v{previous.version} ({previous.score})</span></div></div><SectionCard title={`${item.name} — analyzer score history`}><p className="muted" style={{ fontSize: 11, marginTop: -5 }}>Institute: {item.institute}. Each point is recorded from a completed Curriculum Analyzer run.</p><div className="version-score-chart" aria-label="Analyzer score by curriculum version">{item.versions.map((version) => <div className="version-score-column" key={version.version}><div className="version-score-value">{version.score}</div><div className="version-score-bar"><span style={{ height: `${version.score}%` }}/></div><strong>v{version.version}</strong></div>)}</div><div className="table-scroll"><table className="data-table"><thead><tr><th>Version</th><th>Analyzer score</th><th>Change from prior version</th><th>Findings resolved</th><th>Analyzed on</th></tr></thead><tbody>{item.versions.map((version, index) => { const delta = index ? version.score - item.versions[index - 1].score : null; return <tr key={version.version}><td><strong>v{version.version}</strong>{index === item.versions.length - 1 && <span className="badge badge-lavender" style={{ marginLeft: 8 }}>Current</span>}</td><td><strong>{version.score}</strong><span className="muted"> /100</span></td><td>{delta === null ? <span className="muted">Baseline</span> : <span className={delta > 0 ? 'score-gain' : 'muted'}>{delta > 0 ? '+' : ''}{delta} points</span>}</td><td>{version.findingsResolved}</td><td>{version.analyzedOn}</td></tr>; })}</tbody></table></div></SectionCard></div>;
}
function PublishedPage() { return <div className="content"><PageHeader eyebrow="Designer / Public record" title="Published curricula" detail="Versions currently visible to their explicitly selected institutes."/><SectionCard title="Published catalogue"><CurriculumTable items={mockCurricula.filter((item) => item.status === 'Published' || item.status === 'Approved')} onAction={() => undefined}/></SectionCard></div>; }
function InstituteCurricula() {
    const published = mockCurricula.filter((item) => item.status === 'Published');
    return <div className="content"><PageHeader eyebrow="Institute / Published access" title="Available curricula" detail="Only curricula explicitly published to Northstar Institute of Technology appear here."/><div style={{ display: 'grid', gap: 12 }}>{published.map((item) => <div className="surface" style={{ padding: 19 }} key={item.id}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}><div><span className="eyebrow">Published · 2026–27</span><h2 className="font-display" style={{ fontSize: 17, margin: '7px 0' }}>{item.name}</h2><p className="muted" style={{ fontSize: 11, margin: 0 }}>{item.program} · Version {item.version} · 8 semesters · 162 credits</p></div><StatusBadge status="Published"/></div><div style={{ display: 'flex', gap: 8, marginTop: 15 }}><button className="btn" data-testid={`button-view-published-${item.id}`}><Eye size={14}/> View curriculum</button><button className="btn" data-testid={`button-view-version-${item.id}`}><History size={14}/> Version history</button></div></div>)}</div></div>;
}
function InstituteCourses() {
    const courses = [['Data Structures', 'CSE201', 'B.Tech CSE · v1.4', 'Dr. Kavya Menon'], ['Database Management Systems', 'CS204', 'B.Tech CSE · v1.4', 'Unassigned'], ['Machine Learning', 'AI201', 'B.Tech AI · v2.0', 'Prof. Nikhil Shah'], ['Deep Learning', 'AI202', 'B.Tech AI · v2.0', 'Unassigned']];
    return <div className="content"><PageHeader eyebrow="Institute / Delivery" title="My courses" detail="Course workspaces inherit the published curriculum version and its outcomes."/><SectionCard title="Assigned and available course workspaces"><table className="data-table"><thead><tr><th>Course</th><th>Code</th><th>Curriculum</th><th>Coordinator</th><th>Action</th></tr></thead><tbody>{courses.map((course, i) => <tr key={course[1]}><td><strong>{course[0]}</strong></td><td>{course[1]}</td><td>{course[2]}</td><td>{course[3] === 'Unassigned' ? <span className="badge badge-amber">Unassigned</span> : course[3]}</td><td><button className="btn" data-testid={`button-open-course-${i}`}><Eye size={14}/> Open</button></td></tr>)}</tbody></table></SectionCard></div>;
}
function Coordinators({ notify }) {
    const [course, setCourse] = useState('Database Management Systems');
    const [coordinator, setCoordinator] = useState('');
    const [assigned, setAssigned] = useState(false);
    return <div className="content"><PageHeader eyebrow="Institute / Delivery ownership" title="Course coordinators" detail="One active coordinator per institute + course + curriculum version. This demo enforces the rule before saving."/><div style={{ display: 'grid', gridTemplateColumns: '.95fr 1.05fr', gap: 16 }}><SectionCard title="Assign coordinator"><label className="label">Course and version</label><select className="select" value={course} onChange={(e) => setCourse(e.target.value)} data-testid="select-coordinator-course"><option>Database Management Systems · CSE204 · v1.4</option><option>Data Structures · CSE201 · v1.4</option><option>Machine Learning · AI201 · v2.0</option></select><label className="label" style={{ marginTop: 15 }}>Coordinator</label><select className="select" value={coordinator} onChange={(e) => setCoordinator(e.target.value)} data-testid="select-coordinator-person"><option value="">Select a faculty member</option><option>Dr. Kavya Menon</option><option>Prof. Nikhil Shah</option><option>Dr. Leena Thomas</option></select><button className="btn btn-primary" style={{ width: '100%', marginTop: 19 }} disabled={!coordinator} onClick={() => { setAssigned(true); notify('Coordinator assignment saved as the single active owner.'); }} data-testid="button-assign-coordinator"><UserCog size={15}/> {assigned ? 'Change coordinator' : 'Assign coordinator'}</button><div style={{ background: '#f8f0e9', border: '1px solid #ecd8ca', borderRadius: '.85rem', padding: 12, marginTop: 16, fontSize: 11, lineHeight: 1.55 }}><strong>Assignment rule</strong><br />An active assignment is unique for this institute, course and published curriculum version.</div></SectionCard><SectionCard title="Assignment history"><div style={{ display: 'grid', gap: 10 }}>{[['Dr. Kavya Menon', 'Data Structures · v1.4', 'Active', '04 Mar 2026'], ['Prof. Nikhil Shah', 'Machine Learning · v2.0', 'Active', '28 Feb 2026'], ['S. Banerjee', 'DBMS · v1.2', 'Ended', '14 Nov 2025']].map((row) => <div className="surface" style={{ padding: 14 }} key={row[1]}><div style={{ display: 'flex', justifyContent: 'space-between' }}><strong style={{ fontSize: 12 }}>{row[0]}</strong><StatusBadge status={row[2]}/></div><p className="muted" style={{ margin: '5px 0 0', fontSize: 11 }}>{row[1]} · {row[3]}</p></div>)}</div></SectionCard></div></div>;
}
function ChangeRequests({ notify }) {
    const [sent, setSent] = useState(false);
    const [status, setStatus] = useState('Submitted');
    return <div className="content"><PageHeader eyebrow="Institute / Curriculum feedback loop" title="Change requests" detail="A structured request enters designer review and never edits a published curriculum directly." action={<span className="badge badge-lavender">Northstar Institute</span>}/><div style={{ display: 'grid', gridTemplateColumns: '1fr .8fr', gap: 16 }}><SectionCard title="Request a curriculum change">{sent ? <div style={{ textAlign: 'center', padding: 20 }}><CheckCircle2 size={32} color="#50865d"/><h3 className="font-display" style={{ fontSize: 18, margin: '10px 0' }}>Request submitted</h3><p className="muted" style={{ fontSize: 12 }}>CR-1031 is now visible to the curriculum designer.</p></div> : <form onSubmit={(e) => { e.preventDefault(); setSent(true); notify('Change request CR-1031 submitted.'); }}><label className="label">Course</label><select className="select" data-testid="select-change-course"><option>Data Structures</option><option>Database Management Systems</option><option>Machine Learning</option></select><label className="label" style={{ marginTop: 13 }}>Current issue</label><input className="field" required placeholder="Describe the gap you observed" data-testid="input-change-issue"/><label className="label" style={{ marginTop: 13 }}>Suggested change</label><input className="field" required placeholder="What should be added or adjusted?" data-testid="input-change-suggestion"/><label className="label" style={{ marginTop: 13 }}>Reason / evidence</label><textarea className="textarea" required placeholder="Connect this request to student or delivery evidence." data-testid="textarea-change-reason"/><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 13 }}><div><label className="label">Priority</label><select className="select"><option>High</option><option>Medium</option><option>Low</option></select></div><div><label className="label">Academic year</label><select className="select"><option>2027–28</option><option>2028–29</option></select></div></div><button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} data-testid="button-submit-change-request"><Send size={14}/> Submit change request</button></form>}</SectionCard><SectionCard title="Request status"><div style={{ display: 'grid', gap: 0 }}>{['Submitted', 'Under Designer Review', 'Accepted / Rejected'].map((item, i) => <div key={item} style={{ display: 'flex', gap: 12, minHeight: 68, position: 'relative' }}><div style={{ width: 24, height: 24, borderRadius: '50%', display: 'grid', placeItems: 'center', background: i === 0 || (i === 1 && status !== 'Submitted') ? '#dfd2f2' : '#eeeaf0', color: '#694a98', zIndex: 1 }}><Check size={13}/></div>{i < 2 && <div style={{ width: 1, background: '#ded5e6', position: 'absolute', left: 12, top: 24, bottom: 0 }}/>}<div><strong style={{ display: 'block', fontSize: 12 }}>{item}</strong><span className="muted" style={{ fontSize: 10 }}>{i === 0 ? 'CR-1031 · just now' : i === 1 ? 'Awaiting designer response' : 'Decision will be recorded here'}</span></div></div>)}</div><button className="btn" onClick={() => { setStatus('Under Review'); notify('Demo status progressed to Under Designer Review.'); }} data-testid="button-progress-change-status"><RefreshCw size={14}/> Progress demo status</button></SectionCard></div></div>;
}
function Feedback({ notify }) {
    return <div className="content"><PageHeader eyebrow="Institute / Voice of delivery" title="Feedback" detail="Capture what students and faculty encounter in the published curriculum."/><div style={{ maxWidth: 720 }}><SectionCard title="Share delivery feedback"><label className="label">Curriculum</label><select className="select"><option>B.Tech CSE · v1.4</option><option>B.Tech AI · v2.0</option></select><label className="label" style={{ marginTop: 14 }}>Feedback category</label><select className="select"><option>Course coverage</option><option>Assessment design</option><option>Resources</option><option>Learning outcomes</option></select><label className="label" style={{ marginTop: 14 }}>Your observation</label><textarea className="textarea" placeholder="Be specific so the designer can act on the evidence." data-testid="textarea-feedback"/><button className="btn btn-primary" style={{ marginTop: 17 }} onClick={() => notify('Feedback shared with the curriculum team.')} data-testid="button-submit-feedback"><Send size={14}/> Share feedback</button></SectionCard></div></div>;
}
function Notifications({ notify }) {
    const [items, setItems] = useState([['New curriculum submitted', 'B.Tech Artificial Intelligence v2.1 is ready for the reviewer queue.', '14 min ago', true], ['Screening completed', 'AI screening report is available with 3 findings.', 'Yesterday', true], ['Reviewer requested changes', 'Assessment balance needs another pass.', '02 Mar 2026', false], ['New AI recommendation available', 'MLOps coverage has been flagged in comparison.', '28 Feb 2026', false]]);
    return <div className="content"><PageHeader eyebrow="Workspace / Notifications" title="Notification center" detail="Workflow events, evidence updates and decisions that need your attention." action={<button className="btn" onClick={() => { setItems(items.map((item) => [item[0], item[1], item[2], false])); notify('All notifications marked as read.'); }} data-testid="button-mark-all-read"><Check size={14}/> Mark all read</button>}/><div style={{ display: 'grid', gap: 9 }}>{items.map((item, i) => <button key={item[0]} className="surface" style={{ textAlign: 'left', padding: 16, display: 'flex', gap: 13, alignItems: 'flex-start', borderLeft: item[3] ? '3px solid #9070bf' : undefined }} onClick={() => notify('Notification marked as read and opened.')} data-testid={`button-notification-${i}`}><span className="brand-mark" style={{ width: 32, height: 32, borderRadius: 10, flexShrink: 0 }}><Bell size={14}/></span><span style={{ flex: 1 }}><strong style={{ display: 'block', fontSize: 12 }}>{item[0]}</strong><span className="muted" style={{ display: 'block', fontSize: 11, marginTop: 5 }}>{item[1]}</span><span className="muted" style={{ display: 'block', fontSize: 10, marginTop: 9 }}>{item[2]}</span></span>{item[3] && <span className="badge badge-lavender">New</span>}</button>)}</div></div>;
}
function SettingsPage({ notify }) {
    return <div className="content"><PageHeader eyebrow="Workspace / Preferences" title="Settings" detail="Keep your role workspace precise, quiet and easy to audit."/><div style={{ maxWidth: 760, display: 'grid', gap: 14 }}><SectionCard title="Profile"><div className="form-grid"><Field label="Name" value="Ananya Iyer"/><Field label="Organization" value="Curriculum Design Cell"/><Field label="Work email" value="ananya.iyer@curriculum.lab"/><Field label="Time zone" value="Asia / Kolkata"/></div><button className="btn btn-primary" style={{ marginTop: 18 }} onClick={() => notify('Profile preferences saved.')} data-testid="button-save-profile"><Save size={14}/> Save profile</button></SectionCard><SectionCard title="Workspace preferences"><label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', fontSize: 12, borderBottom: '1px solid hsl(var(--border))' }}><span><strong style={{ display: 'block' }}>Evidence reminders</strong><span className="muted" style={{ fontSize: 10 }}>Notify me when a source is missing or outdated.</span></span><input type="checkbox" defaultChecked/></label><label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', fontSize: 12 }}><span><strong style={{ display: 'block' }}>Decision digest</strong><span className="muted" style={{ fontSize: 10 }}>A daily summary of workflow changes.</span></span><input type="checkbox" defaultChecked/></label></SectionCard></div></div>;
}
function Modal({ title, onClose, children, wide = false }) {
    return <div style={{ position: 'fixed', inset: 0, zIndex: 45, background: 'rgba(43,28,59,.35)', display: 'grid', placeItems: 'center', padding: 18 }}><div className="surface" style={{ width: wide ? 'min(900px, 100%)' : 'min(520px, 100%)', maxHeight: '90dvh', overflowY: 'auto', padding: 23 }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}><h2 className="font-display" style={{ fontSize: 19, margin: 0 }}>{title}</h2><button className="btn icon-btn" onClick={onClose} data-testid="button-close-modal"><X size={16}/></button></div>{children}</div></div>;
}
export default App;
