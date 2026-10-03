"""URL configuration for apprenticehack project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

from onboarding import views as onboarding_views

urlpatterns = [
    path('', onboarding_views.home, name='home'),
    path('onboarding/', include('onboarding.urls')),
    path('admin/', admin.site.urls),
    path('', include('fivenine.urls')),
]
