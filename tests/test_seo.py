from pathlib import Path
from struct import unpack


def test_landing_has_complete_search_and_social_metadata(client):
    response = client.get('/', base_url='https://truenorth.example')
    body = response.get_data(as_text=True)

    assert '<html lang="es-CA">' in body
    assert 'name="description"' in body
    assert 'content="index, follow, max-image-preview:large' in body
    assert '<link rel="canonical" href="https://truenorth.example/">' in body
    assert 'property="og:image" content="https://truenorth.example/static/images/og-image.png"' in body
    assert 'name="twitter:card" content="summary_large_image"' in body
    assert 'type="application/ld+json"' in body
    assert '"@type": "WebApplication"' in body


def test_base_includes_favicon_and_manifest_set(client):
    body = client.get('/').get_data(as_text=True)

    assert '/static/images/favicon.ico' in body
    assert '/static/images/favicon.svg' in body
    assert '/static/images/apple-touch-icon.png' in body
    assert '/static/images/safari-pinned-tab.svg' in body
    assert '/static/site.webmanifest' in body


def test_brand_assets_exist_with_expected_dimensions():
    images = Path(__file__).parents[1] / 'src' / 'static' / 'images'

    expected = {
        'favicon-16.png': (16, 16),
        'favicon-32.png': (32, 32),
        'apple-touch-icon.png': (180, 180),
        'icon-192.png': (192, 192),
        'icon-512.png': (512, 512),
        'icon-512-maskable.png': (512, 512),
        'mstile-150.png': (150, 150),
        'og-image.png': (1200, 630),
    }
    for filename, size in expected.items():
        # PNG stores width and height in the fixed IHDR header. Reading them
        # directly keeps this app test independent from the asset generator's
        # optional Pillow dependency.
        with (images / filename).open('rb') as image:
            assert image.read(8) == b'\x89PNG\r\n\x1a\n'
            image.read(8)  # IHDR chunk length and name
            assert unpack('>II', image.read(8)) == size


def test_robots_and_sitemap_are_public_and_absolute(client):
    robots = client.get('/robots.txt', base_url='https://truenorth.example')
    assert robots.status_code == 200
    assert robots.mimetype == 'text/plain'
    assert 'Sitemap: https://truenorth.example/sitemap.xml' in robots.get_data(as_text=True)

    sitemap = client.get('/sitemap.xml', base_url='https://truenorth.example')
    assert sitemap.status_code == 200
    assert sitemap.mimetype == 'application/xml'
    assert '<loc>https://truenorth.example/</loc>' in sitemap.get_data(as_text=True)


def test_private_and_operational_routes_send_noindex_header(client, auth_client):
    assert client.get('/login').headers['X-Robots-Tag'].startswith('noindex')
    assert client.get('/healthz').headers['X-Robots-Tag'].startswith('noindex')
    assert auth_client.get('/dashboard').headers['X-Robots-Tag'].startswith('noindex')
