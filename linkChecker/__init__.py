from ts3plugin import ts3plugin, PluginHost
import ts3lib as ts3
import ts3defines, pytson
import urllib, urllib.request
import json

class info(ts3plugin):
    name = "Link Checker"
    apiVersion = pytson.getCurrentApiVersion()
    requestAutoload = True
    version = "1.0"
    author = "Exp"
    description = "Shows you informations to links posted in chat."
    offersConfigure = False
    commandKeyword = ""
    infoTitle = "Link Checker"
    menuItems = []
    hotkeys = []
    apiKey = "AIzaSyCPROZMWeJAP5qKY8jwN_WZNmuDHxRigPU"

    def timestamp(self): return '[{:%Y-%m-%d %H:%M:%S}] '.format(datetime.now())

    def __init__(self):
        self.dlg = None
       
    def onTextMessageEvent(self, schid, targetMode, toID, fromID, fromName, fromUniqueIdentifier, message, ffIgnored):
        try:
            mClientID = ts3.getClientID(schid)[1]
            if (mClientID == fromID):
                return

            messageL = message.lower()

            start = messageL.find("/watch?v=") # youtube.com/watch?v=ID
            count = 9
            if (start == -1):
                start = messageL.find("youtu.be/") # youtu.be/ID
                count = 9
                if (start == -1): # anyother (ex: http://yt.vu/ID)
                    start = messageL.find(".") #look for the first point
                    start = messageL.find("/", start) #then look for the slash 
                    count = 1 #+1 for the id?
                    if (start == -1):
                        return

            end1 = message.find("[", start)
            end2 = message.find("]", start)
            if (end1 < end2):
                end = end1
            else:
                end = end2
            end1 = message.find("?", start + count)
            if (end1 < end and end1 != -1):
                end = end1

            id = message[start + count:end]

            url = "https://www.googleapis.com/youtube/v3/videos?id=" + id + "&key=" + self.apiKey + "&part=snippet,status"
            result = urllib.request.urlopen(url)
            result = result.read().decode('utf-8')
            start = result.find('"title": "')
            if (start == -1):
                return
            end = result.find('"', start + 10)
            msg = result[start + 10: end]
            if (targetMode == 2):
                ts3.printMessage(schid, "[color=red]" + msg + "[/color]", 1)
            else:
                ts3.printMessageToCurrentTab("[color=red]" + msg + "[/color]")
        except:
            from traceback import format_exc;ts3.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon", 0)