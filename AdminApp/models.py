from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.conf import settings


class SiteSettings(models.Model):
    """
    Singleton model — only one row ever exists (pk=1).
    Use SiteSettings.get() everywhere instead of querying directly.
    """
    activation_fee_enabled = models.BooleanField(
        default=True,
        help_text=(
            'When ON: new employers must pay the $39.99 activation fee. '
            'When OFF: all employers get instant free access. '
            'Existing fee-exempt employers are never affected by toggling this back ON.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        state = 'ON' if self.activation_fee_enabled else 'OFF'
        return f'Site Settings (activation fee: {state})'

    @classmethod
    def get(cls):
        """Return the singleton row, creating it if it does not exist."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Faq(models.Model):
    """A single FAQ (question & answer) shown on the site FAQ page."""

    CAT_GENERAL      = 'general'
    CAT_SERVICES     = 'services'
    CAT_PRICING      = 'pricing'
    CAT_HOW_IT_WORKS = 'how_it_works'
    CAT_VERIFICATION = 'verification'
    CAT_SCHEDULING   = 'scheduling'
    CAT_PAYMENTS     = 'payments'
    CAT_CAREGIVERS   = 'caregivers'
    CAT_COVERAGE     = 'coverage'
    CAT_SUPPORT      = 'support'

    CATEGORY_CHOICES = [
        (CAT_GENERAL,      'General'),
        (CAT_SERVICES,     'Services'),
        (CAT_PRICING,      'Pricing & Rates'),
        (CAT_HOW_IT_WORKS, 'How It Works'),
        (CAT_VERIFICATION, 'Caregiver Verification'),
        (CAT_SCHEDULING,   'Scheduling'),
        (CAT_PAYMENTS,     'Payments'),
        (CAT_CAREGIVERS,   'For Caregivers'),
        (CAT_COVERAGE,     'Coverage'),
        (CAT_SUPPORT,      'Support'),
    ]

    question   = models.CharField(max_length=255, help_text="The question shown to visitors.")
    answer     = models.TextField(help_text="The full answer body.")
    category   = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CAT_GENERAL)
    is_active  = models.BooleanField(default=True, help_text="Unchecked hides this FAQ from the public site.")
    order      = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'category', 'question']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question


class Service(models.Model):
    """A care service offered by GetMeCare, manageable from the admin panel."""

    title               = models.CharField(max_length=120, help_text="e.g. Personal Support Worker (PSW)")
    slug              = models.SlugField(max_length=130, unique=True, help_text="URL-friendly identifier used in links.")
    short_description   = models.CharField(max_length=255, help_text="One-line summary shown on the service cards.")
    description         = models.TextField(help_text="Full description shown on the service detail page.")
    image              = models.ImageField(upload_to='services/', blank=True, null=True, help_text="Card image (optional). Falls back to icon.")
    icon              = models.CharField(max_length=50, blank=True, help_text="Font Awesome class, e.g. fa-heartbeat")
    rate              = models.CharField(max_length=50, blank=True, help_text="e.g. From $28 CAD/hr")
    tag               = models.CharField(max_length=30, blank=True, help_text="Badge text, e.g. Most Popular")
    is_active         = models.BooleanField(default=True, help_text="Unchecked hides this service from the public site.")
    order             = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    @property
    def rate_from(self):
        if not self.rate:
            return ''
        rate = self.rate.strip()
        if rate.lower().startswith('from '):
            return 'From '
        return ''

    @property
    def rate_amount(self):
        if not self.rate:
            return ''
        rate = self.rate.strip()
        if rate.lower().startswith('from '):
            return rate[5:].strip()
        return rate

    @property
    def tag_color(self):
        colors = ['teal', 'yellow', 'pink', 'green', 'grey']
        return colors[(self.pk or 0) % len(colors)]

    def save(self, *args, **kwargs):
        # Auto-populate the slug from the title if it is empty.
        if not self.slug and self.title:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class BlogPost(models.Model):
    """
    Blog posts for SEO, educational content, caregiver guides, and family resources.
    """
    CAT_CAREGIVER_TIPS  = 'caregiver_tips'
    CAT_FAMILY_GUIDE    = 'family_guide'
    CAT_SENIOR_CARE     = 'senior_care'
    CAT_ONTARIO_HEALTH  = 'ontario_health'
    CAT_PSW_CAREER      = 'psw_career'

    CATEGORY_CHOICES = [
        (CAT_CAREGIVER_TIPS,  'Caregiver & PSW Tips'),
        (CAT_FAMILY_GUIDE,    'Family & Care Seekers'),
        (CAT_SENIOR_CARE,     'Senior & Dementia Care'),
        (CAT_ONTARIO_HEALTH,  'Ontario Healthcare & Funding'),
        (CAT_PSW_CAREER,      'PSW Career & Growth'),
    ]

    title               = models.CharField(max_length=250, help_text="Article title for readers and search engines")
    slug                = models.SlugField(max_length=260, unique=True, db_index=True, help_text="SEO URL slug, e.g. how-to-hire-psw-ontario")
    category            = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CAT_FAMILY_GUIDE)
    author_name         = models.CharField(max_length=120, default="Getmecare-Ontario")
    author_role         = models.CharField(max_length=120, default="Ontario Home Care & PSW Network")
    author_avatar       = models.ImageField(upload_to='blog/authors/', blank=True, null=True)
    featured_image      = models.ImageField(upload_to='blog/', blank=True, null=True, help_text="Upload custom blog cover")
    featured_image_url  = models.URLField(blank=True, max_length=500, help_text="External image URL fallback (e.g. Unsplash CDN)")
    image_alt           = models.CharField(max_length=200, blank=True, help_text="SEO alt text for image")
    excerpt             = models.TextField(help_text="Short engaging summary (1-2 sentences) shown on cards and search results")
    content             = models.TextField(help_text="Full post content in HTML or rich text format")
    tags                = models.CharField(max_length=250, blank=True, help_text="Comma-separated keywords e.g. psw, home care, dementia, ontario")
    meta_title          = models.CharField(max_length=160, blank=True, help_text="Custom SEO title tag (leaves default if empty)")
    meta_description    = models.CharField(max_length=300, blank=True, help_text="Custom SEO meta description (uses excerpt if empty)")
    meta_keywords       = models.CharField(max_length=250, blank=True, help_text="Comma-separated keywords for meta tags")
    read_time_minutes   = models.PositiveIntegerField(default=5, help_text="Estimated reading time in minutes")
    is_published        = models.BooleanField(default=True, db_index=True)
    is_featured         = models.BooleanField(default=False, help_text="Highlight in banners / top placement")
    views_count         = models.PositiveIntegerField(default=0)
    published_at        = models.DateTimeField(default=timezone.now, db_index=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']
        verbose_name = 'Blog Post'
        verbose_name_plural = 'Blog Posts'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            from django.utils.text import slugify
            base_slug = slugify(self.title)[:240]
            candidate = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog_detail', kwargs={'slug': self.slug})

    @property
    def tags_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def seo_title(self):
        return self.meta_title or f"{self.title} — GetMeCare Ontario"

    @property
    def seo_description(self):
        return self.meta_description or self.excerpt[:160]

    @property
    def display_image(self):
        if self.featured_image:
            try:
                return self.featured_image.url
            except Exception:
                pass
        if self.featured_image_url:
            return self.featured_image_url
        return '/static/Caregiver/images/hero-image.png'


class BlogComment(models.Model):
    """
    Comments and threaded replies for blog articles.
    Supports both registered users and guests.
    Supports Ajax creation, editing, and deletion with permission tracking.
    """
    post         = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_comments')
    author_name  = models.CharField(max_length=100)
    author_email = models.EmailField(blank=True)
    content      = models.TextField()
    parent       = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    guest_token  = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    is_approved  = models.BooleanField(default=True, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Blog Comment'
        verbose_name_plural = 'Blog Comments'

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post.title[:30]}"

    def can_manage(self, request, client_token=None):
        """Returns True if the current user or guest with token has permission to edit/delete."""
        if not request:
            return False
        if request.user.is_authenticated:
            if request.user.is_staff or request.user.is_superuser:
                return True
            if self.user_id and self.user_id == request.user.id:
                return True
        # Guest token verification
        session_tokens = request.session.get('guest_comment_tokens', [])
        if self.guest_token:
            if self.guest_token in session_tokens:
                return True
            if client_token and self.guest_token == client_token:
                return True
        return False


