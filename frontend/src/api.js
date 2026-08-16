
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/rag/upload`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
  return res.json(); // { filename, message, total_chunks }
}

export async function askQuestion(query) {
  const res = await fetch(`${BASE_URL}/rag/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || 'Ask failed');
  return res.json(); // { query, answer }
}