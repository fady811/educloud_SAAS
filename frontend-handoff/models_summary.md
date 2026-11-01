# EduCloud LMS — Models Summary
Source: code only (apps/*/models.py, apps/*/serializers.py)
READ-ONLY snapshot

## Base classes

All models extend `TimeStampedModel` (adds `created_at`, `updated_at`).
Tenant-scoped models extend `TenantModel` (adds `workspace` FK, composite indexes).

---

## accounts.User

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField (PK) | no | — |
| email | EmailField unique | yes | — |
| phone | CharField(20) unique | yes | — |
| first_name | CharField(150) | no (blank) | — |
| last_name | CharField(150) | no (blank) | — |
| is_super_admin | BooleanField | no | — |
| email_verified_at | DateTimeField | yes | — |
| phone_verified_at | DateTimeField | yes | — |
| deleted_at | DateTimeField | yes | — |
| is_active | BooleanField | no | — |
| created_at | DateTimeField | no | — |
| updated_at | DateTimeField | no | — |

Serializer (UserSerializer) exposes: `id, email, phone, first_name, last_name, is_verified, created_at`
- `is_verified` is a @property: True if email_verified_at OR phone_verified_at is set
- `password` is NEVER serialized
- WRITABLE: email, phone, first_name, last_name (via UserRegistrationSerializer)
- READ-ONLY: id, is_verified, created_at

Constraint: email OR phone must be non-null (DB-level check constraint).

---

## accounts.UserSession

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| user_id | FK accounts.User | no | — |
| workspace_id | FK workspaces.Workspace | yes | — |
| session_key_hash | CharField(64) unique | no | — |
| device_info | JSONField | no | {} default |
| ip_address | GenericIPAddressField | yes | — |
| revoked_at | DateTimeField | yes | — |
| last_active_at | DateTimeField auto_now | no | — |
| created_at / updated_at | DateTimeField | no | — |

Serializer exposes: `id, device_info, ip_address, created_at, last_active_at, is_current`
- `is_current` = computed: True if session_key_hash matches sha256(current session key)
- `session_key_hash` is NEVER serialized

---

## workspaces.Workspace

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| subdomain | CharField(32) unique | yes | — |
| status | CharField(30) | no | WorkspaceStatus |
| deactivation_cause | CharField(20) | yes | DeactivationCause |
| settings_json | JSONField | no | {} default |
| grace_period_days | SmallIntegerField | no | — |
| deleted_at | DateTimeField | yes | — |
| purge_after | DateTimeField | yes | — |
| limit_policy | JSONField | no | {} default |
| retention_days | IntegerField | no | 90 default |

Serializer (WorkspaceSerializer) exposes: `id, subdomain, display_name, status, grace_period_days, settings_json, created_at`
- `display_name` = computed from settings_json["display_name"]
- settings_json contains branding: display_name, logo_file_id, theme, primary_color, landing_text, description, meta
- WRITABLE via WorkspaceBrandingSerializer: display_name, logo_url, primary_color, secondary_color

---

## workspaces.WorkspaceMembership

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| user_id | FK accounts.User | no | — |
| workspace_id | FK workspaces.Workspace | no | — |
| role | CharField(20) | no | Role |
| is_owner | BooleanField | no | — |
| billing_anchor_date | DateField | yes | — |

Exposed in MeWorkspacesView as inline dict: `workspace_id, subdomain, role, is_owner, status`
Exposed in WorkspaceMembershipSerializer: `id, user_id, workspace_id, role, is_owner, joined_at`
NOTE: `joined_at` referenced in serializer but field is `created_at` on model — source field unclear.

---

## files.StoredFile (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| key | CharField(512) unique | no | — |
| original_name | CharField(255) | no | — |
| content_type | CharField(100) | no | — |
| size_bytes | BigIntegerField | no | — |
| category | CharField(30) | no | FileCategory |
| scan_status | CharField(20) | no | ScanStatus |
| scan_result | JSONField | yes | — |
| uploaded_by_id | BigIntegerField | yes | — |
| is_public | BooleanField | no | False default |
| deleted_at | DateTimeField | yes | — |

