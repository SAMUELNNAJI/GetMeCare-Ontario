from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class CustomUser(AbstractUser):
    EMPLOYER = 'employer'
    CAREGIVER = 'caregiver'

    ROLE_CHOICES = [
        (EMPLOYER, 'Employer / Family'),
        (CAREGIVER, 'Caregiver / PSW'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=EMPLOYER,
    )
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_employer(self):
        return self.role == self.EMPLOYER

    @property
    def is_caregiver(self):
        return self.role == self.CAREGIVER


# ──────────────────────────────────────────────────────────────
# Caregiver profile (status tracking + hourly rate)
# ──────────────────────────────────────────────────────────────
class CaregiverProfile(models.Model):
    STATUS_PENDING  = 'pending_admin_review'
    STATUS_ACTIVE   = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending Admin Review'),
        (STATUS_ACTIVE,   'Active & Verified'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user        = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='caregiver_profile',
    )
    status      = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    CARE_TYPE_CHOICES = [
        ('senior_elder',  'Senior / Elder Care'),
        ('dementia',      'Dementia & Alzheimer'),
        ('palliative',    'Palliative Care'),
        ('post_surgery',  'Post-Surgery Recovery'),
        ('postpartum',    'Postpartum Care'),
        ('companion',     'Companion Care'),
        ('mobility',      'Mobility Assistance'),
        ('live_in',       'Live-In Care'),
        ('overnight',     'Overnight Care'),
        ('respite',       'Respite Care'),
        ('psw_general',   'General PSW'),
        ('other',         'Other'),
    ]
    care_type   = models.TextField(
        blank=True,
        help_text='Comma-separated care type keys e.g. senior_elder,dementia',
    )

    hourly_rate = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text='Standard baseline rate in CAD/hr',
    )
    city           = models.CharField(max_length=100, blank=True)
    skills         = models.TextField(blank=True, help_text='Comma-separated skill tags')
    profile_image  = models.ImageField(
        upload_to='caregiver_avatars/',
        null=True, blank=True,
        help_text='Profile photo (JPG/PNG, max 5 MB)',
    )
    # Bank / direct-deposit details (stored plain — encrypt in production)
    bank_name          = models.CharField(max_length=100, blank=True)
    bank_account_name  = models.CharField(max_length=150, blank=True,
                         help_text='Account holder name as it appears on the account')
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_transit_number = models.CharField(max_length=10, blank=True,
                          help_text='5-digit transit number')
    bank_institution_number = models.CharField(max_length=5, blank=True,
                              help_text='3-digit institution number')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.get_status_display()}"

    @property
    def skills_list(self):
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    @property
    def care_types_list(self):
        """Return list of care type keys from the comma-separated field."""
        return [v.strip() for v in self.care_type.split(',') if v.strip()]

    @property
    def care_types_display(self):
        """Return list of human-readable care type labels."""
        lookup = dict(self.CARE_TYPE_CHOICES)
        return [lookup.get(k, k) for k in self.care_types_list]

    def has_all_required_documents(self):
        """Check if all 5 required documents are uploaded (approved or pending)."""
        from Account.forms import REQUIRED_DOC_TYPES
        user_doc_types = set(
            self.user.documents.filter(
                doc_type__in=REQUIRED_DOC_TYPES
            ).values_list('doc_type', flat=True).distinct()
        )
        return len(user_doc_types) == len(REQUIRED_DOC_TYPES)


