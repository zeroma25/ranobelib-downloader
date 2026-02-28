"""
RanobeLIB API - модуль для скачивания новелл с сайта RanobeLIB
"""

from .api import RanobeLibAPI
from .auth import RanobeLibAuth
from .branches import get_branch_info_for_display, get_formatted_branches_with_teams
from .creators import EpubCreator, Fb2Creator, HtmlCreator, TxtCreator
from .img import ImageHandler
from .parser import RanobeLibParser
from .processing import ContentProcessor
from .settings import Settings, settings

__version__ = "0.3.5"

__all__ = [
    "ContentProcessor",
    "EpubCreator",
    "Fb2Creator",
    "get_branch_info_for_display",
    "get_formatted_branches_with_teams",
    "HtmlCreator",
    "ImageHandler",
    "RanobeLibAPI",
    "RanobeLibAuth",
    "RanobeLibParser",
    "Settings",
    "settings",
    "TxtCreator",
] 