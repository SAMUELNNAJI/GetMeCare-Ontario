from django.urls import path
from . import views

urlpatterns = [
    path('api/chat/', views.chat_endpoint, name='chat_endpoint'),
    path('api/chat/history/', views.get_chat_history, name='chat_history'),
    path('api/conversations/', views.get_conversations, name='get_conversations'),
    path('api/conversations/create/', views.create_conversation, name='create_conversation'),
    path('api/conversations/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
]