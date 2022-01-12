#!/usr/bin/env python3

import os
from setuptools import setup

setup(
    name = "ble-wifi-config",
    version = "0.1",
    author = "Vinh Le",
    author_email = "vinhlq@hotmail.com",
    description = "Config wifi SSID & Passphrase over BLE on raspberry pi",
    license = "BSD",
    url = "https://github.com/vinhlq/raspi-ble-wifi-config",
    python_requires='>3.5.2',
    packages=['src'],
    install_requires=[
      'dbus-python',
      'pygobject'
    ],
    # this will create the /usr/local/bin/ble-wifi-config entrypoint script
    entry_points = {
        'console_scripts' : [
          'ble-wifi-config = src.app:main'
        ]
    },
    data_files = [
        ('/lib/systemd/system/', ['ble-wifi-config.service'])
        ],
    classifiers=[
        "License :: OSI Approved :: BSD License",
    ],
)