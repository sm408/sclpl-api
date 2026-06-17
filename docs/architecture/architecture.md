# Architecture Guide

SCLPLAPI uses a layered architecture:

- UI
- Services
- Core
- Storage / Infrastructure

The core runtime should stay independent from UI concerns so the project can later support headless execution or CLI-oriented workflows without re-architecting the system.

