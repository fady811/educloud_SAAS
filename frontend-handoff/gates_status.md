# EduCloud LMS — Acceptance Gates Status (§22.7)
Source: tests/ directory inspection; test suite COULD NOT RUN (PostgreSQL not available in container)
READ-ONLY snapshot

---

## Test suite cannot run in this container

PostgreSQL is not available at localhost:5432 in the handoff container.
All test status below is COULD NOT EXERCISE.

---

## Test files found

| File | Test methods |
|---|---|
| tests/test_audit.py | 33 |
| tests/test_e2e_api.py | 53 |
| tests/test_followup.py | 18 |
| tests/test_remediation.py | 34 |
| **Total** | **138** |

The summary from previous session confirms: **138/138 tests passing** when PostgreSQL is available.
(This was verified during the AuditLog/IdempotencyKey model registration fix task.)

---

## Gate coverage

| Gate | Status | Notes |
|---|---|---|
| Unit tests | COULD NOT EXERCISE | 138 tests exist; confirmed passing in prior session |
| Integration / E2E API (test_e2e_api.py) | COULD NOT EXERCISE | 53 tests |
| Isolation suite | UNKNOWN | No dedicated isolation test file found |
| Permission-matrix suite | UNKNOWN | No dedicated permission-matrix test file found |
| Concurrency suite | UNKNOWN | No dedicated concurrency test file found |
| Coverage | UNKNOWN | No coverage config file inspected |

---

## Last known good state (from prior session)

All 138 tests passed after the AuditLog/IdempotencyKey registration fix.
Test command used: `SECRET_KEY=test-key python manage.py test --settings=config.settings.test`

---

## How to run locally

```bash
cd educloud-backend
SECRET_KEY=test-key python manage.py test --settings=config.settings.test
```

Requires PostgreSQL at localhost:5432 (db: educloud, user: educloud, password: educloud).
