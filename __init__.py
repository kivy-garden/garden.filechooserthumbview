import os
import mimetypes
import ast
import traceback
import shutil
import subprocess

from threading import Thread
from os.path import join, exists, dirname
from tempfile import mktemp, mkdtemp

from PIL import Image

from kivy.app import App
from kivy.animation import Animation
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.utils import QueryDict
from kivy.uix.filechooser import FileChooserController
from kivy.properties import ListProperty, ObjectProperty, DictProperty, \
    StringProperty, NumericProperty
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput
from kivy.uix.anchorlayout import AnchorLayout
from kivy.clock import Clock

from kivymd.theming import ThemableBehavior

# directory with this package
_path = os.path.dirname(os.path.realpath(__file__))

Builder.load_string("""
#:import os os
#:import images_path kivymd.images_path
#:import MDSeparator kivymd.card.MDSeparator
#:import MDLabel kivymd.label.MDLabel
#:import MDRaisedButton kivymd.button.MDRaisedButton


<SelectFileBox>:
    anchor_x: 'right'
    size_hint_y: None
    height: select_button.height

    MDRaisedButton:
        id: select_button
        text: 'Select'
        on_release:
            root.callback(root.chooser.path_current_select_file)


<LabelMetaData@Label>:
    size_hint_y: None
    text_size: self.width, None
    height: self.texture_size[1]
    shorten: True
    shorten_from: 'center'


<FilechooserThumbviewWindow>:
    size_hint: None, None
    background: '{}/transparent.png'.format(images_path)

    canvas.before:
        Color:
            rgba: root.canvas_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [15,]

    BoxLayout:
        spacing: dp(10)
        padding: dp(10)
        orientation: 'vertical'

        MDLabel:
            text: '    {}'.format(root.file_chooser.path)
            color: 1, 1, 1, 1
            size_hint_y: None
            height: self.texture_size[1]

        MDSeparator:

        BoxLayout:
            spacing: dp(5)

            BoxLayout:
                id: root_box
                orientation: 'vertical'
                spacing: dp(10)

            MDSeparator:
                id: sep
                orientation: 'vertical'
                opacity: 0

            BoxLayout:
                id: box_file
                orientation: 'vertical'
                spacing: dp(10)
                size_hint: None, None
                size: 0, 0

                Image:
                    id: previous_file
                    size_hint: None, None
                    size: 0, 0
                    pos_hint: {'center_x': .5}

                MDSeparator:

                BoxLayout:
                    id: box_metadata
                    orientation: 'vertical'
                    spacing: dp(10)
                    size_hint_y: None
                    height:self.minimum_height

                    LabelMetaData:
                        id: label_name_file
                    LabelMetaData:
                        id: label_weight_file
                    LabelMetaData:
                        id: label_size_file
                    

<FileChooserThumbView>:
    on_entry_added: stacklayout.add_widget(args[1])
    on_entries_cleared: stacklayout.clear_widgets()
    _scrollview: scrollview

    ScrollView:
        id: scrollview
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
    image: image
    locked: False
    path: ctx.path
    selected: self.path in ctx.controller().selection
    size_hint: None, None
    on_touch_down:
        self.collide_point(*args[1].pos) and \
        ctx.controller().entry_touched(self, args[1])
    on_touch_up:
        self.collide_point(*args[1].pos) and \
        ctx.controller().entry_released(self, args[1])
    size:
        ctx.controller().thumbsize + dp(52), \
        ctx.controller().thumbsize + dp(52)

    canvas:
        Color:
            rgba: 1, 1, 1, 1 if self.selected else 0
        BorderImage:
            border: 8, 8, 8, 8
            pos: root.pos
            size: root.size
            source: 'atlas://data/images/defaulttheme/filechooser_selected'

    AsyncImage:
        id: image
        size: ctx.controller().thumbsize, ctx.controller().thumbsize
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

FLAC_MIME = "audio/flac"
MP3_MIME = "audio/mpeg"

AVCONV_BIN = 'avconv'
FFMPEG_BIN = 'ffmpeg'
CONVERT_BIN = 'convert'


class SelectFileBox(AnchorLayout):
    callback = ObjectProperty()
    chooser = ObjectProperty()


class FilechooserThumbviewWindow(ThemableBehavior, ModalView):
    canvas_color = ListProperty()
    file_chooser = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.canvas_color = self.theme_cls.primary_color
        self.canvas_color[3] = .75


class FileChooserThumbView(FileChooserController):
    """Implementation of :class:`FileChooserController` using an icon view
    with thumbnails."""

    _ENTRY_TEMPLATE = 'FileThumbEntry'

    callback = ObjectProperty()
    """The function that will be called when you click 'Select'.
    """

    previous_background_text_color = ListProperty([0, 0, 0, .5])
    previous_foreground_text_color = ListProperty([1, 1, 1, 1])
    """The color of the field to display the contents of text files."""

    window_size = ListProperty([dp(600), dp(400)])
    """Window size."""

    thumbsize = NumericProperty(dp(72))
    """The size of the thumbnails. It defaults to 64dp."""

    file_icon = StringProperty('{}/data/file.png'.format(_path))
    folder_icon = StringProperty('{}/data/folder.png'.format(_path))
    """Used icons in the fileshooser."""

    showthumbs = NumericProperty(-1)
    '''Thumbnail limit. If set to a number > 0, it will show the thumbnails
    only if the directory doesn't contain more files or directories. If set
    to 0 it won't show any thumbnail. If set to a number < 0 it will always
    show the thumbnails, regardless of how many items the current directory
    contains.
    By default it is set to -1, so it will show all the thumbnails.
    '''

    play_overlay = StringProperty(os.path.join(_path, 'play_overlay.png'))
    """Path to a PIL supported image file (e.g. png) that will be put over
    videos thumbnail (e.g. a "play" button). If it's an empty string nothing
    will happen.
    Defaults to "".
    """

    thumbdir = StringProperty(mkdtemp(prefix="kivy-", suffix="-thumbs"))
    '''Custom directory for the thumbnails. By default it uses tempfile to
    generate it randomly.
    '''

    filmstrip_left = StringProperty()
    filmstrip_right = StringProperty()

    _thumbs = DictProperty()
    _scrollview = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.thumbnail_generator = ThreadedThumbnailGenerator()
        if not exists(self.thumbdir):
            os.mkdir(self.thumbdir)
        self.box_previous_open = False
        self.select_file_box = None
        self.text_input_previous = None
        self.window_chooser = None
        self.real_window_width = 0
        self.type_previous = 'unknown'
        self.path_current_select_file = ''
        self.ext_data = ast.literal_eval(
            open('{}/extdata.json'.format(_path), encoding='utf-8').read())
        self.bind(selection=self.selection_file)

    def clear_cache(self, *args):
        try:
            shutil.rmtree(self.thumbdir, ignore_errors=True)
        except:
            traceback.print_exc()

    def set_select_file_box(self, *args):
        """Adds a box with a "Select" button to the bottom area
        of the file preview."""

        if not self.select_file_box:
            self.select_file_box = SelectFileBox(
                callback=self.callback, chooser=self)
            self.window_chooser.ids.box_file.add_widget(self.select_file_box)
            self.window_chooser.ids.sep.opacity = 1

    def remove_select_file_box(self):
        self.window_chooser.ids.box_file.remove_widget(self.select_file_box)
        self.window_chooser.ids.sep.opacity = 0
        self.select_file_box = None

    def remove_object_for_previous_text(self):
        if self.text_input_previous:
            self.window_chooser.ids.box_file.remove_widget(
                self.text_input_previous)
            self.text_input_previous = None

    def hide_previous_file(self):
        """Called when the preview box is open. Hides boxing previews."""

        self.remove_select_file_box()
        window_chooser = self.window_chooser
        Animation(width=self.real_window_width, d=.15).start(window_chooser)
        Animation(size=(0, 0), d=.15).start(window_chooser.ids.previous_file)
        Animation(size=(0, 0), d=.15).start(window_chooser.ids.box_file)
        window_chooser.ids.label_name_file.text = ''
        window_chooser.ids.label_weight_file.text = ''
        window_chooser.ids.label_size_file.text = ''
        self.remove_object_for_previous_text()
        self.box_previous_open = False

    def show_previous_file(self):
        """Calls animation methods to display a file preview."""

        percent_increment = (self.window_chooser.width / 100) * 40
        if not self.box_previous_open:
            self.real_window_width = self.window_chooser.width
            self.animation_window_zoom(percent_increment)
            self.animation_for_box_previous_file(percent_increment)
            self.animation_previous_file(percent_increment)
        else:
            self.animation_previous_file(percent_increment)
        self.box_previous_open = True

    def animation_previous_file(self, percent_increment):
        """Animation of the image preview when clicking on the file icon."""

        if self.type_previous in ('image', 'unknown'):
            size_file = \
                (percent_increment - dp(200), self.window_chooser.height - dp(210))
        elif self.type_previous == 'text':
            size_file = (0, 0)
        anim = Animation(size=size_file, d=.15)
        anim.bind(on_complete=self.set_select_file_box)
        anim.start(self.window_chooser.ids.previous_file)

    def animation_for_box_previous_file(self, percent_increment):
        """Animation of the box for the image when you click
        on the file icon."""

        anim = Animation(
            size=(percent_increment, self.window_chooser.height), d=.15)
        anim.bind(on_complete=self.set_file_metadata)
        anim.start(self.window_chooser.ids.box_file)

    def animation_window_zoom(self, percent_increment):
        """Animation of increasing the size of the root window."""
        anim = Animation(
            width=self.window_chooser.width + percent_increment, d=.15)
        anim.start(self.window_chooser)

    def selection_file(self, instance, value):
        """Called when clicking on the folder or file icon."""

        if not len(value):  # go back to the branch in the directory tree
            if self.box_previous_open:
                self.hide_previous_file()
            return

        self.path_current_select_file = value[0]
        self.type_previous = self.get_type_previous()
        self.set_previuos_image()

        if not self.box_previous_open:
            self.show_previous_file()
        else:
            self.remove_object_for_previous_text()
            self.show_previous_file()
            self.set_file_metadata()

    def add_object_for_previous_text(self):
        """Adds a Text object for preview the contents of text files."""

        def set_cursor(inteval):
            self.text_input_previous.cursor = [0, 0]

        with open(self.path_current_select_file) as file:
            content = file.read()
        primary_color = self.window_chooser.canvas_color
        if self.text_input_previous:
            self.text_input_previous.text = content
        else:
            self.text_input_previous = TextInput(
                size_hint_y=None, readonly=True,
                background_color=self.previous_background_text_color,
                foreground_color=self.previous_foreground_text_color,
                height=self.window_chooser.height - dp(200), text=content,
                cursor_color=primary_color, selection_color=primary_color)
            self.window_chooser.ids.box_file.add_widget(
                self.text_input_previous, index=-1)
        Clock.schedule_once(set_cursor, .5)

    def set_file_metadata(self, *args):
        image_size = os.path.getsize(self.path_current_select_file)
        self.window_chooser.ids.label_name_file.text = \
            'Name file: {}'.format(
                os.path.split(self.path_current_select_file)[1])
        self.window_chooser.ids.label_weight_file.text = \
            'Weight: {} bytes'.format(str(image_size))
        if self.type_previous == 'image':
            im = Image.open(self.path_current_select_file)
            size_data = 'Size: {}'.format(str(im.size))
        else:
            if self.type_previous != 'unknown':
                size_data = 'Type: {}'.format(self.get_type_previous(True))
            else:
                size_data = ''
        self.window_chooser.ids.label_size_file.text = size_data

        if self.type_previous == 'text':
            self.add_object_for_previous_text()

    def set_previuos_image(self):
        """Sets the image or file type icon for the Image object
        in the right corner of the manager window."""

        path_previous_icon = '{}/data/file.png'.format(_path)
        if self.type_previous == 'image':
            path_previous_icon = self.path_current_select_file
        elif self.type_previous == 'unknown':
            path_to_previous_icon = \
                self.ext_data.get(
                    os.path.splitext(self.path_current_select_file)[1], None)
            path_previous_icon = \
                path_previous_icon if not path_to_previous_icon else \
                    '{}/data/{}.png'.format(_path, path_to_previous_icon)
        self.window_chooser.ids.previous_file.source = path_previous_icon

    def get_type_previous(self, for_mata_data=False):
        """Defines one of the file preview modes:
        image, text, unknown file type."""

        mime = get_mime(self.path_current_select_file)
        if for_mata_data:
            return mime
        if 'text' in mime or 'x-sh' in mime or \
                os.path.splitext(self.path_current_select_file)[1] == '.kv':
            return 'text'
        elif 'image' in mime:
            return 'image'
        else:
            return 'unknown'

    def show(self):
        """Opens the Filechooser window."""

        self.window_chooser = FilechooserThumbviewWindow(
            size=self.window_size, file_chooser=self)
        self.window_chooser.ids.root_box.add_widget(self)
        self.window_chooser.open()

    def _dir_has_too_much_files(self, path):
        if self.showthumbs < 0:
            return False

        nbr_file_in_dir = len(
            os.listdir(dirname(path))
        )
        return nbr_file_in_dir > self.showthumbs

    def _create_entry_widget(self, ctx):
        # instantiate the widget
        widget = super(FileChooserThumbView, self)._create_entry_widget(ctx)

        kctx = QueryDict(ctx)
        # default icon
        if kctx.isdir:
            widget.image.source = \
                self.folder_icon if kctx.isdir else self.file_icon
        # schedule generation for later execution
        self.thumbnail_generator.append(widget.image, kctx, self._get_image)
        self.thumbnail_generator.run()
        #if widget.image.source == self.file_icon:
        #    self._set_previuos_image(kctx, widget)

        return widget

    def _set_previuos_image(self, kctx, widget):
        ext = os.path.splitext(kctx['path'])[1]
        name_icon = self.ext_data.get(ext)
        if name_icon:
            widget.image.source = 'data/{}.png'.format(name_icon)
        else:
            widget.image.source = 'data/file.png'

    def _get_image(self, ctx):
        try:
            App.get_running_app().bind(on_stop=self.clear_cache)
        except AttributeError:
            pass
        except:
            traceback.print_exc()

        if ctx.isdir:
            return self.folder_icon

        # if the directory contains more files
        # than what has been configurated
        # we directly return a default file icon
        if self._dir_has_too_much_files(ctx.path):
            return self.file_icon

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
            return self.file_icon

        return self.file_icon

    def _generate_image_from_flac(self, flac_path):
        # if we don't have the python module to
        # extract image from flac, we just return
        # default file's icon
        try:
            from mutagen.flac import FLAC
        except ImportError:
            return self.file_icon

        try:
            audio = FLAC(flac_path)
            art = audio.pictures

            return self._generate_image_from_art(
                art,
                flac_path
            )
        except (IndexError, TypeError):
            return self.file_icon
        except:
            return self.file_icon

    def _generate_image_from_mp3(self, mp3_path):
        # if we don't have the python module to
        # extract image from mp3, we just return
        # default file's icon
        try:
            from mutagen.id3 import ID3
        except ImportError:
            return self.file_icon

        try:
            audio = ID3(mp3_path)
            art = audio.getall("APIC")
            return self._generate_image_from_art(
                art,
                mp3_path
            )
        except (IndexError, TypeError):
            return self.file_icon
        except:
            return self.file_icon

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
        # we save it inside a file, and return this file's temporary path

        image = self._gen_temp_file_name(extension)
        with open(image, "w") as img:
            img.write(data)
        return image

    def _generate_image_from_video(self, video_path):
        # we try to use an external software (avconv or ffmpeg)
        # to get a frame as an image, otherwise => default file icon
        data = extract_image_from_video(
            video_path, self.thumbsize, self.play_overlay)

        try:
            if data:
                return self._generate_image_from_data(video_path, ".png", data)
            else:
                return self.file_icon
        except:
            traceback.print_exc()
            return self.file_icon

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


class ThreadedThumbnailGenerator(object):
    """
    Class that runs thumbnail generators in a another thread and
    asynchronously updates image widgets
    """

    def __init__(self):
        self.thumbnail_queue = []
        self.thread = None

    def append(self, widget, ctx, func):
        self.thumbnail_queue.append([widget, ctx, func])

    def run(self):
        if self.thread is None or not self.thread.isAlive():
            self.thread = Thread(target=self._loop)
            self.thread.start()

    def _loop(self):
        while len(self.thumbnail_queue) != 0:
            # call user function that generates the thumbnail
            image, ctx, func = self.thumbnail_queue.pop(0)
            image.source = func(ctx)


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


def get_mime(file_name):
    try:
        mime = mimetypes.guess_type(file_name)[0]
        if mime is None:
            return ""
        return mime
    except TypeError:
        return ""

    return ""


def extract_image_from_video(path, size, play_overlay):
    data = None
    if exec_exists(AVCONV_BIN):
        data = get_png_from_video(AVCONV_BIN, path, int(size), play_overlay)
    elif exec_exists(FFMPEG_BIN):
        data = get_png_from_video(FFMPEG_BIN, path, int(size), play_overlay)
    return data


# generic function to call a software to extract a PNG
# from an video file, it return the raw bytes, not an
# image file
def get_png_from_video(software, video_path, size, play_overlay):
    return subprocess.Popen(
        [
            software,
            '-i',
            video_path,
            '-i',
            play_overlay,
            '-filter_complex',
            '[0]scale=-1:' + str(size) + '[video],[1]scale=-1:' + str(size) +
            '[over],' +
            '[video][over]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2',
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
    p = subprocess.Popen(
        [
            software,
            bg,
            "-gravity",
            "Center",
            fg,
            "-compose",
            "Over",
            "-composite",
            out
        ])
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
    from kivy.app import App

    from kivymd.theming import ThemeManager

    KV_STRING = """
#:import MDRaisedButton kivymd.button.MDRaisedButton


FloatLayout:
    orientation: 'vertical'

    MDRaisedButton:
        text: 'Open window'
        on_release: app.open_window()
        pos_hint: {'center_x': .5, 'center_y': .5}
"""


    class Test(App):
        theme_cls = ThemeManager()
        theme_cls.primary_palette = 'BlueGrey'
        theme_cls.theme_style = 'Dark'

        def build(self):
            return Builder.load_string(KV_STRING)

        def callback(self, path):
            print(path)

        def open_window(self):
            window = FileChooserThumbView(
                callback=self.callback, window_size=(dp(450), dp(550)))
            window.show()


    Test().run()
