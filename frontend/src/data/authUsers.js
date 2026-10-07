// Authentication & Role-Based Access Control (RBAC) Data Model
// Supports 3 institutional roles: CFO / Admin, Senior Accountant, and External Auditor

export const DEMO_USERS = {
  cfo: {
    id: 'usr_cfo_01',
    name: 'Alex Vance',
    email: 'alex.vance@acme.corp',
    password: 'password123',
    role: 'cfo',
    roleTitle: 'Chief Financial Officer',
    roleBadge: 'CFO (Admin)',
    badgeColor: 'navy',
    avatar: 'AV',
    company: 'Acme Technologies Inc.',
    description: 'Executive authority: final journal posting, irrevocable period locks, and policy administration.',
    permissions: {
      canApprove: true,
      canEdit: true,
      canClosePeriod: true,
      canManageSettings: true,
      canViewIntelligence: true,
      canReconcile: true,
      canDispatchInvoices: true,
      canManageTeam: true,
      isReadOnly: false,
    }
  },
  accountant: {
    id: 'usr_acc_02',
    name: 'Sarah Chen',
    email: 'sarah.chen@acme.corp',
    password: 'password123',
    role: 'accountant',
    roleTitle: 'Senior Staff Accountant',
    roleBadge: 'Accountant (Editor)',
    badgeColor: 'teal',
    avatar: 'SC',
    company: 'Acme Technologies Inc.',
    description: 'Operational lead: transaction classification, reconciliation proposals, and invoice drafting.',
    permissions: {
      canApprove: false,
      canEdit: true,
      canClosePeriod: false,
      canManageSettings: false,
      canViewIntelligence: true,
      canReconcile: true,
      canDispatchInvoices: true,
      canManageTeam: false,
      isReadOnly: false,
    }
  },
  auditor: {
    id: 'usr_aud_03',
    name: 'Marcus Reed',
    email: 'marcus.reed@deloitte-audit.com',
    password: 'password123',
    role: 'auditor',
    roleTitle: 'Independent Audit Partner',
    roleBadge: 'Auditor (Read-Only)',
    badgeColor: 'amber',
    avatar: 'MR',
    company: 'Deloitte Financial Advisory',
    description: 'Forensic inspection: read-only access to immutable ledgers, audit logs, and GAAP/IFRS telemetry.',
    permissions: {
      canApprove: false,
      canEdit: false,
      canClosePeriod: false,
      canManageSettings: false,
      canViewIntelligence: true,
      canReconcile: false,
      canDispatchInvoices: false,
      canManageTeam: false,
      isReadOnly: true,
    }
  }
};

const STORAGE_KEY = 'ledgerai_authenticated_user';

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.role && DEMO_USERS[parsed.role]) {
        // Merge in fresh permission definitions in case of updates
        return {
          ...DEMO_USERS[parsed.role],
          ...parsed
        };
      }
    }
  } catch (err) {
    console.error('Failed reading user from localStorage', err);
  }
  // Default to CFO for seamless experience
  return DEMO_USERS.cfo;
}

export function setStoredUser(user) {
  try {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch (err) {
    console.error('Failed storing user to localStorage', err);
  }
}
