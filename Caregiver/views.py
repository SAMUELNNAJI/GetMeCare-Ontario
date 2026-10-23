import time
import uuid

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Q, F
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from Account.models import CaregiverProfile, JobPosting, Shift
from AdminApp.models import Faq, Service, BlogPost, BlogComment

# Contact-form submissions are delivered to this inbox (admin notification).
CONTACT_FORM_INBOX = 'getmecareontario@gmail.com'


def home(request):
    verified_caregivers = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE,
        account_status='active',
    ).select_related('user').order_by('-created_at')[:3]
    recent_blogs = BlogPost.objects.filter(
        is_published=True
    ).order_by('-published_at')[:6]
    return render(request, 'Caregiver/index.html', {
        'verified_caregivers': verified_caregivers,
        'recent_blogs': recent_blogs,
    })



def browse(request):
    """Browse caregivers — paginated 20, with city / care-type / rate filters."""
    qs = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE,
        account_status='active',
    ).select_related('user').annotate(
        avg_rating=Avg(
            'user__received_caregiver_reviews__rating',
            filter=Q(user__received_caregiver_reviews__shift__status=Shift.STATUS_COMPLETED),
        ),
        review_count=Count(
            'user__received_caregiver_reviews',
            filter=Q(user__received_caregiver_reviews__shift__status=Shift.STATUS_COMPLETED),
        ),
    ).order_by('user__first_name')

    # ── Filters ──────────────────────────────────────────────
    city      = request.GET.get('city', '').strip()
    care_type = request.GET.get('care_type', '').strip()
    rate_min  = request.GET.get('rate_min', '')
    rate_max  = request.GET.get('rate_max', '')
    sort      = request.GET.get('sort', '')

    if city:
        qs = qs.filter(city__icontains=city)
    if care_type:
        qs = qs.filter(skills__icontains=care_type)
    if rate_min:
        try:
            qs = qs.filter(hourly_rate__gte=float(rate_min))
        except ValueError:
            pass
    if rate_max:
        try:
            qs = qs.filter(hourly_rate__lte=float(rate_max))
        except ValueError:
            pass

    if sort == 'rate_asc':
        qs = qs.order_by('hourly_rate')
    elif sort == 'rate_desc':
        qs = qs.order_by('-hourly_rate')
    elif sort == 'newest':
        qs = qs.order_by('-created_at')
    # default: alphabetical (already set above)

    paginator  = Paginator(qs, 20)
    page_num   = request.GET.get('page', 1)
    page_obj   = paginator.get_page(page_num)

    # Build distinct city list for filter sidebar
    cities = (
        CaregiverProfile.objects
        .filter(status=CaregiverProfile.STATUS_ACTIVE, account_status='active')
        .exclude(city='')
        .values_list('city', flat=True)
        .distinct()
        .order_by('city')
    )

    return render(request, 'Caregiver/browse.html', {
        'page_obj':   page_obj,
        'total':      paginator.count,
        'city':       city,
        'care_type':  care_type,
        'rate_min':   rate_min,
        'rate_max':   rate_max,
        'sort':       sort,
        'cities':     cities,
    })


