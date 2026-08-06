from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('browse/', views.browse, name='browse'),
    path('browse-jobs/', views.browse_jobs, name='browse_jobs'),
    path('how-it-works/', views.how_it_works, name='how_it_works'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
]
