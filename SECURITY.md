# Security Policy

## 1. Safety Goals

The LiteLLM Control Plane coordinates upstream API credentials and routes traffic. Consequently, security is a core project requirement.
*   **Doppler Secrets**: Secrets must never be stored in the database or logged in application logs.
*   **Least Privilege**: All access tokens (LiteLLM Admin keys, Doppler Service Tokens, DB credentials) must be scoped to the minimum required permissions.

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability in this project, please do **not** open a public issue. Instead, report it privately.

*   **Email**: Send reports to `security@yourcompany.com` (or the repository administrator).
*   **Response Window**: We will acknowledge receipt of your report within 48 hours and provide a proposed timeline for mitigation.

---

## 3. Prohibited Practices

To protect secrets and environments:
*   Never hardcode credentials or test API keys.
*   Always mask or sanitize sensitive credentials in exceptions and error traces.
*   Do not log authorization headers or JWT payloads in HTTP requests.
