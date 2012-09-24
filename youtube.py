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

    def __init__(self, xml):
        self.root = etree.fromstring(xml)

        # This seems necessary to avoid having to prefix tag names with the
        # full namespace URL every time
        self._xpath_eval = etree.XPathEvaluator(self.root)
        for prefix, url in self.root.nsmap.iteritems():
            # lxml and xpath don't like empty prefixes, so we give a name to
            # the Atom namespace
            prefix = prefix or "atom"
            self._xpath_eval.register_namespace(prefix, url)

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
        return cls(resp.read())

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
        entry.set("{%s}fields" % nsmap['gd'],
                  'media:group(media:title,media:keywords)')

        group = etree.Element("{%s}group" % nsmap['media'])
        entry.append(group)

        title = etree.Element("{%s}title" % nsmap['media'])
        title.set('type', 'plain')
        title.text = attributes.get('title', self.title)
        group.append(title)

        description = etree.Element("{%s}description" % nsmap['media'])
        description.set('type', 'plain')
        description.text = attributes.get('description', self.description)
        group.append(description)

        xml = etree.tostring(entry)
        resp = _youtube_api_urlopen(
            edit_url, data=xml, content_type='application/xml', method='PATCH')
        resp.read()

    def __repr__(self):
        return "<YouTubeVideo title: %r description: %r>" % (
            self.title, self.description)