# ──────────────────────────────────────────────────────────────
# Shift — created by admin, assigned to a caregiver + employer
# ──────────────────────────────────────────────────────────────
class Shift(models.Model):
    STATUS_SCHEDULED  = 'scheduled'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED  = 'completed'
    STATUS_CANCELLED  = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED,   'Scheduled'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED,   'Completed'),
        (STATUS_CANCELLED,   'Cancelled'),
    ]

    caregiver   = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='caregiver_shifts',
        limit_choices_to={'role': CustomUser.CAREGIVER},
    )
    employer    = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='employer_shifts',
        limit_choices_to={'role': CustomUser.EMPLOYER},
    )
    city        = models.CharField(max_length=100, blank=True)
    start_date  = models.DateField()
    start_time  = models.TimeField()
    end_time    = models.TimeField(null=True, blank=True)   # kept for legacy display; derived from start_time + duration_hours
    duration_hours = models.DecimalField(
        max_digits=4, decimal_places=1,
        null=True, blank=True,
        help_text='How many hours the caregiver is booked for (e.g. 4.0)',
    )
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2)
    status      = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date', '-start_time']

    def __str__(self):
        return f"Shift #{self.pk} — {self.caregiver.get_full_name()} on {self.start_date}"

    @property
    def employer_city(self):
        """Masked — return only city, never full address."""
        return self.city or 'Ontario'

    @property
    def total_cost(self):
        """Employer charge: hourly_rate × duration_hours."""
        from decimal import Decimal
        if self.duration_hours and self.hourly_rate:
            return round(Decimal(str(self.duration_hours)) * self.hourly_rate, 2)
        return None


# ──────────────────────────────────────────────────────────────
# ShiftLog — clock-in / clock-out record + payment state
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# CaregiverDocument — file uploads for verification
# ──────────────────────────────────────────────────────────────
class CaregiverDocument(models.Model):
    DOC_PSW_CERT      = 'psw_certificate'
    DOC_VSC           = 'vulnerable_sector_check'
    DOC_GOVERNMENT_ID = 'government_id'
    DOC_FIRST_AID     = 'first_aid'
    DOC_RESUME        = 'resume'
    DOC_OTHER         = 'other'

    DOC_TYPE_CHOICES = [
        (DOC_PSW_CERT,      'PSW Certificate'),
        (DOC_VSC,           'Vulnerable Sector Check'),
        (DOC_GOVERNMENT_ID, 'Government ID'),
        (DOC_FIRST_AID,     'First Aid / CPR Certificate'),
        (DOC_RESUME,        'Resume / CV'),
        (DOC_OTHER,         'Other'),
    ]

    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user        = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    doc_type    = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file        = models.FileField(upload_to='caregiver_docs/%Y/%m/')
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note        = models.TextField(blank=True, help_text='Admin review note')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.get_doc_type_display()}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


# ──────────────────────────────────────────────────────────────
# BookingProposal — created by caregiver during chat negotiation
# ──────────────────────────────────────────────────────────────
class BookingProposal(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_BOOKED   = 'booked'
    STATUS_DECLINED = 'declined'
    STATUS_EXPIRED  = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_BOOKED,   'Booked & Paid'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_EXPIRED,  'Expired'),
    ]

    # Link back to the chat thread where this was proposed
    conversation_id = models.PositiveIntegerField(
        help_text='DirectConversation PK — soft FK to avoid circular import',
    )
    caregiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_proposals',
        limit_choices_to={'role': CustomUser.CAREGIVER},
    )
    employer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='received_proposals',
        limit_choices_to={'role': CustomUser.EMPLOYER},
    )
    negotiated_rate = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text='Agreed hourly rate in CAD',
    )
    message = models.CharField(
        max_length=255,
        blank=True,
        help_text='Optional note from caregiver',
    )
    # Set when employer accepts and books
    shift = models.OneToOneField(
        'Shift',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='booking_proposal',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    is_read = models.BooleanField(
        default=False,
        help_text='True once the recipient (employer) has opened the conversation',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Proposal #{self.pk} — {self.caregiver.get_full_name()} "
            f"→ {self.employer.get_full_name()} @ ${self.negotiated_rate}/hr [{self.get_status_display()}]"
        )


class ShiftLog(models.Model):
    PAY_PENDING  = 'pending'
    PAY_PAID     = 'paid'
    PAY_DISPUTED = 'disputed'

    PAY_CHOICES = [
        (PAY_PENDING,  'Pending'),
        (PAY_PAID,     'Paid'),
        (PAY_DISPUTED, 'Disputed'),
    ]

    shift           = models.OneToOneField(
        Shift,
        on_delete=models.CASCADE,
        related_name='log',
    )
    clock_in_time   = models.DateTimeField(null=True, blank=True)
    clock_out_time  = models.DateTimeField(null=True, blank=True)
    hours_worked    = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
    )
    amount_earned   = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Caregiver's 85% share",
    )
    payment_status  = models.CharField(
        max_length=15,
        choices=PAY_CHOICES,
        default=PAY_PENDING,
    )
    is_disputed     = models.BooleanField(default=False)
    dispute_note    = models.TextField(blank=True)

    def __str__(self):
        return f"Log for Shift #{self.shift.pk}"

    def calculate_earnings(self):
        """Compute hours worked (actual) and earnings based on booked duration_hours.

        hours_worked reflects actual time clocked.
        amount_earned uses the booked duration_hours so the caregiver always
        receives the full agreed pay regardless of when they clock out.
        """
        if self.clock_in_time and self.clock_out_time:
            from decimal import Decimal
            # Actual time on site (for records)
            delta = self.clock_out_time - self.clock_in_time
            self.hours_worked = round(delta.total_seconds() / 3600, 2)
            # Pay based on booked duration (what employer paid for)
            booked = self.shift.duration_hours if self.shift.duration_hours else Decimal(str(self.hours_worked))
            gross = Decimal(str(booked)) * self.shift.hourly_rate
            self.amount_earned = round(gross * Decimal('0.85'), 2)


