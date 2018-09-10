import os, json, configparser, webbrowser, traceback, urllib.parse, itertools, sys, locale, os
import ts3defines, ts3lib, ts3client, ts3help, pytson, pytsonui
from datetime import datetime
from ts3lib import *
from ts3plugin import *
from pytsonui import *
from ts3defines import *
from devtools import *
from ts3help import *
from ts3client import *
from PythonQt.QtGui import *
from PythonQt.QtCore import *
from PythonQt.QtNetwork import *
from PythonQt.Qt import *
from PythonQt.private import *
from PythonQt.QtSql import *
from PythonQt.QtUiTools import *
from bluscream import *


urlrequest = False
def url(url):
    try:
        from PythonQt.QtNetwork import QNetworkAccessManager, QNetworkRequest
        #if urlrequest: return
        urlrequest = QNetworkAccessManager()
        urlrequest.connect("finished(QNetworkReply*)", urlResponse)
        urlrequest.get(QNetworkRequest(QUrl(url)))
    except:
        from traceback import format_exc
        try: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon::autorun", 0)
        except: print("Error in autorun: "+format_exc())
def urlResponse(reply):
    try:
        from PythonQt.QtNetwork import QNetworkReply
        if reply.error() == QNetworkReply.NoError:
            print("Error: %s (%s)"%(reply.error(), reply.errorString()))
            print("Content-Type: %s"%reply.header(QNetworkRequest.ContentTypeHeader))
            print("<< reply.readAll().data().decode('utf-8') >>")
            print("%s"%reply.readAll().data().decode('utf-8'))
            print("<< reply.readAll().data() >>")
            print("%s"%reply.readAll().data())
            print("<< reply.readAll() >>")
            print("%s"%reply.readAll())
            return reply
        else:
            err = logMessage("Error checking for update: %s" % reply.error(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon.PluginHost.updateCheckFinished", 0)
            if err != ts3defines.ERROR_ok:
                print("Error checking for update: %s" % reply.error())
        urlrequest.delete()
    except:
        from traceback import format_exc
        try: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "PyTSon::autorun", 0)
        except: print("Error in autorun: "+format_exc())

def findWidget(name):
    try:
        name = name.lower()
        widgets = self.topLevelWidgets()
        widgets = widgets + self.allWidgets()
        ret = dict()
        c = 0
        for x in widgets:
            c += 1
            if name in x.objectName.lower() or name in str(x.__class__).lower():
                ret["class:"+str(x.__class__)+str(c)] = "obj:"+x.objectName;continue
            if hasattr(x, "text"):
                if name in x.text.lower():
                    ret["class:"+str(x.__class__)+str(c)] = "obj:"+x.objectName
        return ret
    except:
        print("error")
def widgetbyclass(name):
    ret = []
    widgets = self.topLevelWidgets()
    widgets = widgets + self.allWidgets()
    for x in widgets:
        if name in str(x.__class__).replace("<class '","").replace("'>",""):
            ret.extend(x)
    return ret
def widgetbyobject(name):
    name = name.lower()
    widgets = self.topLevelWidgets()
    widgets = widgets + self.allWidgets()
    for x in widgets:
        if str(x.objectName).lower() == name:
            return x


def file(name, content):
    with open(os.path.expanduser("~/Desktop/"+name+".txt"), "w") as text_file:
        print(str(content), file=text_file)

def getvar(clid):
    for name, var in getItems(ConnectionProperties) + getItems(ConnectionPropertiesRare):
        ret = "=== Results for {0} ===\n".format(name)
        try:
            (err, var1) = getConnectionVariableAsDouble(schid, clid, var)
            (er, ec) = getErrorMessage(err)
            ret += "getConnectionVariableAsDouble: err={0} var={1}\n".format(ec, var1)
        except Exception as e:
            ret += "getConnectionVariableAsDouble err={0}\n".format(e)
        try:
            (err, var2) = getConnectionVariableAsUInt64(schid, clid, var)
            (er, ec) = getErrorMessage(err)
            ret += "getConnectionVariableAsUInt64: err={0} var={1}\n".format(ec, var2)
        except Exception as e:
            ret += "getConnectionVariableAsUInt64 err={0}\n".format(e)
        try:
            (err, var3) = getConnectionVariableAsString(schid, clid, var)
            (er, ec) = getErrorMessage(err)
            ret += "getConnectionVariableAsString: err={0} var={1}\n".format(ec, var3)
        except Exception as e:
            ret += "getConnectionVariableAsString err={0}\n".format(e)
        print("{0}================".format(ret))

#if error == 0:
    #error, ownnick = getClientDisplayName(schid, ownid)
    # if error == 0:
    #     def p(c, cmd="test", clid=0):
    #         if c == 0:
    #             print("Sent command "+cmd+" to PluginCommandTarget_CURRENT_CHANNEL")
    #         elif c == 1:
    #             print("Sent command "+cmd+" to PluginCommandTarget_SERVER")
    #         elif c == 2:
    #             print("Sent command "+cmd+" to PluginCommandTarget_CLIENT")
    #             sendPluginCommand(schid, cmd, c, [clid])
    #             return
    #         elif c == 3:
    #             print("Sent command "+cmd+" to PluginCommandTarget_CURRENT_CHANNEL_SUBSCRIBED_CLIENTS")
    #         elif c == 4:
    #             print("Sent command "+cmd+" to PluginCommandTarget_MAX")
    #         sendPluginCommand(schid, cmd, c, [])

def error(errorCode):
    (err, msg) = ts3lib.getErrorMessage(errorCode)
    print("{}: \"{}\" ({})".format(errorCode,msg,err))

def encoding():
    print('locale.getpreferredencoding()', locale.getpreferredencoding())
    print('sys.getfilesystemencoding()', sys.getfilesystemencoding())
    print('os.environ["PYTHONIOENCODING"]', os.environ["PYTHONIOENCODING"])
    print('chr(9786).encode("utf8"): ', chr(9786).encode("utf8"))
    print(chr(246), chr(9786), chr(9787))
    print("sys.stdout.encoding:", sys.stdout.encoding)
    print("sys.stdout.isatty()", sys.stdout.isatty())

def printMetadata(item, methods=True, signals=True, slots=True, props=True):
    meta = item.metaObject()
    print(item.className)
    if methods:
        print("--------------------------------Methods:-------(Types: 1 = Signal, 2 = Slot")
        for i in range(meta.methodCount()):
            method = meta.method(i)
            methodType = method.methodType()
            if signals and methodType == 1 or slots and methodType == 2 or methodType != 1 and methodType != 2: 
                print("[{}] [Type: {}] {} {}".format(i, methodType, method.typeName(), method.methodSignature()))
    if props:
        print("--------------------------------Properties:--------------------------------")
        for i in range(meta.propertyCount()):
            print("{}={}".format(i, meta.property(i).name()))

self = QApplication.instance()
tree = [item for item in self.allWidgets() if item.objectName == "ServerTreeView"][0]
tree.setAnimated(True)
timer = QTimer()
timer.setTimerType(2)
schid = getCurrentServerConnectionHandlerID()
last = ""
(_e, ownid) = getClientID(schid);clid=ownid;ownID=ownid
(_e, owncid) = getChannelOfClient(schid, ownid);cid=owncid;ownCID=owncid
#if "aaa_ts3Ext" in PluginHost.active: ts3host = PluginHost.active["aaa_ts3Ext"].ts3host
#else: ts3host = ts3Ext.ts3SessionHost(next(iter(PluginHost.active.values())))

print('(pyTSon v{} on {} | Console started at: {:%Y-%m-%d %H:%M:%S})'.format(pytson.getVersion(),pytson.platformstr(),datetime.now()))
print("Client curAPI: {} | LibVer: {} | LibVerNum: {}".format(pytson.getCurrentApiVersion(),ts3lib.getClientLibVersion(),ts3lib.getClientLibVersionNumber()))
print("Python {} {} API: {}".format(sys.platform, sys.version, sys.api_version))
print("sys.executable: %s"%sys.executable)
print("ts3lib.getAppPath(): %s"%ts3lib.getAppPath())
print("ts3lib.getConfigPath(): %s"%ts3lib.getConfigPath())
print("ts3lib.getResourcesPath(): %s"%ts3lib.getResourcesPath())
print("ts3lib.getPluginPath(): %s"%ts3lib.getPluginPath())
print("pytson.getConfigPath(): %s"%pytson.getConfigPath())
print("pytson.getPluginPath(): %s"%pytson.getPluginPath())
print("bluscream.getScriptPath(): %s"%getScriptPath("console"))
i = 0
for item in sys.path:
    print('sys.path[{}]"{}"'.format(i, item))
    i+=1
print("")
print(sys.flags)
print("")

class testClass(object):
    def __init__(): pass
    def testFunction(): pass

def test(name):
    name = name
    instance = self.instance()
    # widgets = instance.topLevelWidgets()
    widgets = instance.allWidgets()
    for x in widgets:
        if str(x.objectName) == name:
            return x
def check():
    timer.timeout.connect(tick)
    timer.start(500)

def tick():
    name = self.activeWindow().className()
    if name != last:
        last = name
        print(name)

def stop():
    if timer.isActive():timer.stop()

def widgetByName(name):
    return [item for item in self.allWidgets() if item.objectName == name]