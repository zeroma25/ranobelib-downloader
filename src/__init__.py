"""
RanobeLIB API - модуль для скачивания новелл с сайта RanobeLIB
"""

from .api import RanobeLibAPI
from .auth import RanobeLibAuth
from .processing import ContentProcessor
from .branches import get_branch_info_for_display, get_formatted_branches_with_teams
from .creators import EpubCreator, Fb2Creator, TxtCreator, HtmlCreator
from .img import ImageHandler
from .parser import RanobeLibParser
from .settings import Settings, settings

__version__ = "0.1"

__all__ = [
    "ContentProcessor",
    "EpubCreator",
    "Fb2Creator",
    "TxtCreator",
    "HtmlCreator",
    "ImageHandler",
    "RanobeLibAPI",
    "RanobeLibAuth",
    "RanobeLibParser",
    "Settings",
    "settings",
    "get_branch_info_for_display",
    "get_formatted_branches_with_teams",
] 