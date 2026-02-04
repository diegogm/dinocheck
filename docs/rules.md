# Rule Packs

Dinocheck includes rule packs for different languages and frameworks. All packs are enabled by default.

## Available Packs

| Pack | Description |
|------|-------------|
| **python** | Security, correctness, testing, and reliability rules for Python |
| **django** | ORM, transactions, DRF, migrations, and Celery task rules |
| **react** | Hooks, performance, security, patterns, and accessibility for JSX |
| **typescript** | Type safety, async patterns, and security for TS/JS |
| **css** | Performance, accessibility, maintainability, and compatibility for CSS |
| **docker** | Dockerfile security, build optimization, and runtime config |
| **docker-compose** | Compose security, networking, and reliability |
| **sh** | Shell script security, error handling, and portability |
| **vue** | Vue.js reactivity, templates, and XSS prevention |

## Pack Commands

```bash
# List all available packs
dino packs list

# Show details of a specific pack
dino packs info python

# Explain a specific rule
dino explain django/n-plus-one
```

## Python Pack

Rules for Python code quality, security, and testing.

**Categories:**

- **security** - SQL injection, command injection, insecure deserialization
- **correctness** - Mutable defaults, exception handling, iterator exhaustion
- **testing** - Over-mocking, missing assertions, test isolation
- **reliability** - Resource leaks, race conditions, error handling
- **maintainability** - Code complexity, naming, structure

## Django Pack

Rules for Django applications, ORM, and Django REST Framework.

**Categories:**

- **orm** - N+1 queries, bulk operations, queryset optimization
- **security** - Authorization, CSRF, SQL injection
- **drf** - Serializer validation, permission classes, pagination
- **migrations** - Data migrations, schema changes, rollbacks
- **tasks** - Celery task idempotency, retries, timeouts

## React Pack

Rules for React components in JSX files.

**Categories:**

- **hooks** - Exhaustive deps, conditional hooks, stale closures, naming conventions
- **performance** - Inline objects in JSX, missing keys, unnecessary re-renders, large components
- **security** - dangerouslySetInnerHTML, unsafe href, user input injection
- **patterns** - Prop drilling, direct state mutation, useEffect fetch cleanup, index as key
- **accessibility** - Missing alt text, click without keyboard support, missing form labels

## CSS Pack

Rules for CSS stylesheets.

**Categories:**

- **performance** - Universal selectors, inefficient selectors, layout thrashing
- **accessibility** - Color contrast, focus indicators, reduced motion
- **maintainability** - Specificity issues, magic numbers, redundant rules
- **compatibility** - Vendor prefixes, unsupported properties
- **best-practices** - Important overuse, shorthand consistency

## TypeScript Pack

Rules for TypeScript and JavaScript code.

**Categories:**

- **types** - Type safety, any abuse, missing generics
- **async** - Promise handling, race conditions, error propagation
- **security** - XSS, injection, unsafe operations
- **reliability** - Null checks, error handling, edge cases

## Docker Pack

Rules for Dockerfile best practices.

**Categories:**

- **security** - Running as root, secrets in images, vulnerable base images
- **build** - Layer optimization, caching, multi-stage builds
- **runtime** - Health checks, signal handling, resource limits

## Docker Compose Pack

Rules for Docker Compose configurations.

**Categories:**

- **security** - Privileged containers, exposed ports, secrets management
- **networking** - Network isolation, service discovery, port conflicts
- **reliability** - Restart policies, health checks, resource limits

## Shell Pack

Rules for shell scripts (bash, sh).

**Categories:**

- **security** - Command injection, unsafe variable expansion
- **reliability** - Error handling, exit codes, quoting
- **portability** - POSIX compliance, bashisms, cross-platform

## Vue Pack

Rules for Vue.js applications.

**Categories:**

- **reactivity** - Reactive pitfalls, computed vs methods, watchers
- **security** - XSS in templates, v-html usage, sanitization
- **templates** - Template best practices, slot usage, prop validation

## Excluding Packs

To exclude packs you don't need:

```yaml
# dino.yaml
exclude_packs:
  - vue
  - docker
  - docker-compose
```

## Disabling Specific Rules

To disable individual rules:

```yaml
# dino.yaml
disabled_rules:
  - python/broad-exception
  - django/n-plus-one
```
