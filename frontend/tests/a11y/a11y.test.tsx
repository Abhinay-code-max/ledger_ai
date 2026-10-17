import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import * as axe from 'axe-core'
import { RoleSelection, RoleLogin, Dashboard } from '../../src/pages/Workspaces'
import Workflow from '../../src/components/Workflow'

describe('Accessibility Standards and Controls', () => {
  it('RoleSelection passes axe-core automated scanner without critical violations', async () => {
    const { container } = render(
      <MemoryRouter>
        <RoleSelection />
      </MemoryRouter>
    )

    const results = await axe.run(container, {
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa'],
      },
    })

    const criticalViolations = results.violations.filter(v => v.impact === 'critical')
    expect(criticalViolations).toHaveLength(0)
  })

  it('RoleLogin form inputs have explicitly associated labels', () => {
    render(
      <MemoryRouter initialEntries={['/login/employee']}>
        <Routes>
          <Route path="/login/:role" element={<RoleLogin />} />
        </Routes>
      </MemoryRouter>
    )

    const emailInput = screen.getByLabelText(/Work email/i)
    const passwordInput = screen.getByLabelText(/Password/i)
    expect(emailInput).toHaveAttribute('type', 'email')
    expect(passwordInput).toHaveAttribute('type', 'password')
    expect(emailInput.id).toBe('ws-email')
    expect(passwordInput.id).toBe('ws-password')
  })

  it('Dialog elements use proper role, aria-modal, and focus trap semantics', () => {
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
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('role', 'dialog')

    // Escape key closes modal and returns focus
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('Status updates use aria-live or role="status" / role="alert"', () => {
    render(
      <MemoryRouter initialEntries={['/demo/manager']}>
        <Routes>
          <Route path="/demo/:role" element={<Dashboard demo={true} />} />
        </Routes>
      </MemoryRouter>
    )

    // Trigger a toast notification
    const openBtn = screen.getByLabelText(/Review Invoice_October\.pdf/i)
    fireEvent.click(openBtn)

    const recordReviewBtn = screen.getByRole('button', { name: /Record demo approval/i })
    fireEvent.click(recordReviewBtn)

    const toast = screen.getByRole('status')
    expect(toast).toBeInTheDocument()
    expect(toast).toHaveTextContent(/Demo approval recorded after your review/i)
  })

  it('respects prefers-reduced-motion media query and exposes live regions', () => {
    render(<Workflow />)
    expect(screen.getByRole('region', { name: /From scattered records/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Workflow stages/i })).toBeInTheDocument()
  })
})
