"""Shared enums and TextChoices (§12.4.1)."""
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    TEACHER = "TEACHER", "Teacher"
    TEAM_MEMBER = "TEAM_MEMBER", "Team Member"
    STUDENT = "STUDENT", "Student"
    PARENT = "PARENT", "Parent"


class ActorType(models.TextChoices):
    USER = "USER", "User"
    SYSTEM = "SYSTEM", "System"
    ADMIN = "ADMIN", "Admin"


class WorkspaceStatus(models.TextChoices):
    SETUP = "SETUP", "Setup"
    PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
    ACTIVE = "ACTIVE", "Active"
    GRACE_PERIOD = "GRACE_PERIOD", "Grace Period"
    FROZEN = "FROZEN", "Frozen"
    DEACTIVATED = "DEACTIVATED", "Deactivated"
    DELETED = "DELETED", "Deleted"


class DeactivationCause(models.TextChoices):
    NON_PAYMENT = "NON_PAYMENT", "Non-Payment"
    ADMIN_ACTION = "ADMIN_ACTION", "Admin Action"


class GradeLevel(models.TextChoices):
    PRIMARY_1 = "PRIMARY_1", "Primary 1"
    PRIMARY_2 = "PRIMARY_2", "Primary 2"
    PRIMARY_3 = "PRIMARY_3", "Primary 3"
    PRIMARY_4 = "PRIMARY_4", "Primary 4"
    PRIMARY_5 = "PRIMARY_5", "Primary 5"
    PRIMARY_6 = "PRIMARY_6", "Primary 6"
    PREP_1 = "PREP_1", "Prep 1 (إعدادي)"
    PREP_2 = "PREP_2", "Prep 2"
    PREP_3 = "PREP_3", "Prep 3"
    SEC_1 = "SEC_1", "Secondary 1 (ثانوي)"
    SEC_2 = "SEC_2", "Secondary 2"
    SEC_3 = "SEC_3", "Secondary 3"
    OTHER = "OTHER", "Other"


