# AI Development Rules

## General Principles

- Always write production-ready code.
- Prioritize readability over cleverness.
- Follow SOLID principles.
- Follow DRY (Don't Repeat Yourself).
- Follow KISS (Keep It Simple).
- Follow YAGNI (You Aren't Gonna Need It).
- Every function should have a single responsibility.
- Every file should have one clear purpose.
- Never leave TODOs or unfinished implementations.
- Never generate mock implementations unless explicitly requested.
- Never duplicate logic.

---

# Project Structure

- Keep a clean folder structure.
- Group files by feature rather than file type whenever possible.
- Separate:
  - API
  - Business Logic
  - Database
  - UI
  - Utilities
  - Types
  - Config

Example:

src/
    features/
        auth/
        users/
        products/
    shared/
    database/
    config/
    utils/

---

# Naming

Use meaningful names.

Good:

getUserById()
createOrder()
calculateTotal()

Bad:

doStuff()
temp()
aaa()
data2()

Avoid abbreviations unless universally accepted.

---

# Functions

- One function = one responsibility.
- Maximum 30-40 lines whenever possible.
- Maximum 3-4 parameters.
- Extract repeated code.
- Return early instead of nested if statements.
- Prefer pure functions.

Example:

Bad

if(user){
    if(user.active){
        ...
    }
}

Good

if(!user) return
if(!user.active) return

...

---

# Classes

- Keep classes small.
- One responsibility only.
- Prefer composition over inheritance.

---

# Comments

Do not write unnecessary comments.

Bad

// increment i
i++

Good code should explain itself.

Only comment:

- business rules
- complex algorithms
- important decisions

---

# Error Handling

Never ignore errors.

Always

- validate inputs
- throw meaningful exceptions
- log unexpected errors
- return user-friendly messages

Never

catch(e){}

---

# Logging

Use structured logging.

Log:

- errors
- warnings
- important events

Never log:

- passwords
- tokens
- secrets
- personal information

---

# Security

Always

- validate input
- sanitize input
- hash passwords
- use parameterized queries
- use environment variables
- protect sensitive endpoints

Never

- hardcode secrets
- expose stack traces
- trust client input

---

# Database

- Normalize schema.
- Use indexes when necessary.
- Avoid N+1 queries.
- Keep transactions atomic.
- Use migrations.
- Never write raw SQL if ORM already provides a clean solution.

---

# API

REST rules:

GET

- no side effects

POST

- create

PUT

- replace

PATCH

- partial update

DELETE

- remove

Always

- proper status codes
- validation
- pagination
- filtering
- sorting

Response format:

{
    "success": true,
    "data": {},
    "message": "",
    "meta": {}
}

---

# Validation

Validate everything.

Never trust:

- request body
- query params
- headers
- uploaded files

---

# Configuration

Keep configuration outside the code.

Use:

.env

Never hardcode:

- URLs
- passwords
- API keys
- secrets

---

# Dependencies

Only install dependencies when necessary.

Prefer native language features.

Remove unused packages.

---

# Performance

Avoid premature optimization.

But always:

- cache expensive operations
- lazy load where appropriate
- avoid unnecessary re-renders
- minimize database calls

---

# Testing

Every important business logic should be testable.

Write:

- Unit tests
- Integration tests when needed

Avoid tightly coupled code.

---

# Code Style

Always use consistent formatting.

Prefer:

- descriptive variable names
- small files
- explicit return types
- immutable data when possible

Avoid:

- magic numbers
- deeply nested code
- duplicated logic

---

# Architecture

Use layered architecture.

Controller

↓

Service

↓

Repository

↓

Database

Never access database directly from controllers.

Business logic belongs inside services.

---

# Git

Write meaningful commits.

Good:

feat(auth): add refresh token support

fix(products): handle empty category

refactor(user): simplify validation

Bad:

update

fix

changes

---

# Documentation

Document:

- public APIs
- environment variables
- setup process
- architecture decisions

README should always be up to date.

---

# Before Finishing

Before completing any task always verify:

- Code compiles.
- No lint errors.
- No type errors.
- No duplicated logic.
- No unused imports.
- No dead code.
- Error handling exists.
- Validation exists.
- Naming is clear.
- Folder structure remains clean.
- Code follows project conventions.
- Production ready.

---

# AI Behavior

When generating code:

- Always analyze the existing project structure first.
- Follow existing architecture unless it is clearly incorrect.
- Never rewrite unrelated files.
- Never introduce breaking changes unless requested.
- Minimize code changes.
- Explain architectural decisions when necessary.
- Produce complete implementations, not placeholders.

---

# CI/CD & Linting Verification

Before completing any task that involves modifying Python code, you MUST:
1. Run `python3 -m ruff check . --fix` locally to automatically format the code and catch any strict linting violations (such as trailing whitespace).
2. Never push unlinted code.

After pushing code to the remote repository, you MUST:
1. Check the GitHub Actions CI/CD pipeline status (using `gh run list` and `gh run view`) to ensure the pipeline passes successfully.
2. Only consider the task complete if the pipeline is green.

- Before executing commands like `git push`, `gh workflow run`, or running PyPI release scripts, you MUST ask the user for explicit permission first. Do not deploy or push changes autonomously without confirmation.
