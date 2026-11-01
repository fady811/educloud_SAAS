"""Account-specific enums."""
from django.db import models


class PermissionKey(models.TextChoices):
    """Granular team member permission keys (REQ-ROLE-02, §5.13.2)."""
    # Student management
    STUDENT_VIEW = "STUDENT_VIEW", "View Students"
    STUDENT_CREATE = "STUDENT_CREATE", "Create Students"
    STUDENT_EDIT = "STUDENT_EDIT", "Edit Students"
    STUDENT_DEACTIVATE = "STUDENT_DEACTIVATE", "Deactivate Students"
    # Content management
    CONTENT_VIEW = "CONTENT_VIEW", "View Content"
    CONTENT_CREATE = "CONTENT_CREATE", "Create Content"
    CONTENT_EDIT = "CONTENT_EDIT", "Edit Content"
    CONTENT_ARCHIVE = "CONTENT_ARCHIVE", "Archive Content"
    # Group management
    GROUP_VIEW = "GROUP_VIEW", "View Groups"
    GROUP_CREATE = "GROUP_CREATE", "Create Groups"
    GROUP_EDIT = "GROUP_EDIT", "Edit Groups"
    GROUP_ASSIGN = "GROUP_ASSIGN", "Assign Students to Groups"
    # Assessment management
    ASSESSMENT_CREATE = "ASSESSMENT_CREATE", "Create Assessments"
    ASSESSMENT_EDIT = "ASSESSMENT_EDIT", "Edit Assessments"
    ASSESSMENT_GRADE = "ASSESSMENT_GRADE", "Grade Assessments"
    # Payment management
    PAYMENT_VIEW = "PAYMENT_VIEW", "View Payments"
    PAYMENT_CONFIRM = "PAYMENT_CONFIRM", "Confirm Payments"
    PAYMENT_REJECT = "PAYMENT_REJECT", "Reject Payments"
    # Attendance
    ATTENDANCE_RECORD = "ATTENDANCE_RECORD", "Record Attendance"
    ATTENDANCE_VIEW_REPORTS = "ATTENDANCE_VIEW_REPORTS", "View Attendance Reports"
    # Reports
    REPORTS_VIEW = "REPORTS_VIEW", "View Reports"
    # Communication
    COMM_ANNOUNCEMENTS = "COMM_ANNOUNCEMENTS", "Send Announcements"
    COMM_DMS = "COMM_DMS", "Send Direct Messages"
