import React, { useState } from 'react';
import {
  Lock,
  Mail,
  User,
  ShieldCheck,
  Building,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  X,
  ArrowRight,
  Sparkles,
  KeyRound
} from 'lucide-react';
import { DEMO_USERS } from '../data/authUsers';

export default function AuthModal({
  isOpen,
  onClose,
  initialMode = 'signin', // 'signin' | 'signup'
  onSuccessLogin
}) {
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [selectedRole, setSelectedRole] = useState('cfo');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleQuickLogin = (roleKey) => {
    setIsLoading(true);
    setError(null);
    const demo = DEMO_USERS[roleKey];
    setTimeout(() => {
      setIsLoading(false);
      onSuccessLogin(demo);
      onClose();
    }, 400);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (mode === 'signin') {
      if (!email.trim() || !password.trim()) {
        setError('Please enter both email address and password.');
        return;
      }
      setIsLoading(true);
      setTimeout(() => {
        setIsLoading(false);
        // Find matching demo user or create session from input
        const matchedRole = Object.values(DEMO_USERS).find(u => u.email.toLowerCase() === email.toLowerCase());
        if (matchedRole) {
          onSuccessLogin(matchedRole);
        } else {
          // Dynamic authenticated user with selected or inferred role
          const customUser = {
            id: `usr_${Date.now()}`,
            name: email.split('@')[0].replace('.', ' '),
            email: email,
            role: selectedRole,
            roleTitle: DEMO_USERS[selectedRole].roleTitle,
            roleBadge: DEMO_USERS[selectedRole].roleBadge,
            badgeColor: DEMO_USERS[selectedRole].badgeColor,
            avatar: email.substring(0, 2).toUpperCase(),
            company: 'Enterprise Org',
            permissions: DEMO_USERS[selectedRole].permissions
          };
          onSuccessLogin(customUser);
        }
        onClose();
      }, 500);
    } else {
      // Sign Up validation
      if (!name.trim() || !email.trim() || !password.trim()) {
        setError('Please fill in your name, work email, and password.');
        return;
      }
      setIsLoading(true);
      setTimeout(() => {
        setIsLoading(false);
        const newUser = {
          id: `usr_${Date.now()}`,
          name: name.trim(),
          email: email.trim(),
          company: company.trim() || 'Acme Technologies Inc.',
          role: selectedRole,
          roleTitle: DEMO_USERS[selectedRole].roleTitle,
          roleBadge: DEMO_USERS[selectedRole].roleBadge,
          badgeColor: DEMO_USERS[selectedRole].badgeColor,
          avatar: name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'US',
          permissions: DEMO_USERS[selectedRole].permissions
        };
        onSuccessLogin(newUser);
        onClose();
      }, 500);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(4, 14, 27, 0.72)',
        backdropFilter: 'blur(6px)',
        zIndex: 100,
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
          maxWidth: '520px',
          boxShadow: 'var(--shadow-panel)',
          border: '1px solid var(--border-light)',
          overflow: 'hidden',
          position: 'relative'
        }}
      >
        {/* Top Header */}
        <div
          style={{
            padding: '24px 28px 18px',
            backgroundColor: 'var(--navy-900)',
            color: '#FFFFFF',
            position: 'relative'
          }}
        >
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '20px',
              right: '20px',
              background: 'none',
              border: 'none',
              color: 'var(--text-light-muted)',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px'
            }}
          >
            <X size={20} />
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: 'var(--navy-800)',
                border: '1px solid rgba(35, 199, 184, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Lock size={16} color="var(--teal-400)" />
            </div>
            <div>
              <span style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em' }}>
                Ledger <span style={{ color: 'var(--teal-400)' }}>Ai</span>
              </span>
            </div>
          </div>

          <h2 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '4px', color: '#FFFFFF' }}>
            {mode === 'signin' ? 'Sign in to your financial control room' : 'Create an institutional account'}
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-light-muted)' }}>
            Enterprise multi-tenant ledger with cryptographic separation of duties.
          </p>

          {/* Mode Switcher Tabs */}
          <div
            style={{
              display: 'flex',
              gap: '6px',
              marginTop: '18px',
              backgroundColor: 'rgba(0,0,0,0.25)',
              padding: '4px',
              borderRadius: 'var(--radius-md)'
            }}
          >
            <button
              onClick={() => { setMode('signin'); setError(null); }}
              style={{
                flex: 1,
                padding: '7px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                fontSize: '12px',
                fontWeight: '700',
                cursor: 'pointer',
                backgroundColor: mode === 'signin' ? '#FFFFFF' : 'transparent',
                color: mode === 'signin' ? 'var(--navy-900)' : 'var(--text-light-muted)',
                transition: 'all var(--transition-fast)'
              }}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('signup'); setError(null); }}
              style={{
                flex: 1,
                padding: '7px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                fontSize: '12px',
                fontWeight: '700',
                cursor: 'pointer',
                backgroundColor: mode === 'signup' ? '#FFFFFF' : 'transparent',
                color: mode === 'signup' ? 'var(--navy-900)' : 'var(--text-light-muted)',
                transition: 'all var(--transition-fast)'
              }}
            >
              Create Account
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px 28px 28px', maxHeight: '72vh', overflowY: 'auto' }}>
          {/* Quick Demo Role Logins */}
          <div style={{ marginBottom: '22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                ⚡ Quick Demo One-Click Role Logins
              </span>
              <span style={{ fontSize: '11px', color: 'var(--teal-600)', fontWeight: '600' }}>
                Instant Access
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
              <button
                type="button"
                onClick={() => handleQuickLogin('cfo')}
                style={{
                  padding: '10px 8px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  backgroundColor: 'var(--bg-canvas)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all var(--transition-fast)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--navy-800)';
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-light)';
                  e.currentTarget.style.backgroundColor = 'var(--bg-canvas)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'var(--navy-900)', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: '700' }}>
                  AV
                </div>
                <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)' }}>CFO / Admin</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Full Access</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('accountant')}
                style={{
                  padding: '10px 8px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  backgroundColor: 'var(--bg-canvas)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all var(--transition-fast)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--teal-500)';
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-light)';
                  e.currentTarget.style.backgroundColor = 'var(--bg-canvas)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'var(--teal-600)', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: '700' }}>
                  SC
                </div>
                <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--teal-700)' }}>Accountant</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Operations</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('auditor')}
                style={{
                  padding: '10px 8px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  backgroundColor: 'var(--bg-canvas)',
                  cursor: 'pointer',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all var(--transition-fast)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--alert-amber-badge)';
                  e.currentTarget.style.backgroundColor = '#FFFFFF';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-light)';
                  e.currentTarget.style.backgroundColor = 'var(--bg-canvas)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#D97706', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: '700' }}>
                  MR
                </div>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#B45309' }}>Auditor</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Read-Only</div>
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '18px 0', color: 'var(--text-tertiary)', fontSize: '12px' }}>
            <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-light)' }} />
            <span>or continue with credentials</span>
            <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-light)' }} />
          </div>

          {error && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--alert-red-bg)',
                border: '1px solid var(--alert-red-border)',
                color: 'var(--alert-red-text)',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '16px'
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {mode === 'signup' && (
              <>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)', marginBottom: '6px' }}>
                    Full Legal Name
                  </label>
                  <div style={{ position: 'relative' }}>
                    <User size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                    <input
                      type="text"
                      placeholder="e.g. Eleanor Vance"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '9px 12px 9px 36px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-light)',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)', marginBottom: '6px' }}>
                    Company / Entity Name
                  </label>
                  <div style={{ position: 'relative' }}>
                    <Building size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                    <input
                      type="text"
                      placeholder="e.g. Apex Dynamics Ltd."
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '9px 12px 9px 36px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-light)',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>
              </>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)', marginBottom: '6px' }}>
                Corporate Work Email
              </label>
              <div style={{ position: 'relative' }}>
                <Mail size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                <input
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px 9px 36px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-light)',
                    fontSize: '13px',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)' }}>
                  Password
                </label>
                {mode === 'signin' && (
                  <button
                    type="button"
                    onClick={() => setError('Password reset instructions dispatched to your verified security email.')}
                    style={{ background: 'none', border: 'none', color: 'var(--teal-600)', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div style={{ position: 'relative' }}>
                <KeyRound size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '11px' }} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 38px 9px 36px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-light)',
                    fontSize: '13px',
                    outline: 'none'
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(prev => !prev)}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    top: '9px',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer'
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Role Assignment Selector */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: 'var(--navy-900)', marginBottom: '6px' }}>
                Institutional Authorization Role
              </label>
              <select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  fontSize: '13px',
                  backgroundColor: '#FFFFFF',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                <option value="cfo">Chief Financial Officer (Admin - Full Posting & Period Close)</option>
                <option value="accountant">Senior Accountant (Operational - Transactions & Invoices)</option>
                <option value="auditor">External Auditor (Read-Only - GAAP/IFRS Inspection)</option>
              </select>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                {DEMO_USERS[selectedRole].description}
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '11px',
                fontSize: '14px',
                fontWeight: '700',
                backgroundColor: 'var(--navy-900)',
                marginTop: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <span>{isLoading ? 'Verifying Credentials...' : mode === 'signin' ? 'Sign In to Workspace' : 'Create Account & Sign In'}</span>
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Institutional Compliance Seal */}
          <div
            style={{
              marginTop: '20px',
              padding: '10px 14px',
              backgroundColor: 'var(--bg-canvas)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '11px',
              color: 'var(--text-muted)'
            }}
          >
            <ShieldCheck size={18} color="var(--teal-600)" />
            <span>Enforced with AES-256 GCM encryption & SOC2 Type II cryptographic audit logs.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
