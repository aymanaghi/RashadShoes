from urllib.parse import parse_qs, urlparse

from django.urls import reverse


def test_catalog_hides_sold_out_and_inactive(client, make_product):
    make_product(name="In Stock")
    make_product(name="Sold Out", stock={"42": 0})
    make_product(name="Hidden", is_active=False)

    html = client.get(reverse("catalog:list")).content.decode()

    assert "In Stock" in html
    assert "Sold Out" not in html
    assert "Hidden" not in html


def test_size_filter_only_shows_shoes_with_that_size_in_stock(client, make_product):
    make_product(name="Has 42", stock={"42": 1})
    make_product(name="Only 44", stock={"44": 1, "42": 0})

    html = client.get(reverse("catalog:list"), {"size": "42"}).content.decode()

    assert "Has 42" in html
    assert "Only 44" not in html


def test_gender_filter_includes_unisex_for_men(client, make_product):
    make_product(name="Mens", gender="men")
    make_product(name="Unisex Runner", gender="unisex")
    make_product(name="Womens", gender="women")

    html = client.get(reverse("catalog:list"), {"gender": "men"}).content.decode()

    assert "Mens" in html and "Unisex Runner" in html
    assert "Womens" not in html


def test_search_by_brand_and_code(client, make_product):
    p = make_product(name="Samba", brand="Adidas")
    make_product(name="Go Walk", brand="Skechers")
    code = p.variants.get().sku

    assert "Samba" in client.get("/", {"q": "adidas"}).content.decode()
    html = client.get("/", {"q": code}).content.decode()
    assert "Samba" in html and "Go Walk" not in html


def test_product_page_whatsapp_link_carries_size_and_code(client, make_product, whatsapp):
    product = make_product(name="Air Force 1", price="85", stock={"42": 2, "43": 0})
    v42 = product.variants.get(size="42")

    response = client.get(product.get_absolute_url(), {"color": "White", "size": "42"})

    link = response.context["whatsapp_link"]
    parsed = urlparse(link)
    assert parsed.netloc == "wa.me" and parsed.path == f"/{whatsapp}"
    text = parse_qs(parsed.query)["text"][0]
    assert "Size: 42" in text
    assert f"Code: {v42.sku}" in text
    assert "Price: $85" in text
    assert product.get_absolute_url() in text


def test_sold_out_size_cannot_be_selected(client, make_product, whatsapp):
    product = make_product(stock={"42": 1, "43": 0})

    response = client.get(product.get_absolute_url(), {"size": "43"})

    assert response.context["selected"] is None
    assert "Size: " not in parse_qs(urlparse(response.context["whatsapp_link"]).query)["text"][0]


def test_product_page_without_whatsapp_number_still_works(client, make_product):
    product = make_product()
    response = client.get(product.get_absolute_url())
    assert response.status_code == 200
    assert response.context["whatsapp_link"] is None
    assert b"WhatsApp ordering opens soon" in response.content


def test_inactive_product_page_is_404(client, make_product):
    product = make_product(is_active=False)
    assert client.get(product.get_absolute_url()).status_code == 404
