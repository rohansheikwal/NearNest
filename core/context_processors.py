from .models import Notification
from services.models import ServiceCategory


def global_context(request):
    """Global context available in all templates."""
    categories = ServiceCategory.objects.filter(is_active=True).order_by('order', 'name')
    context = {
        'global_categories': categories,
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
    if hasattr(request, 'user') and request.user.is_authenticated:
        context['unread_notifications_count'] = request.user.notifications.filter(is_read=False).count()
        context['recent_notifications'] = request.user.notifications.all()[:5]

    return context
