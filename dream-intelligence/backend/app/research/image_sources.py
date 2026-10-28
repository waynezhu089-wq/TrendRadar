"""Explicit supported image sources. No dynamic discovery or arbitrary fetch targets."""
IMAGE_SOURCES = {
    'https://openverse.org/': 'openverse',
    'https://film-grab.com/': 'filmgrab',
}
SOURCE_NAMES = {'openverse': 'Openverse', 'filmgrab': 'FilmGrab'}


def image_source_ids(websites):
    if not websites or len(set(websites)) != len(websites) or any(url not in IMAGE_SOURCES for url in websites):
        raise ValueError('Choose supported image sources')
    return [IMAGE_SOURCES[url] for url in websites]
