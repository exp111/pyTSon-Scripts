from ts3plugin import ts3plugin, PluginHost
import ts3lib as ts3
import ts3defines, pytson
import urllib, urllib.request
import json

class info(ts3plugin):
    name = "addBookmarkFix"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = "Remove links with faulty tags"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = "addBookmarkFix"
    menuItems = []
    hotkeys = []

    def timestamp(self): return '[{:%Y-%m-%d %H:%M:%S}] '.format(datetime.now())

    def __init__(self):
        self.dlg = None
       
    def onTextMessageEvent(self, schid, targetMode, toID, fromID, fromName, fromUniqueIdentifier, message, ffIgnored):
        try:
            messageL = message.lower()

            bookmarkFind = messageL.find("addbookmark=") # ts3server://localhost?addbookmark=
            if (bookmarkFind == -1):
                return

            closedFind = messageL.find("]")
            if (closedFind == -1):
                return

            tagFind = messageL.find("<")
            if (tagFind == -1):
                return

            if (tagFind > closedFind or tagFind < bookmarkFind):
                return

            ts3.printMessageToCurrentTab("[color=red]{0} send a faulty link[/color]".format(fromName))

            return True # ignore msg
        except:
            from traceback import format_exc;ts3.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon", 0)