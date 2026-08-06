from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, CaregiverProfile, Shift, ShiftLog


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'role', 'is_staff', 'date_joined')
    list_filter   = ('role', 'is_staff', 'is_active')
    fieldsets     = UserAdmin.fieldsets + (
        ('Role & Contact', {'fields': ('role', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Contact', {'fields': ('role', 'phone')}),
    )


@admin.register(CaregiverProfile)
class CaregiverProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'status', 'hourly_rate', 'city', 'updated_at')
    list_filter   = ('status',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'city')
    list_editable = ('status',)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display  = ('id', 'caregiver', 'employer', 'start_date', 'start_time',
                     'end_time', 'hourly_rate', 'status', 'city')
    list_filter   = ('status', 'start_date')
    search_fields = ('caregiver__username', 'employer__username', 'city')
    list_editable = ('status',)
    date_hierarchy = 'start_date'


@admin.register(ShiftLog)
class ShiftLogAdmin(admin.ModelAdmin):
    list_display  = ('shift', 'clock_in_time', 'clock_out_time',
                     'hours_worked', 'amount_earned', 'payment_status', 'is_disputed')
    list_filter   = ('payment_status', 'is_disputed')
    list_editable = ('payment_status',)
    search_fields = ('shift__caregiver__username',)