def browse_jobs(request):
    """Browse open job postings — paginated 30, with city / care-type / schedule filters."""
    qs = JobPosting.objects.filter(
        status=JobPosting.STATUS_OPEN
    ).select_related('employer').order_by('-created_at')

    # ── Filters ──────────────────────────────────────────────
    city      = request.GET.get('city', '').strip()
    care_type = request.GET.get('care_type', '').strip()
    schedule  = request.GET.get('schedule', '').strip()
    rate_min  = request.GET.get('rate_min', '')
    rate_max  = request.GET.get('rate_max', '')
    sort      = request.GET.get('sort', '')

    if city:
        qs = qs.filter(city__icontains=city)
    if care_type:
        qs = qs.filter(care_type=care_type)
    if schedule:
        qs = qs.filter(schedule=schedule)
    if rate_min:
        try:
            qs = qs.filter(hourly_rate__gte=float(rate_min))
        except ValueError:
            pass
    if rate_max:
        try:
            qs = qs.filter(hourly_rate__lte=float(rate_max))
        except ValueError:
            pass

    if sort == 'rate_asc':
        qs = qs.order_by('hourly_rate')
    elif sort == 'rate_desc':
        qs = qs.order_by('-hourly_rate')
    elif sort == 'oldest':
        qs = qs.order_by('created_at')
    # default: newest first (already set above)

    paginator = Paginator(qs, 30)
    page_num  = request.GET.get('page', 1)
    page_obj  = paginator.get_page(page_num)

    # Distinct cities for sidebar
    cities = (
        JobPosting.objects
        .filter(status=JobPosting.STATUS_OPEN)
        .exclude(city='')
        .values_list('city', flat=True)
        .distinct()
        .order_by('city')
    )

    return render(request, 'Caregiver/browse-jobs.html', {
        'page_obj':   page_obj,
        'total':      paginator.count,
        'city':       city,
        'care_type':  care_type,
        'schedule':   schedule,
        'rate_min':   rate_min,
        'rate_max':   rate_max,
        'sort':       sort,
        'cities':     cities,
        'care_type_choices': JobPosting.CARE_TYPE_CHOICES,
        'schedule_choices':  JobPosting.SCHEDULE_CHOICES,
    })


def how_it_works(request):
    faqs = Faq.objects.filter(is_active=True).order_by('order', 'category', 'question')
    return render(request, 'Caregiver/how_it_works.html', {'faqs': faqs})


def services(request):
    services = Service.objects.filter(is_active=True).order_by('order', 'title')
    return render(request, 'Caregiver/services.html', {'services': services})


def contact(request):
    from Caregiver.antispam import generate_contact_challenge, check_contact_submission
    from django.contrib import messages as dj_messages

    if request.method == 'POST':
        is_valid, err_msg, is_bot = check_contact_submission(request)

        # ── Honeypot or bot caught: fake success silently (bots move on, zero spam sent) ──
        if is_bot:
            dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            n1, n2, tok = generate_contact_challenge()
            return render(request, 'Caregiver/contact.html', {
                'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
            })

        # ── Verification failed ──
        if not is_valid:
            dj_messages.error(request, err_msg)
            n1, n2, tok = generate_contact_challenge()
            return render(request, 'Caregiver/contact.html', {
                'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok,
                'form_data': request.POST,
            })

        first_name = request.POST.get('firstName', '').strip()
        last_name  = request.POST.get('lastName', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', '').strip()
        subject    = request.POST.get('subject', '').strip()
        message    = request.POST.get('message', '').strip()

        if first_name and last_name and email and role and subject and message:
            plain_body = (
                f"New verified contact form inquiry:\n\n"
                f"Name: {first_name} {last_name}\n"
                f"Email: {email}\n"
                f"Phone: {phone or 'Not provided'}\n"
                f"Role: {role}\n\n"
                f"Subject: {subject}\n\n"
                f"Message:\n{message}"
            )

            ok = False
            try:
                from django.conf import settings as _s
                from django.core.mail import get_connection, EmailMessage

                gmail_user = getattr(_s, 'GMAIL_USER', '') or CONTACT_FORM_INBOX
                gmail_pass = getattr(_s, 'GMAIL_APP_PASSWORD', '')

                clean_pass = (gmail_pass or '').replace(' ', '').strip()
                if len(clean_pass) >= 32 and clean_pass[:16] == clean_pass[16:32]:
                    clean_pass = clean_pass[:16]

                if not gmail_user or not clean_pass:
                    import logging as _log
                    _log.getLogger(__name__).error(
                        "Contact form cannot send via Gmail: GMAIL_USER or GMAIL_APP_PASSWORD missing."
                    )
                else:
                    try:
                        conn = get_connection(
                            backend='django.core.mail.backends.smtp.EmailBackend',
                            host='smtp.gmail.com',
                            port=587,
                            username=gmail_user,
                            password=clean_pass,
                            use_tls=True,
                            timeout=15,
                        )
                        email_msg = EmailMessage(
                            subject=f'[Contact Form] {subject} — {first_name} {last_name}',
                            body=plain_body,
                            from_email=gmail_user,
                            to=[CONTACT_FORM_INBOX],
                            reply_to=[email],
                            connection=conn,
                        )
                        email_msg.send(fail_silently=False)
                        ok = True
                    except Exception:
                        # Fallback to SSL 465
                        conn_ssl = get_connection(
                            backend='django.core.mail.backends.smtp.EmailBackend',
                            host='smtp.gmail.com',
                            port=465,
                            username=gmail_user,
                            password=clean_pass,
                            use_ssl=True,
                            timeout=15,
                        )
                        email_msg = EmailMessage(
                            subject=f'[Contact Form] {subject} — {first_name} {last_name}',
                            body=plain_body,
                            from_email=gmail_user,
                            to=[CONTACT_FORM_INBOX],
                            reply_to=[email],
                            connection=conn_ssl,
                        )
                        email_msg.send(fail_silently=False)
                        ok = True
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).exception('Contact form email failed via Gmail: %s', exc)
                ok = False

            if ok:
                dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            else:
                dj_messages.error(request, "Sorry, there was a problem sending your message. Please email us directly at getmecareontario@gmail.com.")
        else:
            dj_messages.error(request, 'Please fill in all required fields.')

        n1, n2, tok = generate_contact_challenge()
        return render(request, 'Caregiver/contact.html', {
            'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
        })

    # GET request
    n1, n2, tok = generate_contact_challenge()
    return render(request, 'Caregiver/contact.html', {
        'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
    })


