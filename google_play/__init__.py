import re
import time
import os.path
import urllib
import contextlib
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import requests
import dateparser

CATEGORIES = [
    "application", "app_wallpaper", "app_widgets", "arcade",
    "books_and_reference", "brain", "business", "cards",
    "casual", "comics", "communication", "education",
    "entertainment", "finance", "game", "game_wallpaper",
    "game_widgets", "health_and_fitness", "libraries_and_demo", "lifestyle",
    "media_and_video", "medical", "music_and_audio", "news_and_magazines",
    "personalization", "photography", "productivity", "racing",
    "shopping", "social", "sports", "sports_games",
    "tools", "transportation", "travel_and_local", "weather"
]

FREE = 'topselling_free'
PAID = 'topselling_paid'


def _get_apps(url):
    r = requests.get(url)
    r.raise_for_status()

    apps = []
    soup = BeautifulSoup(r.content, "lxml")
    for elem in soup.find_all('div', 'card'):
        apps.append(elem.attrs['data-docid'])

    return apps


def leaderboard(identifier, category=None, start=0,
                num=24, hl="en"):
    if identifier not in ('topselling_paid', 'topselling_free'):
        raise Exception("identifier must be topselling_paid or topselling_free")

    url = 'https://play.google.com/store/apps'
    if category:
        if category not in CATEGORIES:
            raise Exception('%s not exists in category list' % category)
        url += "/category/" + str(category).upper()

    url += "/collection/%s?start=%s&num=%s&hl=%s" % (identifier, start, num, hl)

    return _get_apps(url)


def search(query, start=0, num=24, hl="en", gl='us', c_type="apps"):
    url = ('https://play.google.com/store/search'
           '?q=%s&start=%s&num=%s&hl=%s&gl=%s&c=%s') % (query, start, num, hl, gl, c_type)

    return _get_apps(url)


def developer(developer, start=0, num=24, hl="en"):
    url = ('https://play.google.com/store/apps/developer'
           '?id=%s&start=%s&num=%s&hl=%s') % (urllib.quote_plus(developer), start, num, hl)

    return _get_apps(url)


class AppUnavailable(Exception):
    pass


@contextlib.contextmanager
def hideexception():
    try:
        yield
    except:
        pass


def app(package_name, hl='en', gl='en'):
    package_url = ("https://play.google.com/store/apps/details"
                   "?id=%s&hl=%s&gl=%s") % (package_name, hl, gl)

    r = requests.get(package_url, headers={'User-Agent': str(time.time())})
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            raise AppUnavailable("Application {} unavailable in country {}".format(package_name, gl))
        else:
            raise

    soup = BeautifulSoup(r.content, "lxml")

    app = dict()
    app['title'] = soup.find('div', 'document-title').text.strip()
    app['url'] = package_url
    app['package_id'] = package_name
    app['description'] = soup.find('div', itemprop='description').find('div').contents
    app['category_name'] = soup.find('span', itemprop='genre').text
    app['category_id'] = os.path.split(soup.find('a', 'category')['href'])[1]
    app['logo'] = soup.find('img', "cover-image").attrs['src']
    app['small_logo'] = app['logo'].replace('=w300', '=w100')
    app['price'] = soup.find('meta', itemprop="price").attrs['content']
    app['developer_name'] = soup.find('div', itemprop="author").a.text.strip()
    app['developer_id'] = parse_qs(urlparse(
        soup.find('div', itemprop='author').find('meta', itemprop='url')['content']).query
    )['id'][0]
    app['recent_changes'] = [recent.text for recent in soup.find_all('div', 'recent-change')]
    app['date_published'] = dateparser.parse(soup.find('div', 'content', itemprop='datePublished').text)
    with hideexception():
        app['developer_email'] = soup.find('a', href=re.compile("^mailto")).attrs['href'][7:]
    app['top_developer'] = bool(soup.find_all('meta', itemprop='topDeveloperBadgeUrl'))
    app['in_app_payments'] = bool(soup.find_all('div', 'inapp-msg'))
    app['content_rating'] = soup.find('img', 'content-rating-badge')['alt']

    link = soup.find('a', "dev-link").attrs['href']
    developer_website = re.search('\?q=(.*)&sa', link)
    if developer_website:
        app['developer_website'] = developer_website.group(1) or ''

    with hideexception():
        app['developer_address'] = soup.find('div', 'physical-address').text.strip()

    with hideexception():
        app['rating'] = float(soup.find('div', 'score').text.replace(",", "."))
        hist = soup.find('div', 'rating-histogram')
        app['rating_counts'] = [int(hist.find('div', name).find('span', 'bar-number').text.replace(',', '').replace('\xa0', ''))
                                for name in ('one', 'two', 'three', 'four', 'five')]

    with hideexception():
        app['reviews_num'] = int(soup.find('span', 'reviews-num').text.replace(',', u'').replace(u'\xa0', u''))

    with hideexception():
        app['version'] = soup.find('div', itemprop="softwareVersion").text.strip()

    with hideexception():
        app['size'] = int(float(soup.find('div', itemprop="fileSize").text.strip().replace(',', '.')[:-1]) * 10 ** 6)

    with hideexception():
        app['installs'] = soup.find('div', itemprop="numDownloads").text.strip().replace('\xa0', '')\
            .replace(',', '').replace(b'\xe2\x80\x93'.decode(), ' - ')

    app['android'] = soup.find('div', itemprop="operatingSystems").text.strip()
    app['images'] = [im.attrs['src']
                     for im in soup.find_all('img', itemprop="screenshot")]

    html = soup.find('div', "rec-cluster")
    if html:
        app['similar'] = [similar.attrs['data-docid']
                          for similar in html.find_all('div', 'card')]

    return app
