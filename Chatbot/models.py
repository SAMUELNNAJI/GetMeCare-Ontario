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


# ─────────────────────────────────────────────────────────────
# Direct (user-to-user) messaging
# ─────────────────────────────────────────────────────────────

class DirectConversation(models.Model):
    """A 1-to-1 conversation thread between two users."""
    participant_1 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='conversations_as_p1'
    )
    participant_2 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='conversations_as_p2'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        # Enforce uniqueness so there is only one thread per pair
        unique_together = [('participant_1', 'participant_2')]

    def __str__(self):
        return f"Chat: {self.participant_1} ↔ {self.participant_2}"

    @classmethod
    def get_or_create_for(cls, user_a, user_b):
        """Return (conversation, created) ensuring the lower-pk user is p1."""
        if user_a.pk > user_b.pk:
            user_a, user_b = user_b, user_a
        return cls.objects.get_or_create(
            participant_1=user_a,
            participant_2=user_b,
        )

    def other_participant(self, user):
        return self.participant_2 if self.participant_1_id == user.pk else self.participant_1

    def last_message(self):
        return self.direct_messages.last()

    def unread_count(self, user):
        return self.direct_messages.filter(is_read=False).exclude(sender=user).count()


class DirectMessage(models.Model):
    """A single message inside a DirectConversation."""
    conversation = models.ForeignKey(
        DirectConversation, on_delete=models.CASCADE, related_name='direct_messages'
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_direct_messages'
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"
