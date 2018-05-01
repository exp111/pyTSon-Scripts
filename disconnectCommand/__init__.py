from ts3plugin import ts3plugin, PluginHost
import ts3lib as ts3
import ts3defines, pytson

class info(ts3plugin):
    name = "DisconnectCMD"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = "Disconnect via /py disconnect"
    offersConfigure = False
    commandKeyword = "dc"
    infoTitle = None
    menuItems = []
    hotkeys = []

    def timestamp(self): return '[{:%Y-%m-%d %H:%M:%S}] '.format(datetime.now())

    def __init__(self):
        self.dlg = None
       
    def processCommand(self, schid, command):
        ts3.printMessageToCurrentTab("Disconnecting")
        ts3.stopConnection(schid, "Disconnected via Pytson Script")
        return True