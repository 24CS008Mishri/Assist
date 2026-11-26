const fallbackUsers = [
  { id: 'u1', name: 'Meera Nair', email: 'meera.nair@aicte.gov.in', organization: 'AICTE Headquarters', role: 'admin', status: 'Active' },
  { id: 'u2', name: 'Dr. Arvind Rao', email: 'arvind.rao@review.panel', organization: 'National Review Panel', role: 'reviewer', status: 'Active' },
  { id: 'u3', name: 'Ananya Iyer', email: 'ananya.iyer@curriculum.lab', organization: 'Curriculum Design Cell', role: 'designer', status: 'Active' },
  { id: 'u4', name: 'Rohan Kulkarni', email: 'rohan.k@institute.edu', organization: 'Northstar Institute of Technology', role: 'institute', status: 'Active' },
];

export const mockUsers = fallbackUsers;

function currentDemoUserId() {
  try {
    const saved = localStorage.getItem('aicte-demo-session');
    if (!saved) return null;
    const session = JSON.parse(saved);
    if (session.user_id) return String(session.user_id);
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
    return request('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  },

  getDocuments() {
    return request('/api/documents');
  },

  getAnalyzerCriteria() {
    return request('/api/analyzer/criteria');
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

  deleteDocument(filename, documentId = '') {
    const query = documentId ? `?document_id=${encodeURIComponent(documentId)}` : '';
    return request(`/api/documents/${encodeURIComponent(filename)}${query}`, { method: 'DELETE' });
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

  getWorkflowCurricula() {
    return request('/api/workflow/curricula');
  },

  handoffCurriculum(documentId) {
    return request(`/api/workflow/curricula/${encodeURIComponent(documentId)}/handoff`, { method: 'POST' });
  },

  getMySubmissions() {
    return request('/api/workflow/submissions/mine');
  },

  getEligiblePublications() {
    return request('/api/workflow/publications/eligible');
  },

  getPublishedCurricula() {
    return request('/api/workflow/publications');
  },

  getPublishedCurriculumStructure(submissionId) {
    return request(`/api/workflow/publications/${encodeURIComponent(submissionId)}/curriculum`);
  },

  publishSubmission(submissionId) {
    return request(`/api/workflow/submissions/${encodeURIComponent(submissionId)}/publish`, { method: 'POST' });
  },

  submitInstituteFeedback(submissionId, feedback) {
    return request(`/api/workflow/submissions/${encodeURIComponent(submissionId)}/feedback`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(feedback),
    });
  },

  getChangeRequests() {
    return request('/api/workflow/change-requests');
  },

  getNotifications() {
    return request('/api/workflow/notifications');
  },

  markNotificationRead(notificationId) {
    return request(`/api/workflow/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'PATCH' });
  },

  markAllNotificationsRead() {
    return request('/api/workflow/notifications/read-all', { method: 'POST' });
  },

  updateChangeRequest(submissionId, reviewId, requestId, changes) {
    return request(`/api/workflow/change-requests/${encodeURIComponent(submissionId)}/${encodeURIComponent(reviewId)}/${encodeURIComponent(requestId)}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes),
    });
  },

  getImprovementHistory() {
    return request('/api/workflow/improvements');
  },

  searchResources(subject) {
    return request(`/api/workflow/resources/search?${new URLSearchParams({ subject })}`);
  },

  getResourceSearchHistory() {
    return request('/api/workflow/resources/history');
  },

  getSavedResources() {
    return request('/api/workflow/resources/saved');
  },

  saveResource(resource) {
    return request('/api/workflow/resources/saved', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(resource) });
  },

  removeSavedResource(resourceId) {
    return request(`/api/workflow/resources/saved/${encodeURIComponent(resourceId)}`, { method: 'DELETE' });
  },

  getPendingSubmissions() {
    return request('/api/workflow/submissions');
  },

  getReviewHistory() {
    return request('/api/workflow/submissions/history');
  },

  getAdminSubmissions() {
    return request('/api/workflow/admin/submissions');
  },

  getAdminAuditEvents() {
    return request('/api/workflow/admin/audit-events');
  },

  getAccountProfile() {
    return request('/api/workflow/account/me');
  },

  updateAccountPreferences(preferences) {
    return request('/api/workflow/account/me/preferences', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preferences),
    });
  },

  getSubmission(submissionId) {
    return request(`/api/workflow/submissions/${encodeURIComponent(submissionId)}`);
  },

  submitCurriculum(file, metadata) {
    const body = new FormData();
    body.append('file', file);
    for (const [key, value] of Object.entries(metadata)) body.append(key, String(value));
    return request('/api/workflow/submissions', { method: 'POST', body });
  },

  submitPreparedCurriculum(metadata) {
    return request('/api/workflow/submissions/prepared', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(metadata),
    });
  },

  async getSubmissionDocument(submissionId) {
    const headers = new Headers();
    const demoUserId = currentDemoUserId();
    if (demoUserId) headers.set('X-Demo-User-Id', demoUserId);
    const response = await fetch(`/api/workflow/submissions/${encodeURIComponent(submissionId)}/document`, { headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `Request failed: ${response.status}`);
    }
    return URL.createObjectURL(await response.blob());
  },

  async getDraftDocument(curriculumId, documentId) {
    const headers = new Headers();
    const demoUserId = currentDemoUserId();
    if (demoUserId) headers.set('X-Demo-User-Id', demoUserId);
    const query = new URLSearchParams({ curriculum_id: curriculumId });
    const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/original?${query}`, { headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `Request failed: ${response.status}`);
    }
    return URL.createObjectURL(await response.blob());
  },

  analyzeSubmission(submissionId) {
    return request(`/api/workflow/submissions/${encodeURIComponent(submissionId)}/analyze`, { method: 'POST' });
  },

  decideSubmission(submissionId, decision, feedback, justification = '') {
    return request(`/api/workflow/submissions/${encodeURIComponent(submissionId)}/decision`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, feedback, justification }),
    });
  },

  getAdminUsers() { return request('/api/workflow/users'); },
  getInstitutions() { return request('/api/workflow/institutions'); },
  createInstitution(name) {
    return request('/api/workflow/institutions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  },
  createUser(user) {
    return request('/api/workflow/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(user) });
  },
  assignInstitution(userId, instituteId) {
    return request(`/api/workflow/users/${encodeURIComponent(userId)}/institution`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ institute_id: instituteId || null }) });
  },
  updateUser(userId, changes) {
    return request(`/api/workflow/users/${encodeURIComponent(userId)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes) });
  },

  askAssistant(question, history = []) {
    return request('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history }),
    });
  },
};
