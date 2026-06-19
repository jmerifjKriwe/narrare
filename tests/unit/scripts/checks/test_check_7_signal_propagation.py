"""Tests for Check 7 — Signal propagation gate."""

from __future__ import annotations

from _ai_interaction_checks.check_7_signal_propagation import _check_execute_signal


def test_execute_with_signal_passes() -> None:
    """execute: (signal) => ... is compliant."""
    content = """
    const op = useAIOperation({
      execute: (signal) => apiWrapper(signal),
    });
    """
    issues = _check_execute_signal(content)
    assert issues == []


def test_execute_async_with_signal_passes() -> None:
    """execute: async (signal) => ... is compliant."""
    content = """
    const op = useAIOperation({
      execute: async (signal) => {
        return await apiWrapper(signal);
      },
    });
    """
    issues = _check_execute_signal(content)
    assert issues == []


def test_execute_without_params_fails() -> None:
    """execute: () => ... is a violation (no signal parameter)."""
    content = """
    const op = useAIOperation({
      execute: () => doSomething(),
    });
    """
    issues = _check_execute_signal(content)
    assert len(issues) == 1
    assert "no signal parameter" in issues[0]


def test_execute_async_without_params_fails() -> None:
    """execute: async () => ... is a violation."""
    content = """
    const op = useAIOperation({
      execute: async () => {
        return await doSomething();
      },
    });
    """
    issues = _check_execute_signal(content)
    assert len(issues) == 1
    assert "no signal parameter" in issues[0]


def test_execute_with_wrong_param_name_fails() -> None:
    """execute: (foo) => ... is a violation (param not named 'signal')."""
    content = """
    const op = useAIOperation({
      execute: (foo) => doSomething(foo),
    });
    """
    issues = _check_execute_signal(content)
    assert len(issues) == 1
    assert "not 'signal'" in issues[0]


def test_execute_with_underscore_signal_passes() -> None:
    """execute: (_signal) => ... is compliant (signal in param name)."""
    content = """
    const op = useAIOperation({
      execute: (_signal) => doSomething(),
    });
    """
    issues = _check_execute_signal(content)
    assert issues == []


def test_no_execute_definition_returns_empty() -> None:
    """Content without execute: callbacks returns no issues."""
    content = """
    const x = useAIOperation({ execute: mock.execute });
    // This is just passing execute as a property, not defining it
    """
    issues = _check_execute_signal(content)
    assert issues == []


def test_multiple_executes_all_checked() -> None:
    """Multiple execute definitions are all checked independently."""
    content = """
    const op1 = useAIOperation({
      execute: (signal) => api1(signal),
    });
    const op2 = useAIOperation({
      execute: () => api2(),
    });
    """
    issues = _check_execute_signal(content)
    assert len(issues) == 1
    assert "no signal parameter" in issues[0]