Serializer exposes: `id, key, original_name, content_type, size_bytes, category, scan_status, is_public, created_at, url`
- `url` = computed: presigned URL via storage service; can be null on error
- `scan_result` is NEVER serialized
- WRITABLE via UploadRequestSerializer: filename, content_type, category, size_bytes (returns upload presign data, not the file record directly)

---

## content.Subject (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| name | CharField(150) | no | — |
| grade_level | CharField(20) | no (blank) | GradeLevel |
| color | CharField(7) | no (blank) | — |
| archived_at | DateTimeField | yes | — |

Serializer exposes: `id, name, grade_level, color, archived_at`

---

## content.Course (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| subject_id | FK content.Subject | yes | — |
| title | CharField(255) | no | — |
| description | TextField | no (blank) | — |
| visibility | CharField(20) | no | Visibility |
| pricing_type | CharField(20) | no | PricingType |
| price | DecimalField(12,2) | yes | — |
| cover_image_id | BigIntegerField | yes | — |
| archived_at | DateTimeField | yes | — |

Serializer exposes: `id, title, description, visibility, pricing_type, price, subject_id, archived_at, created_at`
- `price` serialized as decimal string (COERCE_DECIMAL_TO_STRING=True)
- NOTE: CourseWriteSerializer uses default "PRIVATE" for visibility — DIFFERS from model default "DRAFT"

---

## content.Lesson (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| parent_type | CharField(20) | no | LessonParentType |
| parent_id | BigIntegerField | no | — |
| title | CharField(255) | no | — |
| order | PositiveIntegerField | no | 0 default |
| is_free_preview | BooleanField | no | False default |
| archived_at | DateTimeField | yes | — |

Serializer exposes: `id, title, parent_type, parent_id, order, is_free_preview, archived_at`

---

## groups.Group (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| name | CharField(150) | no | — |
| subject_id | BigIntegerField | yes | — |
| teacher_id | BigIntegerField | yes | — |
| status | CharField(20) | no | GroupStatus |
| max_students | PositiveIntegerField | yes | — |
| color | CharField(7) | no (blank) | — |
| description | TextField | no (blank) | — |
| archived_at | DateTimeField | yes | — |

Serializer exposes: `id, name, subject_id, teacher_id, status, max_students, color, description, archived_at, created_at`

---

## groups.Session (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| group_id | FK groups.Group | no | — |
| title | CharField(255) | no (blank) | — |
| scheduled_at | DateTimeField | no | — |
| duration_minutes | PositiveIntegerField | no | 60 default |
| notes | TextField | no (blank) | — |
| cancelled_at | DateTimeField | yes | — |

Serializer exposes: `id, group_id, title, scheduled_at, duration_minutes, notes, cancelled_at`

---

## groups.AttendanceRecord (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| session_id | FK groups.Session | no | — |
| student_id | BigIntegerField | no | — |
| status | CharField(20) | no | AttendanceStatus |
| notes | CharField(500) | no (blank) | — |
| recorded_by_id | BigIntegerField | yes | — |

Serializer exposes: `id, student_id, status, notes`

---

## enrollment.Enrollment (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| workspace_id | FK | no | — |
| student_id | BigIntegerField | no | — |
| enrollable_type | CharField(20) | no | EnrollableType |
| enrollable_id | BigIntegerField | no | — |
| status | CharField(20) | no | EnrollmentStatus |
| enrolled_at | DateTimeField auto_now_add | no | — |
| expires_at | DateTimeField | yes | — |
| unenrolled_at | DateTimeField | yes | — |
| enrolled_by_id | BigIntegerField | yes | — |
| notes | TextField | no (blank) | — |

Serializer: not read — UNKNOWN exact fields (apps/enrollment/serializers.py not read)

---

## billing.Package (TimeStampedModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| name | CharField(100) | no | — |
| slug | SlugField(60) unique | no | — |
| description | TextField | no (blank) | — |
| price_egp | DecimalField(12,2) | no | — |
| duration_months | SmallIntegerField | no | 1 default |
| max_students | IntegerField | yes | — |
| storage_gb | DecimalField(8,2) | yes | — |
| max_subjects_courses | IntegerField | yes | — |
| max_groups | IntegerField | yes | — |
| max_team_members | IntegerField | yes | — |
| is_active | BooleanField | no | True default |
| display_order | SmallIntegerField | no | 0 default |

