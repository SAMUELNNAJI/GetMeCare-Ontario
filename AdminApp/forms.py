from django import forms
from .models import Faq, Service


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
