from django.urls import path
from . import views

app_name = 'CareGiverAcc'

urlpatterns = [
    path('caregiver-acc/',             views.dashboard,   name='dashboard'),
    path('caregiver-acc/schedule/',    views.my_schedule, name='my_schedule'),
    path('caregiver-acc/earnings/',    views.earnings,    name='earnings'),
    path('caregiver-acc/documents/',                    views.documents,          name='documents'),
    path('caregiver-acc/documents/<int:doc_id>/reupload/', views.reupload_document, name='reupload_document'),
    path('caregiver-acc/documents/<int:doc_id>/view/',    views.serve_document,     name='serve_document'),
]
