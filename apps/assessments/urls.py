from rest_framework.routers import DefaultRouter
from apps.assessments.views import ExamViewSet, QuestionViewSet, ExamAttemptViewSet, AssignmentViewSet, AssignmentSubmissionViewSet

router = DefaultRouter()
router.register("exams", ExamViewSet, basename="exam")
router.register("questions", QuestionViewSet, basename="question")
router.register("exam-attempts", ExamAttemptViewSet, basename="exam-attempt")
router.register("assignments", AssignmentViewSet, basename="assignment")
router.register("assignment-submissions", AssignmentSubmissionViewSet, basename="assignment-submission")
urlpatterns = router.urls
