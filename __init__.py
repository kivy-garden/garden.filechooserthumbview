#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""FileChooserThumbView
====================

The FileChooserThumbView widget is similar to FileChooserIconView,
but if possible it shows a thumbnail instead of a normal icon.

Usage
-----

You can set some properties in order to control its performance:

* **showthumbs:** Thumbnail limit. If set to a number > 0, it will show the
thumbnails only if the directory doesn't contain more files or directories.
If set to 0 it won't show any thumbnail. If set to a number < 0 it will always
show the thumbnails, regardless of how many items the current directory
contains. By default it is set to -1, so it will show all the thumbnails.
* **thumbdir:** Custom directory for the thumbnails. By default it uses
tempfile to generate it randomly.
* **thumbsize:** The size of the thumbnails. It defaults to 64d
"""

# Thanks to allan-simon for making the code more readable and less "spaghetti" :)

import os
import mimetypes
#(enable for debugging)
import traceback
import shutil
import subprocess
from os.path import join, exists, dirname
from chardet import detect as chardetect
from tempfile import mktemp, mkdtemp
from PIL import Image, ImageOps

from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.properties import DictProperty
from kivy.properties import ObjectProperty
from kivy.properties import BooleanProperty
from kivy.properties import NumericProperty
from kivy.uix.filechooser import FileChooserController


Builder.load_string("""
<FileChooserThumbView>:
    on_entry_added: stacklayout.add_widget(args[1])
    on_entries_cleared: stacklayout.clear_widgets()
    scrollview: scrollview

    ScrollView:
        id: scrollview
        pos: root.pos
        size: root.size
        size_hint: None, None
        do_scroll_x: False

        Scatter:
            do_rotation: False
            do_scale: False
            do_translation: False
            size_hint_y: None
            height: stacklayout.height
            StackLayout:
                id: stacklayout
                width: scrollview.width
                size_hint_y: None
                height: self.minimum_height
                spacing: '10dp'
                padding: '10dp'

