from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import plugins._wait.helpers.wait as wait_helper
import plugins._wait.tools.wait as wait_tool_module
from plugins._wait.helpers.wait import format_remaining_time, managed_wait
from plugins._wait.tools.wait import WaitTool


UTC = timezone.utc


class _FakeClock:
    """Deterministic clock standing in for Localization around managed_wait."""

    def __init__(self, start: datetime) -> None:
        self.now_value = start
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.now_value

    def advance(self, seconds: float) -> None:
        self.now_value += timedelta(seconds=seconds)


class _FakeLocalization:
    """Localization stand-in exposing the .get() accessor the code expects."""

    def __init__(self, clock: _FakeClock) -> None:
        self._clock = clock

    def get(self):
        return self

    def now(self) -> datetime:
        return self._clock.now()

    def localtime_str_to_utc_dt(self, value: str):
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

    def serialize_datetime(self, dt):
        return dt.isoformat() if dt else ""


class _FakeLog:
    def __init__(self) -> None:
        self.headings: list[str] = []

    def update(self, **kwargs) -> None:
        if "heading" in kwargs:
            self.headings.append(kwargs["heading"])


class _FakeAgent:
    def __init__(self, clock: _FakeClock, intervention_pause: float = 0.0, pause_limit: int = 0) -> None:
        self.clock = clock
        self.intervention_pause = intervention_pause
        self.pause_limit = pause_limit
        self.interventions = 0

    async def handle_intervention(self, *args, **kwargs) -> None:
        self.interventions += 1
        if self.interventions <= self.pause_limit:
            self.clock.advance(self.intervention_pause)

    def read_prompt(self, name: str, **kwargs) -> str:
        return f"waited until {kwargs.get('target_time')}"


def _make_tool(agent, args: dict) -> WaitTool:
    tool = WaitTool(agent=agent, name="wait", method="execute", args=args, message="wait", loop_data=None)
    tool.log = _FakeLog()
    return tool


def _install_clock(monkeypatch, clock: _FakeClock, localization: _FakeLocalization | None = None) -> None:
    monkeypatch.setattr(wait_helper, "Localization", localization or _FakeLocalization(clock))
    monkeypatch.setattr(wait_tool_module, "Localization", localization or _FakeLocalization(clock))


def _patch_sleep(monkeypatch, clock: _FakeClock) -> None:
    async def fake_sleep(seconds: float) -> None:
        # Advance at least a tick so zero-length sleeps cannot stall the fake clock.
        advanced = max(seconds, 0.01)
        clock.sleeps.append(seconds)
        clock.advance(advanced)

    # Bind a shim asyncio on the helper module only, keeping the real global asyncio untouched.
    monkeypatch.setattr(wait_helper, "asyncio", SimpleNamespace(sleep=fake_sleep))


def test_format_remaining_time_days_hours_minutes_seconds() -> None:
    assert format_remaining_time(90061) == "1d 1h 1m 1s remaining"


def test_format_remaining_time_tenth_second_precision_under_a_minute() -> None:
    assert format_remaining_time(125.4) == "2m 5.4s remaining"
    assert format_remaining_time(65) == "1m 5.0s remaining"


def test_format_remaining_time_clamps_negative_and_zero() -> None:
    assert format_remaining_time(0) == "0.0s remaining"
    assert format_remaining_time(-3) == "0.0s remaining"


def test_format_remaining_time_keeps_whole_seconds_for_long_waits() -> None:
    assert format_remaining_time(7265) == "2h 1m 5s remaining"


@pytest.mark.anyio
async def test_wait_tool_rejects_non_positive_duration(monkeypatch):
    clock = _FakeClock(datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC))
    _install_clock(monkeypatch, clock)
    agent = _FakeAgent(clock)

    response = await _make_tool(agent, {"seconds": 0}).execute()

    assert response.break_loop is False
    assert "positive" in response.message.lower()


@pytest.mark.anyio
async def test_wait_tool_rejects_invalid_duration_arguments(monkeypatch):
    clock = _FakeClock(datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC))
    _install_clock(monkeypatch, clock)
    agent = _FakeAgent(clock)

    response = await _make_tool(agent, {"seconds": "abc"}).execute()

    assert response.break_loop is False
    assert "invalid wait arguments" in response.message.lower()


@pytest.mark.anyio
async def test_wait_tool_rejects_past_until_timestamp(monkeypatch):
    clock = _FakeClock(datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC))
    _install_clock(monkeypatch, clock)
    agent = _FakeAgent(clock)

    response = await _make_tool(agent, {"until": "2000-01-01 00:00:00"}).execute()

    assert response.break_loop is False
    assert "past" in response.message.lower()


@pytest.mark.anyio
async def test_wait_tool_accepts_valid_duration_and_completes(monkeypatch):
    clock = _FakeClock(datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC))
    _install_clock(monkeypatch, clock)
    _patch_sleep(monkeypatch, clock)
    agent = _FakeAgent(clock)

    response = await _make_tool(agent, {"seconds": 2}).execute()

    assert response.break_loop is False
    assert "2026" in response.message
    assert agent.interventions > 0


@pytest.mark.anyio
async def test_managed_wait_anchors_ticks_to_whole_seconds(monkeypatch):
    start = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    clock = _FakeClock(start)
    agent = _FakeAgent(clock)
    log = _FakeLog()
    _install_clock(monkeypatch, clock)
    _patch_sleep(monkeypatch, clock)

    target = start + timedelta(seconds=3)
    result = await managed_wait(
        agent=agent,
        target_time=target,
        is_duration_wait=True,
        log=log,
        get_heading_callback=lambda text: text,
    )

    assert result == target
    sleeps = clock.sleeps
    assert 0 < len(sleeps) < 10
    # Whole-second anchoring: intermediate sleeps sit on 1.0s boundaries.
    assert all(abs(s - 1.0) < 0.01 for s in sleeps[:-1])
    assert sleeps[-1] <= 1.0


@pytest.mark.anyio
async def test_managed_wait_extends_target_after_long_intervention_pause(monkeypatch):
    start = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    clock = _FakeClock(start)
    agent = _FakeAgent(clock, intervention_pause=2.0, pause_limit=1)
    _install_clock(monkeypatch, clock)
    _patch_sleep(monkeypatch, clock)

    target = start + timedelta(seconds=3)
    result = await managed_wait(
        agent=agent,
        target_time=target,
        is_duration_wait=True,
        log=None,
        get_heading_callback=lambda text: text,
    )

    assert result > target  # pause longer than one sleep cycle shifts the target


@pytest.mark.anyio
async def test_managed_wait_keeps_absolute_target_when_not_duration_wait(monkeypatch):
    start = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    clock = _FakeClock(start)
    agent = _FakeAgent(clock, intervention_pause=2.0, pause_limit=1)
    _install_clock(monkeypatch, clock)
    _patch_sleep(monkeypatch, clock)

    target = start + timedelta(seconds=3)
    result = await managed_wait(
        agent=agent,
        target_time=target,
        is_duration_wait=False,
        log=None,
        get_heading_callback=lambda text: text,
    )

    assert result == target


@pytest.mark.anyio
async def test_wait_tool_until_wait_survives_intervention_pause(monkeypatch):
    start = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    clock = _FakeClock(start)
    _install_clock(monkeypatch, clock)
    _patch_sleep(monkeypatch, clock)
    agent = _FakeAgent(clock, intervention_pause=2.0)

    response = await _make_tool(agent, {"until": "2026-09-20 12:00:05"}).execute()

    assert response.break_loop is False
    assert clock.sleeps  # the wait actually slept
