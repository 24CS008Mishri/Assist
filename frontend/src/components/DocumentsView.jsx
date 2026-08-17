import { useEffect, useRef, useState } from 'react';
import { Check, FileText, MessageCircle, Trash2, Upload } from 'lucide-react';
import { FolioShell, Surface } from './FolioShell';
import { uploadPdf, fetchDocuments, deleteDocument } from '../api'; 



export function DocumentsView({ onNavigate, onLogout }) {
  const [documents, setDocuments] = useState([]);
  const [notice, setNotice] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef(null);

  const announce = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(''), 2800);
  };


// 1. Load existing documents from MongoDB when component mounts
  useEffect(() => {
    const loadSavedDocuments = async () => {
      try {
        const data = await fetchDocuments();
        // Map backend schema to UI format
        const formattedDocs = data.map((doc, idx) => ({
          id: doc._id || `${idx}-${Date.now()}`,
          name: doc.filename,
          date: doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'Previously uploaded',
          size: `${doc.total_chunks} chunks indexed`,
        }));
        setDocuments(formattedDocs);
      } catch (err) {
        announce('Failed to load document library.');
      } finally {
        setLoading(false);
      }
    };

    loadSavedDocuments();
  }, []);


  const uploadDocument = async (file) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      announce('Only PDF files are supported.');
      return;
    }

    setUploading(true);
    try {
      const result = await uploadPdf(file);
      setDocuments((current) => [
        {
          id: `${Date.now()}`,
          name: result.filename,
          date: 'Today',
          size: `${result.total_chunks} chunks indexed`,
        },
        ...current.filter((doc) => doc.name !== result.filename),
      ]);
      announce(result.message || `${result.filename} is ready in your library.`);
    } catch (err) {
      announce(err.message || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <FolioShell active="documents" onNavigate={onNavigate} onLogout={onLogout}>
      <div className="folio-heading">
        <div>
          <div className="folio-eyebrow">Your quiet workspace</div>
          <h1>Documents</h1>
        </div>
        <div className="folio-actions">
          <input
            ref={fileInputRef}
            className="folio-upload-input"
            type="file"
            accept="application/pdf,.pdf"
            data-testid="input-upload-pdf"
            onChange={(event) => {
              uploadDocument(event.target.files?.[0]);
              event.currentTarget.value = '';
            }}
          />
          <button
            type="button"
            className="folio-button"
            data-testid="button-upload-pdf"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={17} strokeWidth={1.9} />
            {uploading ? 'Uploading...' : 'Upload PDF'}
          </button>
          <button
            type="button"
            className="folio-button pink"
            data-testid="button-ask-chat"
            onClick={() => onNavigate('chat')}
          >
            <MessageCircle size={17} strokeWidth={1.9} />
            Ask in chat
          </button>
        </div>
      </div>
      <Surface className="folio-docs">
        {documents.length === 0 ? (
          <div className="folio-empty" data-testid="empty-documents">
            <strong>Your desk is clear.</strong>
            Upload a PDF to begin a thoughtful conversation.
          </div>
        ) : (
          documents.map((document) => (
            <div className="folio-doc" key={document.id} data-testid={`row-document-${document.id}`}>
              <div className="folio-file">
                <FileText size={23} strokeWidth={1.7} />
              </div>
              <div className="folio-doc-info">
                <div className="folio-doc-name" data-testid={`text-document-${document.id}`}>
                  {document.name}
                </div>
                <div className="folio-meta">
                  {document.date}
                  <span aria-hidden="true" style={{ margin: '0 10px' }}>
                  
                  </span>
                  {document.size}
                </div>
              </div>
              <button
                type="button"
                className="folio-icon-button"
                aria-label={`Delete ${document.name}`}
                data-testid={`button-delete-${document.id}`}
                onClick={async () => {
                  try {
                    await deleteDocument(document.name);
                    setDocuments((current) => current.filter((item) => item.id !== document.id));
                    announce(`${document.name} removed from your library.`);
                  } catch (err) {
                    announce(err.message || 'Failed to delete document.');
                  }
                }}
              >
                <Trash2 size={18} strokeWidth={1.8} />
              </button>
            </div>
          ))
        )}
      </Surface>
      <div className="folio-footnote">
        <span data-testid="text-document-count">
          {documents.length} {documents.length === 1 ? 'file' : 'files'} in your library
        </span>
        <span className="folio-saved" data-testid="status-saved">
          <Check size={15} strokeWidth={2.2} />
          Everything is saved locally
        </span>
      </div>
      {notice && (
        <div className="folio-toast" role="status" data-testid="status-notice">
          {notice}
        </div>
      )}
    </FolioShell>
  );
}