def privacy(request):
    return render(request, 'Caregiver/privacy.html')


def terms(request):
    return render(request, 'Caregiver/terms.html')


def caregiver_profile(request, pk):
    """Public profile page for a single active caregiver."""
    profile = get_object_or_404(
        CaregiverProfile.objects.select_related('user'),
        pk=pk,
        status=CaregiverProfile.STATUS_ACTIVE,
        account_status='active',
    )
    # Star-fill percentage for the 1-5 public credibility rating (real data,
    # averaged from completed-shift employer reviews only).
    try:
        rating_value = profile.rating or 0
    except Exception:
        rating_value = 0
    rating_pct = int(round(float(rating_value) / 5 * 100))

    return render(request, 'Caregiver/caregiver-profile.html', {
        'profile': profile,
        'rating_pct': rating_pct,
    })


# ──────────────────────────────────────────────────────────────
# Public Blog & Educational Guides
# ──────────────────────────────────────────────────────────────

def blog_index(request):
    """
    Public listing of all published blog posts with category filtering,
    search, pagination, and featured article hero.
    """
    import json
    from django.urls import reverse

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    tag = request.GET.get('tag', '').strip()

    qs = BlogPost.objects.filter(is_published=True).order_by('-published_at')

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(excerpt__icontains=q) |
            Q(content__icontains=q) |
            Q(tags__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    if tag:
        qs = qs.filter(tags__icontains=tag)

    # Categories with published counts
    category_counts = []
    for cat_key, cat_label in BlogPost.CATEGORY_CHOICES:
        count = BlogPost.objects.filter(is_published=True, category=cat_key).count()
        category_counts.append({
            'key': cat_key,
            'label': cat_label,
            'count': count,
        })

    # Featured post (for hero callout on page 1)
    featured_post = None
    page_number = request.GET.get('page', 1)
    try:
        page_num_int = int(page_number)
    except ValueError:
        page_num_int = 1

    if page_num_int == 1 and not q and not category and not tag:
        featured_post = qs.filter(is_featured=True).first() or qs.first()

    grid_qs = qs.exclude(pk=featured_post.pk) if featured_post else qs
    paginator = Paginator(grid_qs, 9)
    page_obj = paginator.get_page(page_number)

    # Breadcrumb JSON-LD
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": request.build_absolute_uri('/')
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Ontario Caregiver & Family Blog",
                "item": request.build_absolute_uri(reverse('blog_index'))
            }
        ]
    }

    return render(request, 'Caregiver/blog-index.html', {
        'page_obj': page_obj,
        'posts': page_obj,
        'featured_post': featured_post,
        'search_q': q,
        'category_filter': category,
        'tag_filter': tag,
        'category_counts': category_counts,
        'total_posts': paginator.count,
        'breadcrumb_schema_json': json.dumps(breadcrumb_schema),
    })


