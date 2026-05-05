import sys
import os


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path):
    return os.path.join(get_app_dir(), relative_path)
