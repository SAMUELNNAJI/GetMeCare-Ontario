from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.conf import settings
from .models import ChatConversation, ChatMessage, SiteKnowledge, CaregiverRecommendation, SupportChat, SupportMessage
from Account.models import CaregiverProfile, BookingProposal, EmployerProfile
from .pii_filter import find_pii, pii_error_message
from GETMECARE.email_utils import send_offline_chat_notification, send_support_offline_notification, send_support_resolved_email
import json
import re
import requests

User = get_user_model()


@csrf_exempt
@require_http_methods(["POST"])
def chat_endpoint(request):
    """Main chatbot endpoint that processes user questions and returns responses"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id')
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Get user if authenticated
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Get or create conversation
        conversation = None
        if conversation_id:
            try:
                conversation = ChatConversation.objects.get(id=conversation_id, user=user)
            except ChatConversation.DoesNotExist:
                pass
        
        if not conversation:
            # Create new conversation
            title = user_message[:50] + '...' if len(user_message) > 50 else user_message
            conversation = ChatConversation.objects.create(
                user=user,
                title=title
            )
        
        # Process the message and get response
        response_data = process_message(user_message, user)
        
        # Save chat history
        chat_message = ChatMessage.objects.create(
            conversation=conversation,
            user=user,
            message=user_message,
            response=response_data['response'],
            is_caregiver_referral=response_data.get('is_caregiver_referral', False)
        )
        
        # Update conversation title if it's the first message
        if conversation.messages.count() == 1:
            conversation.title = user_message[:50] + '...' if len(user_message) > 50 else user_message
            conversation.save()
        
        # If it's a caregiver referral, save the recommendations
        if response_data.get('caregiver_recommendations'):
            for caregiver_data in response_data['caregiver_recommendations']:
                try:
                    caregiver = CaregiverProfile.objects.get(id=caregiver_data['id'])
                    CaregiverRecommendation.objects.create(
                        chat_message=chat_message,
                        caregiver=caregiver,
                        match_score=caregiver_data['match_score']
                    )
                except CaregiverProfile.DoesNotExist:
                    pass
        
        return JsonResponse({
            'response': response_data['response'],
            'is_caregiver_referral': response_data.get('is_caregiver_referral', False),
            'caregiver_recommendations': response_data.get('caregiver_recommendations', []),
            'conversation_id': conversation.id,
            'conversation_title': conversation.title
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def process_message(message, user=None):
    """Process user message and generate appropriate response using Groq AI"""
    message_lower = message.lower()
    
    # Check for caregiver referral requests
    if any(keyword in message_lower for keyword in ['caregiver', 'psw', 'personal support worker', 'find caregiver', 'need caregiver', 'recommend caregiver']):
        return handle_caregiver_request(message, user)
    
    # Get site knowledge context for AI
    site_context = get_site_knowledge_context()
    
    # Use Groq API for AI-powered responses
    ai_response = get_groq_response(message, site_context)
    
    if ai_response:
        return {
            'response': ai_response,
            'is_caregiver_referral': False
        }
    
    # Fallback to default response
    return {
        'response': get_default_response(message),
        'is_caregiver_referral': False
    }


def match_site_knowledge(message):
    """Match user message against site knowledge base"""
    message_lower = message.lower()
    
    # Try exact keyword matches first
    knowledge_items = SiteKnowledge.objects.all()
    
    for item in knowledge_items:
        # Check if any keyword matches
        if item.keywords:
            keywords = [k.strip().lower() for k in item.keywords.split(',')]
            if any(keyword in message_lower for keyword in keywords):
                return item
        
        # Check if question matches
        if item.question.lower() in message_lower:
            return item
    
    # Check for partial matches in category
    for item in knowledge_items:
        if item.category.lower() in message_lower:
            return item
    
    return None


def handle_caregiver_request(message, user):
    """Handle requests for caregiver recommendations"""
    # Extract location, skills, or other preferences from message
    location = extract_location(message)
    skills = extract_skills(message)
    
    # Query active caregivers
    caregivers = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE
    )
    
    # Filter by location if specified
    if location:
        caregivers = caregivers.filter(city__icontains=location)
    
    # Filter by skills if specified
    if skills:
        for skill in skills:
            caregivers = caregivers.filter(skills__icontains=skill)
    
    # Get top matches
    caregiver_recommendations = []
    for caregiver in caregivers[:5]:  # Return top 5
        match_score = calculate_match_score(caregiver, location, skills)
        caregiver_recommendations.append({
            'id': caregiver.id,
            'name': caregiver.user.get_full_name(),
            'city': caregiver.city,
            'skills': caregiver.skills_list,
            'hourly_rate': str(caregiver.hourly_rate) if caregiver.hourly_rate else 'Not specified',
            'match_score': match_score
        })
    
    # Sort by match score
    caregiver_recommendations.sort(key=lambda x: x['match_score'], reverse=True)
    
    response_text = f"I found {len(caregiver_recommendations)} verified caregivers for you. "
    if location:
        response_text += f"Located in or near {location}. "
    if skills:
        response_text += f"With skills in: {', '.join(skills)}. "
    response_text += "You can view their profiles and contact them through our platform."
    
    return {
        'response': response_text,
        'is_caregiver_referral': True,
        'caregiver_recommendations': caregiver_recommendations
    }


def extract_location(message):
    """Extract location from user message"""
    # Common Ontario cities
    ontario_cities = [
        'toronto', 'ottawa', 'hamilton', 'mississauga', 'brampton', 'london',
        'windsor', 'kitchener', 'waterloo', 'markham', 'vaughan', 'richmond hill',
        'barrie', 'oshawa', 'whitby', 'ajax', 'pickering', 'burlington', 'milton'
    ]
    
    message_lower = message.lower()
    for city in ontario_cities:
        if city in message_lower:
            return city.capitalize()
    
    return None


def extract_skills(message):
    """Extract caregiving skills from user message"""
    skill_keywords = {
        'personal care': ['personal care', 'bathing', 'grooming', 'hygiene'],
        'senior care': ['senior', 'elderly', 'aging', 'elder'],
        'dementia': ['dementia', 'alzheimer', 'memory'],
        'mobility': ['mobility', 'transfer', 'walking', 'movement'],
        'medication': ['medication', 'medicine', 'drugs'],
        'companionship': ['companionship', 'company', 'social', 'friendly'],
        'postpartum': ['postpartum', 'newborn', 'baby', 'infant'],
        'cooking': ['cooking', 'meal preparation', 'food', 'nutrition'],
        'light housekeeping': ['housekeeping', 'cleaning', 'chores']
    }
    
    message_lower = message.lower()
    found_skills = []
    
    for skill, keywords in skill_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            found_skills.append(skill)
    
    return found_skills


def calculate_match_score(caregiver, location, skills):
    """Calculate match score for caregiver recommendation"""
    score = 50  # Base score for being active
    
    if location and caregiver.city and location.lower() in caregiver.city.lower():
        score += 30
    
    if skills:
        caregiver_skills = [s.lower() for s in caregiver.skills_list]
        for skill in skills:
            if any(skill in cs for cs in caregiver_skills):
                score += 10
    
    return min(score, 100)  # Cap at 100


def get_site_knowledge_context():
    """Get all site knowledge as context for AI"""
    knowledge_items = SiteKnowledge.objects.all()
    context = "GetMeCare Ontario Information:\n\n"
    
    for item in knowledge_items:
        context += f"Q: {item.question}\nA: {item.answer}\n\n"
    
    return context


def get_groq_response(user_message, site_context):
    """Get AI response from Groq API"""
    try:
        api_key = getattr(settings, 'GROQ_API_KEY', None)
        if not api_key:
            return None
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = f"""You are a helpful assistant for GetMeCare Ontario, a platform that connects families with pre-vetted caregivers and Personal Support Workers (PSWs). 

