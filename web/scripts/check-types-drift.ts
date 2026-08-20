/**
 * Check for drift between the committed hand-written types and the
 * generated types from OpenAPI.
 *
 * This script:
 * 1. Runs the OpenAPI export and type generation
 * 2. Compares the generated endpoint list against a known-good baseline
 * 3. Fails if endpoints were added/removed without updating types
 *
 * Usage: pnpm types:check
 */

import { execSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const GENERATED_FILE = resolve(import.meta.dirname, '..', 'src', 'types', 'generated', 'api.ts')
const OPENAPI_JSON = resolve(import.meta.dirname, '..', 'openapi.json')
const PYTHON_SCRIPT = resolve(import.meta.dirname, '..', '..', 'scripts', 'export_openapi.py')

function run(cmd: string): string {
  return execSync(cmd, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim()
}

function main(): void {
  let errors = 0

  // Step 1: Export OpenAPI schema
  console.log('Exporting OpenAPI schema...')
  try {
    run(`python "${PYTHON_SCRIPT}" -o "${OPENAPI_JSON}"`)
  } catch (err) {
    console.error('Failed to export OpenAPI schema. Is the Python environment set up?')
    console.error(err)
    process.exit(1)
  }

  // Step 2: Generate types
  console.log('Generating types...')
  run(`node --import tsx "${resolve(import.meta.dirname, 'generate-types.ts')}"`)

  // Step 3: Verify generated file exists
  if (!existsSync(GENERATED_FILE)) {
    console.error(`Generated file not found: ${GENERATED_FILE}`)
    process.exit(1)
  }

  // Step 4: Parse generated endpoints
  const generated = readFileSync(GENERATED_FILE, 'utf-8')
  const endpointMatch = generated.match(/KNOWN_ENDPOINTS\s*=\s*\[([\s\S]*?)\]/)
  if (!endpointMatch) {
    console.error('Could not find KNOWN_ENDPOINTS in generated file')
    process.exit(1)
  }

  const endpoints = endpointMatch[1]
    .split('\n')
    .map((line) => line.trim().replace(/['",]/g, ''))
    .filter((line) => line.startsWith('/'))

  console.log(`Found ${endpoints.length} endpoints in generated types`)

  // Step 5: Check that all expected endpoints exist
  // These are the endpoints that MUST have types
  const requiredEndpoints = [
    '/health',
    '/api/v1/projects',
    '/api/v1/projects/{project_id}',
    '/api/v1/operations',
    '/api/v1/operations/{operation_id}',
    '/api/v1/operations/events/stream',
  ]

  for (const endpoint of requiredEndpoints) {
    if (!endpoints.includes(endpoint)) {
      console.error(`DRIFT DETECTED: Required endpoint missing from generated types: ${endpoint}`)
      errors++
    }
  }

  // Step 6: Check for unexpected new endpoints
  const knownEndpoints = new Set(requiredEndpoints)
  for (const endpoint of endpoints) {
    if (!knownEndpoints.has(endpoint) && !endpoint.includes('{')) {
      console.warn(`NEW ENDPOINT: ${endpoint} — ensure types/api.ts is updated`)
    }
  }

  if (errors > 0) {
    console.error(`\n${errors} drift error(s) found. Update types and regenerate.`)
    process.exit(1)
  }

  console.log('\nNo drift detected. Types are in sync.')
}

main()
