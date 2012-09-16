"""This file contains some lightweight tools for interacting with the YouTube
API. Currently included are:

get_video: Return a YouTubeVideo with a given video ID.

YouTubeVideo: A class to represent a YouTube video.
"""

import gdata.gauth
import gdata.youtube.service

import secrets

_service = gdata.youtube.service.YouTubeService()
_service.email, _service.password = secrets.get_youtube_password()
_service.developer_key = secrets.youtube_developer_key
_service.ProgrammaticLogin()


class YouTubeVideo(object):
    """A light wrapper around gdata.youtube.YouTubeVideoEntry so we can work
    with a cleaner API that hides the XML format of the GData API output.
    """

    def __init__(self, video_entry):
        self.video_entry = video_entry

    def __repr__(self):
        return "<YouTubeVideo title: %r>" % self.title

    @property
    def title(self):
        return self.video_entry.media.title.text

    @property
    def description(self):
        return self.video_entry.media.description.text

    @description.setter  # @Nolint
    def description(self, value):
        self.video_entry.media.description.text = value

    @property
    def duration(self):
        return int(self.video_entry.media.duration.seconds)

    def put(self):
        assert any(link.rel == 'edit' for link in self.video_entry.link), \
            'Video entry is not editable'
        result = _service.UpdateVideoEntry(self.video_entry)
        assert result, 'Video entry update failed'


def get_video(video_id, read_only=True):
    """Return a YouTubeVideo with the given video ID. If the authenticated user
    owns the video, use read_only=False to fetch from the user's uploads in
    order to allow editing.
    """
    if read_only:
        format = '/feeds/api/videos/%s'
    else:
        format = '/feeds/api/users/default/uploads/%s'

    entry = _service.GetYouTubeVideoEntry(format % video_id)
    return YouTubeVideo(entry)

# TODO(alpert): Figure out why the privacy settings are lost when a video entry
# is saved.
