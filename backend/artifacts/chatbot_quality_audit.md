# Chatbot Quality Audit Report

## Overview
- Generated at: 2026-05-08T22:08:46.519525+00:00
- Total test questions: 50
- Overall pass rate: 1.0

## Pass Rate by Intent
- HYBRID: 14/14 (1.0)
- RAG_ONLY: 9/9 (1.0)
- SMALL_TALK: 7/7 (1.0)
- SQL_ONLY: 14/14 (1.0)
- UNSUPPORTED: 6/6 (1.0)

## Worst Failed Questions
- None

## Hallucination Cases
- No high-risk hallucination case detected.

## Routing Errors
- None

## Citation Issues
- None

## Stale Response Issues
- None

## UI/Debug Leakage Issues
- None

## Recommended Fixes (Priority)
- P2 — No critical failures detected: Keep the audit in CI and expand multilingual edge-case coverage.

## Minimal Acceptance Check
- At least 40 questions: True
- All required intents covered: True
- Uses real DB values: True
- Uses fake/non-existing values: True
- Clear pass/fail + priority fixes: True