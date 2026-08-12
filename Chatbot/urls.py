from django.urls import path
from . import views

urlpatterns = [
    # AI chatbot API (existing)
    path('api/chat/', views.chat_endpoint, name='chat_endpoint'),
    path('api/chat/history/', views.get_chat_history, name='chat_history'),
    path('api/conversations/', views.get_conversations, name='get_conversations'),
    path('api/conversations/create/', views.create_conversation, name='create_conversation'),
    path('api/conversations/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),

    # Direct messaging (user-to-user)
    path('messages/', views.chat_list, name='chat_list'),
    path('messages/<int:conv_id>/', views.chat_room, name='chat_room'),
    path('messages/start/<int:user_id>/', views.chat_start, name='chat_start'),
    path('messages/<int:conv_id>/send/', views.chat_send, name='chat_send'),
    path('messages/<int:conv_id>/poll/', views.chat_poll, name='chat_poll'),

    # Booking proposals
    path('messages/<int:conv_id>/proposals/send/', views.send_proposal,  name='chatbot_send_proposal'),
    path('messages/<int:conv_id>/proposals/poll/', views.poll_proposals, name='chatbot_poll_proposals'),
    path('proposals/<int:proposal_pk>/decline/',   views.decline_proposal, name='chatbot_decline_proposal'),

    # Admin monitor
    path('admin/monitor/', views.admin_chat_monitor, name='admin_chat_monitor'),

    # Live Support Chat (HTMX real-time)
    path('support/', views.support_chat, name='support_chat'),
    path('support/<int:chat_id>/', views.support_chat_detail, name='support_chat_detail'),
    path('support/<int:chat_id>/send/', views.support_chat_send, name='support_chat_send'),
    path('support/<int:chat_id>/poll/', views.support_chat_poll, name='support_chat_poll'),

    # Admin support chat
    path('admin/support/', views.admin_support, name='admin_support'),
    path('admin/support/<int:chat_id>/reply/', views.admin_support_reply, name='admin_support_reply'),
    path('admin/support/<int:chat_id>/poll/', views.admin_support_poll, name='admin_support_poll'),
    path('admin/support/<int:chat_id>/resolve/', views.admin_support_resolve, name='admin_support_resolve'),
]
