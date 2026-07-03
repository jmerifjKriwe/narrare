# CI Warning Visibility — Implementation Plan

> **For agentic workers:** Each task is independently testable before commit.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `continue-on-error: true` with visible `::warning::` annotations + job summary aggregation, and make stable checks blocking.

**Architecture:** Warning-only scripts exit 0 but emit GitHub Actions `::warning::` annotations. Stable scripts (current_state_facts, eval_drift smoke) become blocking by removing `continue-on-error`. A cross-job aggregator collects all warnings into `$GITHUB_STEP_SUMMARY`.

**Tech Stack:** Python 3.14, GitHub Actions, shell

---

### Task 1: Fix performance check scripts (exit 0)

**Files:**
- Modify: `scripts/check_pytest_collection_performance.py:84`
- Modify: `scripts/check_test_performance.py:53`

Both scripts already emit `::warning::` annotations. They just need to exit 0 instead of 1 so the step stays green without `continue-on-error`.

- [ ] **Fix `check_pytest_collection_performance.py:84`**

  Change `return 1` to `return 0` on the threshold-exceeded path.

- [ ] **Fix `check_test_performance.py:53`**

  Change `return 1` to `return 0` in `check_threshold()`.

- [ ] **Verify both scripts**

  Run: `uv run python scripts/check_pytest_collection_performance.py`
  Run: `uv run python scripts/check_test_performance.py --duration 999 --threshold 10`
  Expected: Both exit 0, output contains `::warning::`

---

### Task 2: CI YAML — remove continue-on-error, add blocking

**Files:**
- Modify: `.github/workflows/ci.yml` (multiple locations)
- Modify: `.github/workflows/eval-nightly.yml:87-91`

Changes in `ci.yml`:

1. **Architecture job — `check_eval_drift`** (line 178-180):
   - Remove `continue-on-error: true`
   - Rename step from "Check eval drift (WARNING-only)" to "Check eval drift"

2. **Architecture job — `check_current_state_facts`** (line 184-186):
   - Remove `continue-on-error: true`
   - Remove the `if: always()` condition
   - Rename step from "Check SSOT facts (CURRENT_STATE.md drift)" to "Check SSOT facts (CURRENT_STATE.md)"

3. **Test-unit job — `check_pytest_collection_performance`** (line 340-343):
   - Remove `continue-on-error: true`
   - Keep `if: always() && steps.tests.outcome != 'cancelled'`
   - Rename from "Check pytest collection performance (WARNING-only)" to "Check pytest collection performance"

4. **Frontend job — `check_frontend_test_performance`** (line 562-574):
   - Remove `continue-on-error: true`
   - Keep `if: always() && steps.frontend-tests.outcome != 'cancelled'`
   - Rename from "Check frontend test performance (WARNING-only)" to "Check frontend test performance"

Changes in `eval-nightly.yml`:

5. **Nightly job — `check_eval_drift`** (line 87-91):
   - **Keep** `continue-on-error: true` (runtime evals can legitimately drift)
   - No other changes

---

### Task 3: CI YAML — warning collector per job

**Files:**
- Modify: `.github/workflows/ci.yml`

Each job that has warning-only steps (architecture, test-unit, frontend) gets:
- A final step that collects `::warning::` lines from all previous steps
- Uploads them as an artifact for cross-job aggregation

