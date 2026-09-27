"""Watching memory, and doing something about it before the OS does.

A pipeline that holds three times its budget in intermediates should finish, slower,
by writing some of them to disk. What it should not do is die -- an `OOMKilled` after
forty minutes of requests costs the requests as well as the run, and says nothing about
which value was too big.

Two watermarks, both fractions of the budget (SPEC section 12):

- **soft, 70%** -- stop admitting new work and start spilling. Nothing is wrong yet;
  this is the point at which continuing to grow would make it wrong.
- **hard, 85%** -- reduce concurrency, and warn *with the numbers*. "Memory pressure" is
  not actionable; "1.2G of 1.4G, reduced concurrency 16 -> 8" is.

**Measuring is deliberately cheap and approximate.** RSS is sampled, not computed, and
the store's own byte counts are estimates. Both are used to decide whether to write a
file, and that decision tolerates being wrong by a factor of two. Being exact would cost
more than the thing it protects.

**CPU and event-loop lag** (ADR 0016) are two further, optional signals. Memory is not
always what runs out first: a `foreach` over process-lane steps can pin every core, and
a starved asyncio loop shows up as lag long before memory moves. Both are off unless
`@limits` sets a threshold, and neither spills anything -- they only pace admission.
At soft, one step fewer; at hard, half; never below 1; and back up one step at a time
once every watched signal is clear again. Running steps always finish.
"""

from __future__ import annotations

import asyncio
import os
import platform
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

#: Fractions of the budget. Named rather than inlined because the numbers are a policy
#: and the policy is worth being able to see in one place.
SOFT = 0.70
HARD = 0.85

#: What a run may use when nobody said. A share of the machine rather than a constant:
#: the same workflow on a laptop and a build box should not have the same ceiling.
DEFAULT_SHARE = 0.5

#: Floor for the default. Below this the watermarks fire on an empty run.
MIN_BUDGET = 512 * 1024 * 1024

_UNITS = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}

#: How often the loop-lag timer expects to fire, in seconds.
LAG_TICK = 0.1

#: The shortest span a CPU/lag sample covers. Sampling after every publish would read
#: CPU over a few milliseconds, which is noise, and would re-pace on every blip.
LOAD_WINDOW = 0.5

_RANK = {"ok": 0, "soft": 1, "hard": 2}


class Spillable(Protocol):
    """What the governor needs from a store. Nothing else about it."""

    def spill_candidates(self) -> list[str]:
        """Live, unspilled bindings, largest first.

        Pinned ones are included: spilling is not freeing. The value is still there and
        still readable, it is just on disk -- which is exactly what should happen to the
        large answer a run has finished computing but not yet written.
        """
        ...

    def spill(self, name: str) -> int:
        """Move one binding to disk. Returns the bytes recovered."""
        ...


@dataclass(slots=True)
class Pressure:
    """One sample, and what it implies."""

    used: int
    budget: int
    level: str = "ok"

    @property
    def fraction(self) -> float:
        return self.used / self.budget if self.budget else 0.0

    def describe(self) -> str:
        return f"{human(self.used)} of {human(self.budget)} ({self.fraction:.0%})"


@dataclass(frozen=True, slots=True)
class Load:
    """CPU and loop-lag thresholds. All None -- the default -- watches neither.

    CPU is a percentage of the whole machine (0-100); lag is in seconds. The probes are
    injectable for the same reason `Governor.probe` is: the policy should be testable
    without burning a core or blocking a loop on purpose.
    """

    cpu_soft: float | None = None
    cpu_hard: float | None = None
    lag_soft: float | None = None
    lag_hard: float | None = None
    #: System CPU percent since the previous call, or None when it cannot be measured.
    cpu_probe: Callable[[], float | None] | None = None
    #: Worst loop lateness since the previous call, in seconds. None means a `LoopLag`.
    lag_probe: Callable[[], float] | None = None
    clock: Callable[[], float] = time.monotonic
    window: float = LOAD_WINDOW

    @property
    def cpu(self) -> bool:
        return self.cpu_soft is not None or self.cpu_hard is not None

    @property
    def lag(self) -> bool:
        return self.lag_soft is not None or self.lag_hard is not None


