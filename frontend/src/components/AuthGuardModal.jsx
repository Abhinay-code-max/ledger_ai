import React from 'react';
import {
  ShieldAlert,
  Lock,
  ArrowRight,
  X,
  AlertTriangle,
  UserCheck,
  CheckCircle2
} from 'lucide-react';
import { DEMO_USERS } from '../data/authUsers';

export default function AuthGuardModal({
  isOpen,
  onClose,
  guardDetails, // { actionName, requiredRole, reason }
  currentUser,
  onSwitchRole
}) {
  if (!isOpen || !guardDetails) return null;

  const { actionName, requiredRole = 'cfo', reason } = guardDetails;

  const roleNameMap = {
    cfo: 'Chief Financial Officer (Admin)',
    accountant: 'Senior Accountant (Editor)',
    auditor: 'External Auditor (Read-Only)'
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(4, 14, 27, 0.75)',
        backdropFilter: 'blur(5px)',
        zIndex: 110,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="animate-fade-in"
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: 'var(--radius-xl)',
          width: '100%',
          maxWidth: '480px',
          boxShadow: 'var(--shadow-panel)',
          border: '1px solid var(--border-light)',
          overflow: 'hidden'
        }}
      >
        {/* Guard Warning Banner */}
        <div
          style={{
            padding: '20px 24px',
            backgroundColor: '#FEF2F2',
            borderBottom: '1px solid #FECACA',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                backgroundColor: '#DC2626',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ShieldAlert size={20} />
            </div>
            <div>
              <div style={{ fontSize: '15px', fontWeight: '800', color: '#991B1B' }}>
                Authorization Required
              </div>
              <div style={{ fontSize: '11px', color: '#B91C1C' }}>
                Institutional Separation-of-Duties Policy
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#991B1B',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px' }}>
          <div style={{ marginBottom: '18px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Attempted Protected Action
            </div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--navy-900)' }}>
              "{actionName}"
            </div>
          </div>

          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'var(--bg-canvas)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-light)',
              marginBottom: '18px',
              fontSize: '13px',
              color: 'var(--text-secondary)',
              lineHeight: 1.5
            }}
          >
            {reason || `Your current role (${currentUser?.roleTitle || currentUser?.role}) does not possess write/approval authority for this action. This workflow is restricted to ${roleNameMap[requiredRole] || requiredRole}.`}
          </div>

          {/* Current Session vs Required Role Comparison */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '22px' }}>
            <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-canvas)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: '10px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Your Current Session
              </div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--navy-900)', marginTop: '2px' }}>
                {currentUser?.name}
              </div>
              <span className={`badge badge-${currentUser?.badgeColor || 'amber'}`} style={{ marginTop: '4px', fontSize: '10px' }}>
                {currentUser?.roleBadge || currentUser?.role}
              </span>
            </div>

            <div style={{ padding: '10px 12px', backgroundColor: 'var(--teal-50)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(14, 170, 165, 0.3)' }}>
              <div style={{ fontSize: '10px', fontWeight: '700', color: 'var(--teal-700)', textTransform: 'uppercase' }}>
                Required Minimum Role
              </div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--navy-900)', marginTop: '2px' }}>
                {requiredRole.toUpperCase()}
              </div>
              <span className="badge badge-teal" style={{ marginTop: '4px', fontSize: '10px' }}>
                Full Write / Approval
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {requiredRole === 'cfo' && currentUser?.role !== 'cfo' && (
              <button
                onClick={() => {
                  onSwitchRole('cfo');
                  onClose();
                }}
                className="btn-primary"
                style={{
                  width: '100%',
                  padding: '10px',
                  backgroundColor: 'var(--navy-900)',
                  fontSize: '13px',
                  justifyContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <UserCheck size={16} />
                <span>Switch to CFO (Alex Vance) & Execute</span>
                <ArrowRight size={14} />
              </button>
            )}

            {requiredRole === 'accountant' && currentUser?.role === 'auditor' && (
              <button
                onClick={() => {
                  onSwitchRole('accountant');
                  onClose();
                }}
                className="btn-teal"
                style={{
                  width: '100%',
                  padding: '10px',
                  fontSize: '13px',
                  justifyContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <UserCheck size={16} />
                <span>Switch to Accountant (Sarah Chen)</span>
                <ArrowRight size={14} />
              </button>
            )}

            <button
              onClick={onClose}
              className="btn-secondary"
              style={{ width: '100%', padding: '9px', fontSize: '13px', justifyContent: 'center' }}
            >
              Cancel / Stay in {currentUser?.roleBadge || 'Current Role'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
