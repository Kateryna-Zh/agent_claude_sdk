# Python Interview Topics

# Python Interview Core Topics

This document covers common Python topics asked in technical interviews.

## Language Basics
- Variables are dynamically typed
- Everything is an object
- Functions are first-class citizens

## Data Structures
- list: ordered, mutable
- tuple: ordered, immutable
- set: unordered, unique
- dict: key-value mapping

## Mutability
- mutable: list, dict, set
- immutable: int, float, str, tuple

Understanding mutability is critical for debugging bugs.

## Functions
- default arguments are evaluated once
- keyword vs positional arguments
- *args and **kwargs

## Decorators
Used to wrap functions with additional behavior.

Common use cases:
- logging
- authentication
- timing
- validation

## Exceptions
- try / except / else / finally
- custom exceptions
- never catch bare Exception unless justified

## OOP Concepts
- inheritance
- composition (preferred)
- method resolution order (MRO)

## Common Traps
- mutable default arguments
- shallow vs deep copy
- late binding in closures

## Python in Production
- virtual environments
- dependency pinning
- logging instead of print
- type hints for clarity
