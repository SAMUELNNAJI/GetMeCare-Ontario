from django.db import models


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
