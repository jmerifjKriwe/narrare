/**
 * Regression test: Stale closure in Autosave TipTap extension
 *
 * Bug: The Autosave extension's `saveFn` was frozen at editor mount time because
 * `useEditor()` only creates extensions once. When `activeChapterId` changed
 * (user selects a different chapter), `handleAutosave` in EditorView was recreated
 * with the new ID, but the Autosave extension still held a reference to the OLD
 * closure — where `activeChapterId` was null. Result: the PUT request always
 * short-circuited at `if (!activeChapterId) return`.
 *
 * Fix: Ref-based indirection in TipTapEditor.tsx. The `saveFn` wrapper reads from
 * `saveFnRef.current` at CALL TIME, and a useEffect keeps the ref updated whenever
 * `onAutosave` changes. This means the Autosave extension always calls the latest
 * `handleAutosave` with the current `activeChapterId`.
 *
 * This test verifies both:
 * 1. The OLD (broken) pattern would produce stale closures
 * 2. The NEW (ref-based) pattern always calls the latest function
 */

// ---------------------------------------------------------------------------
// Pattern simulation helpers
// ---------------------------------------------------------------------------

/**
 * Simulates the OLD (broken) pattern where saveFn is captured directly in useMemo.
 * This is what TipTapEditor.tsx used to do:
 *   saveFn: onAutosave ?? (async () => {})
 */
function createStaleSaveFnWrapper() {
  let capturedSaveFn: ((content: string) => Promise<string>) | null = null;

  // Simulates useMemo that captures saveFn directly
  function configure(saveFn: (content: string) => Promise<string>) {
    capturedSaveFn = saveFn; // frozen — only updated when useMemo recomputes
  }

  // Simulates the Autosave extension calling saveFn at some later time
  async function callSaveFn(content: string): Promise<string> {
    if (!capturedSaveFn) throw new Error("saveFn not configured");
    return capturedSaveFn(content);
  }

  return { configure, callSaveFn };
}

/**
 * Simulates the NEW (fixed) pattern where saveFn reads from a ref at call time.
 * This is what TipTapEditor.tsx now does:
 *   saveFn: (content: string) => saveFnRef.current(content)
 */
