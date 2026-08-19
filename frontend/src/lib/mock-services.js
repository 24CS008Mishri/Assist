const fallbackUsers = [
  { id: 'u1', name: 'Meera Nair', email: 'meera.nair@aicte.gov.in', organization: 'AICTE Headquarters', role: 'admin', status: 'Active' },
  { id: 'u2', name: 'Dr. Arvind Rao', email: 'arvind.rao@review.panel', organization: 'National Review Panel', role: 'reviewer', status: 'Active' },
  { id: 'u3', name: 'Ananya Iyer', email: 'ananya.iyer@curriculum.lab', organization: 'Curriculum Design Cell', role: 'designer', status: 'Active' },
  { id: 'u4', name: 'Rohan Kulkarni', email: 'rohan.k@institute.edu', organization: 'Northstar Institute of Technology', role: 'institute', status: 'Active' },
];

const fallbackCurricula = [
  { id: 'c1', name: 'B.Tech Artificial Intelligence', program: 'AI & Data Science', version: '2.1', designer: 'Ananya Iyer', status: 'Under Review', score: 82, submitted: '18 Feb 2026' },
  { id: 'c2', name: 'B.Tech Computer Science & Engineering', program: 'Computer Science', version: '1.4', designer: 'Ananya Iyer', status: 'Published', score: 91, submitted: '06 Jan 2026' },
  { id: 'c3', name: 'B.Tech Electronics & Communication Engineering', program: 'Electronics', version: '1.1', designer: 'K. S. Menon', status: 'Changes Requested', score: 74, submitted: '28 Feb 2026' },
  { id: 'c4', name: 'B.Tech Artificial Intelligence', program: 'AI & Data Science', version: '2.0', designer: 'A. Sen', status: 'Approved', score: 88, submitted: '12 Dec 2025' },
];

const fallbackChanges = [
  { id: 'CR-1024', course: 'Data Structures', issue: 'Insufficient graph algorithm coverage.', suggestion: 'Add advanced graph algorithms.', reason: 'Students require additional preparation for advanced coursework.', priority: 'High', status: 'Submitted' },
  { id: 'CR-1018', course: 'DBMS', issue: 'Distributed systems module is brief.', suggestion: 'Add a practical transaction lab.', reason: 'Align lab exposure with current industry practice.', priority: 'Medium', status: 'Under Review' },
];

export const sourceCards = [
  {
    type: 'Model Curriculum',
    title: 'AICTE Model Curriculum for Undergraduate Degree Courses',
    section: 'Credit and semester structure',
    detail: 'Reference guidance for programme structure, credit distribution, and curriculum balance.',
  },
  {
    type: 'Policy Standard',
    title: 'Outcome Based Education Guidelines',
    section: 'Course outcome mapping',
    detail: 'Guidance for measurable course outcomes, programme outcomes, and assessment alignment.',
  },
  {
    type: 'Approval Handbook',
    title: 'AICTE Approval Process Handbook',
    section: 'Academic requirements',
    detail: 'Applicable governance requirements for technical programmes and institutional delivery.',
  },
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

  let message = `Request failed (${response.status})`;
  try {
    const payload = await response.json();
    message = payload.detail || payload.message || message;
  } catch {
    // Preserve the status-based message for non-JSON responses.
  }
  const error = new Error(message);
  error.status = response.status;
  throw error;
}

async function loadOrFallback(path, fallback) {
  try {
    return await request(path);
  } catch {
    return fallback;
  }
}

// Prefer backend demo data, but keep the frontend usable when the API is offline.
export const [mockUsers, mockCurricula, mockChanges] = await Promise.all([
  loadOrFallback('/api/users', fallbackUsers),
  loadOrFallback('/api/curricula', fallbackCurricula),
  loadOrFallback('/api/changes', fallbackChanges),
]);

export const mockService = {
  async login(role, email = '') {
    try {
      return await request('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, email: email || null }),
      });
    } catch {
      const user = mockUsers.find((item) => item.role === role) || fallbackUsers[0];
      return { ...user, email: email || user.email };
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

  askAssistant(question) {
    return request('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
  },
};
