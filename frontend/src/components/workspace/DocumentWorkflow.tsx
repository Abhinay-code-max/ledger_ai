import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  FileCheck2,
  FileText,
  Hash,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { DocumentResponse, DocumentVersionResponse, ExtractionResponse } from '../../types/api'

interface DocumentWorkflowProps {
  onDocumentSelected?: (doc: DocumentResponse, version: DocumentVersionResponse | null) => void
  selectedDocId?: string | null
}

export const DocumentWorkflow: React.FC<DocumentWorkflowProps> = ({
  onDocumentSelected,
  selectedDocId,
}) => {
  const { client, hasPermission, latestProgressEvent } = useAuth()
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [versions, setVersions] = useState<Record<string, DocumentVersionResponse[]>>({})
  const [extractions, setExtractions] = useState<Record<string, ExtractionResponse>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadProgressMsg, setUploadProgressMsg] = useState<string>('')
  const [activeDoc, setActiveDoc] = useState<DocumentResponse | null>(null)

  const loadDocuments = async () => {
    setIsLoading(true)
    try {
      const res = await client.listDocuments(50)
      setDocuments(res.items)
      if (res.items.length > 0 && !activeDoc) {
        selectDoc(res.items[0])
      }
    } catch (err) {
      console.error('Failed to list documents:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadDocuments()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (latestProgressEvent && latestProgressEvent.resource_type === 'document') {
      void loadDocuments()
    }
  }, [latestProgressEvent])

  useEffect(() => {
    if (selectedDocId && documents.length > 0) {
      const match = documents.find((d) => d.id === selectedDocId)
      if (match && (!activeDoc || activeDoc.id !== selectedDocId)) {
        void selectDoc(match)
      }
    }
  }, [selectedDocId, documents])

  const selectDoc = async (doc: DocumentResponse) => {
    setActiveDoc(doc)
    try {
      const verList = await client.getDocumentVersions(doc.id)
      setVersions((prev) => ({ ...prev, [doc.id]: verList }))
      if (onDocumentSelected) {
        onDocumentSelected(doc, verList[0] || null)
      }
    } catch (err) {
      console.error('Failed to load document versions:', err)
    }
  }

  // Calculate SHA-256 hash using Web Crypto API
  const computeSha256 = async (bytes: ArrayBuffer): Promise<string> => {
    const hashBuffer = await crypto.subtle.digest('SHA-256', bytes)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    setUploadError(null)
    setUploadProgressMsg('Reading file and computing SHA-256 digest…')

    try {
      const arrayBuffer = await file.arrayBuffer()
      const digest = await computeSha256(arrayBuffer)
      const mediaType = file.type || 'application/pdf'
      const byteSize = file.size

      setUploadProgressMsg('Requesting scoped upload URL from Role 4…')
      const initRes = await client.initiateDocumentUpload({
        original_filename: file.name,
        media_type: mediaType,
        byte_size: byteSize,
        sha256: digest,
      })

      setUploadProgressMsg('Uploading evidence via short-lived scoped URL…')
      await client.uploadToScopedStorageUrl(initRes.upload_url, arrayBuffer, mediaType, byteSize)

      setUploadProgressMsg('Completing upload and triggering automated malware scan…')
      const completeRes = await client.completeDocumentUpload(initRes.upload_id, {
        sha256: digest,
        byte_size: byteSize,
      })

      setUploadProgressMsg('Upload complete! Evidence accepted.')
      await loadDocuments()
      await selectDoc(completeRes)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setIsUploading(false)
      event.target.value = ''
    }
  }

  const handleRunExtraction = async (doc: DocumentResponse) => {
    const docVersions = versions[doc.id] || []
    const acceptedVer = docVersions.find((v) => v.status === 'ACCEPTED') || docVersions[0]
    if (!acceptedVer) return

    setIsLoading(true)
    try {
      const extRes = await client.triggerDocumentExtraction(doc.id, {
        document_version_id: acceptedVer.id,
      })
      setExtractions((prev) => ({ ...prev, [doc.id]: extRes }))
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Extraction trigger failed.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Document Intake & Ingestion</h2>
          <p>Short-lived scoped storage uploads, malware scanning, and AI extraction.</p>
        </div>
        <div className="ws-header-actions">
          <label className="button primary ws-upload-btn">
            <Upload size={14} />
            <span>Upload Evidence</span>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileUpload}
              disabled={isUploading || !hasPermission('document:write')}
              style={{ display: 'none' }}
            />
          </label>
          <button
            onClick={loadDocuments}
            disabled={isLoading}
            className="button secondary"
            title="Refresh list"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {uploadProgressMsg && isUploading && (
        <div className="ws-status-banner info">
          <Loader2 size={16} className="spinning" />
          <span>{uploadProgressMsg}</span>
        </div>
      )}

      {uploadError && (
        <div className="ws-status-banner error" role="alert">
          <AlertCircle size={16} />
          <span>{uploadError}</span>
        </div>
      )}

      <div className="ws-layout-split">
        {/* Document list */}
        <div className="ws-panel ws-doc-list-panel">
          <div className="ws-panel-title">
            <h3>Registered Documents ({documents.length})</h3>
          </div>
          {documents.length === 0 ? (
            <div className="ws-empty">
              <FileText size={24} />
              <p>No documents uploaded yet. Upload a PDF invoice to start.</p>
            </div>
          ) : (
            <div className="ws-doc-cards">
              {documents.map((doc) => {
                const isSelected = activeDoc?.id === doc.id
                return (
                  <div
                    key={doc.id}
                    className={`ws-doc-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => selectDoc(doc)}
                  >
                    <div className="ws-doc-card-icon">
                      <FileText size={18} />
                    </div>
                    <div className="ws-doc-card-details">
                      <strong>{doc.original_filename}</strong>
                      <span className="ws-doc-id">ID: {doc.id.slice(0, 8)}…</span>
                      <span className={`ws-badge ws-status-${doc.status.toLowerCase()}`}>
                        {doc.status}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Selected Document Details & Version Inspection */}
        <div className="ws-panel ws-doc-detail-panel">
          {activeDoc ? (
            <div>
              <div className="ws-panel-title">
                <div>
                  <h3>{activeDoc.original_filename}</h3>
                  <p className="ws-subtext">Document ID: {activeDoc.id}</p>
                </div>
                <span className={`ws-badge ws-status-${activeDoc.status.toLowerCase()}`}>
                  {activeDoc.status}
                </span>
              </div>

              {/* Version & Integrity Details */}
              <div className="ws-details-group">
                <h4>Version Integrity & Scan Status</h4>
                {versions[activeDoc.id]?.map((ver) => (
                  <div key={ver.id} className="ws-version-row">
                    <div className="ws-version-meta">
                      <span>Version {ver.version_number}</span>
                      <span className="ws-badge success">{ver.status}</span>
                      <span className="ws-badge info">Scan: {ver.scan_status}</span>
                    </div>
                    <div className="ws-hash-display">
                      <Hash size={12} />
                      <code>{ver.actual_sha256 || 'Hash pending'}</code>
                    </div>
                  </div>
                )) || <p className="ws-subtext">Loading version data…</p>}
              </div>

              {/* Extraction Trigger & Results */}
              <div className="ws-details-group">
                <div className="ws-group-header">
                  <h4>Document Extraction & Validation</h4>
                  <button
                    onClick={() => handleRunExtraction(activeDoc)}
                    disabled={isLoading || !hasPermission('document:read')}
                    className="button primary small"
                  >
                    <Sparkles size={13} />
                    <span>Run AI Extraction</span>
                  </button>
                </div>

                {extractions[activeDoc.id] ? (
                  <div className="ws-extraction-results">
                    <div className="ws-extraction-header">
                      <span>Status: {extractions[activeDoc.id].status}</span>
                      <span
                        className={`ws-badge ${
                          extractions[activeDoc.id].validation_outcome === 'VALIDATED'
                            ? 'success'
                            : 'warning'
                        }`}
                      >
                        {extractions[activeDoc.id].validation_outcome}
                      </span>
                    </div>

                    {extractions[activeDoc.id].contract_payload?.fields && (
                      <table className="ws-record-table">
                        <thead>
                          <tr>
                            <th>Field</th>
                            <th>Extracted Value</th>
                            <th>Confidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extractions[activeDoc.id].contract_payload!.fields!.map((f, i) => (
                            <tr key={i}>
                              <td>{f.field_name}</td>
                              <td>
                                <strong>
                                  {typeof f.value === 'object' && f.value !== null
                                    ? JSON.stringify(f.value)
                                    : String(f.value ?? '—')}
                                </strong>
                              </td>
                              <td>
                                {f.confidence !== undefined
                                  ? `${(f.confidence * 100).toFixed(1)}%`
                                  : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                ) : (
                  <p className="ws-subtext">
                    Click "Run AI Extraction" to dispatch to Role 1 and classify via Role 6.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="ws-empty">
              <FileCheck2 size={24} />
              <p>Select a document from the list to view its version integrity and extracted details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
