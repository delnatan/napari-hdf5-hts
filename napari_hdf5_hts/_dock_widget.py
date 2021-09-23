"""
This module is an example of a barebones QWidget plugin for napari

It implements the ``napari_experimental_provide_dock_widget`` hook specification.
see: https://napari.org/docs/dev/plugins/hook_specifications.html

Replace code below according to your needs.
"""
from napari_plugin_engine import napari_hook_implementation
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QListWidget,
    QLabel,
)
from magicgui import magic_factory
import h5py
from pathlib import Path
from natsort import natsorted
from skimage.filters import threshold_otsu
import napari


class HDF5ImageWidget(QWidget):
    # your QWidget.__init__ can optionally request the napari viewer instance
    # in one of two ways:
    # 1. use a parameter called `napari_viewer`, as done here
    # 2. use a type annotation of 'napari.viewer.Viewer' for any parameter
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari.current_viewer()

        openbtn = QPushButton("Open h5 file")
        openbtn.clicked.connect(self._open_dialog)

        self.datakeys = None
        self.listwidget = QListWidget()
        self.imagelabel = QLabel("<image filename>.h5")
        self.pixszlabel = QLabel("<pixel size> µm")
        self.objlabel = QLabel("<objective_name>")

        self.setLayout(QVBoxLayout())

        self.layout().addWidget(openbtn)
        self.layout().addWidget(self.imagelabel)
        self.layout().addWidget(self.listwidget)
        self.layout().addWidget(self.pixszlabel)
        self.layout().addWidget(self.objlabel)

    def _open_dialog(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open file",
            "",
            "HDF5 image file (*.h5 *.hdf5);;",
        )

        if filename:

            self.viewer.layers.clear()
            self.listwidget.clear()

            with h5py.File(filename, "r") as f:
                datakeys = list(f.keys())
                chnames = f.attrs["channels"]
                try:
                    pxdims = f.attrs["pixelsize"]
                    objname = f.attrs["objective_name"]
                except AttributeError:
                    pxdims = None
                    objname = None

            self.filename = filename
            filepath = Path(filename)
            displayname = filepath.name
            
            self.imagelabel.setText(displayname)

            if pxdims is not None:
                self.pixszlabel.setText(f"{pxdims[0]:0.4f} µm / pixel")
            if objname is not None:
                self.objlabel.setText(f"{objname.split(',')[0]}")

            datakeys = natsorted(datakeys)

            self.chnames = chnames
            self.datakeys = datakeys

            for key in self.datakeys:
                self.listwidget.addItem(key)

            self.listwidget.currentItemChanged.connect(self._fetch_data)

    def _fetch_data(self, key):
        if key is not None:
            key_text = key.text()
            # clear layers
            self.viewer.layers.clear()
            # read image data
            with h5py.File(self.filename, "r") as f:
                _img = f[key_text][:]
            # add image data
            self.viewer.add_image(
                _img,
                channel_axis=3,
                colormap=["cyan", "magenta", "gray"],
                name=[f"{key_text} ({c})" for c in self.chnames],
            )


@magic_factory(call_button="Run threshold")
def example_magic_widget(
    img_layer: "napari.layers.Image",
) -> "napari.types.LabelsData":
    # get data from Image layer
    if img_layer is not None:
        _data = img_layer.data
        print(_data.shape)
        print(f"you have selected {img_layer}")
        thres = threshold_otsu(_data)
        _out = _data > thres
        return _out.astype(int)


# the list of widgets returned here shows up under the plugin menu
@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [HDF5ImageWidget, example_magic_widget]
