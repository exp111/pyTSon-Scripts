from ts3plugin import ts3plugin, PluginHost
import ts3lib as ts3
import ts3defines, pytson

class info(ts3plugin):
    name = "no u"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = "no no u"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = "no u"
    menuItems = []
    hotkeys = []

    def timestamp(self): return '[{:%Y-%m-%d %H:%M:%S}] '.format(datetime.now())

    def __init__(self):
        self.dlg = None
       
    def onTextMessageEvent(self, schid, targetMode, toID, fromID, fromName, fromUniqueIdentifier, message, ffIgnored):
        try:
            mClientID = ts3.getClientID(schid)[1]
            if (mClientID == fromID):
                return

            messageL = message.lower()
            parts = message.split(" ")
            
            msg = "no "
            foundNo = False
            foundU = False

            for current in parts:
                if (current == "no"):
                    msg += "no "
                    foundNo = True
                elif (current == "u"):
                    msg += current
                    foundU = True
                    break
                else:
                    continue
            
            if (not foundNo or not foundU):
                return

            if (targetMode == 1): #private msg
                ts3.requestSendPrivateTextMsg(schid, msg, fromID, "")
            if (targetMode == 2): #channel msg
                ts3.requestSendChannelTextMsg(schid, msg, 0, "")
        except:
            from traceback import format_exc;ts3.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon", 0)

    def onClientPokeEvent(self, schid, fromClientID, pokerName, pokerUniqueIdentity, message, ffIgnored):
        try:
            mClientID = ts3.getClientID(schid)[1]
            if (mClientID == fromClientID):
                return

            messageL = message.lower()
            parts = message.split(" ")
            
            msg = "no "
            foundNo = False
            foundU = False

            for current in parts:
                if (current == "no"):
                    msg += "no "
                    foundNo = True
                elif (current == "u"):
                    msg += current
                    foundU = True
                    break
                else:
                    continue
            
            if (not foundNo or not foundU):
                return

            ts3.requestClientPoke(schid, fromClientID, msg, "")
        except:
            from traceback import format_exc;ts3.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon", 0)