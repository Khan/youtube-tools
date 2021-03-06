"""This file contains some lightweight tools for interacting with the YouTube
API. Currently included are:

YouTubeVideo: A class to represent a YouTube video.
"""

import json
import time
import urllib
import urllib2
import urlparse

from lxml import etree

import secrets


_access_token_cache = (None, None)  # (token, expires)


def get_access_token():
    """Return an access token useable immediately, ensuring to renew the token
    if the last retrieved one has expired.
    """
    global _access_token_cache
    expires = _access_token_cache[1]

    # If the token expires within 10 seconds, renew it now
    if expires is None or expires - time.time() < 10:
        resp = urllib2.urlopen(
            'https://accounts.google.com/o/oauth2/token',
            urllib.urlencode({
                'client_id': secrets.oauth_client_id,
                'client_secret': secrets.oauth_client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': secrets.youtube_refresh_token,
            }))
        data = json.loads(resp.read())

        _access_token_cache = (
            data['access_token'], time.time() + data['expires_in'])

    return _access_token_cache[0]


def _youtube_api_urlopen(path, data=None, method='GET',
                         content_type='application/x-www-form-urlencoded'):
    headers = {
        'X-GData-Key': 'key=' + secrets.youtube_developer_key,
        'Authorization': 'Bearer ' + get_access_token(),

        'Content-Type': content_type,
    }

    req = urllib2.Request(
        urlparse.urljoin('https://gdata.youtube.com/', path),
        data, headers=headers)

    # Ugh -- from http://stackoverflow.com/a/9023005/49485.
    req.get_method = lambda: method

    return urllib2.urlopen(req)


class YouTubeVideo(object):
    """A wrapper around the YouTube API for retrieving and updating video
    properties.
    """

    def __init__(self, root=None, nsmap=None):
        self.root = root
        self._xpath_eval = self._xpath_evaluator(self.root, nsmap)

    @staticmethod
    def _xpath_evaluator(root, nsmap=None):
        # This seems necessary to avoid having to prefix tag names with the
        # full namespace URL every time
        xpath = etree.XPathEvaluator(root)
        for prefix, url in (nsmap or root.nsmap).iteritems():
            # lxml and xpath don't like empty prefixes, so we give a name to
            # the Atom namespace
            prefix = prefix or "atom"
            xpath.register_namespace(prefix, url)
        return xpath

    @classmethod
    def get(cls, video_id, read_only=True):
        """Return a YouTubeVideo with the given video ID. If the authenticated
        user owns the video, pass read_only=False to fetch from the user's
        uploads in order to allow editing.
        """
        if read_only:
            format = '/feeds/api/videos/%s?v=2'
        else:
            format = '/feeds/api/users/default/uploads/%s?v=2'

        resp = _youtube_api_urlopen(format % video_id)
        root = etree.parse(resp).getroot()
        return cls(root)

    @classmethod
    def all_for_user(cls, user='default'):
        """Return a generator that yields all of a user's uploads. If no user
        is passed, the uploads of the authenticated user are returned.
        """
        per_page = 50  # YouTube's maximum allowed
        url = "/feeds/api/users/%s/uploads?v=2&max-results=%d" % (
            user, per_page)

        while url is not None:
            resp = _youtube_api_urlopen(url)
            feed = etree.parse(resp).getroot()
            xpath = cls._xpath_evaluator(feed)

            for entry in xpath('atom:entry'):
                yield YouTubeVideo(root=entry, nsmap=feed.nsmap)

            # URL for the next page of results
            nexts = xpath('atom:link[@rel="next"]')
            if nexts:
                url = nexts[0].get('href')
            else:
                url = None

    @property
    def id(self):
        els = self._xpath_eval('media:group/yt:videoid')
        assert len(els) == 1
        return els[0].text

    @property
    def title(self):
        els = self._xpath_eval('media:group/media:title')
        assert len(els) == 1
        return els[0].text

    @property
    def description(self):
        els = self._xpath_eval('media:group/media:description')
        assert len(els) == 1
        return els[0].text

    @property
    def keywords(self):
        els = self._xpath_eval('media:group/media:keywords')
        assert len(els) == 1
        return els[0].text

    @property
    def is_draft(self):
        return bool(self._xpath_eval('app:control/app:draft'))

    @property
    def _edit_url(self):
        """Return the URL to which a PUT or PATCH request to update the video
        should be sent.
        """
        els = self._xpath_eval('atom:link[@rel="edit"]')
        if len(els) == 1:
            return els[0].get('href')

    def update(self, **attributes):
        """Update a video's attributes.

        Example:
            video.update(title='monkey')

        Currently only title and description are supported.
        """
        edit_url = self._edit_url
        assert edit_url is not None, 'Video is not editable'

        # Copy over the xmlns attributes
        nsmap = self.root.nsmap
        entry = etree.Element('entry', nsmap=nsmap)

        group = etree.Element("{%s}group" % nsmap['media'])
        entry.append(group)

        fields = []

        if 'title' in attributes:
            title = etree.Element("{%s}title" % nsmap['media'])
            title.set('type', 'plain')
            title.text = attributes['title']
            group.append(title)
            fields.append('media:title')

        if 'description' in attributes:
            description = etree.Element("{%s}description" % nsmap['media'])
            description.set('type', 'plain')
            description.text = attributes['description']
            group.append(description)
            fields.append('media:description')

        if 'keywords' in attributes:
            keywords = etree.Element("{%s}keywords" % nsmap['media'])
            keywords.set('type', 'plain')
            keywords.text = attributes['keywords']
            group.append(keywords)
            fields.append('media:keywords')

        entry.set("{%s}fields" % nsmap['gd'],
                  'media:group(%s)' % ','.join(fields))

        xml = etree.tostring(entry, encoding='unicode')
        tries = 0
        while True:
            try:
                resp = _youtube_api_urlopen(
                    edit_url, data=xml.encode('utf-8'),
                    content_type='application/xml; charset=utf-8',
                    method='PATCH')
                resp.read()
                return
            except urllib2.HTTPError, e:
                if e.code == 503:
                    tries += 1
                    if tries >= 8:
                        raise
                    else:
                        print 'retrying', tries
                        time.sleep(tries ** 3)
                else:
                    raise

    def __repr__(self):
        return "<YouTubeVideo id: %r title: %r description: %r>" % (
            self.id, self.title, self.description)
