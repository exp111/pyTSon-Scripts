from ts3plugin import ts3plugin, PluginHost
import ts3lib
import ts3defines, pytson
import os
from PythonQt.QtGui import *
from PythonQt.QtCore import *

class info(ts3plugin):
    name = "iconReplacer"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = "Replaces the new (ugly) icon with the old one"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = "Icon Replacer"
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_GLOBAL, 0, "Replace Icon", "")]
    hotkeys = []

    def __init__(self):
        self.dlg = None

    def onMenuItemEvent(self, schid, atype, menuItemID, selectedItemID):
        try:
            if menuItemID == 0:
                pluginPath = pytson.getPluginPath("scripts", self.name)
                mainWindow = [item for item in QApplication.instance().topLevelWidgets() if type(item).__name__ == "MainWindow"][0]
                if not mainWindow:
                    return
                mainWindow.setWindowIcon(QIcon(os.path.join(pluginPath, "small.ico")))
        except: from traceback import format_exc;ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)