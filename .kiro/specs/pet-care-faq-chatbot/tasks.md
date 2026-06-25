# Implementation Plan: Pet Care FAQ Chatbot

## Overview

This plan implements a floating AI-powered FAQ chatbot widget for The Furever Home website. The implementation covers three subsystems: (1) the Python KB sync script that fetches pet care articles into Google Sheets, (2) the client-side Retriever that queries and scores articles via the gviz endpoint, and (3) the Chatbot Widget + AI Responder UI embedded in `index.html`. All frontend code is plain HTML/CSS/JS in the single `index.html` file; the sync script follows the existing `petfinder_sync.py` pattern.

## Tasks

- [x] 1. Implement KB Sync Script core infrastructure
  - [x] 1.1 Create `cron/faq_kb_sync.py` with credential loading and CLI argument parsing
    - Create the file following the same structure as `cron/petfinder_sync.py`
    - Load `GOOGLE_CREDENTIALS_JSON` and `SHEET_ID` from environment variables
    - Implement `--dry-run` flag using `sys.argv`
    - Set up gspread client authentication with the same scopes pattern
    - _Requirements: 3.1, 3.5, 3.6_

  - [x] 1.2 Implement article fetching from RSS feeds (ASPCA, PetMD, AKC)
    - Write a `fetch_articles_from_source(source_config)` function that fetches and parses RSS/sitemap XML
    - Support at least 3 sources with configurable feed URLs
    - Extract: title, canonical URL, source name, full HTML content
    - Handle HTTP errors (status >= 400) and network errors: log error with source name and URL, skip article, continue
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 1.3 Implement article transformation and field extraction
    - Write `extract_keywords(title, summary)` → comma-separated list of at most 10 lowercase terms
    - Write `truncate_text(html_content, max_chars=1500)` → plain text, HTML stripped, truncated at last complete word boundary
    - Write `categorize_article(title, summary)` → one of "nutrition", "training", "health", "behavior", "general"
    - Write `generate_summary(text, max_chars=300)` → summary of at most 300 characters
    - Generate `articleId` as SHA-256 hash (first 12 hex chars) of canonical URL
    - _Requirements: 2.2, 2.4, 2.5, 3.3_

  - [ ]* 1.4 Write property tests for keyword extraction (Property 2)
    - **Property 2: Keyword extraction constraints**
    - **Validates: Requirements 2.4, 3.3**
    - Use Hypothesis to generate random title+summary strings
    - Assert output is comma-separated, at most 10 terms, all lowercase alphabetic

  - [ ]* 1.5 Write property tests for text truncation (Property 3)
    - **Property 3: Text truncation at word boundary**
    - **Validates: Requirements 2.5, 3.3**
    - Use Hypothesis to generate random strings of varying length
    - Assert output ≤ 1500 chars, no HTML tags, ends at complete word boundary

  - [x] 1.6 Implement deduplication and Google Sheets write logic
    - Read existing `articleId` values from `pet_care_kb` tab
    - Skip any article whose `articleId` already exists
    - Write new articles as rows matching the schema: `articleId`, `title`, `url`, `source`, `category`, `summary`, `keywords`, `fullText`, `fetchedAt`
    - Store `fetchedAt` as ISO 8601 UTC timestamp
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 3.5_

  - [ ]* 1.7 Write property test for article ID uniqueness (Property 1)
    - **Property 1: Article ID uniqueness (deduplication)**
    - **Validates: Requirements 2.3**
    - Use Hypothesis to generate random article lists with duplicate URLs
    - Assert no two written rows share the same `articleId`

  - [x] 1.8 Implement row cap enforcement (prune to 500 rows)
    - After writing new articles, check if total rows exceed 500
    - Delete rows with lowest `fetchedAt` values until total ≤ 500
    - _Requirements: 2.7_

  - [ ]* 1.9 Write property test for row cap enforcement (Property 4)
    - **Property 4: Knowledge Base row cap enforcement**
    - **Validates: Requirements 2.7**
    - Use Hypothesis to generate random row counts and timestamps
    - Assert post-prune count ≤ 500 and removed rows are exactly the oldest

  - [x] 1.10 Implement run summary output
    - Print number of articles fetched per source, new articles written, duplicates skipped, and total elapsed time in seconds
    - In `--dry-run` mode, print fetched articles to stdout without writing to sheet
    - _Requirements: 3.6, 3.8_

