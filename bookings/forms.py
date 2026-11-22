from django import forms
from .models import ServiceRequest
from django.utils import timezone


class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ['requested_date', 'requested_time', 'service_location', 'work_description', 'notes']
        widgets = {
            'requested_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'requested_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'service_location': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'e.g. Flat 4B, Sunrise Apartments, MG Road'
            }),
            'work_description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe the work you need — be specific so the provider can help you effectively...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Any special instructions? (optional)'
            }),
        }

    def clean_requested_date(self):
        date = self.cleaned_data.get('requested_date')
        if date and date < timezone.now().date():
            raise forms.ValidationError("The requested date cannot be in the past.")
        return date