def blog_detail(request, slug):
    """
    Public article detail page optimized for Google SEO (JSON-LD, OpenGraph,
    Twitter cards, semantic HTML, related posts, and view counts).
    """
    import json
    from django.urls import reverse

    # Allow staff to preview unpublished drafts
    if request.user.is_staff or request.user.is_superuser:
        post = get_object_or_404(BlogPost, slug=slug)
    else:
        post = get_object_or_404(BlogPost, slug=slug, is_published=True)

    # Increment view count
    BlogPost.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)

    # Related posts in same category or recent
    related_posts = BlogPost.objects.filter(
        is_published=True
    ).exclude(pk=post.pk).filter(
        category=post.category
    ).order_by('-published_at')[:3]

    if len(related_posts) < 3:
        fallback_posts = BlogPost.objects.filter(
            is_published=True
        ).exclude(pk=post.pk).exclude(
            pk__in=[p.pk for p in related_posts]
        ).order_by('-published_at')[:3 - len(related_posts)]
        related_posts = list(related_posts) + list(fallback_posts)

    canonical_url = request.build_absolute_uri(post.get_absolute_url())

    # Build absolute image URL
    img_src = post.display_image
    if img_src.startswith('/'):
        image_url = request.build_absolute_uri(img_src)
    else:
        image_url = img_src

    # JSON-LD Schema.org for BlogPosting
    article_schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url
        },
        "headline": post.title,
        "description": post.seo_description,
        "image": [image_url],
        "datePublished": post.published_at.isoformat(),
        "dateModified": post.updated_at.isoformat(),
        "author": {
            "@type": "Person",
            "name": post.author_name,
            "jobTitle": post.author_role
        },
        "publisher": {
            "@type": "Organization",
            "name": "GetMeCare Ontario",
            "url": request.build_absolute_uri('/'),
            "logo": {
                "@type": "ImageObject",
                "url": request.build_absolute_uri('/static/Caregiver/images/sitelog.png')
            }
        },
        "keywords": post.tags
    }

    # Breadcrumb JSON-LD
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": request.build_absolute_uri('/')
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Blog & Guides",
                "item": request.build_absolute_uri(reverse('blog_index'))
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": post.title,
                "item": canonical_url
            }
        ]
    }

    # Fetch approved top-level comments with replies
    comments_qs = post.comments.filter(
        is_approved=True, parent=None
    ).select_related('user').prefetch_related(
        'replies', 'replies__user'
    ).order_by('-created_at')
    total_comments_count = post.comments.filter(is_approved=True).count()

    # Paginate top-level comments (5 per page)
    comments_paginator = Paginator(comments_qs, 5)
    comment_page_number = request.GET.get('c_page', 1)
    comments_page = comments_paginator.get_page(comment_page_number)

    # Ajax response for comment pagination
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and 'c_page' in request.GET:
        from django.template.loader import render_to_string
        comments_html = render_to_string('Caregiver/partials/blog_comments_list.html', {
            'comments_page': comments_page,
            'post': post,
            'user': request.user,
        }, request=request)
        return JsonResponse({
            'success': True,
            'comments_html': comments_html,
            'current_page': comments_page.number,
            'total_pages': comments_paginator.num_pages,
            'total_comments': total_comments_count,
            'has_next': comments_page.has_next(),
            'has_previous': comments_page.has_previous(),
        })

    return render(request, 'Caregiver/blog-detail.html', {
        'post': post,
        'related_posts': related_posts,
        'canonical_url': canonical_url,
        'image_url': image_url,
        'article_schema_json': json.dumps(article_schema),
        'breadcrumb_schema_json': json.dumps(breadcrumb_schema),
        'comments': comments_page,
        'comments_page': comments_page,
        'total_comments_count': total_comments_count,
    })


