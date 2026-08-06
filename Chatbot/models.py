from django.db import models
from django.contrib.auth import get_user_model
from Account.models import CaregiverProfile

User = get_user_model()


class ChatConversation(models.Model):
    """Store individual chat conversations/sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=100, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Conversation: {self.title}"
    
    def get_first_message(self):
        """Get the first message of the conversation for title generation"""
        first_message = self.messages.first()
        if first_message:
            return first_message.message[:50] + '...' if len(first_message.message) > 50 else first_message.message
        return 'New Chat'


class ChatMessage(models.Model):
    """Store chat conversation history"""
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    response = models.TextField()
    is_caregiver_referral = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Chat: {self.message[:50]}..."


class SiteKnowledge(models.Model):
    """Store site information for the chatbot to reference"""
    category = models.CharField(max_length=100)
    question = models.CharField(max_length=255)
    answer = models.TextField()
    keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for matching")
    priority = models.IntegerField(default=0, help_text="Higher priority matches first")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-priority', 'category']
    
    def __str__(self):
        return f"{self.category}: {self.question}"


class CaregiverRecommendation(models.Model):
    """Track caregiver referrals made by the chatbot"""
    chat_message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='recommendations')
    caregiver = models.ForeignKey(CaregiverProfile, on_delete=models.CASCADE)
    match_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-match_score']
    
    def __str__(self):
        return f"Recommended {self.caregiver.user.get_full_name()} (Score: {self.match_score})"