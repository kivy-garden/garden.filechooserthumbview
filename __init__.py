#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""FileChooserThumbView
====================

The FileChooserThumbView widget is similar to FileChooserIconView,
but if possible it shows a thumbnail instead of a normal icon.

Usage
-----

You can set some properties in order to control its performance:

* **showthumbs:** Thumbnail limit. If set to a number > 0, it will show the thumbnails only if the directory doesn't contain more files or directories. If set to 0 it won't show any thumbnail. If set to a number < 0 it will always show the thumbnails, regardless of how many items the current directory contains. By default it is set to -1, so it will show all the thumbnails.
* **thumbdir:** Custom directory for the thumbnails. By default it uses tempfile to generate it randomly.
* **thumbsize:** The size of the thumbnails. It defaults to 64d
"""

import os, mimetypes, subprocess #, traceback (enable for debugging)
from os.path import join, exists, dirname
from chardet import detect as chardetect
from tempfile import mktemp, mkdtemp

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, DictProperty, ObjectProperty, BooleanProperty, NumericProperty
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
        text: ctx.controller()._unicode_noerrs(ctx.name)
        text_size: (ctx.controller().thumbsize, self.height)
        halign: 'center'
        shorten: True
        size: ctx.controller().thumbsize, '16dp'
        pos: root.center_x - self.width / 2, root.y + dp(16)

    Label:
        text: ctx.controller()._unicode_noerrs(ctx.controller()._gen_label(ctx))
        font_size: '11sp'
        color: .8, .8, .8, 1
        size: ctx.controller().thumbsize, '16sp'
        pos: root.center_x - self.width / 2, root.y
        halign: 'center'

    """)


