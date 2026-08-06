from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.conf import settings
from .models import ChatConversation, ChatMessage, SiteKnowledge, CaregiverRecommendation
from Account.models import CaregiverProfile
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