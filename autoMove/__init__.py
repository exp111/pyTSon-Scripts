import pytson, ts3lib, ts3defines
from ts3plugin import ts3plugin
from datetime import datetime
from pytson import getPluginPath
from configparser import ConfigParser
import json
from os import path

class autoMove(ts3plugin):
    name = "autoMove"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = False
    version = "1.0"
    author = "exp111"
    description = "Move Clients automatically to your other Channels"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = None
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL, 0, "Set as Source Channel", ""),
                 (ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL, 1, "Remove from Source Channels", ""),
                 (ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL, 2, "Set as Destination Channel", ""),
                 (ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL, 3, "Remove from Destination Channels", "")]
    hotkeys = []
    debug = False
    ini = path.join(getPluginPath(), "scripts", name, "config.ini")
    cfg = ConfigParser()

    sourceChannel = []
    destinationChannel = []

    def timestamp(self): return '[{:%Y-%m-%d %H:%M:%S}] '.format(datetime.now())

    def writeConfig(self):
        self.cfg["general"] = {"sourceChannel" : json.dumps(self.sourceChannel), "destinationChannel" : json.dumps(self.destinationChannel)}

        with open(self.ini, 'w') as configfile:
            self.cfg.write(configfile)

    def readConfig(self):
        if path.isfile(self.ini):
            self.cfg.read(self.ini)
        
        self.sourceChannel = json.loads(self.cfg["general"]["sourceChannel"])
        self.destinationChannel = json.loads(self.cfg["general"]["destinationChannel"])

    def __init__(self):
        #Load config
        if path.isfile(self.ini):
            self.readConfig()
        else:
            self.writeConfig()
            
        ts3lib.logMessage("{0} script for pyTSon by {1} loaded from \"{2}\".".format(self.name,self.author,__file__), ts3defines.LogLevel.LogLevel_INFO, "Python Script", 0)
        if self.debug: ts3lib.printMessageToCurrentTab("{0}[color=orange]{1}[/color] Plugin for pyTSon by [url=https://github.com/{2}]{2}[/url] loaded.".format(self.timestamp(),self.name,self.author))

    def addChannel(self, channel, targetList):
        if channel in targetList:
            ts3lib.printMessageToCurrentTab("Channel already added.")
            return False
        else:
            targetList.append(channel)
        return True

    def removeChannel(self, channel, targetList):
        if channel in targetList:
            targetList.remove(channel)
        else:
            ts3lib.printMessageToCurrentTab("Channel not in list.")
            return False
        return True

    def onMenuItemEvent(self, schid, atype, menuItemID, channel):
        try:
            result = False
            if menuItemID == 0:
                result = self.addChannel(channel, self.sourceChannel)
            elif menuItemID == 1:
                result = self.removeChannel(channel, self.sourceChannel)
            elif menuItemID == 2:
                result = self.addChannel(channel, self.destinationChannel)
            elif menuItemID == 3:
                result = self.removeChannel(channel, self.destinationChannel)

            #Save to config
            if result == True:
                self.writeConfig()

        except: from traceback import format_exc;ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def onClientMoveEvent(self, serverConnectionHandlerID, clientID, oldChannelID, newChannelID, visibility, moveMessage):
        try:
            if newChannelID in self.sourceChannel:
                if len(self.destinationChannel) > 0:
                    destChannel = self.destinationChannel[0] #TODO: Check which channel is best
                    (err, path, password) = ts3lib.getChannelConnectInfo(serverConnectionHandlerID, destChannel)
                    ts3lib.requestClientMove(serverConnectionHandlerID, clientID, destChannel, password)
                else:
                    ts3lib.printMessageToCurrentTab("No Destination Channel availabe.")
        except: from traceback import format_exc;ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)
