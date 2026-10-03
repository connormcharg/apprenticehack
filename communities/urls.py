from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("", views.community_list, name="list"),
    path("new/", views.community_create, name="create"),
    path("<int:pk>/", views.community_detail, name="detail"),
    path("<int:pk>/join/", views.community_join, name="join"),
    path("<int:pk>/leave/", views.community_leave, name="leave"),
    path("<int:pk>/events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/join/", views.event_join, name="event_join"),
    path("events/<int:pk>/leave/", views.event_leave, name="event_leave"),
    path("<int:pk>/messages/", views.message_create, name="message_create"),
]
