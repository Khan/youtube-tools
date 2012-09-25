"""This script adds links to khanacademy.org to all the videos in a YouTube
account that are in the topic tree.

Set up secrets.py, then just run me as

    python add_ka_links.py
"""
import argparse
import json
import re
import time
import urllib2

import youtube


def description_is_annotated(description):
    match = re.match(r'^\s*Learn more: https?://.+(?:\n|$)', description or '')
    return bool(match)


def annotate_description(description, url):
    # Make sure not to double-annotate descriptions
    if description_is_annotated(description):
        return description
    else:
        header = "Learn more: %s" % url
        if description:
            return header + '\n' + description
        else:
            return header


def fetch_ka_library():
    resp = urllib2.urlopen('https://www.khanacademy.org/api/v1/topictree')
    return json.load(resp)


def all_youtube_ids(library):
    """Return a set of every youtube_id in the given topic tree."""
    def iter(node):
        if node['kind'] == "Topic":
            for child in node['children']:
                for youtube_id in iter(child):
                    yield youtube_id
        elif node['kind'] == "Video":
            yield node['youtube_id']

    return set(iter(library))


def add_ka_links(youtube_ids, dry_run):
    updated = 0
    unpublished = 0
    already_annotated = 0
    not_in_topic_tree = 0

    try:
        for video in youtube.YouTubeVideo.all_for_user():
            if video.id in youtube_ids:
                if video.is_draft:
                    # YouTube returns an error if we try to update these
                    print ".. skipping %s (unpublished)" % video.id
                    unpublished += 1
                elif description_is_annotated(video.description):
                    print ".. skipping %s (already annotated)" % video.id
                    already_annotated += 1
                else:
                    print ".. updating description for %s" % video.id

                    url = "http://www.khanacademy.org/video?v=%s" % video.id
                    if not dry_run:
                        video.update(description=annotate_description(
                            video.description, url))

                        # YouTube returns 403s if you make requests too fast,
                        # but sleeping 1 second for each video seemed to be
                        # enough to get through ~2500 videos
                        time.sleep(1)

                    updated += 1
            else:
                print ".. skipping %s (not in topic tree)" % video.id
                not_in_topic_tree += 1
    finally:
        print (
            "%d updated, %d unpublished, %d already annotated, "
            "%d not in topic tree" % (
                updated, unpublished, already_annotated, not_in_topic_tree))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Add Khan Academy links to YouTube videos.')
    parser.add_argument(
        '-n', '--dry-run', action='store_true', default=False,
        help='skip the actual description update requests')
    args = parser.parse_args()

    print "Fetching Khan Academy video library..."
    library = fetch_ka_library()
    youtube_ids = all_youtube_ids(library)

    print "Fetching YouTube uploaded videos..."
    add_ka_links(youtube_ids, args.dry_run)
