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
"""

from __future__ import annotations

import os
import platform
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

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