@require_POST
def blog_comment_add(request, post_id):
    """
    Ajax endpoint: add a comment or reply to a blog post.
    Supports both registered users and guest visitors.
    """
    post = get_object_or_404(BlogPost, pk=post_id)
    content = request.POST.get('content', '').strip()
    parent_id = request.POST.get('parent_id', '').strip()

    if not content:
        return JsonResponse({'success': False, 'error': 'Comment cannot be empty.'}, status=400)

    guest_token = None
    if request.user.is_authenticated:
        author_name = request.user.get_full_name() or request.user.username
        author_email = request.user.email
        user = request.user
    else:
        author_name = request.POST.get('author_name', '').strip() or 'Guest Reader'
        author_email = request.POST.get('author_email', '').strip()
        user = None
        guest_token = uuid.uuid4().hex
        # Save token in session so this browser can edit/delete
        session_tokens = request.session.get('guest_comment_tokens', [])
        session_tokens.append(guest_token)
        request.session['guest_comment_tokens'] = session_tokens
        request.session.modified = True

    parent = None
    if parent_id:
        try:
            parent = BlogComment.objects.get(pk=parent_id, post=post)
        except BlogComment.DoesNotExist:
            parent = None

    comment = BlogComment.objects.create(
        post=post,
        user=user,
        author_name=author_name,
        author_email=author_email,
        content=content,
        parent=parent,
        guest_token=guest_token,
        is_approved=True,
    )

    total_count = post.comments.filter(is_approved=True).count()

    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'author_name': comment.author_name,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%b %d, %Y at %I:%M %p'),
            'avatar_letter': (comment.author_name[:1] or 'G').upper(),
            'is_user': bool(comment.user),
            'parent_id': comment.parent_id,
            'guest_token': guest_token or '',
            'can_manage': True,
        },
        'total_comments': total_count,
        'message': 'Comment posted successfully!'
    })


@require_POST
def blog_comment_edit(request, comment_id):
    """
    Ajax endpoint: edit an existing comment or reply.
    Verifies user ownership or guest token.
    """
    comment = get_object_or_404(BlogComment, pk=comment_id)
    client_token = request.POST.get('guest_token', '').strip()

    if not comment.can_manage(request, client_token=client_token):
        return JsonResponse({'success': False, 'error': 'You do not have permission to edit this comment.'}, status=403)

    new_content = request.POST.get('content', '').strip()
    if not new_content:
        return JsonResponse({'success': False, 'error': 'Comment content cannot be empty.'}, status=400)

    comment.content = new_content
    comment.save(update_fields=['content', 'updated_at'])

    return JsonResponse({
        'success': True,
        'comment_id': comment.id,
        'content': comment.content,
        'updated_at': comment.updated_at.strftime('%b %d, %Y at %I:%M %p'),
        'message': 'Comment updated successfully!'
    })


@require_POST
def blog_comment_delete(request, comment_id):
    """
    Ajax endpoint: delete an existing comment or reply.
    Verifies user ownership or guest token.
    """
    comment = get_object_or_404(BlogComment, pk=comment_id)
    client_token = request.POST.get('guest_token', '').strip()

    if not comment.can_manage(request, client_token=client_token):
        return JsonResponse({'success': False, 'error': 'You do not have permission to delete this comment.'}, status=403)

    post = comment.post
    del_id = comment.id
    comment.delete()

    total_count = post.comments.filter(is_approved=True).count()

    return JsonResponse({
        'success': True,
        'comment_id': del_id,
        'total_comments': total_count,
        'message': 'Comment deleted successfully!'
    })


