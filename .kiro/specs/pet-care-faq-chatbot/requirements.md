# Requirements Document

## Introduction

The Furever Home pet adoption website serves Bay Area shelter visitors who need guidance on pet care. This feature adds a FAQ-based AI chatbot as a floating widget on the website. The chatbot answers pet care questions by searching a knowledge base of curated articles and blog posts stored in a dedicated Google Sheets tab, then using an AI language model to synthesize a concise, accurate response from the retrieved content. A separate Python cron script (mirroring the existing Petfinder sync pattern) periodically fetches reputable pet care content and populates the knowledge base. The entire feature must work within the existing no-build-tools, single-file HTML/CSS/JS architecture.

---

## Glossary

- **Chatbot_Widget**: The floating chat bubble and conversation panel rendered in `index.html` that visitors interact with.
- **Knowledge_Base**: The Google Sheets tab (named `pet_care_kb`) in the existing spreadsheet (Sheet ID: `1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80`) that stores fetched pet care articles.
- **KB_Sync_Script**: The Python cron script (`cron/faq_kb_sync.py`) that fetches pet care articles and writes them to the Knowledge_Base.
- **Retriever**: The client-side JavaScript module within `index.html` that queries the Knowledge_Base via the Google Sheets gviz endpoint and returns the most relevant articles for a given question.
- **AI_Responder**: The client-side JavaScript module within `index.html` that sends retrieved articles and the user's question to an AI API and returns a synthesized answer.
- **Knowledge_Base_Article**: A single row in the Knowledge_Base sheet representing one pet care article, with fields: `articleId`, `title`, `url`, `source`, `category`, `summary`, `keywords`, `fullText`, `fetchedAt`.
- **Visitor**: A person browsing The Furever Home website.
- **AI_API**: A free or low-cost generative AI API (Google Gemini API free tier preferred, falling back to OpenAI GPT-3.5-turbo) used by the AI_Responder.
- **gviz_Endpoint**: The publicly accessible Google Visualization API URL pattern already used by the site to read Google Sheets data without authentication.
- **Similarity_Search**: A keyword-based relevance matching algorithm run by the Retriever in the browser to score Knowledge_Base_Articles against the Visitor's query.

---

## Requirements

### Requirement 1: Floating Chatbot Widget

**User Story:** As a Visitor, I want a persistent chat button visible on every page, so that I can open the chatbot and ask pet care questions at any time without leaving my current page.

#### Acceptance Criteria

1. THE Chatbot_Widget SHALL render a floating circular button (diameter: 56 px) fixed to the bottom-right corner of every page at a z-index of 400 or greater, keeping it above all other page content (nav: z-index 200, dropdowns: z-index 300).
2. WHEN the Visitor clicks the chat button, THE Chatbot_Widget SHALL expand to display a chat panel at least 320 px wide and 480 px tall (on desktop) containing a conversation history area, a text input field, and a send button.
3. WHEN the chat panel is open and the Visitor clicks the close control, THE Chatbot_Widget SHALL collapse back to the floating button without clearing conversation history.
4. THE Chatbot_Widget SHALL use only the site's existing CSS variables (`--pink`, `--gunmetal`, `--deep-orange`, `--orange`, `--cream`, `--white`, `--light-pink`, `--light-orange`) for all color values, and the site's defined font stack (`system-ui, -apple-system, sans-serif`) for all text.
5. THE Chatbot_Widget SHALL be implemented entirely within `index.html` using plain HTML, CSS, and JavaScript with no external build tools or npm packages.
6. WHEN the viewport width is 768 px or less, THE Chatbot_Widget SHALL expand to occupy 100% of the viewport width and at least 60% of the viewport height.
7. WHEN the Visitor presses Enter while the text input is focused, THE Chatbot_Widget SHALL submit the question; WHEN the Visitor presses Shift+Enter, THE Chatbot_Widget SHALL insert a newline. THE text input SHALL accept a maximum of 500 characters.

---

### Requirement 2: Knowledge Base Schema

**User Story:** As a site maintainer, I want pet care articles stored in a structured Google Sheets tab, so that the chatbot can reliably retrieve and search relevant content.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL be a worksheet named `pet_care_kb` in the existing Google Sheet (`1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80`).
2. THE Knowledge_Base SHALL contain exactly these columns in order: `articleId`, `title`, `url`, `source`, `category`, `summary`, `keywords`, `fullText`, `fetchedAt`.
3. THE Knowledge_Base SHALL enforce that `articleId` is unique per row; the KB_Sync_Script SHALL skip any article whose `articleId` already exists in the sheet.
4. THE Knowledge_Base SHALL store the `keywords` field as a comma-separated list of at most 20 lowercase terms extracted from the article title and summary.
5. THE Knowledge_Base SHALL store the `fullText` field as a plain-text excerpt (no HTML markup) truncated at the last complete word at or within 1,500 characters per article.
6. THE Knowledge_Base SHALL store the `fetchedAt` field as an ISO 8601 UTC timestamp (e.g., `2024-06-15T02:00:00Z`) representing the moment the article was written to the sheet.
7. WHEN the KB_Sync_Script runs and the Knowledge_Base contains more than 500 rows of article data (excluding the header row), THE KB_Sync_Script SHALL delete the rows with the lowest `fetchedAt` values until the total is at or below 500.