class Visibility(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class PricingType(models.TextChoices):
    FREE = "FREE", "Free"
    ONE_TIME = "ONE_TIME", "One-Time"
    MONTHLY = "MONTHLY", "Monthly"


class EnrollableType(models.TextChoices):
    SUBJECT = "SUBJECT", "Subject"
    COURSE = "COURSE", "Course"


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"


class PaymentStatusLink(models.TextChoices):
    NOT_REQUIRED = "NOT_REQUIRED", "Not Required"
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    WAIVED = "WAIVED", "Waived"
    OVERDUE = "OVERDUE", "Overdue"


class LessonParentType(models.TextChoices):
    COURSE = "COURSE", "Course"
    WEEK = "WEEK", "Week"
    SECTION = "SECTION", "Section"


class LessonContentType(models.TextChoices):
    VIDEO = "VIDEO", "Video"
    PDF = "PDF", "PDF"
    TEXT = "TEXT", "Text"
    EXTERNAL_LINK = "EXTERNAL_LINK", "External Link"
    FILE_SET = "FILE_SET", "File Set"


class GroupStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    FULL = "FULL", "Full"
    ARCHIVED = "ARCHIVED", "Archived"


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    EXCUSED = "EXCUSED", "Excused"


class SubscriptionStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class SubPaymentKind(models.TextChoices):
    NEW_SUBSCRIPTION = "NEW_SUBSCRIPTION", "New Subscription"
    RENEWAL = "RENEWAL", "Renewal"
    UPGRADE = "UPGRADE", "Upgrade"
    ADDON = "ADDON", "Add-on"


class SubPaymentStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class AddonType(models.TextChoices):
    STUDENT_SLOTS = "STUDENT_SLOTS", "Student Slots"
    STORAGE_GB = "STORAGE_GB", "Storage GB"


class AddonStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class StudentPaymentModel(models.TextChoices):
    WORKSPACE_MONTHLY = "WORKSPACE_MONTHLY", "Workspace Monthly"
    COURSE_ONE_TIME = "COURSE_ONE_TIME", "Course One-Time"
    COURSE_MONTHLY = "COURSE_MONTHLY", "Course Monthly"


class StudentPaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
    OVERDUE = "OVERDUE", "Overdue"
    REJECTED = "REJECTED", "Rejected"
    DISPUTED = "DISPUTED", "Disputed"
    REFUNDED = "REFUNDED", "Refunded"


class PaymentSource(models.TextChoices):
    STUDENT_SUBMITTED = "STUDENT_SUBMITTED", "Student Submitted"
    TEACHER_DIRECT = "TEACHER_DIRECT", "Teacher Direct"


class PaymentMethod(models.TextChoices):
    VODAFONE_CASH = "VODAFONE_CASH", "Vodafone Cash"
    INSTAPAY = "INSTAPAY", "InstaPay"
    FAWRY = "FAWRY", "Fawry"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    CASH = "CASH", "Cash"
    OTHER = "OTHER", "Other"


class RefundStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    COMPLETED = "COMPLETED", "Completed"


class QuestionType(models.TextChoices):
    MCQ = "MCQ", "MCQ"
    TRUE_FALSE = "TRUE_FALSE", "True/False"
    SHORT_ANSWER = "SHORT_ANSWER", "Short Answer"
    ESSAY = "ESSAY", "Essay"


class ExamStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    CLOSED = "CLOSED", "Closed"


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    SUBMITTED = "SUBMITTED", "Submitted"
    GRADED = "GRADED", "Graded"


class AnnouncementScope(models.TextChoices):
    WORKSPACE = "WORKSPACE", "Workspace"
    SUBJECT = "SUBJECT", "Subject"
    COURSE = "COURSE", "Course"
    GROUP = "GROUP", "Group"


class ScanStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CLEAN = "CLEAN", "Clean"
    INFECTED = "INFECTED", "Infected"
    ERROR = "ERROR", "Error"
    SKIPPED = "SKIPPED", "Skipped"


class FileCategory(models.TextChoices):
    LESSON_VIDEO = "LESSON_VIDEO", "Lesson Video"
    LESSON_DOCUMENT = "LESSON_DOCUMENT", "Lesson Document"
    LESSON_ATTACHMENT = "LESSON_ATTACHMENT", "Lesson Attachment"
    ASSIGNMENT_SUBMISSION = "ASSIGNMENT_SUBMISSION", "Assignment Submission"
    PAYMENT_PROOF = "PAYMENT_PROOF", "Payment Proof"
    BRANDING_LOGO = "BRANDING_LOGO", "Branding Logo"
    ANNOUNCEMENT_ATTACHMENT = "ANNOUNCEMENT_ATTACHMENT", "Announcement Attachment"
    MESSAGE_ATTACHMENT = "MESSAGE_ATTACHMENT", "Message Attachment"


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class TicketCategory(models.TextChoices):
    BILLING = "BILLING", "Billing"
    TECHNICAL = "TECHNICAL", "Technical"
    ACCOUNT = "ACCOUNT", "Account"
    CONTENT = "CONTENT", "Content"
    OTHER = "OTHER", "Other"


class CustomDomainStatus(models.TextChoices):
    PENDING_DNS = "PENDING_DNS", "Pending DNS"
    VERIFYING = "VERIFYING", "Verifying"
    ACTIVE = "ACTIVE", "Active"
    FAILED = "FAILED", "Failed"
    DETACHED = "DETACHED", "Detached"


class NotificationCategory(models.TextChoices):
    NEW_ANNOUNCEMENT = "NEW_ANNOUNCEMENT", "New Announcement"
    EXAM_PUBLISHED = "EXAM_PUBLISHED", "Exam Published"
    GRADE_POSTED = "GRADE_POSTED", "Grade Posted"
    ASSIGNMENT_DUE = "ASSIGNMENT_DUE", "Assignment Due"
    PAYMENT_DUE_OR_OVERDUE = "PAYMENT_DUE_OR_OVERDUE", "Payment Due or Overdue"
    ENROLLMENT_CONFIRMED = "ENROLLMENT_CONFIRMED", "Enrollment Confirmed"
    GROUP_CHANGED = "GROUP_CHANGED", "Group Changed"
    SUBSCRIPTION_STATUS_CHANGED = "SUBSCRIPTION_STATUS_CHANGED", "Subscription Status Changed"
    SUPPORT_TICKET_UPDATE = "SUPPORT_TICKET_UPDATE", "Support Ticket Update"


class LimitKey(models.TextChoices):
    MAX_STUDENTS = "MAX_STUDENTS", "Max Students"
    MAX_SUBJECTS_COURSES = "MAX_SUBJECTS_COURSES", "Max Subjects/Courses"
    MAX_GROUPS = "MAX_GROUPS", "Max Groups"
    MAX_TEAM_MEMBERS = "MAX_TEAM_MEMBERS", "Max Team Members"
    STORAGE_GB = "STORAGE_GB", "Storage GB"


class LimitAction(models.TextChoices):
    WARN = "WARN", "Warn"
    BLOCK_NEW = "BLOCK_NEW", "Block New"
    FREEZE = "FREEZE", "Freeze"
    RESTRICT_FEATURE = "RESTRICT_FEATURE", "Restrict Feature"
    ALLOW_GRACE = "ALLOW_GRACE", "Allow Grace"


class ErrorCode(models.TextChoices):
    # Auth
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS", "Invalid credentials"
    ACCOUNT_NOT_VERIFIED = "ACCOUNT_NOT_VERIFIED", "Account not verified"
    TOKEN_EXPIRED = "TOKEN_EXPIRED", "Token expired"
    TOKEN_INVALID = "TOKEN_INVALID", "Token invalid"
    LOGIN_BLOCKED = "LOGIN_BLOCKED", "Login blocked"
    SESSION_REVOKED = "SESSION_REVOKED", "Session revoked"
    # Workspace
    WORKSPACE_NOT_ACTIVE = "WORKSPACE_NOT_ACTIVE", "Workspace not active"
    WORKSPACE_FROZEN = "WORKSPACE_FROZEN", "Workspace frozen"
    WORKSPACE_DEACTIVATED = "WORKSPACE_DEACTIVATED", "Workspace deactivated"
    GRACE_PERIOD_RESTRICTED = "GRACE_PERIOD_RESTRICTED", "Action restricted in grace period"
    SUBDOMAIN_TAKEN = "SUBDOMAIN_TAKEN", "Subdomain taken"
    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION", "Illegal state transition"
    # Enrollment / content access
    ALREADY_ENROLLED = "ALREADY_ENROLLED", "Already enrolled"
    NOT_ENROLLED = "NOT_ENROLLED", "Not enrolled"
    ENROLLMENT_INACTIVE = "ENROLLMENT_INACTIVE", "Enrollment not active"
    ENROLLMENT_EXPIRED = "ENROLLMENT_EXPIRED", "Enrollment expired"
    OUTSIDE_DATE_WINDOW = "OUTSIDE_DATE_WINDOW", "Outside enrollment date window"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED", "Payment required to access this content"
    PAYMENT_PERIOD_EXPIRED = "PAYMENT_PERIOD_EXPIRED", "Payment period has expired"
    ACCESS_DENIED = "ACCESS_DENIED", "Access denied"
    HAS_ACTIVE_PAID_ENROLLMENTS = "HAS_ACTIVE_PAID_ENROLLMENTS", "Has active paid enrollments"
    # Groups
    GROUP_FULL = "GROUP_FULL", "Group is full"
    ALREADY_IN_GROUP_FOR_SUBJECT = "ALREADY_IN_GROUP_FOR_SUBJECT", "Already in a group for this subject"
    # Billing
    SUBSCRIPTION_ACTIVE = "SUBSCRIPTION_ACTIVE", "Subscription already active"
    SUBSCRIPTION_NOT_FOUND = "SUBSCRIPTION_NOT_FOUND", "Subscription not found"
    PAYMENT_PENDING = "PAYMENT_PENDING", "Payment already pending"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT", "Duplicate payment"
    QUOTE_STALE = "QUOTE_STALE", "Upgrade quote is stale"
    UPGRADE_WOULD_SHORTEN_PERIOD = "UPGRADE_WOULD_SHORTEN_PERIOD", "Upgrade would shorten coverage period"
    UPGRADE_MIN_CHARGE = "UPGRADE_MIN_CHARGE", "Upgrade charge below minimum"
    INVALID_UPGRADE_CHARGE = "INVALID_UPGRADE_CHARGE", "Upgrade charge is invalid (zero, negative, or below minimum)"
    UPGRADE_MIN_REMAINING = "UPGRADE_MIN_REMAINING", "Insufficient days remaining for this upgrade type"
    UPGRADE_NOT_ELIGIBLE = "UPGRADE_NOT_ELIGIBLE", "Not eligible for upgrade"
    # Payments
    POSSIBLE_DUPLICATE_PROOF = "POSSIBLE_DUPLICATE_PROOF", "Possible duplicate proof image"
    REJECTION_REASON_REQUIRED = "REJECTION_REASON_REQUIRED", "Rejection reason required"
    OVER_REFUND = "OVER_REFUND", "Refund amount exceeds received amount"
    # Limits
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED", "Limit exceeded"
    # Exams
    ATTEMPT_EXPIRED = "ATTEMPT_EXPIRED", "Attempt has expired"
    ALREADY_SUBMITTED = "ALREADY_SUBMITTED", "Attempt already submitted"
    STALE_VERSION = "STALE_VERSION", "Stale version — re-fetch and retry"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED", "Attempt limit reached"
    # Files
    FILE_QUARANTINED = "FILE_QUARANTINED", "File is quarantined"
    FILE_PENDING_SCAN = "FILE_PENDING_SCAN", "File scan pending"
    FILE_TYPE_NOT_ALLOWED = "FILE_TYPE_NOT_ALLOWED", "File type not allowed"
    FILE_TOO_LARGE = "FILE_TOO_LARGE", "File too large"
    PATH_TRAVERSAL = "PATH_TRAVERSAL", "Path traversal attempt detected"
    # Generic
    NOT_FOUND = "NOT_FOUND", "Not found"
    PERMISSION_DENIED = "PERMISSION_DENIED", "Permission denied"
    VALIDATION_ERROR = "VALIDATION_ERROR", "Validation error"
    CONFLICT = "CONFLICT", "Conflict"
    INTERNAL_ERROR = "INTERNAL_ERROR", "Internal server error"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR", "External service error"
    EXPORT_FORMAT_NOT_SUPPORTED = "EXPORT_FORMAT_NOT_SUPPORTED", "Export format not supported"
