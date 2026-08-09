# Contributing to GitPilot

Thank you for considering contributing to GitPilot!

## Development Workflow

1. Clone repository:
   ```bash
   git clone https://github.com/your-username/gitpilot-multi-agent.git
   cd gitpilot-multi-agent
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   make install
   ```

3. Run quality checks:
   ```bash
   make lint
   make test
   make demo
   ```

## Code Guidelines

- Python 3.12+ features (type hints, match statements, generic syntax).
- Follow PEP 8 via `ruff`.
- Maintain test coverage for any new features or agent nodes.
- Ensure all file operations use `security.is_path_safe()`.
- Never commit secrets or hard-code credentials.
