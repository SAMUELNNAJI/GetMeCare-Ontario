from django.contrib import admin
from .models import ChatConversation, ChatMessage, SiteKnowledge, CaregiverRecommendation


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'message_preview', 'response_preview', 'is_caregiver_referral', 'created_at']
    list_filter = ['is_caregiver_referral', 'created_at']
    search_fields = ['message', 'response', 'user__username']
    readonly_fields = ['created_at']
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'
    
    def response_preview(self, obj):
        return obj.response[:50] + '...' if len(obj.response) > 50 else obj.response
    response_preview.short_description = 'Response'


@admin.register(SiteKnowledge)
class SiteKnowledgeAdmin(admin.ModelAdmin):
    list_display = ['category', 'question', 'priority', 'created_at']
    list_filter = ['category', 'priority', 'created_at']
    search_fields = ['question', 'answer', 'keywords']
    list_editable = ['priority']


@admin.register(CaregiverRecommendation)
class CaregiverRecommendationAdmin(admin.ModelAdmin):
    list_display = ['caregiver', 'match_score', 'chat_message', 'created_at']
    list_filter = ['match_score', 'created_at']
    search_fields = ['caregiver__user__username', 'chat_message__message']
    readonly_fields = ['created_at']