import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Dashboard } from '../../src/pages/Workspaces'

describe('Empty, Loading, and Error States', () => {
  it('renders empty search state when no records match filter', () => {
    render(
      <MemoryRouter initialEntries={['/demo/employee']}>
        <Routes>
          <Route path="/demo/:role" element={<Dashboard demo={true} />} />
        </Routes>
      </MemoryRouter>
    )

    const searchInput = screen.getByLabelText(/Search documents/i)
    fireEvent.change(searchInput, { target: { value: 'Nonexistent Document 9999' } })

    expect(screen.getByText('No matching documents')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Clear filters/i })).toBeInTheDocument()
  })

  it('renders unverified AMD benchmark empty state with clear disclosure', () => {
    render(
      <MemoryRouter initialEntries={['/demo/admin']}>
        <Routes>
          <Route path="/demo/:role" element={<Dashboard demo={true} />} />
        </Routes>
      </MemoryRouter>
    )

    const benchmarkTabs = screen.getAllByRole('button', { name: /AMD benchmarks/i })
    fireEvent.click(benchmarkTabs[0])

    expect(screen.getByText('No verified measurements supplied')).toBeInTheDocument()
    expect(screen.getByText(/A benchmark needs the hardware model, runtime, dataset/i)).toBeInTheDocument()
  })

  it('renders auth wall error state when non-demo dashboard has no session', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/manager']}>
        <Routes>
          <Route path="/dashboard/:role" element={<Dashboard demo={false} />} />
        </Routes>
      </MemoryRouter>
    )

    const protectedHeader = await screen.findByText('Your workspace is protected.')
    expect(protectedHeader).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to secure sign-in/i })).toBeInTheDocument()
  })
})