---

### Requirement 3: Knowledge Base Sync Script

**User Story:** As a site maintainer, I want a scheduled script that automatically fetches pet care articles and updates the knowledge base, so that the chatbot always has fresh and accurate content.

#### Acceptance Criteria

1. THE KB_Sync_Script SHALL be located at `cron/faq_kb_sync.py` and follow the same structure and credential-loading pattern as `cron/petfinder_sync.py`.
2. THE KB_Sync_Script SHALL fetch pet care articles from at least 3 publicly accessible sources (e.g., ASPCA, PetMD, AKC) using their publicly accessible RSS feeds or sitemaps.
3. WHEN fetching each source, THE KB_Sync_Script SHALL extract: article title, canonical URL, source name, category (one of: "nutrition", "training", "health", "behavior", "general"), a summary of at most 300 characters, a comma-separated keyword list of at most 10 lowercase terms, and a plain-text full-text excerpt (HTML tags stripped) of at most 1,500 characters.
4. IF a network error occurs or the HTTP response status code is 400 or greater during article fetching, THEN THE KB_Sync_Script SHALL log the error with the source name and URL, skip that article, and continue processing remaining sources.
5. THE KB_Sync_Script SHALL authenticate with the Google Sheets API using the same service account credential pattern as `cron/petfinder_sync.py`.
6. THE KB_Sync_Script SHALL support a `--dry-run` flag that prints fetched articles to stdout without writing to the Knowledge_Base.
7. THE KB_Sync_Script SHALL run as a scheduled GitHub Actions workflow at a configurable cron schedule (default: weekly on Sunday at 2:00 AM UTC).
8. WHEN the KB_Sync_Script completes, THE KB_Sync_Script SHALL print a summary including: number of articles fetched per source, number of new articles written (deduplicated by canonical URL), number of duplicates skipped, and total elapsed time in seconds.

---

### Requirement 4: Knowledge Base Retrieval

**User Story:** As a Visitor, I want the chatbot to find the most relevant pet care articles for my question, so that the AI can give me an accurate, grounded answer.

#### Acceptance Criteria

1. WHEN a Visitor submits a question, THE Retriever SHALL fetch all rows from the Knowledge_Base via the gviz_Endpoint using the same URL pattern already used by the site for pet listings data.
2. WHEN scoring articles, THE Retriever SHALL tokenize the Visitor's question into lowercase terms (excluding common English stop-words such as "the", "a", "is", "what") and score each Knowledge_Base_Article by the count of matching terms found in that article's `keywords`, `title`, and `summary` fields; each field match counts as one point.
3. THE Retriever SHALL return up to 5 Knowledge_Base_Articles ranked by descending similarity score; WHEN fewer than 5 articles exist in the Knowledge_Base, THE Retriever SHALL return all available articles. WHEN two articles share the same score, THE Retriever SHALL break the tie by sorting alphabetically by `title` (ascending).
4. IF no Knowledge_Base_Article scores above zero for a given query, THEN THE Retriever SHALL return an empty result set and the Chatbot_Widget SHALL display the fallback message: "I couldn't find relevant articles for that question. Try rephrasing or ask about a different pet care topic."
5. THE Retriever SHALL complete the fetch-and-rank operation within 5 seconds when the Knowledge_Base contains 500 or fewer rows (total response size ≤ 2 MB).
6. IF the fetch-and-rank operation exceeds 5 seconds, THEN THE Retriever SHALL abort the operation and surface a timeout error message to the Chatbot_Widget.
7. IF the gviz_Endpoint returns an HTTP response with status code 400 or greater, THEN THE Retriever SHALL surface an error message to the Chatbot_Widget without retrying.
8. THE Retriever SHALL cache the Knowledge_Base rows in browser memory for the duration of the page session so that subsequent queries within the same session do not re-fetch the sheet.

---

### Requirement 5: AI-Synthesized Response

**User Story:** As a Visitor, I want the chatbot to give me a clear, concise answer to my pet care question, so that I get helpful information without having to read multiple articles.

#### Acceptance Criteria

