# -*- coding: utf-8 -*-
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

_DESCRIPTION_PREAMBLES = {
    # subdomain: text
    'www': u"More free lessons at:",
    'es': u"Más lecciones gratuitas en:",
    'pt': u"Mais aulas gratuitas em:",
    'fr': u"Plus de cours gratuits en vidéo ici :",
}

# Keep any past preambles here so that we can properly unannotate descriptions
_ALL_POSSIBLE_PREAMBLES = _DESCRIPTION_PREAMBLES.values() + [
    u"Learn more:",
]


def description_is_annotated(description):
    return description and unannotate_description(description) != description


def unannotate_description(description):
    call_to_action = r'(?:%s) https?://.+' % '|'.join([
            re.escape(p) for p in _ALL_POSSIBLE_PREAMBLES])
    return re.sub(
        r'^\s*%s(?:\n\s*|$)|\n\s*%s(?=\n|$)' %
            (call_to_action, call_to_action),
        '',
        description or '')


def annotate_description(description, lang, url):
    # Make sure not to double-annotate descriptions
    if description_is_annotated(description):
        description = unannotate_description(description)
    header = "%s %s" % (_DESCRIPTION_PREAMBLES[lang], url)
    if description:
        lines = description.split('\n')
        lines.insert(1, header)
        return '\n'.join(lines)
    else:
        return header


def fetch_ka_library(lang):
    resp = urllib2.urlopen(
        'https://%s.khanacademy.org/api/v1/topictree?kind=Video' % lang)
    return json.load(resp)


def all_youtube_ids(library):
    """Return a set of every youtube_id in the given topic tree."""
    def iter(node):
        if node['kind'] == "Topic":
            for child in node['children']:
                for youtube_id in iter(child):
                    yield youtube_id
        elif node['kind'] == "Video":
            yield node['translated_youtube_id']

    return set(iter(library))


def add_ka_links(youtube_ids, dry_run, lang):
    updated = 0
    unpublished = 0
    already_annotated = 0
    not_in_topic_tree = 0
    annotation_removed = 0

    try:
        for video in youtube.YouTubeVideo.all_for_user():
            if video.id in youtube_ids:
                url = "http://%s.khanacademy.org/video?v=%s" % (lang, video.id)
                new_desc = annotate_description(video.description, lang, url)
                if video.is_draft:
                    # YouTube returns an error if we try to update these
                    print ".. skipping %s (unpublished)" % video.id
                    unpublished += 1
                elif new_desc == video.description:
                    print ".. skipping %s (already annotated)" % video.id
                    already_annotated += 1
                else:
                    print ".. updating description for %s" % video.id

                    if not dry_run:
                        # YouTube refuses to update videos which contain
                        # one-letter keywords; many Spanish videos seem to have
                        # 'y' as a keyword, so strip it out
                        keywords = (video.keywords.split(', ')
                                    if video.keywords else [])
                        filtered_keywords = [k for k in keywords if len(k) > 1]
                        if len(keywords) > len(filtered_keywords):
                            print ".. .. filtering keywords %s" % keywords
                            keywords = filtered_keywords

                        video.update(
                            description=new_desc,
                            keywords=', '.join(keywords))

                        # YouTube returns 403s if you make requests too fast,
                        # but sleeping 1 second for each video seemed to be
                        # enough to get through ~2500 videos
                        time.sleep(1)

                    updated += 1
            else:
                if description_is_annotated(video.description):
                    print ".. removing from %s (not in topic tree)" % video.id
                    if not dry_run:
                        video.update(description=unannotate_description(
                            video.description))
                        time.sleep(1)
                    annotation_removed += 1
                else:
                    print ".. skipping %s (not in topic tree)" % video.id
                    not_in_topic_tree += 1
    finally:
        print (
            "%d updated, %d unpublished, %d already annotated, "
            "%d not in topic tree (%d annotations removed)" % (
                updated, unpublished, already_annotated, not_in_topic_tree,
                annotation_removed))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Add Khan Academy links to YouTube videos.')
    parser.add_argument(
        '-n', '--dry-run', action='store_true', default=False,
        help='skip the actual description update requests')
    parser.add_argument(
        '-l', '--language', required=True,
        help='subdomain to use when grabbing topictree and making links (www, '
        'es, pt, etc.)')
    args = parser.parse_args()

    print "Fetching Khan Academy video library..."
    library = fetch_ka_library(args.language)
    youtube_ids = all_youtube_ids(library)

    print "Fetching YouTube uploaded videos..."
    add_ka_links(youtube_ids, args.dry_run, args.language)
