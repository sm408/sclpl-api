"""The value store: named bindings, refcounts, and disposal.

Invariant 2 lives here. A value goes in as whatever Python object the step produced and
comes out as the same object — no stringification, no round-trip through JSON. The old
engine's `ExecutionContext` stringified everything between steps, which is why
comparisons, arithmetic, and dataframes were all impossible; there is no shared mutable
dictionary here to repeat that with.

Disposal is by refcount. Every binding knows how many consumers still have to read it;
the last read frees it. `--keep-all` turns that off, and debug mode leaves a tombstone
so a stale read raises something that names the binding instead of `KeyError`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sclpl.errors import SclplError, did_you_mean
from sclpl.values.digest import digest as compute_digest
from sclpl.values.ref import MIN_SPILL_BYTES, Scratch, ValueRef, size_of, spill

Value = Any


class BindingNotFound(SclplError):
    """A read of a name that was never produced."""


class BindingReleased(SclplError):
    """A read of a binding that was already freed.

    This is the tombstone case: it means the liveness analysis and the actual reads
    disagree, which is a bug in the planner rather than in the user's workflow.
    """


@dataclass(slots=True)
class Binding:
    """One named value produced by one step."""

    name: str
    value: Value | ValueRef
    digest: str
    readers: int
    pinned: bool = False
    size_bytes: int = 0
    #: Set when the binding has been freed and debug tombstones are on.
    released: bool = False

    @property
    def spilled(self) -> bool:
        return isinstance(self.value, ValueRef)


@dataclass(slots=True)
class StoreStats:
    live: int = 0
    spilled: int = 0
    released: int = 0
    bytes_live: int = 0
    bytes_spilled: int = 0
    bytes_freed: int = 0
    peak_bytes_live: int = 0

    def as_counts(self) -> dict[str, int]:
        return {
            "live": self.live,
            "spilled": self.spilled,
            "released": self.released,
            "bytes_live": self.bytes_live,
            "bytes_freed": self.bytes_freed,
        }


@dataclass(slots=True)
class Freed:
    """What a release actually recovered. The reporter turns this into an event."""

    name: str
    bytes: int


class ValueStore:
    """Named bindings with refcounted disposal."""

    __slots__ = ("_bindings", "_stats", "_scratch", "_keep_all", "_tombstones")

    def __init__(
        self,
        *,
        scratch: Scratch | None = None,
        keep_all: bool = False,
        tombstones: bool = True,
    ) -> None:
        self._bindings: dict[str, Binding] = {}
        self._stats = StoreStats()
        self._scratch = scratch
        self._keep_all = keep_all
        self._tombstones = tombstones

    # -- writing -----------------------------------------------------------------

    def put(
        self,
        name: str,
        value: Value,
        readers: int,
        *,
        pinned: bool = False,
        digest: str | None = None,
    ) -> Binding:
        """Bind ``value`` to ``name`` for ``readers`` consumers.

        ``readers`` of 0 with ``pinned`` false means nothing downstream wants this, so
        it is freed as soon as it lands. That is not a mistake — a step run purely for
        its side effect produces exactly that.
        """
        size = size_of(value)
        binding = Binding(
            name=name,
            value=value,
            digest=digest if digest is not None else compute_digest(value),
            readers=readers,
            pinned=pinned,
            size_bytes=size,
        )
        self._bindings[name] = binding
        self._stats.live += 1
        self._stats.bytes_live += size
        self._stats.peak_bytes_live = max(self._stats.peak_bytes_live, self._stats.bytes_live)
        if readers <= 0 and not pinned and not self._keep_all:
            self._free(binding)
        return binding

    # -- reading -----------------------------------------------------------------

    def get(self, name: str) -> Value:
        """The value bound to ``name``, rehydrating it if it was spilled."""
        binding = self._require(name)
        value = binding.value
        if isinstance(value, ValueRef):
            return value.load()
        return value

    def has(self, name: str) -> bool:
        binding = self._bindings.get(name)
        return binding is not None and not binding.released

    def binding(self, name: str) -> Binding:
        return self._require(name)

    def names(self) -> list[str]:
        return [name for name, binding in self._bindings.items() if not binding.released]

    def digest_of(self, name: str) -> str:
        return self._require(name).digest

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.has(name)

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return self._stats.live

    # -- disposal ----------------------------------------------------------------

    def retain(self, name: str, count: int = 1) -> bool:
        """Record ``count`` more consumers of ``name``. False if there is nothing to hold.

        The refcount for a binding is fixed when the plan is built, from the nodes that
        exist then. Control flow adds nodes *while the run is going* -- a loop body is
        not a node until the loop knows how many copies it has -- and those nodes read
        things too. Without this, a value read only by a loop body is freed the moment
        the loop's parent settles, and the body fails on a name that is plainly there.
        """
        binding = self._bindings.get(name)
        if binding is None or binding.released:
            return False
        binding.readers += count
        return True

    def release(self, name: str) -> Freed | None:
        """Record one consumer finished with ``name``; free it at zero.

        Returns what was recovered, or None if the binding is still live. The caller
        turns that into a `ValueFreed` event — this module never reports.
        """
        binding = self._bindings.get(name)
        if binding is None or binding.released:
            return None
        binding.readers -= 1
        if binding.readers > 0 or binding.pinned or self._keep_all:
            return None
        return self._free(binding)

    def pin(self, name: str) -> None:
        """Exempt a binding from disposal — an output port, or an explicit `keep`."""
        self._require(name).pinned = True

    def unpin(self, name: str) -> Freed | None:
        binding = self._require(name)
        binding.pinned = False
        if binding.readers <= 0 and not self._keep_all:
            return self._free(binding)
        return None

    def _free(self, binding: Binding) -> Freed:
        recovered = binding.size_bytes
        if isinstance(binding.value, ValueRef):
            self._stats.bytes_spilled -= binding.value.size_bytes
            self._stats.spilled -= 1
            binding.value.drop()
        binding.value = None
        binding.released = True
        self._stats.live -= 1
        self._stats.released += 1
        self._stats.bytes_live -= recovered
        self._stats.bytes_freed += recovered
        if not self._tombstones:
            self._bindings.pop(binding.name, None)
        return Freed(name=binding.name, bytes=recovered)

    # -- spilling ----------------------------------------------------------------

    def spill(self, name: str) -> int:
        """Move a binding to disk. Returns the bytes recovered from memory.

        A no-op when there is no scratch directory, when the binding is already out, or
        when it is too small to be worth a file.
        """
        binding = self._require(name)
        if self._scratch is None or binding.spilled or binding.size_bytes < MIN_SPILL_BYTES:
            return 0
        reference = spill(name, binding.value, self._scratch)
        binding.value = reference
        self._stats.spilled += 1
        self._stats.bytes_spilled += reference.size_bytes
        self._stats.bytes_live -= binding.size_bytes
        return binding.size_bytes

    def spill_candidates(self) -> list[str]:
        """Live, unspilled bindings, largest first — what the governor spills next."""
        candidates = [
            binding
            for binding in self._bindings.values()
            if not binding.released
            and not binding.spilled
            and binding.size_bytes >= MIN_SPILL_BYTES
        ]
        candidates.sort(key=lambda binding: binding.size_bytes, reverse=True)
        return [binding.name for binding in candidates]

    def stats(self) -> StoreStats:
        return self._stats

    def clear(self) -> None:
        for binding in list(self._bindings.values()):
            if isinstance(binding.value, ValueRef):
                binding.value.drop()
        self._bindings.clear()
        self._stats = StoreStats()

    # -- internals ---------------------------------------------------------------

    def _require(self, name: str) -> Binding:
        binding = self._bindings.get(name)
        if binding is None:
            remedies = []
            suggestion = did_you_mean(name, self.names())
            if suggestion:
                remedies.append(suggestion)
            raise BindingNotFound(
                f"no value named {name!r}",
                remedies=remedies or ["check the step id that produces it"],
            )
        if binding.released:
            raise BindingReleased(
                f"{name!r} was freed before this read",
                remedies=[
                    "this is a planner bug, not a workflow error",
                    "run with --keep-all to confirm, and report it",
                ],
            )
        return binding


@dataclass(slots=True)
class Frame:
    """A scope of local names — `let` bindings, and the loop variable in a `foreach`.

    Lookup walks outward to the store. Frames exist so a loop body can bind `item`
    fifty times concurrently without fifty entries in the global namespace.
    """

    values: dict[str, Value] = field(default_factory=dict)
    parent: Frame | None = None

    def get(self, name: str) -> Value:
        frame: Frame | None = self
        while frame is not None:
            if name in frame.values:
                return frame.values[name]
            frame = frame.parent
        raise KeyError(name)

    def has(self, name: str) -> bool:
        frame: Frame | None = self
        while frame is not None:
            if name in frame.values:
                return True
            frame = frame.parent
        return False

    def child(self, **values: Value) -> Frame:
        return Frame(values=dict(values), parent=self)

    def names(self) -> list[str]:
        seen: list[str] = []
        frame: Frame | None = self
        while frame is not None:
            seen.extend(name for name in frame.values if name not in seen)
            frame = frame.parent
        return seen
