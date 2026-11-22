from django import forms
from django.core.exceptions import ValidationError
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'How can we help?'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5,
                                              'placeholder': 'Tell us more...'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Please enter your name.")
        if len(name) < 2:
            raise ValidationError("Name must be at least 2 characters long.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError("Please enter a valid email address.")
        return email

    def clean_subject(self):
        subject = self.cleaned_data.get('subject', '').strip()
        if not subject:
            raise ValidationError("Please enter a subject.")
        if len(subject) < 3:
            raise ValidationError("Subject must be at least 3 characters long.")
        return subject

    def clean_message(self):
        message = self.cleaned_data.get('message', '').strip()
        if not message:
            raise ValidationError("Please enter your message.")
        if len(message) < 10:
            raise ValidationError("Message must be at least 10 characters long.")
        return message
