/**
 * Tests for ResponseViewer component.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ResponseViewer from '@/components/common/ResponseViewer.vue'

describe('ResponseViewer', () => {
  it('shows empty state when no response', () => {
    const wrapper = mount(ResponseViewer, {
      props: { response: null },
    })
    expect(wrapper.text()).toContain('No response yet')
  })

  it('shows loading state', () => {
    const wrapper = mount(ResponseViewer, {
      props: { response: null, loading: true },
    })
    expect(wrapper.text()).toContain('Sending...')
  })

  it('displays status code and duration', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: {
          statusCode: 200,
          headers: {},
          body: '{"ok": true}',
          durationMs: 150,
        },
      },
    })
    expect(wrapper.text()).toContain('200')
    expect(wrapper.text()).toContain('150ms')
  })

  it('applies success class for 2xx status', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: { statusCode: 200, headers: {}, body: '', durationMs: 50 },
      },
    })
    expect(wrapper.find('.status-success').exists()).toBe(true)
  })

  it('applies error class for 4xx status', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: { statusCode: 404, headers: {}, body: '', durationMs: 50 },
      },
    })
    expect(wrapper.find('.status-client-error').exists()).toBe(true)
  })

  it('formats JSON body with indentation', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: {
          statusCode: 200,
          headers: {},
          body: '{"name":"test","value":42}',
          durationMs: 50,
        },
      },
    })
    const code = wrapper.find('code')
    expect(code.text()).toContain('"name": "test"')
    expect(code.text()).toContain('"value": 42')
  })

  it('displays headers in the headers tab', async () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: {
          statusCode: 200,
          headers: { 'content-type': 'application/json', 'x-request-id': 'abc123' },
          body: '',
          durationMs: 50,
        },
      },
    })
    // Click headers tab
    const tabs = wrapper.findAll('.response-tab')
    await tabs[1]!.trigger('click')
    expect(wrapper.text()).toContain('content-type')
    expect(wrapper.text()).toContain('application/json')
    expect(wrapper.text()).toContain('x-request-id')
  })

  it('displays error banner when response has error', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: {
          statusCode: 0,
          headers: {},
          body: '',
          durationMs: 0,
          error: 'Connection refused',
        },
      },
    })
    expect(wrapper.find('.response-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Connection refused')
  })

  it('shows byte count', () => {
    const wrapper = mount(ResponseViewer, {
      props: {
        response: {
          statusCode: 200,
          headers: {},
          body: 'Hello, World!',
          durationMs: 50,
        },
      },
    })
    expect(wrapper.text()).toContain('13 bytes')
  })
})