Your role is to:
- Answer questions about GetMeCare's services, pricing, and how the platform works
- Provide information about caregiver verification and safety measures
- Help users understand the hiring process
- Be friendly, professional, and informative
- Always base your answers on the provided site information
- If you don't know something specific, be honest and suggest contacting support

Here is the site information you should use:
{site_context}

If the user asks about finding caregivers or needs caregiver recommendations, suggest they use the caregiver search feature or provide guidance on what to look for."""

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            print(f"Groq API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error calling Groq API: {str(e)}")
        return None


def get_default_response(message):
    """Generate default response when no specific match is found"""
    message_lower = message.lower()
    
    # Handle common greetings
    if any(greeting in message_lower for greeting in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
        return "Hello! I'm here to help you find the perfect caregiver for your needs. You can ask me about our services, how to find caregivers, or get recommendations based on your specific requirements."
    
    # Handle thanks
    if any(thank in message_lower for thank in ['thank', 'thanks', 'appreciate']):
        return "You're welcome! If you need any more help finding caregivers or have questions about our services, feel free to ask."
    
    # Handle help requests
    if 'help' in message_lower:
        return "I can help you with:\n\n• Finding verified caregivers in your area\n• Information about our services and how they work\n• Understanding caregiver qualifications and skills\n• Guidance on hiring and working with caregivers\n\nWhat would you like to know more about?"
    
    # Default
    return "I'm not sure I understood that. I can help you find caregivers, provide information about our services, or answer questions about how GetMeCare Ontario works. Could you please rephrase your question or let me know what specific information you're looking for?"


@csrf_exempt
@require_http_methods(["GET"])
def get_chat_history(request):
    """Get chat history for a user"""
    user_id = request.GET.get('user_id')
    conversation_id = request.GET.get('conversation_id')
    
    if not user_id:
        return JsonResponse({'error': 'User ID is required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
        
        if conversation_id:
            # Get messages for specific conversation
            try:
                conversation = ChatConversation.objects.get(id=conversation_id, user=user)
                messages = conversation.messages.all().order_by('created_at')
            except ChatConversation.DoesNotExist:
                return JsonResponse({'error': 'Conversation not found'}, status=404)
        else:
            # Get all messages for user (legacy support)
            messages = ChatMessage.objects.filter(user=user).order_by('-created_at')[:20]
        
        history = []
        for msg in messages:
            history.append({
                'id': msg.id,
                'message': msg.message,
                'response': msg.response,
                'is_caregiver_referral': msg.is_caregiver_referral,
                'created_at': msg.created_at.isoformat(),
                'conversation_id': msg.conversation.id if msg.conversation else None
            })
        
        return JsonResponse({'history': history})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@csrf_exempt
@require_http_methods(["GET"])
def get_conversations(request):
    """Get all conversations for a user"""
    user_id = request.GET.get('user_id')
    
    if not user_id:
        return JsonResponse({'error': 'User ID is required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
        conversations = ChatConversation.objects.filter(user=user).order_by('-updated_at')
        
        conversation_list = []
        for conv in conversations:
            conversation_list.append({
                'id': conv.id,
                'title': conv.title,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'message_count': conv.messages.count()
            })
        
        return JsonResponse({'conversations': conversation_list})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def create_conversation(request):
    """Create a new conversation"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        title = data.get('title', 'New Chat')
        
        if not user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        conversation = ChatConversation.objects.create(
            user=user,
            title=title
        )
        
        return JsonResponse({
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_conversation(request, conversation_id):
    """Delete a conversation"""
    user_id = request.GET.get('user_id')
    
    if not user_id:
        return JsonResponse({'error': 'User ID is required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
        conversation = ChatConversation.objects.get(id=conversation_id, user=user)
        conversation.delete()
        
        return JsonResponse({'success': True})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except ChatConversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
# Direct messaging views (user-to-user chat)
# ─────────────────────────────────────────────────────────────
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from .models import DirectConversation, DirectMessage


def _chat_base(user):
    """Return the right base template for the current user's role."""
    if not user.is_authenticated:
        return 'base.html'
    if user.is_admin:
        return 'base.html'
    if user.is_caregiver:
        return 'CareGiverAcc/base_caregiver.html'
    if user.is_employer:
        return 'EmployerApp/base_employer.html'
    return 'base.html'


def _get_chat_block_reason(user):
    """
    Return (redirect_name, message) if this user is not allowed to chat,
    or None if they are permitted.

    Rules:
      - Admin / staff users cannot use the chat at all
      - Caregiver must have CaregiverProfile.status == 'active'
      - Employer must have EmployerProfile.is_active == True
    """
    # Admins (superuser / staff) are not participants in employer-caregiver chat
    if user.is_admin:
        return (
            'AdminApp:dashboard',
            "Admin accounts cannot send or receive messages through the chat system.",
        )

    if user.is_caregiver:
        try:
            profile = user.caregiver_profile
        except CaregiverProfile.DoesNotExist:
            return ('Account:caregiver_dashboard',
                    "Your caregiver profile is not set up yet. Please complete your profile before messaging.")
        if profile.status != CaregiverProfile.STATUS_ACTIVE:
            status_label = profile.get_status_display()
            return ('Account:caregiver_dashboard',
                    f"Your account is currently {status_label}. "
                    "You will be able to message employers once your account is activated by an admin.")

    elif user.is_employer:
        try:
            profile = user.employer_profile
        except EmployerProfile.DoesNotExist:
            return ('EmployerApp:activate_account',
                    "Please activate your employer account before messaging caregivers.")
        if not profile.is_active:
            return ('EmployerApp:activate_account',
                    "Your employer account is not yet activated. "
                    "Please complete activation to message caregivers.")

    return None  # allowed


@login_required
def chat_list(request):
    """Show all conversations the current user is part of."""
    block = _get_chat_block_reason(request.user)
    if block:
        redirect_name, message = block
        messages.warning(request, message)
        return redirect(redirect_name)

    convs = DirectConversation.objects.filter(
        Q(participant_1=request.user) | Q(participant_2=request.user)
    ).select_related('participant_1', 'participant_2').order_by('-updated_at')

    conversations = []
    for conv in convs:
        other = conv.other_participant(request.user)
        last  = conv.last_message()
        unread = conv.unread_count(request.user)
        conversations.append({
            'conv': conv,
            'other': other,
            'last': last,
            'unread': unread,
        })

    return render(request, 'chat/chat-list.html', {
        'conversations': conversations,
        'base_template': _chat_base(request.user),
    })


@login_required
def chat_room(request, conv_id):
    """Open a conversation thread."""
    block = _get_chat_block_reason(request.user)
    if block:
        redirect_name, message = block
        messages.warning(request, message)
        return redirect(redirect_name)

    conv = get_object_or_404(
        DirectConversation,
        Q(participant_1=request.user) | Q(participant_2=request.user),
        pk=conv_id,
    )
    # Mark messages from the other person as read
    conv.direct_messages.filter(is_read=False).exclude(
        sender=request.user
    ).update(is_read=True)

    # Mark pending proposals addressed to this user as read
    BookingProposal.objects.filter(
        conversation_id=conv_id,
        employer=request.user,
        is_read=False,
    ).update(is_read=True)

    messages_qs = list(conv.direct_messages.select_related('sender').all())
    proposals_qs = list(
        BookingProposal.objects.filter(
            conversation_id=conv_id,
        ).filter(
            Q(caregiver=request.user) | Q(employer=request.user)
        ).order_by('created_at')
    )
    other = conv.other_participant(request.user)

    # Interleave messages and proposals by created_at
    chat_items = []
    for m in messages_qs:
        chat_items.append({'type': 'message', 'obj': m, 'ts': m.created_at})
    for p in proposals_qs:
        chat_items.append({'type': 'proposal', 'obj': p, 'ts': p.created_at})
    chat_items.sort(key=lambda x: x['ts'])

    return render(request, 'chat/chat-room.html', {
        'conv': conv,
        'messages': messages_qs,
        'proposals': proposals_qs,
        'chat_items': chat_items,
        'other': other,
        'base_template': _chat_base(request.user),
    })


@login_required
def chat_start(request, user_id):
    """Start or resume a conversation with any user (called from browse card)."""
    block = _get_chat_block_reason(request.user)
    if block:
        redirect_name, message = block
        messages.warning(request, message)
        return redirect(redirect_name)

    other_user = get_object_or_404(User, pk=user_id)
    if other_user == request.user:
        return redirect('chat_list')
    conv, _ = DirectConversation.get_or_create_for(request.user, other_user)
    return redirect('chat_room', conv_id=conv.pk)


@login_required
@require_POST
def chat_send(request, conv_id):
    """POST a message — returns JSON with bubble HTML + new message pk.

    Returning the pk lets the client advance its polling cursor immediately,
    preventing the poller from re-inserting the same bubble as a duplicate.
    """
    block = _get_chat_block_reason(request.user)
    if block:
        _, message = block
        return JsonResponse({'ok': False, 'error': message}, status=403)

    conv = get_object_or_404(
        DirectConversation,
        Q(participant_1=request.user) | Q(participant_2=request.user),
        pk=conv_id,
    )
    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)

    # ── PII guard ─────────────────────────────────────────────
    # Block messages that contain email addresses, phone numbers,
    # or bank / account numbers.
    pii_matches = find_pii(body)
    if pii_matches:
        return JsonResponse(
            {'ok': False, 'error': pii_error_message(pii_matches), 'pii': True},
            status=400,
        )

    # ── Server-side duplicate guard ───────────────────────────
    # Reject if the same sender sent the identical body in the last 3 seconds
    from django.utils import timezone as tz
    cutoff = tz.now() - timezone.timedelta(seconds=3)
    dup = conv.direct_messages.filter(
        sender=request.user,
        body=body,
        created_at__gte=cutoff,
    ).order_by('-pk').first()
    if dup:
        # Return the existing pk so the client can still advance its cursor
        from django.template.loader import render_to_string
        html = render_to_string(
            'chat/partials/message_bubble.html',
            {'msg': dup, 'me': request.user},
            request=request,
        )
        return JsonResponse({'ok': True, 'pk': dup.pk, 'html': html, 'duplicate': True})

    msg = DirectMessage.objects.create(
        conversation=conv,
        sender=request.user,
        body=body,
    )
    DirectConversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())

    # ── Offline email notification ─────────────────────────────
    # Notify the other participant if they have not been active recently.
    # "Offline" = no session activity in the past 5 minutes (uses last_login
    # as a lightweight proxy; replace with a proper last-seen tracker if needed).
    try:
        recipient = conv.other_participant(request.user)
        _five_min_ago = timezone.now() - timezone.timedelta(minutes=5)
        _is_offline = (
            recipient.last_login is None
            or recipient.last_login < _five_min_ago
        )
        if _is_offline and recipient.email:
            send_offline_chat_notification(
                recipient=recipient,
                sender=request.user,
                message_body=body,
                conversation_id=conv.pk,
            )
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Offline chat notification failed for conv %s', conv.pk)

    from django.template.loader import render_to_string
    html = render_to_string(
        'chat/partials/message_bubble.html',
        {'msg': msg, 'me': request.user},
        request=request,
    )
    return JsonResponse({'ok': True, 'pk': msg.pk, 'html': html, 'duplicate': False})


@login_required
def chat_poll(request, conv_id):
    """Polling endpoint — return any messages after `after` (message pk).

    Includes ALL new messages (both sides) so the client can deduplicate by
    DOM id rather than relying on the server to exclude the sender's own
    messages (which causes them to go missing when the optimistic bubble
    was never inserted, e.g. after a page reload mid-send).
    """
    conv = get_object_or_404(
        DirectConversation,
        Q(participant_1=request.user) | Q(participant_2=request.user),
        pk=conv_id,
    )
    after_pk = request.GET.get('after', 0)
    try:
        after_pk = int(after_pk)
    except (ValueError, TypeError):
        after_pk = 0

    new_msgs = conv.direct_messages.filter(
        pk__gt=after_pk
    ).select_related('sender').order_by('pk')

    # Mark incoming messages as read
    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    return render(request, 'chat/partials/poll_messages.html', {
        'messages': new_msgs,
        'me': request.user,
    })


# ─── Admin monitor ────────────────────────────────────────────
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def admin_chat_monitor(request):
    """Admin view — see all conversations and messages on the platform."""
    convs = DirectConversation.objects.all().select_related(
        'participant_1', 'participant_2'
    ).order_by('-updated_at')

    # Optional: filter by conversation
    selected_conv = None
    messages = []
    conv_id = request.GET.get('conv')
    if conv_id:
        selected_conv = get_object_or_404(DirectConversation, pk=conv_id)
        messages = selected_conv.direct_messages.select_related('sender').all()

    conversations = []
    for conv in convs:
        last = conv.last_message()
        conversations.append({'conv': conv, 'last': last})

    return render(request, 'chat/admin-chat-monitor.html', {
        'conversations': conversations,
        'selected_conv': selected_conv,
        'messages': messages,
    })


# ─────────────────────────────────────────────────────────────
# Booking Proposal views (caregiver → employer)
# ─────────────────────────────────────────────────────────────
from django.template.loader import render_to_string


@login_required
@require_POST
def send_proposal(request, conv_id):
    """Caregiver sends a price proposal inside a chat thread."""
    if not request.user.is_caregiver:
        return JsonResponse({'error': 'Only caregivers can send proposals.'}, status=403)

    conv = get_object_or_404(
        DirectConversation,
        Q(participant_1=request.user) | Q(participant_2=request.user),
        pk=conv_id,
    )
    employer = conv.other_participant(request.user)
    if not employer.is_employer:
        return JsonResponse({'error': 'The other participant is not an employer.'}, status=400)

    try:
        rate = request.POST.get('rate', '').strip()
        from decimal import Decimal, InvalidOperation
        rate = Decimal(rate)
        if rate <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return JsonResponse({'error': 'Invalid rate.'}, status=400)

    message = request.POST.get('message', '').strip()[:255]

    # Expire any existing pending proposals in this conversation
    BookingProposal.objects.filter(
        conversation_id=conv_id,
        caregiver=request.user,
        employer=employer,
        status=BookingProposal.STATUS_PENDING,
    ).update(status=BookingProposal.STATUS_EXPIRED)

    proposal = BookingProposal.objects.create(
        conversation_id=conv_id,
        caregiver=request.user,
        employer=employer,
        negotiated_rate=rate,
        message=message,
        status=BookingProposal.STATUS_PENDING,
    )

    html = render_to_string(
        'chat/partials/proposal_card.html',
        {'proposal': proposal, 'me': request.user},
        request=request,
    )
    return JsonResponse({'html': html, 'proposal_pk': proposal.pk})


@login_required
def poll_proposals(request, conv_id):
    """Return updated/new proposal cards after a given pk for HTMX polling."""
    conv = get_object_or_404(
        DirectConversation,
        Q(participant_1=request.user) | Q(participant_2=request.user),
        pk=conv_id,
    )
    after_pk = request.GET.get('after', 0)
    try:
        after_pk = int(after_pk)
    except (ValueError, TypeError):
        after_pk = 0

    proposals = BookingProposal.objects.filter(
        conversation_id=conv_id,
        pk__gt=after_pk,
    ).filter(
        Q(caregiver=request.user) | Q(employer=request.user)
    ).order_by('pk')

    html_parts = []
    for p in proposals:
        html_parts.append(
            render_to_string(
                'chat/partials/proposal_card.html',
                {'proposal': p, 'me': request.user},
                request=request,
            )
        )
    return HttpResponse(''.join(html_parts))


@login_required
@require_POST
def decline_proposal(request, proposal_pk):
    """Employer declines a proposal."""
    proposal = get_object_or_404(
        BookingProposal,
        pk=proposal_pk,
        employer=request.user,
        status=BookingProposal.STATUS_PENDING,
    )
    proposal.status = BookingProposal.STATUS_DECLINED
    proposal.save(update_fields=['status', 'updated_at'])
    return redirect('chat_room', conv_id=proposal.conversation_id)


# ─────────────────────────────────────────────────────────────
# Live Support Chat (HTMX real-time)
# ─────────────────────────────────────────────────────────────

@login_required
def support_chat(request):
    """User-facing support chat page."""
    chat = SupportChat.objects.filter(user=request.user, is_resolved=False).first()
    if not chat:
        chat = SupportChat.objects.create(user=request.user)
    return redirect('support_chat_detail', chat_id=chat.pk)


@login_required
def support_chat_detail(request, chat_id):
    """Show a specific support chat for the current user."""
    chat = get_object_or_404(SupportChat, pk=chat_id, user=request.user)
    messages_qs = chat.messages.select_related('sender').all()
    return render(request, 'chat/support-chat.html', {
        'chat': chat,
        'messages': messages_qs,
        'base_template': _chat_base(request.user),
    })


@login_required
@require_POST
def support_chat_send(request, chat_id):
    """User sends a support message."""
    chat = get_object_or_404(SupportChat, pk=chat_id, user=request.user)
    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)

    pii_matches = find_pii(body)
    if pii_matches:
        return JsonResponse(
            {'ok': False, 'error': pii_error_message(pii_matches), 'pii': True},
            status=400,
        )

    from django.utils import timezone as tz
    cutoff = tz.now() - timezone.timedelta(seconds=3)
    dup = chat.messages.filter(
        sender=request.user,
        body=body,
        created_at__gte=cutoff,
    ).order_by('-pk').first()
    if dup:
        html = render_to_string(
            'chat/partials/support_message.html',
            {'msg': dup, 'me': request.user},
            request=request,
        )
        return JsonResponse({'ok': True, 'pk': dup.pk, 'html': html, 'duplicate': True})

    msg = SupportMessage.objects.create(
        chat=chat,
        sender=request.user,
        body=body,
    )
    SupportChat.objects.filter(pk=chat.pk).update(updated_at=timezone.now())

    # Notify admin if offline (last_login > 5 min ago) — user sent this message
    try:
        from django.contrib.auth import get_user_model as _gum
        _admins = _gum().objects.filter(is_staff=True, email__isnull=False).exclude(email='')
        _five_min_ago = timezone.now() - timezone.timedelta(minutes=5)
        for _admin in _admins:
            if _admin.last_login is None or _admin.last_login < _five_min_ago:
                send_support_offline_notification(
                    recipient=_admin,
                    sender=request.user,
                    message_body=body,
                    chat_id=chat.pk,
                    is_admin=True,
                )
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Support offline admin email failed for chat %s', chat.pk)

    html = render_to_string(
        'chat/partials/support_message.html',
        {'msg': msg, 'me': request.user},
        request=request,
    )
    return JsonResponse({'ok': True, 'pk': msg.pk, 'html': html, 'duplicate': False})


@login_required
def support_chat_poll(request, chat_id):
    """HTMX poll endpoint — return any new messages after `after` pk."""
    chat = get_object_or_404(SupportChat, pk=chat_id, user=request.user)
    after_pk = request.GET.get('after', 0)
    try:
        after_pk = int(after_pk)
    except (ValueError, TypeError):
        after_pk = 0

    new_msgs = chat.messages.filter(
        pk__gt=after_pk
    ).select_related('sender').order_by('pk')

    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    return render(request, 'chat/partials/support_messages_poll.html', {
        'messages': new_msgs,
        'me': request.user,
    })


# ── Admin support views ──────────────────────────────────────

@staff_member_required
def admin_support(request):
    """Admin dashboard — see all active support chats."""
    chats = SupportChat.objects.filter(is_resolved=False).select_related('user').order_by('-updated_at')
    resolved = SupportChat.objects.filter(is_resolved=True).select_related('user').order_by('-updated_at')[:50]

    selected_chat = None
    messages = []
    chat_id = request.GET.get('chat')
    if chat_id:
        selected_chat = get_object_or_404(SupportChat, pk=chat_id)
        messages = selected_chat.messages.select_related('sender').all()

    return render(request, 'chat/admin-support.html', {
        'chats': chats,
        'resolved': resolved,
        'selected_chat': selected_chat,
        'messages': messages,
    })


@staff_member_required
@require_POST
def admin_support_reply(request, chat_id):
    """Admin replies to a support chat."""
    chat = get_object_or_404(SupportChat, pk=chat_id)
    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)

    pii_matches = find_pii(body)
    if pii_matches:
        return JsonResponse(
            {'ok': False, 'error': pii_error_message(pii_matches), 'pii': True},
            status=400,
        )

    from django.utils import timezone as tz
    cutoff = tz.now() - timezone.timedelta(seconds=3)
    dup = chat.messages.filter(
        sender=request.user,
        body=body,
        created_at__gte=cutoff,
    ).order_by('-pk').first()
    if dup:
        html = render_to_string(
            'chat/partials/support_message.html',
            {'msg': dup, 'me': request.user},
            request=request,
        )
        return JsonResponse({'ok': True, 'pk': dup.pk, 'html': html, 'duplicate': True})

    msg = SupportMessage.objects.create(
        chat=chat,
        sender=request.user,
        body=body,
    )
    SupportChat.objects.filter(pk=chat.pk).update(updated_at=timezone.now())

    # Notify the user if offline — admin just replied
    try:
        _five_min_ago = timezone.now() - timezone.timedelta(minutes=5)
        _user = chat.user
        if _user.last_login is None or _user.last_login < _five_min_ago:
            send_support_offline_notification(
                recipient=_user,
                sender=request.user,
                message_body=body,
                chat_id=chat.pk,
                is_admin=False,
            )
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Support offline user email failed for chat %s', chat.pk)

    html = render_to_string(
        'chat/partials/support_message.html',
        {'msg': msg, 'me': request.user},
        request=request,
    )
    return JsonResponse({'ok': True, 'pk': msg.pk, 'html': html, 'duplicate': False})


@staff_member_required
def admin_support_poll(request, chat_id):
    """HTMX poll endpoint for admin — return any new messages after `after` pk."""
    chat = get_object_or_404(SupportChat, pk=chat_id)
    after_pk = request.GET.get('after', 0)
    try:
        after_pk = int(after_pk)
    except (ValueError, TypeError):
        after_pk = 0

    new_msgs = chat.messages.filter(
        pk__gt=after_pk
    ).select_related('sender').order_by('pk')

    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    return render(request, 'chat/partials/support_messages_poll.html', {
        'messages': new_msgs,
        'me': request.user,
    })


@staff_member_required
@require_POST
def admin_support_resolve(request, chat_id):
    """Mark a support chat as resolved."""
    chat = get_object_or_404(SupportChat, pk=chat_id)
    chat.is_resolved = True
    chat.save(update_fields=['is_resolved', 'updated_at'])
    # Notify the user their support request has been resolved
    try:
        send_support_resolved_email(chat.user, chat)
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Support resolved email failed for chat %s', chat_id)
    return redirect('admin_support')
