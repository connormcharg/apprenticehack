from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('manifest.webmanifest', views.manifest, name='manifest'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('signup/', views.signup, name='signup'),
    path('quiz/', views.quiz, name='quiz'),
    path('login/', auth_views.LoginView.as_view(template_name='fivenine/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('home/', views.dashboard, name='dashboard'),
    path('goals/', views.goal_list, name='goal_list'),
    path('goals/<int:pk>/toggle/', views.goal_toggle, name='goal_toggle'),
    path('tasks/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
    path('plan/', views.evening_plan, name='evening_plan'),
    path('events/', views.event_list, name='event_list'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/feed-<uuid:token>.ics', views.ics_feed, name='ics_feed'),
    path('api/chat/', views.assistant_api, name='assistant_api'),
]
