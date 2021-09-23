#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="napari_hdf5_hts",
    version="1a",
    install_requires=[
        "natsort",
        "h5py",
    ],
)
