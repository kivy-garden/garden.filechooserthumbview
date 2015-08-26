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
