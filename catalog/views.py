from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from .models import Brand, Category, Gender, Product, ProductImage, Variant, size_sort_key
from .whatsapp import order_link


def catalog(request):
    products = (
        Product.objects.visible()
        .select_related("brand", "category")
        .prefetch_related(Prefetch("images", queryset=ProductImage.objects.order_by("position", "id")))
    )

    gender = request.GET.get("gender", "")
    category = request.GET.get("category", "")
    brand = request.GET.get("brand", "")
    size = request.GET.get("size", "").replace(",", ".")
    query = request.GET.get("q", "").strip()

    if gender in Gender.values:
        # Unisex shoes show up for men and women too.
        genders = [gender, Gender.UNISEX] if gender in (Gender.MEN, Gender.WOMEN) else [gender]
        products = products.filter(gender__in=genders)
    if category:
        products = products.filter(category__slug=category)
    if brand:
        products = products.filter(brand__slug=brand)
    if size:
        products = products.filter(variants__size=size, variants__stock__gt=0)
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(category__name__icontains=query)
            | Q(variants__color__icontains=query)
            | Q(variants__sku__iexact=query)
        )
    products = products.distinct()

    in_stock = Variant.objects.filter(stock__gt=0, product__is_active=True)
    sizes = sorted(set(in_stock.values_list("size", flat=True)), key=size_sort_key)

    context = {
        "products": products,
        "genders": [(g.value, g.label) for g in Gender if g != Gender.UNISEX],
        "categories": Category.objects.filter(products__in=Product.objects.visible()).distinct(),
        "brands": Brand.objects.filter(products__in=Product.objects.visible()).distinct(),
        "sizes": sizes,
        "selected": {"gender": gender, "category": category, "brand": brand, "size": size, "q": query},
        "filtered": any([gender, category, brand, size, query]),
    }
    return render(request, "catalog/list.html", context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category").prefetch_related("images"),
        slug=slug,
        is_active=True,
    )
    variants = list(product.variants.all())

    # Colours in the order they were added, each with total pairs.
    colors = []
    for v in variants:
        entry = next((c for c in colors if c["name"] == v.color), None)
        if entry is None:
            entry = {"name": v.color, "stock": 0}
            colors.append(entry)
        entry["stock"] += v.stock

    requested_color = request.GET.get("color", "")
    available_colors = [c["name"] for c in colors if c["stock"] > 0]
    if requested_color in [c["name"] for c in colors]:
        color = requested_color
    else:
        color = available_colors[0] if available_colors else (colors[0]["name"] if colors else "")

    sizes = sorted((v for v in variants if v.color == color), key=lambda v: size_sort_key(v.size))
    requested_size = request.GET.get("size", "")
    selected = next((v for v in sizes if v.size == requested_size and v.stock > 0), None)

    images = list(product.images.all())
    color_images = [img for img in images if img.color.lower() == color.lower()]
    gallery = color_images + [img for img in images if img not in color_images]

    page_url = request.build_absolute_uri(product.get_absolute_url())
    related = (
        Product.objects.visible()
        .filter(Q(category=product.category) | Q(brand=product.brand))
        .exclude(pk=product.pk)
        .select_related("brand")
        .prefetch_related("images")[:4]
    )

    context = {
        "product": product,
        "colors": colors,
        "color": color,
        "sizes": sizes,
        "selected": selected,
        "gallery": gallery,
        "sold_out": not available_colors,
        "whatsapp_link": order_link(product, selected, page_url),
        "related": related,
    }
    return render(request, "catalog/product.html", context)
