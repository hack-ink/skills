---
name: rust-style
description: Use when implementing or reviewing Rust code and you need hack-ink mandatory Rust conventions.
---

# Rust Style (hack-ink)

## Overview

Mandatory conventions for Rust code and Rust development workflows in this repository.

## Scope

- These rules apply to Rust crates, binaries, and tooling in this repository.
- They do not apply to non-Rust projects.

## When to use

- You are about to implement, refactor, or review Rust code in this repo.
- You are about to change error handling, logging, time/TLS deps, or module layout.

## Tooling and workflow (required)

- The Rust toolchain is pinned. Do not modify `rust-toolchain.toml`, `.cargo/config.toml`, or `.rustfmt.toml`.
- Do not install, update, or override toolchains.
- Do not invoke system package managers.

## Runtime safety

- Do not use `unwrap()` in non-test code.
- `expect()` requires a clear, user-actionable message.

## Time and TLS

- Use the `time` crate for all date and time types. Do not add `chrono`.
- Use rustls for TLS. Use native-tls only when rustls is not supported.

## Formatting and layout

- `rustfmt` output is the final authority for formatting.
- Use tabs (`\t`) for indentation.
- Use a flat module structure. Do not create or keep `mod.rs`.
- If `mod.rs` exists, flatten it into `a.rs` and `a/xxx.rs` style files.

## Error handling

- Use `color_eyre::eyre::Result` for fallible APIs. Do not introduce `anyhow`.
- Use `#[error(transparent)]` only for thin wrappers where this crate adds no context and the upstream message is already sufficient for developers.
- Use `ok_or_else` to convert `Option` to `Result` with context.

## Logging

- Always use structured fields for dynamic values such as identifiers, names, counts, and errors.
- Use short, action-oriented messages as complete sentences.

## Borrowing and ownership

- Use borrowing with `&` over `.as_*()` conversions when both are applicable.
- Avoid `.clone()` unless it is required by ownership or lifetimes, or it clearly improves clarity.
- Use `into_iter()` when intentionally consuming collections.
- Do not use scope blocks solely to end a borrow.
- When an early release is required, use an explicit `drop`.
- When the value is a reference and you need to end a borrow without a drop warning, use `let _ = value;`.

## Quick reference

- Formatting: `rustfmt` is final; tabs indentation.
- Error type: `color_eyre::eyre::Result` (do not add `anyhow`).
- Time: `time` crate (do not add `chrono`).
- TLS: rustls (native-tls only if rustls is unsupported).

## Common mistakes

- Adding `chrono`/`anyhow` out of habit (violates repo conventions).
- Using `unwrap()` in non-test code.
- Keeping/adding `mod.rs` instead of flattening modules.

## Outputs

Return evidence for:

- The affected Rust scope and confirmation that the mandatory conventions were applied.
- Time/TLS dependency choices and formatting ownership decisions made.
- Error handling and logging choices aligned with Rust-specific requirements.
- Borrowing/ownership choices where they affect API boundaries and mutability.
