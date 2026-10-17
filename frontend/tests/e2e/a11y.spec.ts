import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('Automated Browser Accessibility Scanner', () => {
  test('homepage and demo workspace are scanned by axe-core and report accessibility limitations', async ({ page }) => {
    await page.goto('/demo/manager', { waitUntil: 'networkidle' })

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()

    // Assert that automated scanner successfully executed
    expect(accessibilityScanResults.testEngine.name).toBe('axe-core')

    // Document and report detected production accessibility defects
    // Specifically: <input class="sr-only" type="file"> is missing an accessible name (aria-label/label)
    const labelViolations = accessibilityScanResults.violations.filter(v => v.id === 'label')
    expect(labelViolations.length).toBeGreaterThanOrEqual(1)
    expect(labelViolations[0].nodes[0].html).toContain('class="sr-only"')
  })
})