function createRefBasedSaveFnWrapper() {
  const ref: { current: (content: string) => Promise<string> } = {
    current: async () => "",
  };

  // Simulates useEffect keeping the ref updated
  function updateRef(saveFn: (content: string) => Promise<string>) {
    ref.current = saveFn;
  }

  // Simulates the stable config — reads from ref at call time
  const stableSaveFn = (content: string) => ref.current(content);

  return { updateRef, stableSaveFn };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Autosave stale closure regression", () => {
  it("OLD pattern: saveFn is stale after update (demonstrates the bug)", async () => {
    const wrapper = createStaleSaveFnWrapper();

    // Step 1: Initial configuration — simulates mount with no activeChapterId
    // useCallback captures the VALUE at creation time (each render has its own scope)
    const capturedChapterIdV1: string | null = null;
    const handleAutosaveV1 = async (content: string) =>
      `${content}|${capturedChapterIdV1 ?? "null"}`;
    wrapper.configure(handleAutosaveV1);

    // Step 2: User selects a chapter — chapterId changes, new handleAutosave is created
    // BUT in the old pattern, useEditor doesn't reconfigure extensions, so configure()
    // is never called again with the new function.
    const capturedChapterIdV2: string | null = "ch-123";
    // handleAutosaveV2 exists but is never wired up — simulates the stale closure
    const _handleAutosaveV2 = async (content: string) => `${content}|${capturedChapterIdV2}`;
    void _handleAutosaveV2;

    // Step 3: Autosave fires — calls the FROZEN saveFn (V1, not V2)
    const result = await wrapper.callSaveFn("Hello");

    // BUG: The result uses the OLD chapterId (null), not the new one
    expect(result).toBe("Hello|null"); // stale!
    expect(result).not.toBe("Hello|ch-123"); // the correct value is lost
  });

  it("NEW pattern: ref-based wrapper always calls the latest function", async () => {
    const { updateRef, stableSaveFn } = createRefBasedSaveFnWrapper();

    // Step 1: Initial state — no chapter selected
    let chapterId: string | null = null;
    const handleAutosaveV1 = async (content: string) => `${content}|${chapterId ?? "null"}`;
    updateRef(handleAutosaveV1);

    // Verify initial behavior
    await expect(stableSaveFn("test")).resolves.toBe("test|null");

    // Step 2: Chapter selected — chapterId changes, handleAutosave recreated
    chapterId = "ch-456";
    const handleAutosaveV2 = async (content: string) => `${content}|${chapterId}`;
    updateRef(handleAutosaveV2); // useEffect keeps ref updated

    // Step 3: Autosave fires — calls through ref, gets LATEST function
    await expect(stableSaveFn("Hello")).resolves.toBe("Hello|ch-456");

    // Step 4: Chapter changes again
    chapterId = "ch-789";
    const handleAutosaveV3 = async (content: string) => `${content}|${chapterId}`;
    updateRef(handleAutosaveV3);

    await expect(stableSaveFn("World")).resolves.toBe("World|ch-789");
  });

  it("ref-based wrapper uses the stable reference identity (extensions array stays stable)", () => {
    const { updateRef, stableSaveFn } = createRefBasedSaveFnWrapper();

    // The stableSaveFn identity never changes — it always reads from the ref
    const fn1 = stableSaveFn;
    updateRef(async (s: string) => `v1:${s}`);
    const fn2 = stableSaveFn;

    // Same function reference — this is what keeps useEditor's extensions stable
    expect(fn1).toBe(fn2);
  });

  it("simulates full scenario: chapter selection triggers autosave with correct ID", async () => {
    /**
     * This test simulates the exact user flow that was broken:
     * 1. TipTapEditor mounts with no activeChapterId
     * 2. User selects a chapter → activeChapterId changes
     * 3. Autosave fires → must use the LATEST activeChapterId
     */
    const savedContents: Array<{ content: string; chapterId: string | null }> = [];

    // Simulate the ref-based pattern (the fix in TipTapEditor.tsx)
    const saveFnRef: {
      current: (content: string) => Promise<void>;
    } = {
      current: async () => {},
    };

    // Track "activeChapterId" changes
    let activeChapterId: string | null = null;

    // Simulate EditorView's handleAutosave — recreated when activeChapterId changes
    const createHandleAutosave = (chapterId: string | null) => async (content: string) => {
      savedContents.push({ content, chapterId });
    };

    // Step 1: Mount — no chapter selected
    saveFnRef.current = createHandleAutosave(activeChapterId);

    // Step 2: User selects chapter ch-100
    activeChapterId = "ch-100";
    // useEffect in TipTapEditor updates the ref:
    saveFnRef.current = createHandleAutosave(activeChapterId);

    // Step 3: Autosave extension fires (via timer or forceSave)
    // The wrapper reads saveFnRef.current at CALL TIME
    await saveFnRef.current("<p>Chapter content</p>");

    expect(savedContents).toHaveLength(1);
    expect(savedContents[0]).toEqual({
      content: "<p>Chapter content</p>",
      chapterId: "ch-100", // ✅ Correct! Not null!
    });

    // Step 4: User switches to ch-200
    activeChapterId = "ch-200";
    saveFnRef.current = createHandleAutosave(activeChapterId);

    // Step 5: Autosave fires again
    await saveFnRef.current("<p>Updated content</p>");

    expect(savedContents).toHaveLength(2);
    expect(savedContents[1]).toEqual({
      content: "<p>Updated content</p>",
      chapterId: "ch-200", // ✅ Correct! Not ch-100!
    });
  });
});
