from services.models import ServiceCategory


def global_context(request):
    """Global context available in all templates."""
    categories = ServiceCategory.objects.filter(is_active=True).order_by('order', 'name')
    return {
        'global_categories': categories,
    }
