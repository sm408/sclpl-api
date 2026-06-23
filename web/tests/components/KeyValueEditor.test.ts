/**
 * Tests for KeyValueEditor component.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'

describe('KeyValueEditor', () => {
  it('renders empty state', () => {
    const wrapper = mount(KeyValueEditor, {
      props: { modelValue: [] },
    })
    expect(wrapper.text()).toContain('No entries')
  })

  it('renders existing entries', () => {
    const wrapper = mount(KeyValueEditor, {
      props: {
        modelValue: [
          { key: 'Accept', value: 'application/json', enabled: true },
          { key: 'X-Custom', value: 'test', enabled: false },
        ],
      },
    })
    const inputs = wrapper.findAll('input')
    // Each entry has 2 inputs (key + value)
    expect(inputs.length).toBeGreaterThanOrEqual(4)
  })

  it('adds a new entry on add button click', async () => {
    const wrapper = mount(KeyValueEditor, {
      props: { modelValue: [] },
    })
    await wrapper.find('.kv-add').trigger('click')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toHaveLength(1)
    expect(emitted![0][0][0].key).toBe('')
  })

  it('removes an entry on remove button click', async () => {
    const wrapper = mount(KeyValueEditor, {
      props: {
        modelValue: [
          { key: 'A', value: '1', enabled: true },
          { key: 'B', value: '2', enabled: true },
        ],
      },
    })
    const removeButtons = wrapper.findAll('.kv-remove')
    await removeButtons[0]!.trigger('click')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toHaveLength(1)
    expect(emitted![0][0][0].key).toBe('B')
  })

  it('toggles entry enabled state', async () => {
    const wrapper = mount(KeyValueEditor, {
      props: {
        modelValue: [{ key: 'A', value: '1', enabled: true }],
        showEnabled: true,
      },
    })
    const toggle = wrapper.find('.kv-toggle')
    expect(toggle.classes()).toContain('active')
    await toggle.trigger('click')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0][0].enabled).toBe(false)
  })

  it('respects custom labels', () => {
    const wrapper = mount(KeyValueEditor, {
      props: {
        modelValue: [],
        keyLabel: 'Header Name',
        valueLabel: 'Header Value',
      },
    })
    expect(wrapper.text()).toContain('Header Name')
    expect(wrapper.text()).toContain('Header Value')
  })

  it('hides toggle when showEnabled is false', () => {
    const wrapper = mount(KeyValueEditor, {
      props: {
        modelValue: [{ key: 'A', value: '1', enabled: true }],
        showEnabled: false,
      },
    })
    expect(wrapper.find('.kv-toggle').exists()).toBe(false)
  })
})
