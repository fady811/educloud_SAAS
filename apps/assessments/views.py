from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin
from apps.core.permissions import WorkspacePermission, ALL_MEMBERS, STUDENT_ONLY
from apps.accounts.enums import PermissionKey
from apps.assessments.models import Exam, Question, ExamAttempt, Assignment, AssignmentSubmission
from apps.assessments.serializers import (
    ExamSerializer, QuestionSerializer, ExamAttemptSerializer,
    AssignmentSerializer, AssignmentSubmissionSerializer,
)
from apps.assessments.services.attempts import start_attempt, submit_attempt


class ExamViewSet(ModelViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = ExamSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.ASSESSMENT_CREATE},
        "PUT": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "PATCH": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "DELETE": {"owner_only": True},
    }

    def get_queryset(self):
        return Exam.objects.filter(workspace_id=self.request.workspace_id)


class QuestionViewSet(ModelViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = QuestionSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.ASSESSMENT_CREATE},
        "PUT": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "PATCH": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "DELETE": {"owner_only": True},
    }

    def get_queryset(self):
        return Question.objects.filter(workspace_id=self.request.workspace_id)


class ExamAttemptViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = ExamAttemptSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        # start and submit are POST — students only
        "POST": {"allowed_roles": STUDENT_ONLY},
    }

    def get_queryset(self):
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        from apps.parents.models import ParentStudentLink
        qs = ExamAttempt.objects.filter(workspace_id=self.request.workspace_id)
        try:
            m = WorkspaceMembership.objects.get(
                user=self.request.user, workspace_id=self.request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            return qs.none()
        if m.role == Role.STUDENT:
            return qs.filter(student_id=self.request.user.id)
        if m.role == Role.PARENT:
            child_ids = ParentStudentLink.objects.filter(
                workspace_id=self.request.workspace_id,
                parent_id=self.request.user.id,
                unlinked_at__isnull=True,
            ).values_list("student_id", flat=True)
            return qs.filter(student_id__in=child_ids)
        return qs

    @action(detail=False, methods=["post"])
    def start(self, request):
        attempt = start_attempt(
            exam_id=request.data.get("exam_id"),
            student_id=request.user.id,
            workspace_id=request.workspace_id,
        )
        return Response(ExamAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        from apps.core.errors import PermissionDeniedError
        # Only the owner of the attempt may submit it
        try:
            attempt_obj = ExamAttempt.objects.get(id=int(pk), workspace_id=request.workspace_id)
        except ExamAttempt.DoesNotExist:
            from apps.core.errors import NotFound
            raise NotFound("Attempt not found")
        if attempt_obj.student_id != request.user.id:
            raise PermissionDeniedError("You may only submit your own attempt.")
        attempt = submit_attempt(
            attempt_id=int(pk),
            student_id=request.user.id,
            answers=request.data.get("answers", {}),
        )
        return Response(ExamAttemptSerializer(attempt).data)


class AssignmentViewSet(ModelViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = AssignmentSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        "POST": {"required_permission_key": PermissionKey.ASSESSMENT_CREATE},
        "PUT": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "PATCH": {"required_permission_key": PermissionKey.ASSESSMENT_EDIT},
        "DELETE": {"owner_only": True},
    }

    def get_queryset(self):
        return Assignment.objects.filter(workspace_id=self.request.workspace_id)


class AssignmentSubmissionViewSet(ListModelMixin, RetrieveModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [WorkspacePermission]
    serializer_class = AssignmentSubmissionSerializer
    permission_map = {
        "GET": {"allowed_roles": ALL_MEMBERS},
        # Only students may submit
        "POST": {"allowed_roles": STUDENT_ONLY},
    }

    def get_queryset(self):
        from apps.core.enums import Role
        from apps.workspaces.models import WorkspaceMembership
        from apps.parents.models import ParentStudentLink
        qs = AssignmentSubmission.objects.filter(workspace_id=self.request.workspace_id)
        try:
            m = WorkspaceMembership.objects.get(
                user=self.request.user, workspace_id=self.request.workspace_id
            )
        except WorkspaceMembership.DoesNotExist:
            return qs.none()
        if m.role == Role.STUDENT:
            return qs.filter(student_id=self.request.user.id)
        if m.role == Role.PARENT:
            child_ids = ParentStudentLink.objects.filter(
                workspace_id=self.request.workspace_id,
                parent_id=self.request.user.id,
                unlinked_at__isnull=True,
            ).values_list("student_id", flat=True)
            return qs.filter(student_id__in=child_ids)
        return qs