@dataclass(frozen=True, slots=True)
class Decision:
    """One change to the admission ceiling, and the measurement that caused it."""

    signal: str
    level: str
    #: Percent for `cpu`, milliseconds for `loop_lag`.
    value: float
    threshold: float
    before: int
    after: int

    @property
    def lowered(self) -> bool:
        return self.after < self.before

    @property
    def severity(self) -> Literal["info", "warning"]:
        return "warning" if self.lowered or self.level == "unavailable" else "info"

    def describe(self) -> str:
        if self.level == "unavailable":
            return (
                "cpu thresholds are set but psutil is not installed, so cpu is not "
                "watched; install it with: pip install 'sclpl[monitor]'"
            )
        name, unit = ("cpu", "%") if self.signal == "cpu" else ("loop lag", "ms")
        mark = "below" if self.level == "ok" else self.level
        return (
            f"{name} at {self.value:.0f}{unit} ({mark} {self.threshold:.0f}{unit}); "
            f"concurrency {self.before} -> {self.after}"
        )


@dataclass(slots=True)
class Governor:
    """Samples memory and decides what to give back.

    Holds no reference to the scheduler. It answers "is there pressure, and what did
    spilling recover", and the caller decides what that means for admission -- which
    keeps the policy testable without a running graph.
    """

    budget: int
    #: How to read resident memory. None means the module's own probe. Injectable so
    #: the policy can be tested without a process that happens to be the right size --
    #: and so a platform where the probe does not work can supply its own.
    probe: Callable[[], int] | None = None
    #: Set when a hard watermark has fired, so the warning is not repeated every sample.
    warned: bool = False
    #: Names spilled by this governor, newest last. For the run summary.
    spilled: list[str] = field(default_factory=list)
    #: CPU and loop-lag thresholds. None watches neither, and changes nothing.
    load: Load | None = None
    #: The ceiling load pressure allows, below whatever memory allows. None: no cut.
    cap: int | None = None
    _lag: LoopLag | None = field(default=None, init=False, repr=False)
    _last: float | None = field(default=None, init=False, repr=False)
    _noted: bool = field(default=False, init=False, repr=False)

    def sample(self, store_bytes: int = 0) -> Pressure:
        """Where memory stands. ``store_bytes`` is what the store believes it holds.

        The larger of RSS and the store's estimate wins. RSS misses nothing but includes
        the interpreter; the store's estimate misses everything the store does not know
        about. Taking the maximum means neither blind spot can hide pressure.
        """
        used = max((self.probe or rss)(), store_bytes)
        level = "ok"
        if used >= self.budget * HARD:
            level = "hard"
        elif used >= self.budget * SOFT:
            level = "soft"
        return Pressure(used=used, budget=self.budget, level=level)

    def relieve(self, store: Spillable, pressure: Pressure) -> int:
        """Spill until back under the soft watermark. Returns the bytes recovered.

        Largest first, because a hundred small files cost a hundred syscalls to recover
        what one large one would. Stops as soon as the estimate says it is enough rather
        than re-sampling RSS each time: RSS does not fall until the allocator returns
        the pages, which it may not do promptly, and waiting for it would spill
        everything.
        """
        target = self.budget * SOFT
        recovered = 0
        for name in store.spill_candidates():
            if pressure.used - recovered <= target:
                break
            freed = store.spill(name)
            if freed:
                recovered += freed
                self.spilled.append(name)
        return recovered

    def concurrency_for(self, current: int, pressure: Pressure) -> int:
        """The ceiling this much pressure allows. Halves at the hard watermark.

        Never below 1: a run that cannot admit anything is a deadlock, and a slow run is
        strictly better than that.
        """
        if pressure.level != "hard":
            return current
        return max(1, current // 2)

    # -- CPU and loop lag ------------------------------------------------------------

    def start(self) -> None:
        """Begin timing the running loop, if lag is watched and nobody supplied a probe."""
        load = self.load
        if load is not None and load.lag and load.lag_probe is None and self._lag is None:
            self._lag = LoopLag()
            self._lag.start()

    def stop(self) -> None:
        if self._lag is not None:
            self._lag.stop()
            self._lag = None

    def admits(self, ceiling: int) -> int:
        """What may run at once, given the ceiling memory allows."""
        return ceiling if self.cap is None else max(1, min(self.cap, ceiling))

    def pace(self, ceiling: int) -> list[Decision]:
        """Sample CPU and loop lag, and move `cap` one decision's worth.

        The worst signal decides, once: CPU at hard and lag at soft halves, rather than
        halving and then taking one more. Recovery needs every signal clear and climbs
        one step per window, so a run that tripped a threshold does not stay slow
        forever, and does not leap straight back into the pressure it just left.
        """
        load = self.load
        if load is None or not (load.cpu or load.lag):
            return []
        now = load.clock()
        if self._last is not None and now - self._last < load.window:
            return []
        self._last = now
        before = self.admits(ceiling)
        notes: list[Decision] = []
        readings: list[tuple[str, float, float | None, float | None]] = []
        if load.cpu:
            cpu = (load.cpu_probe or cpu_percent)()
            if cpu is not None:
                readings.append(("cpu", cpu, load.cpu_soft, load.cpu_hard))
            elif not self._noted:
                self._noted = True
                notes.append(Decision("cpu", "unavailable", 0.0, 0.0, before, before))
        if load.lag:
            probe = load.lag_probe or (self._lag.read if self._lag else lambda: 0.0)
            readings.append(("loop_lag", probe() * 1000, _ms(load.lag_soft), _ms(load.lag_hard)))
        if not readings:
            return notes
        # Worst level wins; on a tie, the first signal (cpu) names the decision.
        signal, value, soft, hard = max(readings, key=lambda reading: _RANK[_level(*reading[1:])])
        level = _level(value, soft, hard)
        if level == "hard":
            after = max(1, before // 2)
        elif level == "soft":
            after = max(1, before - 1)
        else:
            after = before if self.cap is None else min(ceiling, before + 1)
        if after == before:
            return notes
        self.cap = None if after >= ceiling else after
        threshold = hard if level == "hard" or soft is None else soft
        return [*notes, Decision(signal, level, value, threshold or 0.0, before, after)]


def parse_budget(text: str | None) -> int:
    """`4G`, `512M`, `2048` (bytes). None means a share of the machine."""
    if not text:
        return default_budget()
    cleaned = text.strip().lower().rstrip("b")
    if not cleaned:
        return default_budget()
    unit = _UNITS.get(cleaned[-1])
    if unit is None:
        return int(float(cleaned))
    return int(float(cleaned[:-1]) * unit)


def default_budget() -> int:
    """Half the machine, floored. A ceiling nobody chose should still be generous."""
    total = system_memory()
    if total <= 0:
        return MIN_BUDGET
    return max(MIN_BUDGET, int(total * DEFAULT_SHARE))


def human(value: int) -> str:
    """Bytes as something a person can read. Used in every pressure message."""
    size = float(value)
    for suffix in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024 or suffix == "GB":
            return f"{size:.0f}{suffix}" if suffix == "B" else f"{size:.1f}{suffix}"
        size /= 1024
    return f"{size:.1f}GB"


def parse_percent(value: str | float) -> float:
    """`70%` or `70` -> 70.0. A share of the whole machine, so (0, 100]."""
    text = str(value).strip()
    number = float(text[:-1] if text.endswith("%") else text)
    if not 0 < number <= 100:
        raise ValueError(f"a cpu threshold is a percentage in (0, 100], not {value!r}")
    return number


def parse_lag(value: str | float) -> float:
    """`250ms` or `0.25s` -> 0.25 seconds. The unit is required: a bare `250` would
    read as seconds everywhere else in `@limits` and as milliseconds to anyone who
    has measured loop lag before."""
    text = str(value).strip().lower()
    for suffix, scale in (("ms", 0.001), ("s", 1.0)):
        if text.endswith(suffix):
            number = float(text[: -len(suffix)]) * scale
            if number <= 0:
                break
            return number
    raise ValueError(f"a loop-lag threshold needs a unit, e.g. 250ms or 0.25s; got {value!r}")


def parse_load(
    cpu_soft: str | float | None = None,
    cpu_hard: str | float | None = None,
    loop_lag_soft: str | float | None = None,
    loop_lag_hard: str | float | None = None,
) -> Load | None:
    """`@limits` text -> `Load`, or None when nothing is set -- which keeps the
    governor exactly as it was before these signals existed."""
    if cpu_soft is None and cpu_hard is None and loop_lag_soft is None and loop_lag_hard is None:
        return None
    return Load(
        cpu_soft=None if cpu_soft is None else parse_percent(cpu_soft),
        cpu_hard=None if cpu_hard is None else parse_percent(cpu_hard),
        lag_soft=None if loop_lag_soft is None else parse_lag(loop_lag_soft),
        lag_hard=None if loop_lag_hard is None else parse_lag(loop_lag_hard),
    )


def _level(value: float, soft: float | None, hard: float | None) -> str:
    if hard is not None and value >= hard:
        return "hard"
    if soft is not None and value >= soft:
        return "soft"
    return "ok"


def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else seconds * 1000


def cpu_percent() -> float | None:
    """System-wide CPU percent since the previous call; None without psutil.

    System rather than this process: process-lane steps run in child processes, and a
    neighbouring workload starves us just as surely as our own. The first call after
    import reads 0.0, which is the safe direction.
    """
    try:
        import psutil
    except ImportError:
        return None
    return float(psutil.cpu_percent(interval=None))


class LoopLag:
    """How late a periodic timer on the running loop fires.

    A loop that is blocked -- a synchronous sleep, a CPU-bound call in an async step --
    cannot run the timer, so lateness measures starvation directly. `read` also counts
    a tick that is overdue but has not fired yet, because the governor usually samples
    right after the blocking call returns, before the loop has had a chance to run it.
    """

    __slots__ = ("tick", "_loop", "_handle", "_due", "_worst")

    def __init__(self, tick: float = LAG_TICK) -> None:
        self.tick = tick
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handle: asyncio.TimerHandle | None = None
        self._due = 0.0
        self._worst = 0.0

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._arm()

    def stop(self) -> None:
        if self._handle is not None:
            self._handle.cancel()
        self._handle = None
        self._loop = None

    def read(self) -> float:
        """Worst lateness in seconds since the previous read."""
        if self._loop is None:
            return 0.0
        worst = max(self._worst, self._loop.time() - self._due, 0.0)
        self._worst = 0.0
        return worst

    def _arm(self) -> None:
        if self._loop is None:
            return
        self._due = self._loop.time() + self.tick
        self._handle = self._loop.call_at(self._due, self._fire)

    def _fire(self) -> None:
        if self._loop is not None:
            self._worst = max(self._worst, self._loop.time() - self._due)
        self._arm()


# -- measuring --------------------------------------------------------------------
#
# Best-effort, and 0 when it cannot be read. A governor that cannot measure does
# nothing: spilling on a bad reading would make a healthy run slow for no reason.
#
# `platform.system()` rather than `sys.platform`, because a type checker narrows the
# latter to the platform it is running on and then reports every other branch as dead
# code. The same file has to check on Windows and Linux.


def _windows() -> bool:
    return platform.system() == "Windows"


def _win(module: Any, library: str) -> Any:
    """A Windows system library, looked up rather than named.

    `ctypes.windll` does not exist off Windows, so writing it plainly makes the file
    fail to type-check on Linux -- and a `type: ignore` for that is itself unused on
    Windows, so there is no spelling of the attribute that satisfies both. Going through
    `__dict__` sidesteps the question.
    """
    return getattr(module.__dict__["windll"], library)


def rss() -> int:
    """Resident set size of this process, in bytes."""
    return _rss_windows() if _windows() else _rss_posix()


def system_memory() -> int:
    """Total physical memory, in bytes."""
    if _windows():
        return _system_windows()
    sysconf = getattr(os, "sysconf", None)
    if sysconf is None:
        return 0
    try:
        return int(sysconf("SC_PAGE_SIZE")) * int(sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError):
        return 0


def _rss_posix() -> int:
    """`/proc` where it exists, `getrusage` otherwise.

    `getrusage` reports a *peak*, which overstates the current figure. Overstating is
    the safe direction: it spills sooner than needed rather than later than useful.
    """
    sysconf = getattr(os, "sysconf", None)
    if sysconf is not None:
        try:
            with open("/proc/self/statm", encoding="ascii") as handle:
                pages = int(handle.read().split()[1])
            return pages * int(sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, IndexError):
            pass
    try:
        import resource
    except ImportError:
        return 0
    # Reached through getattr because `resource` does not exist on Windows, and a type
    # checker running there has no stubs for its contents.
    getrusage = getattr(resource, "getrusage", None)
    self_id = getattr(resource, "RUSAGE_SELF", 0)
    if getrusage is None:
        return 0
    try:
        peak = int(getrusage(self_id).ru_maxrss)
    except OSError:
        return 0
    # Linux reports kilobytes, macOS reports bytes.
    return peak if platform.system() == "Darwin" else peak * 1024


def _rss_windows() -> int:
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = (
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            )

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)

        # `argtypes` is not optional here. `GetCurrentProcess` returns the pseudo-handle
        # 0xFFFFFFFFFFFFFFFF; without declared types ctypes truncates it to a C int on
        # the way out and then overflows on the way back in. Declaring them lets it pass
        # `HANDLE(-1)` through unchanged, which is what the API wants.
        probe = _win(ctypes, "psapi").GetProcessMemoryInfo
        probe.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        probe.restype = wintypes.BOOL
        ok = probe(wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb)
        return int(counters.WorkingSetSize) if ok else 0
    except Exception:  # noqa: BLE001
        return 0


def _system_windows() -> int:
    try:
        import ctypes
        from ctypes import wintypes

        class Status(ctypes.Structure):
            _fields_ = (
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            )

        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        _win(ctypes, "kernel32").GlobalMemoryStatusEx(ctypes.byref(status))
        return int(status.ullTotalPhys)
    except Exception:  # noqa: BLE001
        return 0
