# Open Questions

## OQ-1: Login Throttle — DB-backed Counter

**Current state:** The login throttle (`apps/accounts/services/login_throttle.py`) fails closed
on cache errors using an in-process dict. This is correct behavior but has two limitations:

1. **Not shared across workers.** Each Gunicorn/uWSGI worker has its own counter. An attacker
   making requests that round-robin across workers can make up to `MAX_ATTEMPTS × worker_count`
   attempts before being blocked.

2. **Does not survive restarts.** A worker restart resets the counter for that process.

**Ideal fix:** A `LoginFailure` model with a DB-backed counter and a periodic cleanup task.
This requires:
- A new migration (needs explicit approval per project scope constraints)
- A management command or Celery task for cleanup

**Action required:** Approve migration for `LoginFailure` model before implementing.

---

## OQ-2: Visibility Enum Import in Serializers

`CourseWriteSerializer` uses `ChoiceField(choices=["DRAFT","PUBLISHED","ARCHIVED"])` with inline
string literals rather than importing `Visibility` from the model enums. This avoids a circular
import at the cost of coupling to string values. Once the team confirms the import path for
`Visibility`, replace the inline list with `Visibility.choices`.

---

## OQ-3: `StudentPayment.notes` Field

`apps/payments/views.py` previously wrote `payment.notes = reason` in the `approve` and `reject`
actions but `StudentPayment` has no `notes` field. The `approve` action has been fixed by removing
the notes write. If internal notes on approved payments are needed, a `notes` field migration on
`StudentPayment` should be planned.