- [x] 2. Checkpoint - Ensure KB Sync Script tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create GitHub Actions workflow for KB sync
  - [x] 3.1 Create `.github/workflows/faq_kb_sync.yml`
    - Define job: checkout repo, setup Python 3.11, install deps from `cron/requirements.txt`, run `python cron/faq_kb_sync.py`
    - Schedule: `0 2 * * 0` (Sunday 2:00 AM UTC) plus `workflow_dispatch` for manual runs
    - Inject `GOOGLE_CREDENTIALS_JSON` and `SHEET_ID` from GitHub Actions secrets
    - Set `timeout-minutes: 10`
    - Non-zero exit code marks workflow as failed
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 3.2 Create or update `cron/requirements.txt` with Python dependencies
    - Add gspread, google-auth, requests, feedparser (and any other required packages)
    - Pin versions for reproducibility
    - _Requirements: 8.1_

- [x] 4. Implement Chatbot Widget UI in `index.html`
  - [x] 4.1 Add chatbot HTML structure and CSS styles to `index.html`
    - Add floating action button (`.chatbot-fab`): 56px circle, fixed bottom-right, z-index 400+
    - Add chat panel (`.chatbot-panel`): 320×480px desktop, 100% width / 60%+ height on mobile (≤768px)
    - Add header with title and close button
    - Add messages area (`.chatbot-messages`): scrollable conversation container
    - Add input bar with textarea (500-char max, `aria-label="Ask a pet care question"`) and send button (`aria-label="Send question"`)
    - Use only site CSS variables (`--pink`, `--gunmetal`, `--deep-orange`, `--orange`, `--cream`, `--white`, `--light-pink`, `--light-orange`) and site font stack
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_

  - [x] 4.2 Implement widget open/close behavior and conversation state
    - Click FAB → expand chat panel, focus text input
    - Click close → collapse to FAB, preserve conversation history in memory
    - On first open: display welcome message "Hi! I'm Furever's pet care assistant. Ask me anything about caring for your new pet! 🐾"
    - Auto-scroll to most recent message after each new message
    - Style visitor messages with `--light-pink` background, chatbot responses with `--white` background
    - _Requirements: 1.2, 1.3, 6.1, 6.3, 6.4, 6.5, 7.5_

  - [x] 4.3 Implement input handling (Enter/Shift+Enter, validation, character counter)
    - Enter (without Shift) submits; Shift+Enter inserts newline
    - Reject empty/whitespace-only submissions silently (keep focus)
    - Enforce 500-character max on input field
    - Show character counter when ≥ 450 characters typed (display remaining count)
    - Disable input + send button during AI response; re-enable after response/error/30s timeout
    - _Requirements: 1.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 4.4 Implement typing indicator
    - Show animated ellipsis in conversation area while awaiting AI response
    - Remove indicator when response arrives or error occurs
    - _Requirements: 6.2_

- [x] 5. Implement Retriever module in `index.html`
  - [x] 5.1 Implement Knowledge Base fetch via gviz endpoint with session caching
    - Fetch all rows from `pet_care_kb` sheet using gviz URL pattern (same as existing pet listings)
    - Parse response into article objects with pre-split keywords
    - Cache in browser memory for session duration (subsequent queries skip re-fetch)
    - Implement 5-second timeout via `AbortController`; abort and surface timeout error on exceed
    - Handle HTTP ≥ 400: surface error message without retrying
    - _Requirements: 4.1, 4.5, 4.6, 4.7, 4.8_

  - [x] 5.2 Implement keyword-based scoring and ranking algorithm
    - Tokenize query: lowercase, split on non-alpha, filter common English stop words
    - Score each article: count matching query tokens in `keywords`, `title`, and `summary` fields (each field match = 1 point)
    - Sort descending by score; break ties alphabetically by `title` (ascending)
    - Return top 5 articles (or fewer if KB has fewer); return empty set if all scores = 0
    - On empty result: display fallback message "I couldn't find relevant articles for that question. Try rephrasing or ask about a different pet care topic."
    - _Requirements: 4.2, 4.3, 4.4_

  - [ ]* 5.3 Write property test for Retriever scoring correctness (Property 5)
    - **Property 5: Retriever scoring correctness**
    - **Validates: Requirements 4.2**
    - Use fast-check to generate random query tokens and article fields
    - Assert score equals total count of distinct query tokens matching across keywords, title, summary

  - [ ]* 5.4 Write property test for Retriever ranking invariant (Property 6)
    - **Property 6: Retriever ranking invariant**
    - **Validates: Requirements 4.3**
    - Use fast-check to generate random scored article arrays
    - Assert result ≤ 5 articles, descending score order, ties broken by ascending title

