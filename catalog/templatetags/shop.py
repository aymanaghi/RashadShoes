from django import template
from django.conf import settings

from catalog.utils import format_money

register = template.Library()


@register.filter
def money(value):
    if value in (None, ""):
        return ""
    return f"{settings.SHOP['CURRENCY_SYMBOL']}{format_money(value)}"


@register.simple_tag(takes_context=True)
def query_with(context, **changes):
    """Current filters with some changed: {% query_with gender='men' %} -> ?gender=men&size=42"""
    params = context["request"].GET.copy()
    for key, value in changes.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