class FileChooserThumbView(FileChooserController):
    '''Implementation of :class:`FileChooserController` using an icon view
    with thumbnails.
    '''
    _ENTRY_TEMPLATE = 'FileThumbEntry'

    thumbdir = StringProperty(mkdtemp(prefix="kivy-", suffix="-thumbs"))
    """Custom directory for the thumbnails. By default it uses tempfile to
    generate it randomly.
    """

    showthumbs = NumericProperty(-1)
    """Thumbnail limit. If set to a number > 0, it will show the thumbnails
    only if the directory doesn't contain more files or directories. If set
    to 0 it won't show any thumbnail. If set to a number < 0 it will always
    show the thumbnails, regardless of how many items the current directory
    contains.
    By default it is set to -1, so it will show all the thumbnails.
    """

    thumbsize = NumericProperty(dp(64))
    """The size of the thumbnails. It defaults to 64dp.
    """

    _thumbs = DictProperty({})
    scrollview = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(FileChooserThumbView, self).__init__(**kwargs)
        if not exists(self.thumbdir):
            os.mkdir(self.thumbdir)

    def _get_image(self, ctx):
        to_return = None

        mutagen = False
        try:
            from mutagen.id3 import ID3
            from mutagen.flac import FLAC
            mutagen = True
        except ImportError:
            mutagen = False

        if ctx.isdir:
            to_return = 'atlas://data/images/defaulttheme/filechooser_folder'
        else:
            if (len(os.listdir(dirname(ctx.path))) <= self.showthumbs and self.showthumbs >= 0) or self.showthumbs < 0:
                try:
                    try:
                        mime = mimetypes.guess_type(ctx.name)[0]
                    except TypeError:
                        mime = ""
                    if not mime:
                        mime = ""

                    if ctx.path in self._thumbs.keys():
                        to_return = self._thumbs[ctx.path]
                    elif mime == "audio/mpeg" and mutagen:
                        try:
                            audio = ID3(ctx.path)
                            art = audio.getall("APIC")
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
                            ext = mimetypes.guess_extension(pix.mime)
                            image = join(self.thumbdir, mktemp()) + ext if ext != ".jpe" else ".jpg"
                            with open(image, "w") as img:
                                img.write(pix.data)
                            to_return = image
                            self._thumbs[ctx.path] = image
                        except IndexError, TypeError:
                            to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                        except:
                            #traceback.print_exc()
                            to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                    elif mime == "audio/flac" and mutagen:
                        try:
                            audio = FLAC(ctx.path)
                            art = audio.pictures
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
                            image = join(self.thumbdir, mktemp()) + mimetypes.guess_extension(pix.mime)
                            with open(image, "w") as img:
                                img.write(pix.data)
                            to_return = image
                            self._thumbs[ctx.path] = image
                        except IndexError, TypeError:
                            to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                        except:
                            #traceback.print_exc()
                            to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                    elif "video/" in mime:
                        data = None
                        #print "ffmpeg:", exec_exists("ffmpeg"), "- avconv:", exec_exists("avconv")
                        if exec_exists("avconv"):
                            data = subprocess.Popen(['avconv', '-i', ctx.path, '-an', '-vcodec', 'png', '-vframes', '1', '-ss', '00:00:01', '-y', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]
                        elif exec_exists("ffmpeg"):
                            data = subprocess.Popen(['ffmpeg', '-i', ctx.path, '-an', '-vcodec', 'png', '-vframes', '1', '-ss', '00:00:01', '-y', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]
                        if data:
                            image = join(self.thumbdir, mktemp()) + ".png"
                            with open(image, "w") as img:
                                img.write(data)
                            to_return = image
                            self._thumbs[ctx.path] = image
                        else:
                            #uri = 'atlas://data/images/mimetypes/{0}'.format(mime.replace("/", "_").replace("-", "_"))
                            #if atlas_texture_exists(uri):
                            #    to_return =  uri
                            #else:
                            to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                    elif "image/" in mime and ("jpeg" in mime or "jpg" in mime or "gif" in mime or "png" in mime) and not ctx.name.endswith(".jpe"):
                        to_return = ctx.path
                    else:
                        #uri = 'atlas://data/images/mimetypes/{0}'.format(mime.replace("/", "_").replace("-", "_"))
                        #if atlas_texture_exists(uri):
                        #    to_return = uri
                        #else:
                        to_return = 'atlas://data/images/defaulttheme/filechooser_file'
                except:
                    #print "EXCEPTION IN get_image"
                    #traceback.print_exc()
                    to_return = 'atlas://data/images/defaulttheme/filechooser_file'
            else:
                to_return = 'atlas://data/images/defaulttheme/filechooser_file'

        return to_return

    def _gen_label(self, ctx):
        size = ctx.get_nice_size()
        t = ""
        try:
            t = os.path.splitext(ctx.name)[1][1:].upper()
        except IndexError:
            pass
        if ctx.name.endswith(".tar.gz"):
            t = "TAR.GZ"
        if ctx.name.endswith(".tar.bz2"):
            t = "TAR.BZ2"
        if t == "":
            label = size
        else:
            label = size + " - " + t
        return label

    def _unicode_noerrs(self, string):
        if not string:
            return u""
        if type(string) == type(unicode()):
            return string
        try:
            return unicode(string, encoding=chardetect(string)["encoding"])
        except:
            raise UnicodeWarning("EXCEPTION IN FileChooserThumbView._unicode_noerrs skipped.\nThis means that file list might not contain all the files that are really present in the directory.\nThis was the exception:")
            traceback.print_exc()
            return u""


def exec_exists(bin):
    try:
        p = subprocess.check_output(["which", bin])
        return True
    except subprocess.CalledProcessError:
        return False
    except:        
        #traceback.print_exc()
        return False

if __name__ == "__main__":
    from kivy.base import runTouchApp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label

    b = BoxLayout(orientation="vertical")
    f = FileChooserThumbView(thumbsize=128)
    l = Label(markup=True, size_hint_y=None)
    f.mylabel = l

    b.add_widget(f)
    b.add_widget(l)

    def setlabel(instance, value):
        instance.mylabel.text = "[b]Selected:[/b] {0}".format(value)

    f.bind(selection=setlabel)

    runTouchApp(b)