- [x] 6. Implement AI Responder module in `index.html`
  - [x] 6.1 Implement `window.CHATBOT_CONFIG` and API selection logic
    - Define config object with `apiKey`, `openaiApiKey`, `sheetId`, `kbSheetName`
    - When `apiKey` is non-empty string → use Gemini API (`gemini-1.5-flash`)
    - When `apiKey` is absent/null/empty → fall back to OpenAI (`gpt-3.5-turbo`) using `openaiApiKey`
    - When both keys missing → display "Chat is not configured yet. Please check back later."
    - _Requirements: 5.5, 5.6_

  - [x] 6.2 Implement prompt construction and AI API calls
    - Build system prompt instructing AI to: answer only pet care questions, cite only provided context, respond in 3 sentences or fewer, refuse non-pet-care questions
    - Include `summary` and `fullText` of up to 5 retrieved articles as context along with original user question
    - Implement `callGemini(prompt)` for Google Gemini API
    - Implement `callOpenAI(prompt)` for OpenAI Chat Completions API
    - _Requirements: 5.1, 5.2, 5.6_

  - [x] 6.3 Implement response rendering with sources and error handling
    - Display synthesized answer followed by "Sources" section listing title + URL of context articles
    - When AI returns out-of-domain refusal → display only refusal text, no Sources section
    - On HTTP/network error → display "I'm having trouble connecting right now — please try again shortly." (never expose API keys or raw errors)
    - _Requirements: 5.3, 5.4, 5.7_

  - [ ]* 6.4 Write property test for API fallback selection (Property 9)
    - **Property 9: AI API fallback selection**
    - **Validates: Requirements 5.6**
    - Use fast-check to generate random config objects
    - Assert Gemini called when apiKey non-empty; OpenAI called when apiKey absent/null/empty

  - [ ]* 6.5 Write property test for prompt context completeness (Property 10)
    - **Property 10: Prompt context completeness**
    - **Validates: Requirements 5.1**
    - Use fast-check to generate random article arrays and questions
    - Assert prompt includes summary + fullText of every article and the original question

- [x] 7. Checkpoint - Ensure all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Wire all components together and finalize
  - [x] 8.1 Integrate Retriever → AI Responder → Widget flow in `index.html`
    - Wire `ChatbotWidget.submit()` to call `Retriever.search()` then `AIResponder.generateAnswer()`
    - Handle all error paths (no match, timeout, API failure, missing config)
    - Ensure input disabled/re-enabled correctly through the full flow
    - Implement 30-second overall timeout that re-enables controls
    - _Requirements: 4.4, 5.4, 7.2_

  - [ ]* 8.2 Write property test for whitespace-only input rejection (Property 7)
    - **Property 7: Whitespace-only input rejection**
    - **Validates: Requirements 7.3**
    - Use fast-check to generate random whitespace strings
    - Assert submission is rejected and message list remains unchanged

  - [ ]* 8.3 Write property test for character limit enforcement (Property 8)
    - **Property 8: Character limit enforcement**
    - **Validates: Requirements 7.6**
    - Use fast-check to generate random strings of varying lengths
    - Assert input capped at 500 chars; counter visible at ≥ 450 showing correct remaining count

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The frontend (tasks 4–8) uses plain JavaScript in `index.html` with no build tools or npm packages
- The Python sync script (tasks 1, 3) mirrors the existing `cron/petfinder_sync.py` structure
- Property tests use Hypothesis (Python) and fast-check (JavaScript)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.2", "4.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "4.2"] },
    { "id": 2, "tasks": ["1.4", "1.5", "1.6", "4.3", "4.4"] },
    { "id": 3, "tasks": ["1.7", "1.8", "5.1"] },
    { "id": 4, "tasks": ["1.9", "1.10", "3.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3"] },
    { "id": 7, "tasks": ["6.4", "6.5", "8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3"] }
  ]
}
```
