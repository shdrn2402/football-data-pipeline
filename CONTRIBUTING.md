## 1. Git Commit Convention for AI Agents

**Target Audience:** All AI Coding Agents and Human Developers working on this repository.

## Core Rules

1. **Language:** All commit messages MUST be written in **English**. No exceptions.
2. **Format:** You MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
3. **Structure:** `<type>[optional scope]: <description>`
4. **CI Skipping:** Commits that do not affect the pipeline's production logic (e.g., changes to TODO files, documentation, or other non-code files) MUST include the `[skip ci]` tag in the commit message to prevent unnecessary CI pipeline runs.

## Allowed Commit Types (Tags)

* **`feat:`** – A new feature or functionality (e.g., `feat: add matches data extraction from API-Football`).
* **`fix:`** – A bug fix (e.g., `fix: resolve rate limit handling in requests`).
* **`chore:`** – Maintenance tasks, project setup, dependency updates. Code changes that do not affect production logic (e.g., `chore: setup project folder structure and python virtual environment`).
* **`refactor:`** – Code changes that neither fix a bug nor add a feature, but improve code structure (e.g., `refactor: extract s3 upload logic to a separate function`).
* **`docs:`** – Documentation changes only (e.g., `docs: update setup instructions in README`).
* **`style:`** – Formatting, missing semi-colons, whitespace, etc. No logic changes.
* **`test:`** – Adding or modifying tests.

## Description Guidelines

* Write in the **imperative, present tense**: use "add" not "added" or "adds", use "fix" not "fixed".
* Do not capitalize the first letter of the description.
* Do not place a period (`.`) at the end of the description.

## Examples

* `chore: initialize ingest directory structure and .env template`
* `feat(terraform): configure aws s3 bucket and iam user`
* `fix(api): correct json parsing logic for teams endpoint`
* `docs: update TODO with databricks transformation task [skip ci]`

## 2. Issue Convention

* **Language:** English.
* **Title Format:** `<Type>: <Description>`
  * Prefix and description MUST start with a capital letter (Capital Case / Title Case)[cite: 4].
  * Common types: `Feature:`, `Fix:`, `Chore:`[cite: 4].
  * *Example:* `Feature: Implement Parent Orchestration Flow for Automated Data Ingestion`[cite: 4]
* **Body Requirements:**
  * Context / Description.
  * Task checklist (`- [ ]`).
  * Acceptance Criteria / Definition of Done (`- [ ]`).

---

## 3. Pull Request (PR) Convention

* **Language:** English.
* **Title Format:** `<Type>(<scope>): <Description>`
  * The type prefix and the description after the colon MUST start with a capital letter[cite: 4].
  * *Example:* `Feature(kestra): Implement data ingestion flow`[cite: 4]
* **Body Requirements:**
  * Must contain a brief summary of implemented changes.
  * Must link and automatically close the target issue using closing keywords (e.g., `Closes #<issue-id>`).
* **Lifecycle:** Merge via **Merge pull request** into `main`, then delete the remote feature branch.

## 4. Branch Naming Convention

All feature branches must start with a category prefix followed by a slash and a short descriptive name in **kebab-case**:

* `feature/<short-description>` – for new capabilities, flows, or pipelines (e.g., `feature/kestra-ingestion-flow`, `feature/kestra-parent-orchestrator`).
* `fix/<short-description>` – for bug fixes (e.g., `fix/rate-limit-retry`).
* `chore/<short-description>` – for repo maintenance, CI/CD, or dependency upgrades.

Rule: Always branch off the latest `main` branch.