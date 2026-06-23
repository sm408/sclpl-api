/**
 * ESLint configuration for SCLPLAPI web workspace.
 *
 * Key rules:
 * - Feature code (src/views, src/components, src/stores) cannot import
 *   the HTTP client or mock adapter directly. They must use the gateway
 *   interfaces from @/gateway.
 * - TypeScript strict rules.
 * - Vue SFC best practices.
 */

import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'

export default tseslint.config(
  // Global ignores
  { ignores: ['dist/**', 'node_modules/**', 'src/types/generated/**'] },

  // Base JS rules
  js.configs.recommended,

  // TypeScript rules
  ...tseslint.configs.recommended,

  // Vue rules
  ...pluginVue.configs['flat/recommended'],

  // Custom rules
  {
    files: ['src/**/*.{ts,vue}'],
    rules: {
      // ── Import boundary ────────────────────────────────────────────
      // Feature code must not import the HTTP client or mock adapter
      // directly. It should use @/gateway (the interface module).
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@/gateway/http',
              message:
                'Import the gateway interface from @/gateway instead. ' +
                'Only the gateway module may import the HTTP adapter.',
            },
            {
              name: '@/gateway/http/client',
              message:
                'Import the gateway interface from @/gateway instead. ' +
                'Only the gateway module may import the HTTP client.',
            },
            {
              name: '@/gateway/http/sse',
              message:
                'Import the gateway interface from @/gateway instead. ' +
                'Only the gateway module may import the SSE client.',
            },
            {
              name: '@/gateway/mock',
              message:
                'Import the gateway interface from @/gateway instead. ' +
                'Only the gateway module may import the mock adapter.',
            },
            {
              name: '@/gateway/mock/fixtures',
              message:
                'Import fixtures from @/gateway for testing only. ' +
                'Feature code should not reference mock data.',
            },
          ],
          patterns: [
            {
              group: ['**/gateway/http/*', '**/gateway/mock/*'],
              message:
                'Feature code cannot import gateway internals. ' +
                'Use @/gateway instead.',
            },
          ],
        },
      ],

      // ── TypeScript ─────────────────────────────────────────────────
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports' },
      ],

      // ── Vue ────────────────────────────────────────────────────────
      'vue/multi-word-component-names': 'off',
    },
  },

  // Test files can import anything
  {
    files: ['tests/**/*.ts'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
)
