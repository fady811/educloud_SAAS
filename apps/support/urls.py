from django.urls import path
from apps.support import views

urlpatterns = [
    path("support/tickets/", views.TicketListCreateView.as_view(), name="ticket-list"),
    path("support/tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket-detail"),
    path("support/tickets/<int:pk>/messages/", views.TicketMessageView.as_view(), name="ticket-messages"),
]
