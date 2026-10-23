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
    path('caregiver/<int:pk>/', views.caregiver_profile, name='caregiver_profile'),
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('blog/comments/add/<int:post_id>/', views.blog_comment_add, name='blog_comment_add'),
    path('blog/comments/edit/<int:comment_id>/', views.blog_comment_edit, name='blog_comment_edit'),
    path('blog/comments/delete/<int:comment_id>/', views.blog_comment_delete, name='blog_comment_delete'),
]

