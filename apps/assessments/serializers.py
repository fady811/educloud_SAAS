from rest_framework import serializers
from apps.assessments.models import Exam, Question, ExamAttempt, Assignment, AssignmentSubmission

class ExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = ["id", "lesson", "title", "instructions", "duration_minutes", "pass_score",
                  "max_attempts", "shuffle_questions", "status", "available_from", "available_until"]

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "exam", "question_type", "body", "choices", "points", "display_order"]

class ExamAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAttempt
        fields = ["id", "exam", "student", "status", "started_at", "submitted_at", "deadline_at", "answers", "version", "score"]

class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ["id", "lesson", "group", "title", "instructions", "due_at", "max_score", "allow_late"]

class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentSubmission
        fields = ["id", "assignment", "student", "file_id", "notes", "submitted_at", "score", "feedback"]
