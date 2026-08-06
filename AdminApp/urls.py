from django.urls import path
from . import views

app_name = 'AdminApp'

urlpatterns = [
    path('admin-panel/',                                      views.dashboard,          name='dashboard'),
    path('admin-panel/users/',                                views.manage_users,       name='manage_users'),
    path('admin-panel/users/<int:user_id>/delete/',           views.delete_user,        name='delete_user'),
    path('admin-panel/caregivers/',                           views.manage_caregivers,  name='manage_caregivers'),
    path('admin-panel/documents/',                            views.review_documents,   name='review_documents'),
    path('admin-panel/documents/<int:doc_id>/approve/',       views.approve_document,   name='approve_document'),
    path('admin-panel/documents/<int:doc_id>/reject/',        views.reject_document,    name='reject_document'),
    path('admin-panel/documents/<int:doc_id>/revoke/',        views.revoke_document,    name='revoke_document'),
    path('admin-panel/caregivers/<int:profile_id>/activate/', views.activate_caregiver, name='activate_caregiver'),
    path('admin-panel/shifts/',                               views.manage_shifts,      name='manage_shifts'),
]
