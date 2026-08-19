const fallbackUsers = [
  { id: 'u1', name: 'Meera Nair', email: 'meera.nair@aicte.gov.in', password: 'governance2026', organization: 'AICTE Headquarters', role: 'admin', status: 'Active' },
  { id: 'u2', name: 'Dr. Arvind Rao', email: 'arvind.rao@review.panel', password: 'governance2026', organization: 'National Review Panel', role: 'reviewer', status: 'Active' },
  { id: 'u3', name: 'Ananya Iyer', email: 'ananya.iyer@curriculum.lab', password: 'governance2026', organization: 'Curriculum Design Cell', role: 'designer', status: 'Active' },
  { id: 'u4', name: 'Rohan Kulkarni', email: 'rohan.k@institute.edu', password: 'governance2026', organization: 'Northstar Institute of Technology', role: 'institute', status: 'Active' },
];

export const mockUsers = fallbackUsers.map(({ password, ...user }) => user);

export const mockCurricula = [
  { id: 'c1', name: 'B.Tech Artificial Intelligence', program: 'AI & Data Science', version: '2.1', designer: 'Ananya Iyer', status: 'Under Review', score: 82, submitted: '18 Feb 2026' },
  { id: 'c2', name: 'B.Tech Computer Science & Engineering', program: 'Computer Science', version: '1.4', designer: 'Ananya Iyer', status: 'Published', score: 91, submitted: '06 Jan 2026' },
  { id: 'c3', name: 'B.Tech Electronics & Communication Engineering', program: 'Electronics', version: '1.1', designer: 'K. S. Menon', status: 'Changes Requested', score: 74, submitted: '28 Feb 2026' },
  { id: 'c4', name: 'B.Tech Artificial Intelligence', program: 'AI & Data Science', version: '2.0', designer: 'A. Sen', status: 'Approved', score: 88, submitted: '12 Dec 2025' },
];

export const mockChanges = [
  { id: 'CR-1024', course: 'Data Structures', issue: 'Insufficient graph algorithm coverage.', suggestion: 'Add advanced graph algorithms.', reason: 'Students require additional preparation for advanced coursework.', priority: 'High', status: 'Submitted' },
  { id: 'CR-1018', course: 'DBMS', issue: 'Distributed systems module is brief.', suggestion: 'Add a practical transaction lab.', reason: 'Align lab exposure with current industry practice.', priority: 'Medium', status: 'Under Review' },
];

// Immutable analyzer runs retained for each curriculum version. The improvement
// tracker uses this audit trail rather than accepting a manually entered score.
export const analyzerScoreHistory = [
  {
    curriculumId: 'ai', name: 'B.Tech Artificial Intelligence', institute: 'Northstar Institute of Technology',
    versions: [
      { version: '1.8', score: 64, analyzedOn: '12 Oct 2025', findingsResolved: 0 },
      { version: '1.9', score: 71, analyzedOn: '18 Nov 2025', findingsResolved: 3 },
      { version: '2.0', score: 78, analyzedOn: '08 Jan 2026', findingsResolved: 5 },
      { version: '2.1', score: 82, analyzedOn: '06 Mar 2026', findingsResolved: 7 },
    ],
  },
  {
    curriculumId: 'ece', name: 'B.Tech Electronics & Communication Engineering', institute: 'Crescent Valley University',
    versions: [
      { version: '0.9', score: 59, analyzedOn: '23 Sep 2025', findingsResolved: 0 },
      { version: '1.0', score: 67, analyzedOn: '15 Jan 2026', findingsResolved: 4 },
      { version: '1.1', score: 74, analyzedOn: '28 Feb 2026', findingsResolved: 6 },
    ],
  },
];

export const sourceCards = [
  { title: 'AICTE Model Curriculum', section: 'Program structure', type: 'Indexed PDF', detail: 'Official curriculum structure and credit requirements.' },
  { title: 'National Education Policy', section: 'Policy alignment', type: 'Indexed PDF', detail: 'Policy guidance used to evaluate curriculum alignment.' },
  { title: 'Assessment Guidelines', section: 'Assessment design', type: 'Indexed PDF', detail: 'Evidence for outcomes, evaluation, and assessment design.' },
];

function currentDemoUserId() {
  try {
    const saved = localStorage.getItem('aicte-demo-session');
    if (!saved) return null;
    const session = JSON.parse(saved);
    const user = fallbackUsers.find((item) => (
      item.id === session.id
      || (
        item.role === session.role
        && (item.email === session.email || item.name === session.name)
      )
    ));
    return user?.id ?? null;
  } catch {
    return null;
  }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const demoUserId = currentDemoUserId();
  if (demoUserId) headers.set('X-Demo-User-Id', demoUserId);

  const response = await fetch(path, { ...options, headers });
  if (response.ok) return response.status === 204 ? null : response.json();

  const payload = await response.json().catch(() => null);
  const error = new Error(payload?.detail || `Request failed: ${response.status}`);
  error.status = response.status;
  throw error;
}

export const mockService = {
  async login(email, password) {
    try {
      return await request('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      const user = fallbackUsers.find((item) => item.email.toLowerCase() === email.trim().toLowerCase() && item.password === password);
      if (!user) throw new Error('Invalid credentials');
      return { name: user.name, email: user.email, role: user.role, organization: user.organization };
    }
  },

  getDocuments() {
    return request('/api/documents');
  },

  uploadDocument(file, metadata = {}) {
    const body = new FormData();
    body.append('file', file);
    for (const [key, value] of Object.entries(metadata)) {
      if (value !== null && value !== undefined && String(value).trim() !== '') {
        body.append(key, String(value).trim());
      }
    }
    return request('/api/documents/upload', { method: 'POST', body });
  },

  deleteDocument(filename) {
    return request(`/api/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' });
  },

  scoreCurriculum(curriculumId, documentId = null) {
    const query = documentId ? `?document_id=${encodeURIComponent(documentId)}` : '';
    return request(`/api/analyzer/score/${encodeURIComponent(curriculumId)}${query}`, {
      method: 'POST',
    });
  },

  analyzeCurriculum(curriculumId, documentId = null) {
    const query = documentId ? `?document_id=${encodeURIComponent(documentId)}` : '';
    return request(`/api/analyzer/analyze/${encodeURIComponent(curriculumId)}${query}`, {
      method: 'POST',
    });
  },

  askAssistant(question, history = []) {
    return request('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history }),
    });
  },
};
