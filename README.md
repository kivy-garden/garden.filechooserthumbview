FileChooserThumbView
====================

The FileChooserThumbView widget is similar to FileChooserIconView,
but if possible it shows a thumbnail instead of a normal icon.

Usage
-----

You can set some properties in order to control its performance:

* **showthumbs:** Thumbnail limit. If set to a number > 0, it will show the thumbnails only if the directory doesn't contain more files or directories. If set to 0 it won't show any thumbnail. If set to a number < 0 it will always show the thumbnails, regardless of how many items the current directory contains. By default it is set to -1, so it will show all the thumbnails.
* **thumbdir:** Custom directory for the thumbnails. By default it uses tempfile to generate it randomly.
* **thumbsize:** The size of the thumbnails. It defaults to 64dp.

#### Example:
```python
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
```

#### Dependencies:
* Kivy version is not less than 1.10.1
* PIL
* [KivyMD](https://github.com/HeaTTheatR/KivyMD)

#### LICENSE:
* MIT
* Project modified from repository - [FilechooserThumbview](https://github.com/kivy-garden/garden.filechooserthumbview)

Video previous
==============
<p align="center">
    <a href="https://www.youtube.com/watch?v=TkRcCoJAd0E"><img src="https://github.com/HeaTTheatR/FilechooserThumbview/blob/master/prevideo.png"></a>
</p>

Image previous
==============
<p align="center">
    <img src="https://github.com/HeaTTheatR/FilechooserThumbview/blob/master/screenshot.png">
</p>

Text previous
==============
<p align="center">
    <img src="https://github.com/HeaTTheatR/FilechooserThumbview/blob/master/screenshot-2.png">
</p>

#### VERSION:
* 0.1.1