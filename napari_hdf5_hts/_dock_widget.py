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
    QCheckBox,
    QLabel,
    QGroupBox,
)
from magicgui import magic_factory
from typing import List
import h5py
from pathlib import Path
from natsort import natsorted
from skimage.filters import threshold_otsu
from skimage.restoration import rolling_ball
import napari


def colormapper(ch_name):
    if "Brightfield" in ch_name:
        return "gray"
    elif "561" in ch_name:
        return "bop orange"
    elif "642" in ch_name:
        return "red"
    else:
        return "viridis"


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
        self.clearcheckbox = QCheckBox("Clear current layers")
        self.channelgroup = QGroupBox("Available channels")
        self.imagelabel = QLabel("<image filename>.h5")
        self.pixszlabel = QLabel("<pixel size> µm")
        self.objlabel = QLabel("<objective_name>")

        self.chbox = QVBoxLayout()
        self.channelgroup.setLayout(self.chbox)

        self.setLayout(QVBoxLayout())

        self.layout().addWidget(openbtn)
        self.layout().addWidget(self.imagelabel)
        self.layout().addWidget(self.clearcheckbox)
        self.layout().addWidget(self.channelgroup)
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
                except BaseException as err:
                    print(f"Unexpected {err=}, {type(err)=}")
                    raise

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
            self.chindices = {ch: i for i, ch in enumerate(self.chnames)}
            self.datakeys = datakeys

            # remove current channels in `chbox`
            for checkbox in self.channelgroup.findChildren(QCheckBox):
                checkbox.deleteLater()

            # populate channel list (start with all checked)
            for i, ch in enumerate(self.chnames):
                _chbox = QCheckBox(f"[{i}]=>{ch}")
                _chbox.setChecked(True)
                self.chbox.addWidget(_chbox)

            for key in self.datakeys:
                self.listwidget.addItem(key)

            self.listwidget.currentItemChanged.connect(self._fetch_data)

    def _fetch_data(self, key):

        clear_layers = self.clearcheckbox.isChecked()

        if key is not None:
            key_text = key.text()
            # clear layers
            if clear_layers:
                self.viewer.layers.clear()

            # determine channel selections
            active_ch = []
            active_ch_str = []

            for checkbox in self.channelgroup.findChildren(QCheckBox):
                _ch_str = checkbox.text().split("=>")[1]
                if checkbox.isChecked():
                    active_ch_str.append(_ch_str)
                    active_ch.append(self.chindices[_ch_str])

            active_ch_tuple = tuple(active_ch)

            # read image data
            with h5py.File(self.filename, "r") as f:
                _img = f[key_text][:]

            _img = _img[..., active_ch_tuple]

            # add image data
            layer_names = [
                f"{key_text} ({c})"
                for i, c in enumerate(self.chnames)
                if i in active_ch
            ]

            current_layers = [layer.name for layer in self.viewer.layers]

            # if any requested layer is not in current layers, then add image
            if not any(check in current_layers for check in layer_names):
                self.viewer.add_image(
                    _img,
                    channel_axis=3,
                    colormap=[colormapper(ch) for ch in active_ch_str],
                    name=layer_names,
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


@magic_factory(call_button="Crop image")
def ROI_cropping(
    img_layer: "napari.layers.Image",
    shape_layer: "napari.layers.Shapes",
) -> List[napari.types.LayerDataTuple]:

    if img_layer is not None and shape_layer is not None:

        # get current image in view
        _data = img_layer._data_view

        # and the shape layer
        _shape = shape_layer.data

        # get only the rectangular ROI
        _roitype = shape_layer.shape_type
        _rectrois = [
            _shape[i] for i, roi in enumerate(_roitype) if roi == "rectangle"
        ]

        ret = []

        # rectangular coordinates are upper-left, upper-right, lower-right, lower-left
        # we only need upper-left and lower-right (0,2)

        for i, coords in enumerate(_rectrois):
            xi, yi = coords[0][1:].astype(int)  # upper-left
            xf, yf = coords[2][1:].astype(int)  # lower-right
            print("x-range : ", xi, xf)
            print("y-range : ", yi, yf)
            _crop = _data[yi:yf, xi:xf]
            ret.append((_crop, {"name": f"Crop {i+1}"}))

        return ret


@magic_factory(
    call_button="Subtract background",
    ball_radius={"widget_type": "SpinBox", "value": 40},
)
def rolling_ball_baseline(
    img_layer: napari.layers.Image,
    ball_radius=40.0,
) -> List[napari.types.LayerDataTuple]:
    if img_layer is not None:
        _data = img_layer._data_view
        bg = rolling_ball(_data, radius=ball_radius)
        return [
            (_data - bg, {"name": "Corrected image"}),
            (bg, {"name": "background"}),
        ]


# the list of widgets returned here shows up under the plugin menu
@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [HDF5ImageWidget, ROI_cropping, rolling_ball_baseline]