# ──────────────────────────────────────────────────────────────
# EmployerProfile — activation / subscription tracking
# ──────────────────────────────────────────────────────────────
class EmployerProfile(models.Model):
    ACTIVATION_FEE = 49.99  # CAD — flat one-time activation fee

    user               = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name='employer_profile',
    )
    is_active          = models.BooleanField(default=False,
                         help_text='True after one-time activation fee is paid')
    activation_paid_at = models.DateTimeField(null=True, blank=True)
    # Stripe / payment reference (filled when real payment is integrated)
    payment_reference  = models.CharField(max_length=200, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f"{self.user.get_full_name()} — {status}"


# ──────────────────────────────────────────────────────────────
# JobPosting — care jobs posted by employers (matched to browse cards)
# ──────────────────────────────────────────────────────────────
class JobPosting(models.Model):
    CARE_TYPE_CHOICES = [
        ('senior_elder',      'Senior / Elder Care'),
        ('dementia',          'Dementia & Alzheimer'),
        ('palliative',        'Palliative Care'),
        ('post_surgery',      'Post-Surgery Recovery'),
        ('postpartum',        'Postpartum Care'),
        ('companion',         'Companion Care'),
        ('mobility',          'Mobility Assistance'),
        ('live_in',           'Live-In Care'),
        ('overnight',         'Overnight Care'),
        ('respite',           'Respite Care'),
        ('other',             'Other'),
    ]

    SCHEDULE_CHOICES = [
        ('weekdays',  'Weekdays'),
        ('weekends',  'Weekends'),
        ('flexible',  'Flexible'),
        ('live_in',   'Live-In'),
        ('overnight', 'Overnight'),
    ]

    STATUS_OPEN   = 'open'
    STATUS_FILLED = 'filled'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN,   'Open'),
        (STATUS_FILLED, 'Filled'),
        (STATUS_CLOSED, 'Closed'),
    ]

    employer       = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        related_name='job_postings',
        limit_choices_to={'role': CustomUser.EMPLOYER},
    )
    title          = models.CharField(max_length=120,
                     help_text='e.g. "Weekend Respite Care"')
    care_type      = models.CharField(max_length=30, choices=CARE_TYPE_CHOICES)
    city           = models.CharField(max_length=100,
                     help_text='Neighbourhood or city, e.g. "Nepean" or "Ottawa"')
    description    = models.TextField(blank=True,
                     help_text='Details about the care needed, patient needs, home environment, etc.')
    hours_per_week = models.PositiveSmallIntegerField(null=True, blank=True,
                     help_text='Estimated weekly hours')
    hourly_rate    = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                     help_text='Offered rate in CAD/hr')
    schedule       = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default='flexible')
    start_date     = models.DateField(null=True, blank=True,
                     help_text='Desired start date (leave blank if flexible)')
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.employer.get_full_name()} ({self.city})"


