# Contributing to LiteLLM Control Plane

Thank you for contributing! To maintain consistency, security, and stability in our AI infrastructure control layer, we enforce a strict set of development guidelines.

## 1. Development Discipline

*   **Spec-Before-Implementation**: If you want to modify or add a module, ensure its specification exists in `docs/modules/` or that the API endpoint is documented in `docs/api-contract.md`. If not, create a proposal first.
*   **English Only**: All code comments, docstrings, schema names, commit messages, and documentation must be written in **English**.
*   **Aesthetics and Design**: If you contribute to user-facing or console outputs, prioritize clean, readable typography, and structured output.

---

## 2. Style Guide & Tooling

*   **Formatter**: We use `black` and `isort`. Run them before submitting changes:
    ```bash
    black src/ tests/
    isort src/ tests/
    ```
*   **Type Checking**: We use `mypy`. Ensure your changes are typed:
    ```bash
    mypy src/
    ```
*   **Testing**: Run unit and integration tests:
    ```bash
    pytest tests/
    ```

---

## 3. Pull Request Checklist

When submitting a Pull Request, verify that you have:
1.  Updated corresponding specs under `docs/` (e.g. data models, API contract, or module documentation).
2.  Ensured all tests pass and coverage is maintained.
3.  Provided a clear, concise PR summary.
4.  Ensured no secrets (such as API keys or Doppler tokens) are committed or output in test/debug logs.