- [ ] **Add warning collector to architecture job** (after all existing steps)

  ```yaml
  - name: Collect warnings for job summary
    if: always()
    run: |
      mkdir -p /tmp/warnings
      echo "## Architecture Job" > /tmp/warnings/warnings-report.txt
      echo "" >> /tmp/warnings/warnings-report.txt
      # ::warning:: annotations are visible in GitHub UI, but we also
      # capture any structured output for the aggregated summary
      echo "See annotations in the job log for details." >> /tmp/warnings/warnings-report.txt

  - uses: actions/upload-artifact@v7
    if: always()
    with:
      name: warnings-architecture
      path: /tmp/warnings/
  ```

  Wait — this is too abstract. Let me think about what meaningful content the warning collector can actually capture.

  The key insight: `::warning::` lines are stdout text. We can redirect the warning script output to a file, then collect those files. But modifying every warning step to tee output is invasive.

  **Simpler approach:** The warning scripts already print structured output (e.g., "Collection time: 142s (threshold: 120s)"). Instead of a collector, we just:
  1. Have each warning script append its findings to a well-known file
  2. Upload that file as an artifact

  Or even simpler: Use a shared wrapper. But that's more complex.

  **Even simpler:** Skip per-job file collection entirely. The `::warning::` annotations ARE the signal. The aggregator job just downloads the pipeline outputs (not possible cross-job without artifacts).

  **Cleanest approach:** Each job writes a simple warnings-report.txt before uploading. The warning scripts don't need to change — we add a step that greps for `::warning::` in the current job's log... but GitHub Actions doesn't expose previous step output that way.

  **Final approach — output file per job:**
  Each job that has warning steps adds a small wrapper that captures output:

  ```yaml
  - name: Check frontend test performance
    id: check-perf
    if: always() && steps.frontend-tests.outcome != 'cancelled'
    run: |
      uv run python scripts/check_test_performance.py \
        --duration "${{ steps.frontend-tests.outputs.duration }}" --threshold 240 \
        | tee /tmp/warnings/frontend-performance.txt
      exit ${PIPESTATUS[0]}
  ```

  This way:
  - The step still works as before (exit code from the script)
  - Output is captured to a file
  - The file gets uploaded as part of the job's warning artifact

  Actually, this is getting complicated. Let me simplify.

  **Simplest viable approach:**
  Add one final upload step per job that checks if `/tmp/warnings/` has files and uploads them. The warning scripts can write to this directory if they want, and the CI step can tee output there.

Let me think about this differently. The real question is: what goes INTO the aggregated summary? The `::warning::` annotations already appear in the GitHub UI. The value of the aggregator is to show a consolidated view.

For the aggregator to have meaningful content, each warning step needs to produce output that gets captured. The simplest way:

**Per-job: Append to warnings file**
Each warning step tees its output:
```yaml
- name: Check pytest collection performance
  shell: bash
  run: |
    mkdir -p /tmp/warnings
    uv run python scripts/check_pytest_collection_performance.py \
      | tee -a /tmp/warnings/report.txt
    exit ${PIPESTATUS[0]}
```

Then upload:
```yaml
- name: Upload warnings
  if: always()
  uses: actions/upload-artifact@v7
  with:
    name: warnings-${{ github.job }}
    path: /tmp/warnings/
```

**Aggregator job:**
```yaml
warnings-summary:
  if: always()
  needs: [architecture, test-unit, frontend]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/download-artifact@v8
      with:
        pattern: warnings-*
        merge-multiple: true
    - name: Build warning summary
      run: |
        echo "# ⚠️ CI Warning Summary" >> $GITHUB_STEP_SUMMARY
        echo "" >> $GITHUB_STEP_SUMMARY
        if [ -f report.txt ] && [ -s report.txt ]; then
          echo '```' >> $GITHUB_STEP_SUMMARY
          cat report.txt >> $GITHUB_STEP_SUMMARY
          echo '```' >> $GITHUB_STEP_SUMMARY
        else
          echo "✅ No warnings." >> $GITHUB_STEP_SUMMARY
        fi
```

This is clean and the effort is genuinely low: ~5 lines per job, ~10 lines for aggregator.

---

### Task 4: Update gate-drift check

**Files:**
- Modify: `scripts/gate_drift_checks.py`

The `check_streaming_compliance` and `check_locale_sync` functions check `_has_continue_on_error`. Since we're removing `continue-on-error` from some scripts, we need to verify these functions still work correctly (they check different scripts than the ones we're changing, so they should be unaffected). Just verify.

---

### Execution Order

1. Task 1: Script exit code fixes (performance checks)
2. Task 4: Verify gate-drift check unaffected
3. Task 2: CI YAML changes (remove `continue-on-error`)
4. Task 3: CI YAML warning collector + aggregator

Each task is independently testable:
- Task 1: `python script.py && echo OK` confirms exit 0
- Task 2: View CI run, verify steps no longer have `continue-on-error`
- Task 3: View CI run summary, verify warning summary appears
