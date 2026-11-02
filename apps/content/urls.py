from django.urls import path
from apps.content import views

urlpatterns = [
    path("subjects/", views.SubjectListCreateView.as_view(), name="subject-list"),
    path("courses/", views.CourseListCreateView.as_view(), name="course-list"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
    path("courses/<int:course_id>/lessons/", views.LessonListCreateView.as_view(), name="lesson-list"),
    path("lessons/<int:pk>/content/", views.LessonContentView.as_view(), name="lesson-content"),
]
