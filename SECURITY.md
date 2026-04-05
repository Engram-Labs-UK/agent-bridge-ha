# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please email security@engramlabs.co.uk with:

- Type of vulnerability
- Full paths of affected source files
- Step-by-step reproduction instructions
- Impact assessment

## Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Resolution target**: Within 30 days

## Security Measures

- Bearer tokens stored in HA's encrypted config entry storage
- Tokens never logged or exposed in diagnostics
- Tool execution validates entity IDs against HA's exposure list
- SSL/TLS supported for bridge connections
