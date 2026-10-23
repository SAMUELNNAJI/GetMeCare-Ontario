from django import forms
from .models import Faq, Service, BlogPost


class FaqForm(forms.ModelForm):
    class Meta:
        model  = Faq
        fields = ['question', 'answer', 'category', 'is_active', 'order']
        widgets = {
            'answer': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'adm-form-control'})


class ServiceForm(forms.ModelForm):
    class Meta:
        model  = Service
        fields = ['title', 'slug', 'short_description', 'description',
                  'image', 'icon', 'rate', 'tag', 'is_active', 'order']
        widgets = {
            'description':       forms.Textarea(attrs={'rows': 5}),
            'short_description': forms.Textarea(attrs={'rows': 3}),
            'image':             forms.FileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'adm-form-control'})
        self.fields['image'].widget = forms.FileInput()

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Auto-populate the slug from the title if it is still empty.
        if not instance.slug and instance.title:
            from django.utils.text import slugify
            instance.slug = slugify(instance.title)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = [
            'title', 'slug', 'category', 'author_name', 'author_role',
            'featured_image', 'featured_image_url', 'image_alt',
            'excerpt', 'content', 'tags',
            'meta_title', 'meta_description', 'meta_keywords',
            'read_time_minutes', 'is_published', 'is_featured'
        ]
        widgets = {
            'excerpt': forms.Textarea(attrs={'rows': 3, 'placeholder': 'A brief 1-2 sentence hook for cards and search snippets...'}),
            'content': forms.Textarea(attrs={'rows': 16, 'placeholder': 'Write your rich blog post content here (HTML supported)...'}),
            'featured_image': forms.FileInput(),
            'meta_description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'SEO meta description (up to 160 characters)...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'adm-form-control'})
        self.fields['featured_image'].widget = forms.FileInput()
        if not self.instance.pk and 'author_name' in self.fields:
            self.fields['author_name'].initial = 'Getmecare-Ontario'

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug and instance.title:
            from django.utils.text import slugify
            base_slug = slugify(instance.title)[:240]
            candidate = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=candidate).exclude(pk=instance.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            instance.slug = candidate
        if commit:
            instance.save()
            self.save_m2m()
        return instance

