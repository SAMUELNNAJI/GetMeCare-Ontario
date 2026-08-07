from django.contrib import admin
from Account.models import EmployerPayment, EmployerProfile


@admin.register(EmployerPayment)
class EmployerPaymentAdmin(admin.ModelAdmin):
    list_display  = (
        'id', 'employer_name', 'payment_type_badge', 'amount',
        'status', 'payment_reference', 'shift_link', 'paid_at',
    )
    list_filter   = ('payment_type', 'status', 'paid_at')
    search_fields = (
        'employer__first_name', 'employer__last_name',
        'employer__email', 'payment_reference', 'description',
    )
    ordering      = ('-paid_at',)
    readonly_fields = (
        'employer', 'payment_type', 'amount', 'status',
        'payment_reference', 'shift', 'description', 'paid_at',
    )
    date_hierarchy = 'paid_at'

    @admin.display(description='Employer', ordering='employer__first_name')
    def employer_name(self, obj):
        return obj.employer.get_full_name() or obj.employer.username

    @admin.display(description='Type')
    def payment_type_badge(self, obj):
        from django.utils.html import format_html
        colours = {
            EmployerPayment.TYPE_ACTIVATION: ('#e8f0fe', '#1a56c4'),
            EmployerPayment.TYPE_BOOKING:    ('#e6f5ee', '#1b7d4f'),
        }
        bg, fg = colours.get(obj.payment_type, ('#f0f0f0', '#555'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600">{}</span>',
            bg, fg, obj.get_payment_type_display(),
        )

    @admin.display(description='Shift')
    def shift_link(self, obj):
        if not obj.shift:
            return '—'
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('admin:Account_shift_change', args=[obj.shift.pk])
        return format_html('<a href="{}">Shift #{}</a>', url, obj.shift.pk)


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display  = (
        'employer_name', 'is_active', 'activation_paid_at',
        'payment_reference', 'created_at',
    )
    list_filter   = ('is_active',)
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Employer', ordering='user__first_name')
    def employer_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
