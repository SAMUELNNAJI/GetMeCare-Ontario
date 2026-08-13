from django.contrib import admin
from .models import Faq, Service


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'is_active', 'order', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['question', 'answer']
    list_editable = ['is_active', 'order']
    list_per_page = 50


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'rate', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'slug', 'short_description', 'description']
    list_editable = ['is_active', 'order', 'rate']
    prepopulated_fields = {'slug': ('title',)}
    list_per_page = 50
