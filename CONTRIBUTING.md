# Contributing to Agent Bridge HA

## Reporting Issues

- Search existing issues before creating a new one
- Include clear reproduction steps for bugs
- Describe expected vs actual behaviour

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run tests and linting:
   ```bash
   python -m pytest tests/ -v
   ruff check custom_components/
   ruff format custom_components/
   ```
5. Commit with clear messages
6. Open a pull request

## Code Style

- Python 3.12+, async throughout
- Formatting and linting via `ruff`
- British English in comments and user-facing strings
- Follow HA custom component patterns (config flow, coordinator, entity platforms)

## Testing

All changes must include tests. Target 90% coverage. Mock the bridge API -- never hit a live bridge in tests.

```bash
python -m pytest tests/ -v --cov=custom_components/agent_bridge
```
