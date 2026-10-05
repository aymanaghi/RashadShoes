from django.conf import settings

from .whatsapp import shop_number


def shop(request):
    return {"shop": settings.SHOP, "shop_whatsapp": shop_number()}
