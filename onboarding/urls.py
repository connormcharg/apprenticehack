from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    # Account
    path("sign-up/", views.sign_up, name="sign_up"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
    # Onboarding
    path("", views.about_you, name="about_you"),
    path("hours/", views.hours, name="hours"),
    path("welcome/", views.welcome, name="welcome"),
]
