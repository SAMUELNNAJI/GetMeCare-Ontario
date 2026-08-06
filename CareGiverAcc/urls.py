from django.urls import path
from . import views

app_name = 'CareGiverAcc'

urlpatterns = [
    path('caregiver-acc/',             views.dashboard,   name='dashboard'),
    path('caregiver-acc/schedule/',    views.my_schedule, name='my_schedule'),
    path('caregiver-acc/earnings/',    views.earnings,    name='earnings'),
    path('caregiver-acc/documents/',   views.documents,   name='documents'),
]
