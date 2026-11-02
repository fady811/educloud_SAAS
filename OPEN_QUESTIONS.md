# Open Questions

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