[FileThumbEntry@Widget]:
    locked: False
    path: ctx.path
    selected: self.path in ctx.controller().selection
    size_hint: None, None

    on_touch_down: self.collide_point(*args[1].pos) and ctx.controller().entry_touched(self, args[1])
    on_touch_up: self.collide_point(*args[1].pos) and ctx.controller().entry_released(self, args[1])
    size: ctx.controller().thumbsize + dp(52), ctx.controller().thumbsize + dp(52)

    canvas:
        Color:
            rgba: 1, 1, 1, 1 if self.selected else 0
        BorderImage:
            border: 8, 8, 8, 8
            pos: root.pos
            size: root.size
            source: 'atlas://data/images/defaulttheme/filechooser_selected'

    Image:
        size: ctx.controller().thumbsize, ctx.controller().thumbsize
        source: ctx.controller()._get_image(ctx)
        pos: root.x + dp(24), root.y + dp(40)
    Label:
        text: ctx.name
        text_size: (ctx.controller().thumbsize, self.height)
        halign: 'center'
        shorten: True
        size: ctx.controller().thumbsize, '16dp'
        pos: root.center_x - self.width / 2, root.y + dp(16)

    Label:

        text: ctx.controller()._gen_label(ctx)
        font_size: '11sp'
        color: .8, .8, .8, 1
        size: ctx.controller().thumbsize, '16sp'
        pos: root.center_x - self.width / 2, root.y
        halign: 'center'

    """)

DEFAULT_THEME = 'atlas://data/images/defaulttheme/'
FILE_ICON = DEFAULT_THEME + 'filechooser_file'
FOLDER_ICON = DEFAULT_THEME + 'filechooser_folder'

FLAC_MIME = "audio/flac"
MP3_MIME = "audio/mpeg"

AVCONV_BIN = 'avconv'
FFMPEG_BIN = 'ffmpeg'
CONVERT_BIN = 'convert'

class FileChooserThumbView(FileChooserController):
    '''Implementation of :class:`FileChooserController` using an icon view
    with thumbnails.
    '''
    _ENTRY_TEMPLATE = 'FileThumbEntry'

    thumbdir = StringProperty(mkdtemp(prefix="kivy-", suffix="-thumbs"))
    '''Custom directory for the thumbnails. By default it uses tempfile to
    generate it randomly.
    '''

    showthumbs = NumericProperty(-1)
    '''Thumbnail limit. If set to a number > 0, it will show the thumbnails
    only if the directory doesn't contain more files or directories. If set
    to 0 it won't show any thumbnail. If set to a number < 0 it will always
    show the thumbnails, regardless of how many items the current directory
    contains.
    By default it is set to -1, so it will show all the thumbnails.
    '''

    thumbsize = NumericProperty(dp(64))
    """The size of the thumbnails. It defaults to 64dp.
    """

    play_overlay = StringProperty("")
    """Path to a PIL supported image file (e.g. png) that will be put over
    videos thumbnail (e.g. a "play" button). If it's an empty string nothing
    will happen.
    Defaults to "".
    """

    filmstrip_left = StringProperty("")

    filmstrip_right = StringProperty("")

    _thumbs = DictProperty({})
    scrollview = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(FileChooserThumbView, self).__init__(**kwargs)
        if not exists(self.thumbdir):
            os.mkdir(self.thumbdir)

    def clear_cache(self, *args):
        try:
            shutil.rmtree(self.thumbdir, ignore_errors=True)
        except:
            traceback.print_exc()

    def _dir_has_too_much_files(self, path):
        if (self.showthumbs < 0):
            return False

        nbrFileInDir = len(
            os.listdir(dirname(path))
        )
        return nbrFileInDir > self.showthumbs

    def _get_image(self, ctx):
        try:
            App.get_running_app().bind(on_stop=self.clear_cache)
        except AttributeError:
            pass
        except:
            traceback.print_exc()
            
        if ctx.isdir:
            return FOLDER_ICON

        # if the directory contains more files
        # than what has been configurated
        # we directly return a default file icon
        if self._dir_has_too_much_files(ctx.path):
            return FILE_ICON

        try:
            mime = get_mime(ctx.name)

            # if we already have generated the thumb
            # for this file, we get it directly from our
            # cache
            if ctx.path in self._thumbs.keys():
                return self._thumbs[ctx.path]

            # if it's a picture, we don't need to do
            # any transormation
            if is_picture(mime, ctx.name):
                return ctx.path

            # for mp3/flac an image can be embedded
            # into the file, so we try to get it
            if mime == MP3_MIME:
                return self._generate_image_from_mp3(
                    ctx.path
                )

            if mime == FLAC_MIME:
                return self._generate_image_from_flac(
                    ctx.path
                )
            # if it's a video we will extract a frame out of it
            if "video/" in mime:
                return self._generate_image_from_video(ctx.path)
        except:
            traceback.print_exc()
            return FILE_ICON

        return FILE_ICON

    def _generate_image_from_flac(self, flacPath):
        # if we don't have the python module to
        # extract image from flac, we just return
        # default file's icon
        try:
            from mutagen.flac import FLAC
        except ImportError:
            return FILE_ICON

        try:
            audio = FLAC(flacPath)
            art = audio.pictures

            return self._generate_image_from_art(
                art,
                flacPath
            )
        except IndexError, TypeError:
            return FILE_ICON
        except:
            return FILE_ICON

    def _generate_image_from_mp3(self, mp3Path):
        # if we don't have the python module to
        # extract image from mp3, we just return
        # default file's icon
        try:
            from mutagen.id3 import ID3
        except ImportError:
            return FILE_ICON

        try:
            audio = ID3(mp3Path)
            art = audio.getall("APIC")
            return self._generate_image_from_art(
                art,
                mp3Path
            )
        except IndexError, TypeError:
            return FILE_ICON
        except:
            return FILE_ICON

    def _generate_image_from_art(self, art, path):
        pix = pix_from_art(art)
        ext = mimetypes.guess_extension(pix.mime)
        if ext == 'jpe':
            ext = 'jpg'

        image = self._generate_image_from_data(
            path,
            ext,
            pix.data
        )

        self._thumbs[path] = image
        return image

    def _gen_temp_file_name(self, extension):
        return join(self.thumbdir, mktemp()) + extension

    def _generate_image_from_data(self, path, extension, data):
        # data contains the raw bytes
        # we save it inside a file, and return this temporay
        # file's parth

        image = self._gen_temp_file_name(extension)
        with open(image, "w") as img:
            img.write(data)
        return image

    def _generate_image_from_video(self, videoPath):
        # we try to use an external software (avconv or ffmpeg)
        # to get a frame as an image, otherwise => default file icon
        data = extract_image_from_video(videoPath)

        try:
            if data:
                thumbPath = self._generate_image_from_data(
                    videoPath,
                    ".png",
                    data)

                if self.play_overlay != "" and exists(self.play_overlay):
                    thumb = Image.open(thumbPath)

                    # if we want the thumbnail to contains the complete image
                    # we can use instead the thumbnail function
                    # as used by the play button below
                    # here we use that in order to have squarre image that keep
                    # the ratio and are "full" (i.e we cut a squarre in the
                    # middle of the image
                    thumb = ImageOps.fit(
                        thumb,
                        compute_size(self.thumbsize, *thumb.size),
                        Image.ANTIALIAS
                    )
                    playButton = Image.open(self.play_overlay)

                    playButtonSize = min(thumb.size)
                    print(playButtonSize)
                    playButton.thumbnail(
                        (playButtonSize, playButtonSize),
                        Image.ANTIALIAS

                    )
                    print(thumb.size)
                    print(playButton.size)
                    thumb.paste(playButton, (0, 0), playButton)
                    thumb.save(thumbPath)

                    self._thumbs[videoPath] = thumbPath

                return thumbPath
            else:
                return FILE_ICON
        except:
            traceback.print_exc()
            return FILE_ICON


    def _gen_label(self, ctx):
        size = ctx.get_nice_size()
        temp = ""
        try:
            temp = os.path.splitext(ctx.name)[1][1:].upper()
        except IndexError:
            pass
        if ctx.name.endswith(".tar.gz"):
            temp = "TAR.GZ"
        if ctx.name.endswith(".tar.bz2"):
            temp = "TAR.BZ2"
        if temp == "":
            label = size
        else:
            label = size + " - " + temp
        return label

    def _unicode_noerrs(self, string):
        if not string:
            return u""
        return unicode(string, encoding=chardetect(string)["encoding"])


# test if the file is a supported picture
# file
def is_picture(mime, name):
    if mime is None:
        return False

    return "image/" in mime and (
            "jpeg" in mime or
            "jpg" in mime or
            "gif" in mime or
            "png" in mime
        ) and not name.endswith(".jpe")


def pix_from_art(art):
    pix = None
    if len(art) == 1:
        pix = art[0]
    elif len(art) > 1:
        for pic in art:
            if pic.type == 3:
                pix = pic
    if not pix:
        # This would raise an exception if no image is present,
        # and the default one would be returned
        pix = art[0]
    return pix


def get_mime(fileName):
    try:
        mime = mimetypes.guess_type(fileName)[0]
        if mime is None:
            return ""
        return mime
    except TypeError:
        return ""

    return ""


def extract_image_from_video(path):
    data = None
    if exec_exists(AVCONV_BIN):
        data = get_png_from_video(AVCONV_BIN, path)
    elif exec_exists(FFMPEG_BIN):
        data = get_png_from_video(FFMPEG_BIN, path)
    return data


# generic function to call a software to extract a PNG
# from an video file, it return the raw bytes, not an
# image file
def get_png_from_video(software, videoPath):
    return subprocess.Popen(
        [
            software,
            '-i',
            videoPath,
            '-an',
            '-vcodec',
            'png',
            '-vframes',
            '1',
            '-ss',
            '00:00:01',
            '-y',
            '-f',
            'rawvideo',
            '-'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()[0]

def stack_images(software, bg, fg, out):
    # You need ImageMagick to stack one image onto another
    p = subprocess.Popen([software, bg, "-gravity", "Center", fg, "-compose", "Over", "-composite", out])
    p.wait()

def exec_exists(bin):
    try:
        subprocess.check_output(["which", bin])
        return True
    except subprocess.CalledProcessError:
        return False
    except OSError:
        return False
    except:
        return False

def compute_size(maxs, imgw, imgh):
    if imgw > imgh:
        return maxs, maxs*imgh/imgw
    else:
        return maxs*imgw/imgh, maxs

if __name__ == "__main__":
    from kivy.base import runTouchApp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label

    box = BoxLayout(orientation="vertical")
    fileChooser = FileChooserThumbView(thumbsize=128, play_overlay="/home/davideddu/player-play-overlay.png")
    label = Label(markup=True, size_hint_y=None)
    fileChooser.mylabel = label

    box.add_widget(fileChooser)
    box.add_widget(label)

    def setlabel(instance, value):
        instance.mylabel.text = "[b]Selected:[/b] {0}".format(value)

    fileChooser.bind(selection=setlabel)

    runTouchApp(box)
