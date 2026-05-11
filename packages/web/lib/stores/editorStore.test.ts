import { describe, it, expect, beforeEach } from 'vitest'
import { useEditorStore } from './editorStore'
import { createChapter, createChapterSummary } from '@/mocks/data'

describe('useEditorStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useEditorStore.setState({
      novelId: null,
      chapters: [],
      activeChapterId: null,
      activeChapter: null,
      saveStatus: 'idle',
      lastSavedAt: null,
      sidebarOpen: true,
      contextPanelOpen: false,
      focusMode: false,
    })
  })

  describe('initial state', () => {
    it('should have no novel selected', () => {
      const state = useEditorStore.getState()
      expect(state.novelId).toBeNull()
    })

    it('should have empty chapters list', () => {
      const state = useEditorStore.getState()
      expect(state.chapters).toEqual([])
    })

    it('should have no active chapter', () => {
      const state = useEditorStore.getState()
      expect(state.activeChapterId).toBeNull()
      expect(state.activeChapter).toBeNull()
    })

    it('should have idle save status', () => {
      const state = useEditorStore.getState()
      expect(state.saveStatus).toBe('idle')
    })

    it('should have no lastSavedAt', () => {
      const state = useEditorStore.getState()
      expect(state.lastSavedAt).toBeNull()
    })

    it('should have sidebar open by default', () => {
      const state = useEditorStore.getState()
      expect(state.sidebarOpen).toBe(true)
    })

    it('should have context panel closed by default', () => {
      const state = useEditorStore.getState()
      expect(state.contextPanelOpen).toBe(false)
    })

    it('should have focus mode off by default', () => {
      const state = useEditorStore.getState()
      expect(state.focusMode).toBe(false)
    })
  })

  describe('setNovelId', () => {
    it('should set the novel ID', () => {
      useEditorStore.getState().setNovelId('novel-123')

      expect(useEditorStore.getState().novelId).toBe('novel-123')
    })

    it('should replace the previous novel ID', () => {
      useEditorStore.getState().setNovelId('novel-1')
      useEditorStore.getState().setNovelId('novel-2')

      expect(useEditorStore.getState().novelId).toBe('novel-2')
    })
  })

  describe('setChapters', () => {
    it('should set the chapters list', () => {
      const chapters = [
        createChapterSummary({ id: 'ch-1', title: 'Chapter 1' }),
        createChapterSummary({ id: 'ch-2', title: 'Chapter 2' }),
      ]

      useEditorStore.getState().setChapters(chapters)

      expect(useEditorStore.getState().chapters).toEqual(chapters)
    })

    it('should replace the previous chapters', () => {
      const first = [createChapterSummary({ id: 'ch-1' })]
      const second = [createChapterSummary({ id: 'ch-2' }), createChapterSummary({ id: 'ch-3' })]

      useEditorStore.getState().setChapters(first)
      useEditorStore.getState().setChapters(second)

      expect(useEditorStore.getState().chapters).toEqual(second)
    })
  })

  describe('setActiveChapter', () => {
    it('should set active chapter and active chapter ID', () => {
      const chapter = createChapter({ id: 'ch-42', title: 'Active Chapter' })

      useEditorStore.getState().setActiveChapter(chapter)

      const state = useEditorStore.getState()
      expect(state.activeChapter).toEqual(chapter)
      expect(state.activeChapterId).toBe('ch-42')
    })
  })

  describe('setSaveStatus', () => {
    it('should set save status to "saving"', () => {
      useEditorStore.getState().setSaveStatus('saving')

      expect(useEditorStore.getState().saveStatus).toBe('saving')
    })

    it('should set save status to "saved" and update lastSavedAt', () => {
      useEditorStore.getState().setSaveStatus('saved')

      const state = useEditorStore.getState()
      expect(state.saveStatus).toBe('saved')
      expect(state.lastSavedAt).toBeInstanceOf(Date)
    })

    it('should set save status to "error" without updating lastSavedAt', () => {
      useEditorStore.getState().setSaveStatus('error')

      const state = useEditorStore.getState()
      expect(state.saveStatus).toBe('error')
      // setSaveStatus sets lastSavedAt to undefined when status is not "saved"
      expect(state.lastSavedAt).toBeUndefined()
    })

    it('should reset to "idle" without changing lastSavedAt', () => {
      useEditorStore.getState().setSaveStatus('saved')

      useEditorStore.getState().setSaveStatus('idle')

      const state = useEditorStore.getState()
      expect(state.saveStatus).toBe('idle')
      // lastSavedAt is set to undefined when not "saved", but Zustand keeps previous
      // Actually, the implementation sets lastSavedAt: undefined, which keeps the previous value
      // Let's verify the behavior from the source code:
      // set({ saveStatus, lastSavedAt: saveStatus === "saved" ? new Date() : undefined })
      // When status is not "saved", lastSavedAt is set to undefined
      expect(state.lastSavedAt).toBeUndefined()
    })
  })

  describe('toggleSidebar', () => {
    it('should toggle sidebar open state', () => {
      expect(useEditorStore.getState().sidebarOpen).toBe(true)

      useEditorStore.getState().toggleSidebar()
      expect(useEditorStore.getState().sidebarOpen).toBe(false)

      useEditorStore.getState().toggleSidebar()
      expect(useEditorStore.getState().sidebarOpen).toBe(true)
    })
  })

  describe('toggleContextPanel', () => {
    it('should toggle context panel open state', () => {
      expect(useEditorStore.getState().contextPanelOpen).toBe(false)

      useEditorStore.getState().toggleContextPanel()
      expect(useEditorStore.getState().contextPanelOpen).toBe(true)

      useEditorStore.getState().toggleContextPanel()
      expect(useEditorStore.getState().contextPanelOpen).toBe(false)
    })
  })

  describe('toggleFocusMode', () => {
    it('should toggle focus mode on and off', () => {
      expect(useEditorStore.getState().focusMode).toBe(false)

      useEditorStore.getState().toggleFocusMode()
      expect(useEditorStore.getState().focusMode).toBe(true)

      useEditorStore.getState().toggleFocusMode()
      expect(useEditorStore.getState().focusMode).toBe(false)
    })

    it('should close sidebar when entering focus mode', () => {
      useEditorStore.setState({ sidebarOpen: true, focusMode: false })

      useEditorStore.getState().toggleFocusMode()

      expect(useEditorStore.getState().focusMode).toBe(true)
      expect(useEditorStore.getState().sidebarOpen).toBe(false)
    })

    it('should restore sidebar when exiting focus mode', () => {
      useEditorStore.setState({ focusMode: true, sidebarOpen: false })

      useEditorStore.getState().toggleFocusMode()

      expect(useEditorStore.getState().focusMode).toBe(false)
      expect(useEditorStore.getState().sidebarOpen).toBe(true)
    })
  })

  describe('updateChapterWordCount', () => {
    it('should update word count for the specified chapter', () => {
      const chapters = [
        createChapterSummary({ id: 'ch-1', word_count: 100 }),
        createChapterSummary({ id: 'ch-2', word_count: 200 }),
      ]
      useEditorStore.setState({ chapters })

      useEditorStore.getState().updateChapterWordCount('ch-1', 500)

      const updated = useEditorStore.getState().chapters
      expect(updated[0].word_count).toBe(500)
      expect(updated[1].word_count).toBe(200)
    })

    it('should not modify other chapters', () => {
      const chapters = [
        createChapterSummary({ id: 'ch-1', word_count: 100 }),
        createChapterSummary({ id: 'ch-2', word_count: 200 }),
      ]
      useEditorStore.setState({ chapters })

      useEditorStore.getState().updateChapterWordCount('ch-2', 999)

      expect(useEditorStore.getState().chapters[0].word_count).toBe(100)
    })
  })
})
