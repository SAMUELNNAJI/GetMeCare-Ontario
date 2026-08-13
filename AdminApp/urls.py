from django.urls import path
from . import views

app_name = 'AdminApp'

urlpatterns = [
    path('admin-panel/',                                      views.dashboard,          name='dashboard'),
    path('admin-panel/users/',                                views.manage_users,       name='manage_users'),
    path('admin-panel/users/<int:user_id>/delete/',           views.delete_user,        name='delete_user'),
    path('admin-panel/caregivers/',                           views.manage_caregivers,  name='manage_caregivers'),
    path('admin-panel/employers/',                            views.manage_employers,    name='manage_employers'),
    path('admin-panel/employers/<int:profile_id>/activate/',  views.activate_employer,   name='activate_employer'),
    path('admin-panel/documents/',                            views.review_documents,   name='review_documents'),
    path('admin-panel/documents/<int:doc_id>/approve/',       views.approve_document,   name='approve_document'),
    path('admin-panel/documents/<int:doc_id>/reject/',        views.reject_document,    name='reject_document'),
    path('admin-panel/documents/<int:doc_id>/revoke/',        views.revoke_document,    name='revoke_document'),
    path('admin-panel/documents/<int:doc_id>/view/',          views.serve_document,     name='serve_document'),
    path('admin-panel/caregivers/<int:profile_id>/activate/', views.activate_caregiver, name='activate_caregiver'),
    path('admin-panel/shifts/',                               views.manage_shifts,      name='manage_shifts'),
    # Payout queue
    path('admin-panel/payouts/',                              views.payout_queue,       name='payout_queue'),
    path('admin-panel/payouts/<int:log_pk>/mark-paid/',       views.mark_paid,          name='mark_paid'),
    # Employer payments
    path('admin-panel/employer-payments/',                    views.employer_payments,  name='employer_payments'),
    # Disputes
    path('admin-panel/disputes/',                             views.dispute_list,       name='dispute_list'),
    path('admin-panel/disputes/<int:dispute_pk>/',            views.dispute_detail,     name='dispute_detail'),
    # FAQs
    path('admin-panel/faqs/',                                 views.faq_list,       name='faq_list'),
    path('admin-panel/faqs/add/',                             views.faq_edit,       name='faq_add'),
    path('admin-panel/faqs/<int:faq_id>/edit/',               views.faq_edit,       name='faq_edit'),
    path('admin-panel/faqs/<int:faq_id>/delete/',              views.faq_delete,     name='faq_delete'),
    path('faqs/api/',                                         views.public_faqs,    name='public_faqs'),
    # Services
    path('admin-panel/services/',                             views.service_list,   name='service_list'),
    path('admin-panel/services/add/',                         views.service_edit,   name='service_add'),
    path('admin-panel/services/<int:service_id>/edit/',       views.service_edit,   name='service_edit'),
    path('admin-panel/services/<int:service_id>/delete/',     views.service_delete, name='service_delete'),
    path('services/api/',                                      views.public_services, name='public_services'),
]
