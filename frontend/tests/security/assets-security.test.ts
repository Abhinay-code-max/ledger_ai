import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

describe('Frontend Assets and Security Boundary Scan', () => {
  const frontendDir = path.resolve(__dirname, '../../src')

  function getAllFiles(dir: string, fileList: string[] = []): string[] {
    const files = fs.readdirSync(dir)
    for (const file of files) {
      const fullPath = path.join(dir, file)
      if (fs.statSync(fullPath).isDirectory()) {
        getAllFiles(fullPath, fileList)
      } else if (/\.(tsx?|jsx?|html|css|json)$/.test(file)) {
        fileList.push(fullPath)
      }
    }
    return fileList
  }

  const sourceFiles = getAllFiles(frontendDir)

  it('contains NO service secrets or private credentials in frontend code', () => {
    const secretPatterns = [
      /postgres(ql)?:\/\/[^:]+:[^@]+@/i, // DB passwords
      /redis:\/\/[^:]+:[^@]+@/i,          // Redis passwords
      /synthetic-service-secret/i,       // Service token secret
      /synthetic-maker-token/i,          // Hardcoded maker token
      /synthetic-reviewer-token/i,       // Hardcoded reviewer token
      /-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----/i,
      /AWS_SECRET_ACCESS_KEY/i,
      /LEDGERAI_SERVICE_TOKEN_SECRET/i,
      /minioadmin/i,
    ]

    for (const filePath of sourceFiles) {
      const content = fs.readFileSync(filePath, 'utf-8')
      for (const pattern of secretPatterns) {
        expect(
          pattern.test(content),
          `Security violation: Pattern ${pattern} matched in frontend asset ${path.basename(filePath)}`
        ).toBe(false)
      }
    }
  })

  it('contains NO direct internal role URLs (Roles 1, 2, 3, or 6)', () => {
    const forbiddenInternalRoleUrls = [
      /:8101\b/, // Role 1
      /:8102\b/, // Role 2
      /:8103\b/, // Role 3
      /:8006\b/, // Role 6
      /role1-service/i,
      /role2-accounting/i,
      /role3-reconciliation/i,
      /role6-model/i,
      /http:\/\/role[1236]\.invalid/i,
    ]

    for (const filePath of sourceFiles) {
      const content = fs.readFileSync(filePath, 'utf-8')
      for (const pattern of forbiddenInternalRoleUrls) {
        expect(
          pattern.test(content),
          `Security boundary violation: Direct internal role reference ${pattern} found in ${path.basename(filePath)}`
        ).toBe(false)
      }
    }
  })

  it('contains NO unsafe HTML execution (dangerouslySetInnerHTML)', () => {
    for (const filePath of sourceFiles) {
      const content = fs.readFileSync(filePath, 'utf-8')
      expect(
        content.includes('dangerouslySetInnerHTML'),
        `Security violation: dangerouslySetInnerHTML detected in ${path.basename(filePath)}`
      ).toBe(false)
    }
  })

  it('does NOT store or parse bearer tokens in window.location.search or hash', () => {
    for (const filePath of sourceFiles) {
      const content = fs.readFileSync(filePath, 'utf-8')
      const tokenInUrlRegex = /location\.(search|hash)\.includes\(['"]token/i
      expect(tokenInUrlRegex.test(content)).toBe(false)
    }
  })
})
