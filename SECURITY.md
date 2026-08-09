# Security Policy & Untrusted Input Handling

## Threat Model

GitPilot processes untrusted external data:
1. GitHub issue titles and descriptions.
2. Arbitrary target codebases and repository files.

These inputs may contain malicious instructions designed to alter agent behavior, extract secrets, or execute unauthorized code on the host system.

---

## Defensive Boundaries

### 1. Prompt Injection Defense
- **System / Data Boundary Separation**: Untrusted content (issue text, repo content) is strictly enclosed within `<user_data>` XML blocks.
- **Pattern Scanning**: Inputs are pre-screened for known prompt injection signatures (e.g., `ignore previous instructions`, `read ~/.ssh`, `eval()`).
- **No System Directive Override**: Agents process repository content as passive data, never as executable instructions.

### 2. Path & Workspace Security
- **Strict Boundary Check**: All file operations are checked via `is_path_safe()` to ensure they remain inside the dedicated workspace directory.
- **Forbidden Locations**: Access to `.git/`, `.ssh/`, `.gnupg/`, `/etc/`, and system files is blocked unconditionally.
- **Traversal Prevention**: Path normalization prevents `../` escape attempts.

### 3. Docker Sandboxing
- **Non-Privileged Execution**: Container sandbox runs with `--security-opt no-new-privileges`.
- **Resource Restrictions**: Memory limit (`512MB`), CPU limit (`1.0`), process limit (`100`).
- **Network Control**: Network access disabled (`--network=none`) during test runs.
- **Read-Only Mounts**: Host repository workspace is mounted read-only (`:ro`).
- **No Sensitive Mounts**: Never mounts Docker socket, SSH directory, or root filesystem.

### 4. GitHub Write Operations
- **DRY_RUN Default**: Write operations (`create_branch`, `create_pull_request`) default to `DRY_RUN=true`.
- **Explicit Flag**: Requires explicit `DRY_RUN=false` configuration and valid token to write to GitHub.
- **Secret Protection**: API tokens are read from environment variables and never logged or included in LLM prompts.

---

## Reporting Vulnerabilities

If you discover a security vulnerability in GitPilot, please report it via private channel rather than opening a public issue.
