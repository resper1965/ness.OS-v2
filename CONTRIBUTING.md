# Contributing to n.infraops

First off, thank you for considering contributing to **n.infraops**! It's people like you that make this AIOps platform such a great tool for managing infrastructure and security operations.

## 1. Code of Conduct
By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## 2. Getting Started
- Ensure you have Docker and Docker Compose installed.
- For backend development, Python 3.12+ is required.
- For frontend development, Node.js 20+ is required.

## 3. Development Workflow
1. **Fork** the repository and clone it locally.
2. **Branch** out from `main` using the following naming convention:
   - `feature/your-feature-name`
   - `bugfix/issue-number-description`
   - `hotfix/critical-bug`
3. **Commit** your changes following the [Conventional Commits](#4-commit-guidelines) standard.
4. **Push** your branch and open a **Pull Request (PR)** against the `main` branch.

## 4. Commit Guidelines
We use [Conventional Commits](https://www.conventionalcommits.org/). Your commit messages must follow this format:

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Allowed Types:**
- `feat`: A new feature (e.g., integrating a new RMM tool).
- `fix`: A bug fix.
- `docs`: Documentation only changes.
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc).
- `refactor`: A code change that neither fixes a bug nor adds a feature.
- `perf`: A code change that improves performance.
- `test`: Adding missing tests or correcting existing tests.
- `chore`: Changes to the build process or auxiliary tools.

## 5. Pull Requests
- Fill out the provided PR template.
- Ensure all tests and linting (`flake8`, `black`, `eslint`) pass via GitHub Actions before requesting a review.
- If your change affects the database schema, ensure migrations are included.

## 6. Architecture Decisions
Any significant change to the tech stack or infrastructure must be proposed via an Issue first. Check the [Constitution](.spec-kit/constitution.md) for current architectural boundaries.
