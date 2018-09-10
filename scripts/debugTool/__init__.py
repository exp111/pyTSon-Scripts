import ts3lib as ts3
from ts3plugin import ts3plugin, PluginHost
import ts3defines
import pytson
import datetime, os, time


class debugTool(ts3plugin):
    name = "DebugTool"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = ""
    offersConfigure = False
    commandKeyword = ""
    infoTitle = ""
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CLIENT, 0, "Debug", "")]
    hotkeys = []
    debug = False


    def __init__(self):
        ts3.printMessageToCurrentTab('[{:%Y-%m-%d %H:%M:%S}]'.format(datetime.datetime.now())+" [color=orange]"+self.name+"[/color] Plugin for pyTSon by "+self.author+" loaded.")

    def onMenuItemEvent(self, schid, atype, menuItemID, selectedItemID):
        if menuItemID == 0:
            ts3.requestClientVariables(schid, selectedItemID, "")
            shit = "[COLOR=red]"
            shit += ts3.getClientDisplayName(schid, selectedItemID)[1] + " (" + str(selectedItemID) + "):\n"
            shit += "Unique ID: " + ts3.getClientVariableAsString(schid, selectedItemID, ts3defines.ClientProperties.CLIENT_UNIQUE_IDENTIFIER)[1] + "\n"
            shit += "MetaData: " + ts3.getClientVariableAsString(schid, selectedItemID, ts3defines.ClientProperties.CLIENT_META_DATA)[1] + "\n"
            shit += "IsTalking: " + ts3.getClientVariableAsString(schid, selectedItemID, ts3defines.ClientProperties.CLIENT_FLAG_TALKING)[1] + "\n"
            shit += "[/COLOR]"
            ts3.printMessageToCurrentTab(shit)