# ──────────────────────────────────────────────────────────────
# EmployerPayment — records every payment made by an employer
# (activation fee + shift booking payments)
# ──────────────────────────────────────────────────────────────
class EmployerPayment(models.Model):
    TYPE_ACTIVATION = 'activation'
    TYPE_BOOKING    = 'booking'

    PAYMENT_TYPE_CHOICES = [
        (TYPE_ACTIVATION, 'Account Activation Fee'),
        (TYPE_BOOKING,    'Shift Booking'),
    ]

    STATUS_COMPLETED = 'completed'
    STATUS_FAILED    = 'failed'
    STATUS_REFUNDED  = 'refunded'

    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED,    'Failed'),
        (STATUS_REFUNDED,  'Refunded'),
    ]

    employer          = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='employer_payments',
        limit_choices_to={'role': CustomUser.EMPLOYER},
    )
    payment_type      = models.CharField(
        max_length=15,
        choices=PAYMENT_TYPE_CHOICES,
    )
    amount            = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Amount charged in CAD',
    )
    status            = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
    )
    payment_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text='Stripe / simulated payment reference',
    )
    # Optional link to the shift this payment covers (null for activation fee)
    shift             = models.ForeignKey(
        'Shift',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='employer_payments',
    )
    description       = models.CharField(
        max_length=255,
        blank=True,
        help_text='Human-readable summary, e.g. "Shift #4 — Jane Doe, 3 hrs"',
    )
    paid_at           = models.DateTimeField(auto_now_add=True)
    is_seen           = models.BooleanField(
        default=False,
        help_text='True after the employer has viewed the payment history page',
    )
    admin_seen        = models.BooleanField(
        default=False,
        help_text='True after the admin has viewed the employer payments page',
    )

    class Meta:
        ordering = ['-paid_at']
        verbose_name        = 'Employer Payment'
        verbose_name_plural = 'Employer Payments'

    def __str__(self):
        return (
            f"{self.employer.get_full_name()} — "
            f"{self.get_payment_type_display()} — "
            f"${self.amount} [{self.get_status_display()}]"
        )


# ──────────────────────────────────────────────────────────────
# Dispute — raised by an employer against a caregiver
# ──────────────────────────────────────────────────────────────
class Dispute(models.Model):
    # Categories
    CAT_SERVICE_QUALITY = 'service_quality'
    CAT_NO_SHOW         = 'no_show'
    CAT_LATE_ARRIVAL    = 'late_arrival'
    CAT_MISCONDUCT      = 'misconduct'
    CAT_BILLING         = 'billing'
    CAT_SAFETY          = 'safety_concern'
    CAT_OTHER           = 'other'

    CATEGORY_CHOICES = [
        (CAT_SERVICE_QUALITY, 'Poor Service Quality'),
        (CAT_NO_SHOW,         'Caregiver No-Show'),
        (CAT_LATE_ARRIVAL,    'Late Arrival'),
        (CAT_MISCONDUCT,      'Unprofessional / Misconduct'),
        (CAT_BILLING,         'Billing / Payment Issue'),
        (CAT_SAFETY,          'Safety Concern'),
        (CAT_OTHER,           'Other'),
    ]

    # Statuses
    STATUS_OPEN          = 'open'
    STATUS_UNDER_REVIEW  = 'under_review'
    STATUS_RESOLVED      = 'resolved'
    STATUS_DISMISSED     = 'dismissed'

    STATUS_CHOICES = [
        (STATUS_OPEN,         'Open'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_RESOLVED,     'Resolved'),
        (STATUS_DISMISSED,    'Dismissed'),
    ]

    employer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='raised_disputes',
        limit_choices_to={'role': CustomUser.EMPLOYER},
    )
    caregiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='disputes_against',
        limit_choices_to={'role': CustomUser.CAREGIVER},
    )
    # Optional links — dispute can be tied to a specific shift and/or payment
    shift = models.ForeignKey(
        'Shift',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='disputes',
    )
    payment = models.ForeignKey(
        'EmployerPayment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='disputes',
    )
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(
        help_text='Describe the issue in detail',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    admin_note = models.TextField(
        blank=True,
        help_text='Internal admin notes / resolution details',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Dispute'
        verbose_name_plural = 'Disputes'

    def __str__(self):
        return (
            f"Dispute #{self.pk} — {self.employer.get_full_name()} "
            f"vs {self.caregiver.get_full_name()} [{self.get_status_display()}]"
        )

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    @property
    def is_resolved(self):
        return self.status in (self.STATUS_RESOLVED, self.STATUS_DISMISSED)