Serializer (PackageSerializer) exposes: `id, name, slug, description, price_egp, duration_months, max_students, storage_gb, max_subjects_courses, max_groups, max_team_members, display_order`
- `price_egp`, `storage_gb` serialized as decimal strings

---

## billing.Subscription (TenantModel)

Serializer exposes: `id, package, status, starts_at, ends_at, entitlement_snapshot, proration_credit_egp`

---

## billing.SubscriptionPayment (TenantModel)

Serializer exposes: `id, subscription, kind, amount_egp, status, proof_file_id, submitted_at, reviewed_at, rejection_reason`
NOTE: model field is `rejection_reason` but serializer uses same. `notes` field exists in model but serializer uses `rejection_reason`.

---

## payments.StudentPayment (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| student_id | FK accounts.User | no | — |
| payment_model | CharField(20) | no | StudentPaymentModel |
| amount_egp | DecimalField(12,2) | no | — |
| status | CharField(20) | no | StudentPaymentStatus |
| source | CharField(20) | no | PaymentSource |
| payment_method_id | FK WorkspacePaymentMethod | yes | — |
| proof_file_id | BigIntegerField | yes | — |
| submitted_at | DateTimeField | yes | — |
| reviewed_at | DateTimeField | yes | — |
| reviewed_by_id | BigIntegerField | yes | — |
| notes | TextField | no (blank) | — |
| enrollable_type | CharField(20) | no (blank) | — |
| enrollable_id | BigIntegerField | yes | — |
| period_start | DateField | yes | — |
| period_end | DateField | yes | — |
| status_link | CharField(20) | no (blank) | PaymentStatusLink |

Serializer: UNKNOWN exact fields (apps/payments/serializers.py not read)

---

## assessments.Exam (TenantModel)

Serializer exposes: `id, lesson, title, instructions, duration_minutes, pass_score, max_attempts, shuffle_questions, status, available_from, available_until`
- `correct_answer` in Question is NEVER serialized to students (security)

---

## communication.Announcement (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| id | BigAutoField | no | — |
| author_id | FK accounts.User | no | — |
| scope | CharField(20) | no | AnnouncementScope |
| target_id | BigIntegerField | yes | — |
| title | CharField(200) | no | — |
| body_html | TextField | no | — |
| is_pinned | BooleanField | no | False default |
| published_at | DateTimeField | yes | — |

- `body_html` is sanitized (sanitize_html) on save
- Serializer: UNKNOWN exact fields (apps/communication/serializers.py not read)

---

## communication.Message (TenantModel)

ETag-based polling: MessageViewSet.list() computes MD5 of [id, ...] as ETag; returns 304 if If-None-Match matches.

---

## notifications.Notification (TimeStampedModel — NOT TenantModel, but has workspace FK)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| user_id | FK accounts.User | no | — |
| workspace_id | FK Workspace | yes | — |
| category | CharField(50) | no | NotificationCategory |
| payload | JSONField | no | {} default |
| read_at | DateTimeField | yes | — |

---

## support.SupportTicket (TenantModel)

| Field | Type | Nullable | Choices |
|---|---|---|---|
| submitted_by_id | BigIntegerField | no | — |
| category | CharField(40) | no | TicketCategory |
| subject | CharField(255) | no | — |
| body | TextField | no | — |
| status | CharField(20) | no | TicketStatus |
| assigned_to_id | BigIntegerField | yes | — |
| resolved_at | DateTimeField | yes | — |

---

## adminconsole (no dedicated models — uses models from workspaces, accounts, billing)

WorkspaceListView returns: `id, subdomain, status, created_at` (inline dict, no serializer)
UserListView returns: `id, email, phone, full_name, date_joined` (NOTE: uses `full_name` and `date_joined` — these fields are NOT on the User model as read. DIFFERS: `full_name` is not a model field seen; `display_name` is a property. `date_joined` is not defined — likely from AbstractBaseUser.)
PackageListCreateView returns: `id, slug, name, price_egp, duration_months`
