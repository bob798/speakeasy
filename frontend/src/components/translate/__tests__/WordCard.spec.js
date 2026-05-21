import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WordCard from '../WordCard.vue'

describe('WordCard', () => {
  it('test_renders_word_and_phonetic', () => {
    const wrapper = mount(WordCard, {
      props: { word: 'hello', phonetic: 'həˈloʊ' },
    })
    expect(wrapper.find('.card-word').text()).toBe('hello')
    expect(wrapper.find('.card-ipa').text()).toBe('həˈloʊ')
  })

  it('test_renders_loading_state', () => {
    const wrapper = mount(WordCard, {
      props: { word: 'hello', loading: true },
    })
    expect(wrapper.find('.card-loading').text()).toBe('加载中...')
  })

  it('test_renders_explanation', () => {
    const wrapper = mount(WordCard, {
      props: {
        word: 'hello',
        explanation: {
          meaning: '你好',
          meanings: ['打招呼'],
          example: 'Hello world',
        },
      },
    })
    expect(wrapper.find('.card-meaning').text()).toBe('你好')
    expect(wrapper.find('.card-meanings').text()).toContain('打招呼')
    expect(wrapper.find('.card-example').text()).toContain('Hello world')
  })

  it('test_close_button_emits_close', async () => {
    const wrapper = mount(WordCard, {
      props: { word: 'hello' },
    })
    await wrapper.find('.card-close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('test_renders_without_explanation', () => {
    const wrapper = mount(WordCard, {
      props: { word: 'hello', explanation: null, loading: false },
    })
    expect(wrapper.find('.card-body').exists()).toBe(false)
  })

  it('test_renders_multiple_meanings', () => {
    const wrapper = mount(WordCard, {
      props: {
        word: 'run',
        explanation: {
          meaning: '跑',
          meanings: ['奔跑', '运行', '经营'],
          example: null,
        },
      },
    })
    const items = wrapper.findAll('.meaning-item')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('1.')
    expect(items[0].text()).toContain('奔跑')
    expect(items[1].text()).toContain('2.')
    expect(items[1].text()).toContain('运行')
    expect(items[2].text()).toContain('3.')
    expect(items[2].text()).toContain('经营')
  })
})
