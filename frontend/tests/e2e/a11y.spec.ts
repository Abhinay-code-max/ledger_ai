import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('Automated Browser Accessibility Scanner', () => {
  test('homepage and demo workspace are scanned by axe-core and report accessibility limitations', async ({ page }) => {
    await page.goto('/demo/manager', { waitUntil: 'domcontentloaded' })

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()

    // Assert that automated scanner successfully executed
    expect(accessibilityScanResults.testEngine.name).toBe('axe-core')

    // Verify zero critical or serious accessibility violations
    const criticalViolations = accessibilityScanResults.violations.filter(
      v => v.impact === 'critical' || v.impact === 'serious'
    )
    expect(criticalViolations).toHaveLength(0)

    // Verify file input accessibility defect is resolved with associated label
    const labelViolations = accessibilityScanResults.violations.filter(v => v.id === 'label')
    expect(labelViolations).toHaveLength(0)
  })
})
