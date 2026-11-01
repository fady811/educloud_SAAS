from django.urls import path
from apps.files import views

urlpatterns = [
    path("files/upload/", views.UploadRequestView.as_view(), name="file-upload-request"),
    path("files/<int:pk>/", views.FileDetailView.as_view(), name="file-detail"),
    path("files/<int:pk>/scan-callback/", views.FileScanCallbackView.as_view(), name="file-scan-callback"),
]
