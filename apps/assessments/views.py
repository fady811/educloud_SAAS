from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin
from apps.core.permissions import IsWorkspaceMember
from apps.assessments.models import Exam, Question, ExamAttempt, Assignment, AssignmentSubmission
from apps.assessments.serializers import (
    ExamSerializer, QuestionSerializer, ExamAttemptSerializer,
    AssignmentSerializer, AssignmentSubmissionSerializer,
)
from apps.assessments.services.attempts import start_attempt, submit_attempt


class ExamViewSet(ModelViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = ExamSerializer

    def get_queryset(self):
        return Exam.objects.filter(workspace_id=self.request.workspace_id)


class QuestionViewSet(ModelViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = QuestionSerializer

    def get_queryset(self):
        return Question.objects.filter(workspace_id=self.request.workspace_id)


class ExamAttemptViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = ExamAttemptSerializer

    def get_queryset(self):
        return ExamAttempt.objects.filter(workspace_id=self.request.workspace_id)

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
        attempt = submit_attempt(
            attempt_id=int(pk),
            student_id=request.user.id,
            answers=request.data.get("answers", {}),
        )
        return Response(ExamAttemptSerializer(attempt).data)


class AssignmentViewSet(ModelViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return Assignment.objects.filter(workspace_id=self.request.workspace_id)


class AssignmentSubmissionViewSet(ListModelMixin, RetrieveModelMixin, CreateModelMixin, GenericViewSet):
    permission_classes = [IsWorkspaceMember]
    serializer_class = AssignmentSubmissionSerializer

    def get_queryset(self):
        return AssignmentSubmission.objects.filter(workspace_id=self.request.workspace_id)
