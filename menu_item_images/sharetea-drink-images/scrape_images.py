"""Download all six Sharetea menu categories. Python 3; no pip packages needed."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
import hashlib
import json
import re
import struct
import time

# Used help from AI to generate this file

BASE = 'https://www.1992sharetea.com'
# Verified visible product names; several image alt attributes are incorrect.
PRODUCTS = {
    'brewed-tea': {
        'FreshBrew_11_black.png': 'Classic Tea',
        'FreshBrew_11_green.png': 'Honey Tea',
    },
    'milk-tea': {
        'MilkSeries_01.png': 'Honey Pearl Milk Tea',
        'MilkSeries_02.png': 'Classic Pearl Milk Tea',
        'MilkSeries_03.png': 'Coffee Creama',
        'MilkSeries_04.png': 'Coffee Milk Tea with Coffee Jelly',
        'MilkSeries_05.png': 'Coconut Pearl Milk Tea',
        'MilkSeries_06.png': 'Thai Pearl Milk Tea',
        'MilkSeries_07.png': 'Taro Pearl Milk Tea',
        'MilkSeries_08.png': 'Mango Green Milk Tea',
        'MilkSeries_09.png': 'Golden Retriever',
        'MilkSeries_10.png': 'Hokkaido Pearl Milk Tea',
    },
    'fruit-tea': {
        'Fruity_13.png': 'Mango Green Tea',
        'Fruity_14.png': 'Passion Chess',
        'Fruity_15.png': 'Berry Lychee Burst',
        'Fruity_16.png': 'Peach Tea with Honey Jelly',
        'Fruity_17.png': 'Mango and Passion Fruit Tea',
        'Fruity_18+(1).png': 'Honey Lemonade',
    },
    'non-caffeinated': {
        'NonC_19.png': 'Tiger Boba',
        'NonC_20.png': 'Strawberry Coconut',
        'NonC_21.png': 'Strawberry Coconut Ice Blended',
        'NonC_22.png': 'Halo Halo',
        'NonC_23.png': 'Halo Halo Ice Blended',
        'NonC_24.png': 'Wintermelon Lemonade',
        'NonC_25.png': 'Wintermelon Lemonade Ice Blended',
        'NonC_26.png': 'Wintermelon with Fresh Milk',
    },
    'ice-blended': {
        'IB_32.png': 'Oreo Ice Blended with Pearl',
        'IB_33.png': 'Taro Ice Blended with Pudding',
        'IB_34.png': 'Thai Tea Ice Blended with Pearl',
        'IB_35.png': 'Coffee Ice Blended with Ice Cream',
        'IB_36.png': 'Mango Ice Blended with Ice Cream',
        'IB_37.png': 'Strawberry Ice Blended with Lychee Jelly and Ice Cream',
        'IB_38.png': 'Peach Tea Ice Blended with Lychee Jelly',
        'IB_39.png': 'Lava Flow',
    },
    'new-matcha-series': {
        'Matcha_27.png': 'Matcha Pearl Milk Tea',
        'Matcha_28.png': 'Matcha Fresh Milk',
        'Matcha_29.png': 'Strawberry Matcha Fresh Milk',
        'Matcha_30.png': 'Mango Matcha Fresh Milk',
        'Matcha_31.png': 'Matcha Ice Blended',
    },
}


def fetch(url):
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent': 'ShareteaCourseProjectImageDownloader/1.0'})
            with urlopen(req, timeout=40) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


class MenuImages(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_main = False
        self.images = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        if tag == 'img' and self.in_main:
            attrs = dict(attrs)
            source = attrs.get('data-src') or attrs.get('src') or ''
            url = urljoin(BASE, source)
            original = unquote(urlsplit(url).path.rsplit('/', 1)[-1])
            self.images[original] = url

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False


def extract(category, html):
    parser = MenuImages()
    parser.feed(html)
    expected = PRODUCTS[category]
    missing = expected.keys() - parser.images.keys()
    extra = parser.images.keys() - expected.keys()
    if missing or extra:
        raise RuntimeError(f'Review changed page {category}: missing={sorted(missing)}, new={sorted(extra)}')
    records = []
    for original, name in expected.items():
        filename = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') + '.png'
        records.append({'name': name, 'category': category,
                        'file': 'images/' + filename,
                        'source_page': BASE + '/' + category,
                        'source_image': parser.images[original]})
    return records


def download(record, root):
    data = fetch(record['source_image'])
    if len(data) < 24 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('Expected PNG: ' + record['source_image'])
    width, height = struct.unpack('>II', data[16:24])
    destination = root / record['file']
    temporary = destination.with_suffix('.png.part')
    temporary.write_bytes(data)
    temporary.replace(destination)
    result = {**record, 'width': width, 'height': height,
              'sha256': hashlib.sha256(data).hexdigest()}
    print('Saved ' + record['file'], flush=True)
    return result


def save_images(records, root):
    filenames = [r['file'] for r in records]
    if len(set(filenames)) != len(filenames):
        raise RuntimeError('Duplicate output filenames; review names before downloading')
    (root / 'images').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda record: download(record, root), records))
    (root / 'image-sources.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(f'Downloaded {len(results)} drink images.')


def main():
    def read_category(category):
        html = fetch(BASE + '/' + category).decode('utf-8')
        return extract(category, html)
    with ThreadPoolExecutor(max_workers=4) as pool:
        groups = list(pool.map(read_category, PRODUCTS))
    records = [record for group in groups for record in group]
    save_images(records, Path(__file__).resolve().parent)


if __name__ == '__main__':
    main()