1. WHEN the Retriever returns one or more Knowledge_Base_Articles, THE AI_Responder SHALL send the Visitor's original question and the `summary` and `fullText` fields of up to 5 retrieved articles (all available if fewer than 5 were returned) as context to the AI_API.
2. THE AI_Responder SHALL construct a system prompt that instructs the AI_API to: answer only pet care questions, cite only the provided context articles, respond in 3 sentences or fewer, and respond with a refusal message indicating the question is outside the pet care domain when the question is not pet care related.
3. WHEN the AI_API returns a response to a pet care question, THE Chatbot_Widget SHALL display the synthesized answer followed by a "Sources" section listing the `title` and `url` of all articles sent as context to the AI_API.
4. IF the AI_API call fails with an HTTP error or network error, THEN THE Chatbot_Widget SHALL display the user-facing error message "I'm having trouble connecting right now — please try again shortly." without exposing API keys or raw error details.
5. THE AI_Responder SHALL read the AI_API key from a JavaScript configuration variable (`window.CHATBOT_CONFIG.apiKey`) so that the key is not hard-coded in the source file.
6. THE AI_Responder SHALL use the Google Gemini API (`gemini-1.5-flash` model, free tier) as the primary AI_API; WHERE `window.CHATBOT_CONFIG.apiKey` is absent, null, or an empty string, THE AI_Responder SHALL fall back to the OpenAI Chat Completions API (`gpt-3.5-turbo` model) using `window.CHATBOT_CONFIG.openaiApiKey`.
7. WHEN the AI_API returns an out-of-domain refusal message, THE Chatbot_Widget SHALL display only the refusal message text and SHALL NOT render a "Sources" section.

---

### Requirement 6: Conversation History

**User Story:** As a Visitor, I want to see the full history of my conversation with the chatbot during my session, so that I can refer back to earlier answers.

#### Acceptance Criteria

1. THE Chatbot_Widget SHALL display all messages exchanged in the current session in chronological order, with Visitor messages visually distinguished from chatbot responses using different background colors drawn from the site's CSS variables (`--light-pink` for Visitor messages, `--white` for chatbot responses).
2. WHILE the AI_Responder is awaiting a response from the AI_API, THE Chatbot_Widget SHALL display a typing indicator (animated ellipsis or equivalent) in the conversation area.
3. THE Chatbot_Widget SHALL retain conversation history in JavaScript memory for the duration of the browser session; WHEN the Visitor refreshes or navigates away from the page, THE Chatbot_Widget SHALL start a new empty conversation.
4. WHEN the conversation area contains more messages than are visible in the panel, THE Chatbot_Widget SHALL automatically scroll to the most recent message after each new message is appended.
5. THE Chatbot_Widget SHALL display the welcome message "Hi! I'm Furever's pet care assistant. Ask me anything about caring for your new pet! 🐾" as the first message in the conversation area when the chat panel is opened for the first time in a session.

---

### Requirement 7: Input Handling and Submission

**User Story:** As a Visitor, I want a smooth and accessible way to type and submit questions, so that interacting with the chatbot feels natural and responsive.

#### Acceptance Criteria

1. WHEN the Visitor presses Enter (without Shift) while the text input field is focused, THE Chatbot_Widget SHALL submit the question; WHEN the Visitor presses Shift+Enter, THE Chatbot_Widget SHALL insert a newline character into the input field without submitting.
2. WHEN a question is submitted, THE Chatbot_Widget SHALL clear the text input field and disable both the input field and send button until the AI_Responder returns a response, an error, or 30 seconds elapse (whichever comes first), after which both controls SHALL be re-enabled.
3. IF the Visitor submits an empty or whitespace-only message, THEN THE Chatbot_Widget SHALL not submit the query and SHALL keep focus on the text input field.
4. THE Chatbot_Widget text input field SHALL have `aria-label="Ask a pet care question"` and the send button SHALL have `aria-label="Send question"`.
5. WHEN the chat panel opens, THE Chatbot_Widget SHALL move focus to the text input field.
6. THE text input field SHALL enforce a maximum of 500 characters; WHEN the Visitor has typed 450 or more characters, THE Chatbot_Widget SHALL display a visible character counter showing the remaining characters.

---

### Requirement 8: GitHub Actions Workflow for KB Sync

**User Story:** As a site maintainer, I want the knowledge base to refresh automatically on a schedule via GitHub Actions, so that the chatbot's content stays current without manual effort.

#### Acceptance Criteria

1. THE faq_kb_sync workflow file at `.github/workflows/faq_kb_sync.yml` SHALL define a job that: checks out the repository, sets up Python 3.11, installs dependencies from `cron/requirements.txt`, and runs `python cron/faq_kb_sync.py`.
2. THE faq_kb_sync workflow SHALL run on the schedule `0 2 * * 0` (Sunday 2:00 AM UTC) and SHALL support manual dispatch via `workflow_dispatch`.
3. THE faq_kb_sync workflow SHALL inject the Google Sheets service account credentials into the script via the environment variable `GOOGLE_CREDENTIALS_JSON`, sourced from the same-named GitHub Actions secret used by the existing `nightly_sync.yml` workflow.
4. THE faq_kb_sync workflow SHALL inject the sheet ID into the script via the environment variable `SHEET_ID`, sourced from the same-named GitHub Actions secret used by the existing `nightly_sync.yml` workflow.
5. IF the KB_Sync_Script exits with a non-zero status code, THEN the faq_kb_sync workflow SHALL mark the workflow run as failed so that the site maintainer is notified via GitHub's default failure notification.
6. THE faq_kb_sync workflow job SHALL have a `timeout-minutes: 10` setting to prevent runaway executions.
