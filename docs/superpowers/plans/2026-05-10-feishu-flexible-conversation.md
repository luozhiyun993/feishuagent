# Feishu Flexible Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed-step conversation flow with a slot-driven flow that accepts event details in any order and confirms once all required information is collected.

**Architecture:** `conversation.py` will move from hard-coded question states to a lightweight session with slot extraction, slot merging, and reply generation based on missing fields. `test_conversation.py` will cover out-of-order collection, multi-slot messages, confirmation updates, and extraction failure fallback. Existing runtime logging in `main.py` remains and conversation-level slot logs will be added in `conversation.py`.

**Tech Stack:** Python 3, unittest, OpenAI-compatible DeepSeek chat API, Feishu SDK

---

### Task 1: Replace Fixed-State Tests With Slot-Flow Tests

**Files:**
- Modify: `test_conversation.py`

- [ ] **Step 1: Write failing tests for slot-driven behavior**
- [ ] **Step 2: Run tests to verify they fail against current state-machine behavior**
- [ ] **Step 3: Keep one minimal end-to-end confirmation test for card generation**

### Task 2: Refactor Conversation Session And Extraction

**Files:**
- Modify: `conversation.py`

- [ ] **Step 1: Simplify session state to `IDLE`, `COLLECTING`, `CONFIRM`, `DONE`**
- [ ] **Step 2: Add structured extraction helper returning slot updates plus confirmation flag**
- [ ] **Step 3: Add safe JSON parsing and empty fallback behavior**
- [ ] **Step 4: Add slot merge helpers and required-slot checks**

### Task 3: Rebuild Reply Flow Around Missing Slots

**Files:**
- Modify: `conversation.py`

- [ ] **Step 1: Update `process()` to merge extracted slots on every message**
- [ ] **Step 2: Generate follow-up replies based on missing slots instead of fixed order**
- [ ] **Step 3: Support confirmation, confirmation-time edits, and post-DONE reset**
- [ ] **Step 4: Preserve card generation behavior once all slots are confirmed**

### Task 4: Add Debug Logging And Verify

**Files:**
- Modify: `conversation.py`
- Verify: `main.py`

- [ ] **Step 1: Log extracted slots and merged session slots in `conversation.py`**
- [ ] **Step 2: Run unit tests and confirm all pass**
- [ ] **Step 3: Run one smoke check with stubbed extraction or live model to confirm first-turn and out-of-order behavior**
