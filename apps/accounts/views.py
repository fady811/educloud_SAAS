"""Account views — auth, sessions, team."""
from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, BaseThrottle
from rest_framework.views import APIView

from apps.accounts.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from apps.accounts.enums import PermissionKey
from apps.core.errors import ValidationFailed
from apps.core.permissions import WorkspacePermission

class LoginThrottle(BaseThrottle):
    """
    IP-based login throttle: sliding-window, policy from settings.

    Policy (REQ-SEC-04): LOGIN_THROTTLE_MAX_ATTEMPTS attempts per
    LOGIN_THROTTLE_WINDOW_SECONDS seconds (default 5 / 900 s = 15 min).

    get_ident() uses DRF's standard implementation, which respects
    NUM_PROXIES to safely extract the client IP from X-Forwarded-For.
    With NUM_PROXIES=1 (the production default) the rightmost client IP
    inserted by the trusted proxy is used, preventing header spoofing.

    Cache failures fail open so a Redis outage does not lock out users.
    """

    scope = "login"

    def _policy(self) -> tuple[int, int]:
        from django.conf import settings
        max_attempts = getattr(settings, "LOGIN_THROTTLE_MAX_ATTEMPTS", 5)
        window = getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 900)
        return max_attempts, window

    def _cache_key(self, request) -> str:
        ident = self.get_ident(request)
        return f"throttle_login_{ident}"

    def allow_request(self, request, view) -> bool:
        import time
        from django.core.cache import cache

        max_attempts, window = self._policy()
        key = self._cache_key(request)
        try:
            history: list[float] = cache.get(key) or []
        except Exception:  # noqa: BLE001 — fail open on cache error
            self.wait_seconds: float | None = None
            return True

        now = time.time()
        history = [t for t in history if t > now - window]

        if len(history) >= max_attempts:
            self.wait_seconds = window - (now - history[0])
            return False

        history.append(now)
        try:
            cache.set(key, history, window)
        except Exception:  # noqa: BLE001
            pass
        self.wait_seconds = None
        return True

    def wait(self) -> float | None:
        return getattr(self, "wait_seconds", None)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.registration import register_user
        from apps.accounts.tasks import send_verification_email

        ser = UserRegistrationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user, token = register_user(**ser.validated_data)

        # Queue verification email/SMS
        if user.email:
            send_verification_email.delay(user.id, token.id)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.login_throttle import check_login_allowed, record_failure, clear_counter
        from apps.accounts.services.sessions import create_session

        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        username = ser.validated_data["username"]
        password = ser.validated_data["password"]
        ip = request.META.get("REMOTE_ADDR", "")

        check_login_allowed(username, ip)
        user = authenticate(request, username=username, password=password)

        if not user:
            record_failure(username, ip)
            raise ValidationFailed("Invalid credentials.", code="INVALID_CREDENTIALS")

        if not user.is_verified:
            raise ValidationFailed("Account not yet verified.", code="ACCOUNT_NOT_VERIFIED")

        workspace_id = getattr(request, "workspace_id", None)
        create_session(request, user, workspace_id=workspace_id)
        clear_counter(username)

        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response({"detail": "Logged out."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.accounts.models import UserSession
        sessions = UserSession.objects.filter(user=request.user, revoked_at__isnull=True)
        return Response(UserSessionSerializer(sessions, many=True, context={"request": request}).data)


class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, pk: int) -> Response:
        from apps.accounts.services.sessions import revoke_session
        revoke_session(request, pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request: Request) -> Response:
        from apps.accounts.services.sessions import revoke_others
        revoke_others(request, request.user)
        return Response({"detail": "Other sessions revoked."})


class StudentListCreateView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.STUDENT_VIEW},
        "POST": {"required_permission_key": PermissionKey.STUDENT_CREATE},
    }

    def get(self, request: Request) -> Response:
        from apps.accounts.services.students import get_students
        from apps.accounts.serializers import WorkspaceMembershipStudentSerializer
        qs = get_students(request.workspace_id)
        return Response(WorkspaceMembershipStudentSerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        from apps.accounts.services.students import create_student
        from apps.accounts.serializers import WorkspaceMembershipStudentSerializer
        membership = create_student(
            workspace_id=request.workspace_id,
            email=request.data.get("email") or None,
            phone=request.data.get("phone") or None,
            first_name=request.data.get("first_name", ""),
            last_name=request.data.get("last_name", ""),
            actor_id=request.user.id,
        )
        return Response(WorkspaceMembershipStudentSerializer(membership).data, status=status.HTTP_201_CREATED)


class StudentDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.STUDENT_VIEW},
        "PATCH": {"required_permission_key": PermissionKey.STUDENT_EDIT},
        "DELETE": {"required_permission_key": PermissionKey.STUDENT_DEACTIVATE},
    }

    def _get_membership(self, request, pk):
        from apps.workspaces.models import WorkspaceMembership
        from apps.core.enums import Role
        from apps.core.errors import NotFound
        try:
            return WorkspaceMembership.objects.select_related("user").get(
                user_id=pk, workspace_id=request.workspace_id, role=Role.STUDENT
            )
        except WorkspaceMembership.DoesNotExist:
            raise NotFound("Student not found.")

    def get(self, request: Request, pk: int) -> Response:
        from apps.accounts.serializers import WorkspaceMembershipStudentSerializer
        m = self._get_membership(request, pk)
        return Response(WorkspaceMembershipStudentSerializer(m).data)

    def patch(self, request: Request, pk: int) -> Response:
        from apps.accounts.serializers import WorkspaceMembershipStudentSerializer
        m = self._get_membership(request, pk)
        user = m.user
        for field in ("first_name", "last_name"):
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save(update_fields=["first_name", "last_name"])
        return Response(WorkspaceMembershipStudentSerializer(m).data)

    def delete(self, request: Request, pk: int) -> Response:
        from apps.accounts.services.students import deactivate_student
        deactivate_student(
            workspace_id=request.workspace_id,
            student_id=pk,
            actor_id=request.user.id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentImportView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "POST": {"required_permission_key": PermissionKey.STUDENT_CREATE},
    }

    def post(self, request: Request) -> Response:
        from apps.accounts.services.bulk_import import import_students
        from apps.accounts.serializers import StudentImportJobSerializer

        csv_file = request.FILES.get("file")
        if not csv_file:
            raise ValidationFailed("file is required.")
        content = csv_file.read()

        job = import_students(
            workspace_id=request.workspace_id,
            created_by_id=request.user.id,
            csv_content=content,
        )
        return Response(
            StudentImportJobSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )


class StudentImportDetailView(APIView):
    permission_classes = [WorkspacePermission]
    permission_map = {
        "GET": {"required_permission_key": PermissionKey.STUDENT_VIEW},
    }

    def get(self, request: Request, pk: int) -> Response:
        from apps.accounts.models import StudentImportJob
        from apps.accounts.serializers import StudentImportJobSerializer
        from apps.core.errors import NotFound
        try:
            job = StudentImportJob.objects.get(id=pk, workspace_id=request.workspace_id)
        except StudentImportJob.DoesNotExist:
            raise NotFound("Import job not found.")
        return Response(StudentImportJobSerializer(job).data)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.verification import verify_token
        token = request.data.get("token", "")
        if not token:
            raise ValidationFailed("token is required.")
        verify_token(token)
        return Response({"detail": "Account verified."})


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.verification import resend_verification
        from apps.accounts.models import User
        from apps.accounts.tasks import send_verification_email

        identifier = request.data.get("email") or request.data.get("phone")
        if not identifier:
            raise ValidationFailed("email or phone is required.")

        user = None
        if "@" in str(identifier):
            user = User.objects.filter(email=identifier).first()
        else:
            from apps.core.validators import normalize_phone
            user = User.objects.filter(phone=normalize_phone(identifier)).first()

        if user and not user.is_verified:
            token = resend_verification(user)
            if user.email:
                send_verification_email.delay(user.id, token.id)

        return Response({"detail": "If the account exists and is unverified, a new code has been sent."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.password_reset import request_reset
        identifier = request.data.get("email") or request.data.get("phone") or ""
        if not identifier:
            raise ValidationFailed("email or phone is required.")
        request_reset(identifier=identifier)
        return Response({"detail": "If the account exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.accounts.services.password_reset import confirm_reset
        token = request.data.get("token", "")
        new_password = request.data.get("password", "")
        if not token or not new_password:
            raise ValidationFailed("token and password are required.")
        if len(new_password) < 8:
            raise ValidationFailed("password must be at least 8 characters.")
        confirm_reset(token=token, new_password=new_password)
        return Response({"detail": "Password has been reset."})


class MeWorkspacesView(APIView):
    """List all workspace memberships for the current user (REQ-WS-04, C-01)."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.workspaces.models import WorkspaceMembership
        memberships = (
            WorkspaceMembership.objects
            .filter(user=request.user)
            .select_related("workspace")
            .order_by("created_at")
        )
        data = [
            {
                "workspace_id": m.workspace_id,
                "subdomain": m.workspace.subdomain,
                "role": m.role,
                "is_owner": m.is_owner,
                "status": m.workspace.status,
            }
            for m in memberships
        ]
        return Response(data)
