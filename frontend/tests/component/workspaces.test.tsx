import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RoleSelection, RoleLogin, Dashboard } from '../../src/pages/Workspaces'

describe('Workspaces Component Tests', () => {
  it('renders RoleSelection with administrator, manager, and employee cards', () => {
    render(
      <MemoryRouter>
        <RoleSelection />
      </MemoryRouter>
    )

    expect(screen.getByText('Administrator')).toBeInTheDocument()
    expect(screen.getByText('Finance Manager')).toBeInTheDocument()
    expect(screen.getByText('Finance Employee')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Enter .* workspace/i })).toHaveLength(3)
  })

  it('renders RoleLogin with accessible form labels and controls', () => {
    render(
      <MemoryRouter initialEntries={['/login/manager']}>
        <Routes>
          <Route path="/login/:role" element={<RoleLogin />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByLabelText(/Work email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Sign in to workspace/i })).toBeInTheDocument()
  })

  it('displays auth error banner when identity service is not configured', async () => {
    render(
      <MemoryRouter initialEntries={['/login/admin']}>
        <Routes>
          <Route path="/login/:role" element={<RoleLogin />} />
        </Routes>
      </MemoryRouter>
    )

    const emailInput = screen.getByLabelText(/Work email/i)
    const passwordInput = screen.getByLabelText(/Password/i)
    const submitBtn = screen.getByRole('button', { name: /Sign in to workspace/i })

    fireEvent.change(emailInput, { target: { value: 'admin@company.com' } })
    fireEvent.change(passwordInput, { target: { value: 'password123' } })
    fireEvent.click(submitBtn)

    const errorBanner = await screen.findByRole('alert')
    expect(errorBanner).toBeInTheDocument()
    expect(errorBanner.textContent).toContain('Secure sign-in is not connected')
  })

  it('renders Dashboard in demo mode with sample records and tabs', () => {
    render(
      <MemoryRouter initialEntries={['/demo/manager']}>
        <Routes>
          <Route path="/demo/:role" element={<Dashboard demo={true} />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('DEMO WORKSPACE')).toBeInTheDocument()
    expect(screen.getByText('Invoice_October.pdf')).toBeInTheDocument()
    expect(screen.getByText('Vendor_statement.pdf')).toBeInTheDocument()
  })

  it('opens and closes document review dialog with accessible semantics', async () => {
    render(
      <MemoryRouter initialEntries={['/demo/manager']}>
        <Routes>
          <Route path="/demo/:role" element={<Dashboard demo={true} />} />
        </Routes>
      </MemoryRouter>
    )

    const openBtn = screen.getByLabelText(/Review Invoice_October\.pdf/i)
    fireEvent.click(openBtn)

    const dialog = screen.getByRole('dialog', { name: /Document review/i })
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute('aria-modal', 'true')

    const closeBtn = screen.getByLabelText(/Close document review/i)
    fireEvent.click(closeBtn)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
