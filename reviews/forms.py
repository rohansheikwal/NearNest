from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    RATING_CHOICES = [(i, i) for i in range(1, 6)]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'rating-radio'}),
        label='Your Rating'
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Share your experience with this service...'
            }),
        }
        labels = {
            'comment': 'Your Review'
        }

    def clean_rating(self):
        rating = int(self.cleaned_data.get('rating', 0))
        if not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating

    def clean_comment(self):
        comment = self.cleaned_data.get('comment', '').strip()
        if not comment:
            raise forms.ValidationError("Please enter a review before submitting.")
        return comment
