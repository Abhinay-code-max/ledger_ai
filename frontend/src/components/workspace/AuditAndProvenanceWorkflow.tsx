import React, { useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowDown,
  CheckCircle2,
  Clock,
  GitFork,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { AuditEventResponse, ProvenanceTraceResponse } from '../../types/api'

interface AuditAndProvenanceWorkflowProps {
  initialTraceTarget?: { type: string; id: string } | null
}

export const AuditAndProvenanceWorkflow: React.FC<AuditAndProvenanceWorkflowProps> = ({
  initialTraceTarget,
}) => {
  const { client } = useAuth()
  const [activeTab, setActiveTab] = useState<'audit' | 'provenance'>('audit')
  const [auditEvents, setAuditEvents] = useState<AuditEventResponse[]>([])
  const [traceResult, setTraceResult] = useState<ProvenanceTraceResponse | null>(null)
  const [traceType, setTraceType] = useState('statement_line')
  const [traceId, setTraceId] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isTracing, setIsTracing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState('ALL')

  const loadAuditEvents = async () => {
    setIsLoading(true)
    try {
      const res = await client.listAuditEvents(
        filterType === 'ALL' ? undefined : filterType,
        undefined,
        100,
      )
      setAuditEvents(res)
    } catch (err) {
      console.error('Failed to list audit events:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadAuditEvents()
  }, [filterType]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (initialTraceTarget) {
      setTraceType(initialTraceTarget.type)
      setTraceId(initialTraceTarget.id)
      setActiveTab('provenance')
      void executeTrace(initialTraceTarget.type, initialTraceTarget.id)
    }
  }, [initialTraceTarget])

  const executeTrace = async (type: string, id: string) => {
    if (!id.trim()) {
      setError('Please provide a valid resource UUID to trace.')
      return
    }

    setIsTracing(true)
    setError(null)

    try {
      const trace = await client.getProvenanceTrace(type, id.trim())
      setTraceResult(trace)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provenance trace failed.')
    } finally {
      setIsTracing(false)
    }
  }

  return (
    <div className="ws-workflow-section">
      <div className="ws-section-header">
        <div>
          <h2>Audit Timeline & Provenance Assurance</h2>
          <p>
            Immutable append-only audit trail and unbroken 11-node statement-to-source provenance.
          </p>
        </div>
        <div className="ws-header-actions">
          <button
            onClick={loadAuditEvents}
            disabled={isLoading}
            className="button secondary"
            title="Refresh audit events"
          >
            <RefreshCw size={14} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <div className="ws-status-banner error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="ws-tab-row">
        <button
          className={`ws-tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <Activity size={14} />
          <span>Audit Log Timeline ({auditEvents.length})</span>
        </button>
        <button
          className={`ws-tab-btn ${activeTab === 'provenance' ? 'active' : ''}`}
          onClick={() => setActiveTab('provenance')}
        >
          <GitFork size={14} />
          <span>Statement-to-Source Provenance</span>
        </button>
      </div>

      {/* Audit Timeline Tab */}
      {activeTab === 'audit' && (
        <div className="ws-panel">
          <div className="ws-panel-title">
            <div>
              <h3>Immutable Audit Trail</h3>
              <p className="ws-subtext">
                Every action is cryptographically recorded with actor, outcome, and correlation ID.
              </p>
            </div>

            <div className="ws-audit-filter">
              <select
                aria-label="Filter audit action category"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="ws-context-select"
              >
                <option value="ALL">All Event Types</option>
                <option value="document">Documents</option>
                <option value="document_extraction">Extractions</option>
                <option value="match_proposal">Reconciliation</option>
                <option value="exception">Exceptions</option>
                <option value="journal_proposal">Journal Proposals</option>
                <option value="policy_decision">Policy Decisions</option>
                <option value="approval_action">Approvals</option>
                <option value="posting_operation">Postings</option>
                <option value="close_run">Close Runs</option>
                <option value="financial_statement_snapshot">Statements</option>
              </select>
            </div>
          </div>

          <div className="ws-timeline-list">
            {auditEvents.map((ev) => (
              <div key={ev.id} className="ws-timeline-entry">
                <div className="ws-timeline-dot">
                  <CheckCircle2 size={15} />
                </div>
                <div className="ws-timeline-content">
                  <div className="ws-timeline-header">
                    <strong className="ws-action-name">{ev.action}</strong>
                    <span
                      className={`ws-badge ${
                        ev.outcome === 'SUCCEEDED' ? 'success' : 'error'
                      }`}
                    >
                      {ev.outcome}
                    </span>
                    <span className="ws-subtext">
                      {new Date(ev.created_at).toLocaleTimeString()} ·{' '}
                      {new Date(ev.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="ws-timeline-meta">
                    <span>
                      Resource: <code>{ev.resource_type}</code> ({ev.resource_id.slice(0, 8)}…)
                    </span>
                    <span>
                      Actor: <code>{ev.actor_id}</code>
                    </span>
                    <span>
                      Correlation ID: <code>{ev.correlation_id.slice(0, 8)}…</code>
                    </span>
                  </div>

                  {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                    <div className="ws-timeline-payload">
                      <code>{JSON.stringify(ev.metadata)}</code>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {auditEvents.length === 0 && (
              <div className="ws-empty">
                <Clock size={24} />
                <p>No audit events recorded yet for this criteria.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Provenance Trace Tab */}
      {activeTab === 'provenance' && (
        <div className="ws-panel">
          <div className="ws-panel-title">
            <div>
              <h3>Statement-to-Source Evidence Trace</h3>
              <p className="ws-subtext">
                Graph verification: traverses all 11 nodes from financial statement lines back to immutable source evidence.
              </p>
            </div>
          </div>

          {/* Trace Target Input */}
          <div className="ws-trace-search-bar">
            <select
              value={traceType}
              onChange={(e) => setTraceType(e.target.value)}
              className="ws-context-select"
            >
              <option value="statement_line">statement_line</option>
              <option value="posted_journal">posted_journal</option>
              <option value="journal_proposal">journal_proposal</option>
              <option value="document">document</option>
            </select>

            <input
              type="text"
              placeholder="Enter Resource UUID (e.g. statement line id)"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              className="ws-trace-id-input"
            />

            <button
              onClick={() => executeTrace(traceType, traceId)}
              disabled={isTracing || !traceId.trim()}
              className="button primary small"
            >
              {isTracing ? <Loader2 size={14} className="spinning" /> : <GitFork size={14} />}
              <span>Trace Provenance Path</span>
            </button>
          </div>

          {traceResult ? (
            <div className="ws-trace-visualizer">
              <div className="ws-trace-meta-summary">
                <span className="ws-badge success">
                  UNBROKEN TRACE: {traceResult.nodes.length} Nodes, {traceResult.edges.length} Edges
                </span>
                <span className="ws-badge info">Truncated: {traceResult.truncated ? 'Yes' : 'No'}</span>
              </div>

              {/* Node Sequence Chain */}
              <div className="ws-trace-node-chain">
                {traceResult.nodes.map((node, index) => {
                  const edge = traceResult.edges.find(
                    (e) => e.from_id === node.resource_id || e.to_id === node.resource_id,
                  )
                  return (
                    <React.Fragment key={`${node.resource_type}-${node.resource_id}-${index}`}>
                      <div className="ws-trace-node-card">
                        <div className="ws-node-index">#{index + 1}</div>
                        <div className="ws-node-body">
                          <strong className="ws-node-type">{node.resource_type}</strong>
                          <span className="ws-node-id">
                            ID: <code>{node.resource_id.slice(0, 10)}…</code>
                          </span>
                          <span className="ws-node-ver">Version: {node.resource_version}</span>
                        </div>
                      </div>

                      {index < traceResult.nodes.length - 1 && (
                        <div className="ws-trace-edge-arrow">
                          <ArrowDown size={18} />
                          <span className="ws-edge-label">
                            {edge?.relation || 'CONNECTED_TO'}
                          </span>
                        </div>
                      )}
                    </React.Fragment>
                  )
                })}
              </div>

              {/* Provenance Edge Table */}
              <div className="ws-details-group" style={{ marginTop: '2rem' }}>
                <h4>Provenanced Graph Edges</h4>
                <table className="ws-record-table">
                  <thead>
                    <tr>
                      <th>From Node</th>
                      <th>Relation</th>
                      <th>To Node</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traceResult.edges.map((edge, idx) => (
                      <tr key={idx}>
                        <td>
                          <code>
                            {edge.from_type} ({edge.from_id.slice(0, 8)}…)
                          </code>
                        </td>
                        <td>
                          <span className="ws-badge info">{edge.relation}</span>
                        </td>
                        <td>
                          <code>
                            {edge.to_type} ({edge.to_id.slice(0, 8)}…)
                          </code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="ws-empty">
              <GitFork size={30} />
              <h3>No Provenance Target Traced Yet</h3>
              <p>
                Enter a statement line UUID or click "Trace Provenance" from any Financial Statement
                row to inspect the evidence lineage.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
