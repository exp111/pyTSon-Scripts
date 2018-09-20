import os

from ts3plugin import ts3plugin

import ts3lib, ts3defines, ts3client
import re

from json import load, loads

from PythonQt import BoolResult
from PythonQt.QtGui import (QApplication, QDialog, QAbstractItemView,
                            QTreeView, QHBoxLayout, QItemSelection,
                            QItemSelectionModel, QTextDocument, QWidget, 
                            QInputDialog, QLineEdit, QStyledItemDelegate,
                            QStyle, QFontMetrics, QIcon)
from PythonQt.QtCore import Qt, QEvent, QTimer, QMimeData, QModelIndex, QByteArray
from PythonQt.pytson import EventFilterObject
from PythonQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Helper Functions
def getClientIDByName(name:str, schid:int=0, use_displayname:bool=False, multi:bool=False):
    if not schid: schid = ts3lib.getCurrentServerConnectionHandlerID()
    if multi: results = []
    (err, clids) = ts3lib.getClientList(schid)
    for clid in clids:
        if use_displayname:(err, _name) = ts3lib.getClientDisplayName(schid, clid)
        else: (err, _name) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientProperties.CLIENT_NICKNAME)
        if name == _name:
            if multi: results.append(clid)
            else: return clid
    if multi and len(results): return results

def getChannelIDByName(name:str, schid:int=0, multi:bool=False):
    if not schid: schid = ts3lib.getCurrentServerConnectionHandlerID()
    if multi: results = []
    (err, cids) = ts3lib.getChannelList(schid)
    for cid in cids:
        (err, _name) = ts3lib.getChannelVariable(schid, cid, ts3defines.ChannelProperties.CHANNEL_NAME)
        if name == _name:
            if multi: results.append(cid)
            else: return cid
    if multi and len(results): return results

def getIDByName(name:str, schid:int=0):
    if not schid: schid = ts3lib.getCurrentServerConnectionHandlerID()
    err, sname = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_NAME)
    if sname == name: return 0, ServerTreeItemType.SERVER
    cid = getChannelIDByName(name, schid)
    if cid: return cid, ServerTreeItemType.CHANNEL
    clid = getClientIDByName(name, schid, use_displayname=True)
    if clid: return clid, ServerTreeItemType.CLIENT
    return 0, ServerTreeItemType.UNKNOWN

def getObjectByName(name:str, schid:int=0):
    if not schid: schid = ts3lib.getCurrentServerConnectionHandlerID()
    ID, Type = getIDByName(name, schid)
    if Type == ServerTreeItemType.SERVER:
        return Server(schid)
    elif Type == ServerTreeItemType.CHANNEL:
        return Channel(schid, ID)
    elif Type == ServerTreeItemType.CLIENT:
        err, clid = ts3lib.getClientID(schid)
        if err != ts3defines.ERROR_ok:
            return
        isme = clid == ID
        return Client(schid, ID, isme)
    else:
        return 0

def getOptions():
    """
    :return: dict(options)
    """
    db = ts3client.Config()
    q = db.query("SELECT * FROM Application")
    ret = {}
    while q.next():
        key = q.value("key")
        ret[key] = q.value("value")
    del db
    return ret

def parseBadgesBlob(blob: QByteArray):
    ret = {}
    next = 12
    guid_len = 0;guid = ""
    name_len = 0;name = ""
    url_len = 0;url = ""
    filename = ""
    desc_len = 0;desc = ""
    for i in range(0, blob.size()):
        try:
            if i == next: #guid_len
                guid_len = int(blob.at(i))
                guid = str(blob.mid(i+1, guid_len))
            elif i == (next + 1 + guid_len + 1):
                name_len = int(blob.at(i))
                name = str(blob.mid(i+1, name_len))
            elif i == (next + 1 + guid_len + 1 + name_len + 2):
                url_len = int(blob.at(i))
                url = str(blob.mid(i+1, url_len))
                filename = url.rsplit('/', 1)[1]
            elif i == (next + 1 + guid_len + 1 + name_len + 2 + url_len + 2):
                desc_len = int(blob.at(i))
                desc = str(blob.mid(i+1, desc_len))
                ret[guid] = {"name": name, "url": url, "filename": filename, "description": desc}
                next = (next + guid_len + 2 + name_len + 2 + url_len + 2 + desc_len + 13)
            delimiter = blob.mid(0, 12)
        except:
            ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)
            pass
    return ret, blob


def loadBadges():
    """
    Loads Badges from ts3settings.db
    :return: int(timestamp), str(ret), dict(badges)
    """
    db = ts3client.Config()
    q = db.query("SELECT * FROM Badges") #  WHERE key = BadgesListData
    timestamp = 0
    ret = {}
    badges = QByteArray()
    while q.next():
        key = q.value("key")
        if key == "BadgesListTimestamp":
            timestamp = q.value("value")
        elif key == "BadgesListData":
            ret, badges = parseBadgesBlob(q.value("value"))
    del db
    return timestamp, ret, badges

def parseBadges(client_badges):
    """
    Parses a string of badges.
    :param client_badges:
    :return: tuple(overwolf, dict(badges))
    """
    overwolf = None
    badges = []
    if "verwolf=" in client_badges and "badges=" in client_badges:
        client_badges = client_badges.split(":",1)
        overwolf = bool(int(client_badges[0].split("=",1)[1]))
        badges = client_badges[1].split("=",1)[1].replace(":badges=", ",").split(",")
    elif "verwolf=" in client_badges:
        overwolf = bool(int(client_badges.split("=")[1]))
    elif "badges=" in client_badges:
        badges = client_badges.split("=",1)[1].replace(":badges=", ",").split(",")
    return overwolf, badges

# Helper Classes & Stuff

class network(object):
    nwmc = QNetworkAccessManager()
    dlpath = {}
    def downloadFile(self, url, path):
        """
        :param url:
        :param path:
        """
        self.nwmc.connect("finished(QNetworkReply*)", self._downloadFileReply)
        self.dlpath[url] = path
        self.nwmc.get(QNetworkRequest(QUrl(url)))
    def _downloadFileReply(self, reply):
        #save to file
        er = reply.error()
        if er == QNetworkReply.NoError:
            data = reply.readAll()
            if data.isEmpty():
                return
            url = str(reply.url().toString())
            self.saveDataToFile(self.dlpath[url], data)
            self.dlpath[url] = ""
            
    def saveDataToFile(self, path, data):
        with open(path, 'wb') as file:
            file.write(data.data())            

class ServerTreeItemType:
    UNKNOWN = 0
    SERVER = 1
    CHANNEL = 2
    CLIENT = 3

class ServerViewRoles:
    """
    Additional roles used in ServerviewModel to deliver icons and spacer
    properties.
    """

    itemtype = Qt.UserRole
    statusicons = Qt.UserRole + 1
    isspacer = Qt.UserRole + 2
    spacertype = Qt.UserRole + 3
    spaceralignment = Qt.UserRole + 4
    spacercustomtext = Qt.UserRole + 5


class Channel(object):
    """
    Object wrapper for a channel on a TS3 server.
    """
    sortClientsAfterChannels = True
    def __init__(self, schid, cid):
        super().__init__()
        self.schid = schid
        self.cid = cid
        self.parentNode = None
        self.subchans = []
        self.allsubchans = {}
        self.clients = []

        self.update()

    def _appendClient(self, obj):
        self.clients.insert(self.rowOf(obj) - len(self.subchans), obj)

    def _appendChannel(self, obj, sort=True):
        if sort:
            so = obj.sortOrder
            if so == 0:
                self.subchans.insert(0, obj)
            else:
                self.subchans.insert(self.subchans.index(
                    self.allsubchans[so]) + 1, obj)
                # if exists, the sortorder of the previous successor is not
                # valid anymore, as long it is not updated
        else:
            self.subchans.append(obj)

        self.allsubchans[obj.cid] = obj

    def append(self, obj, sort=True):
        if type(obj) is Client:
            self._appendClient(obj)
        else:
            assert type(obj) is Channel
            self._appendChannel(obj, sort)

        obj.parentNode = self

    def rowOf(self, obj=None, pretend=False):
        if obj is None:
            return self.parentNode.rowOf(self)
        else:
            if type(obj) is Client:
                if obj not in self.clients:
                    if len(self.clients) == 0:
                        return len(self.subchans)

                    for i in range(len(self.clients)):
                        if self.clients[i] < obj:
                            continue

                        return len(self.subchans) + i

                    return len(self.subchans) + len(self.clients)
                else:
                    return len(self.subchans) + self.clients.index(obj)
            else:
                assert type(obj) is Channel
                if obj not in self.subchans or pretend:
                    if obj.sortOrder == 0:
                        return 0
                    else:
                        return self.subchans.index(
                            self.allsubchans[obj.sortOrder]) + 1
                else:
                    return self.subchans.index(obj)

    def remove(self, obj):
        if type(obj) is Client:
            self.clients.remove(obj)
        else:
            assert type(obj) is Channel
            self.subchans.remove(obj)

    def update(self):
        self.cache = {}

    @property
    def name(self):
        if "name" in self.cache:
            return self.cache["name"]

        err, n = ts3lib.getChannelVariableAsString(self.schid, self.cid,
                                                   ts3defines.ChannelProperties.CHANNEL_NAME)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel name", err, self.schid, self.cid)
            return "ERROR_GETTING_NAME: {}".fomrat(err)
        else:
            self.cache["name"] = n
            return n

    @property
    def sortOrder(self):
        if "sortOrder" in self.cache:
            return self.cache["sortOrder"]

        err, so = ts3lib.getChannelVariableAsUInt64(self.schid, self.cid,
                                                    ts3defines.ChannelProperties.CHANNEL_ORDER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel sortorder", err, self.schid,
                      self.cid)
            return 0
        else:
            self.cache["sortOrder"] = so
            return so

    @property
    def isPermanent(self):
        if "isPermanent" in self.cache:
            return self.cache["isPermanent"]

        err, permanent = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                        ts3defines.ChannelProperties.CHANNEL_FLAG_PERMANENT)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel ispermanent flag", err,
                      self.schid, self.cid)
            return True
        else:
            self.cache["isPermanent"] = permanent == 1
            return permanent == 1

    def _updateSpacer(self):
        done = False
        if self.isPermanent:
            m = re.match(r'\[([clr\*]*).*spacer.*](.*)', self.name)
            if m:
                self.cache["isSpacer"] = True

                al = m.group(1)
                if al == "r":
                    self.cache["spacerAlignment"] = Qt.AlignRight
                elif al == "c":
                    self.cache["spacerAlignment"] = Qt.AlignHCenter
                elif al == "*":
                    self.cache["spacerAlignment"] = Qt.AlignJustify
                else:
                    self.cache["spacerAlignment"] = Qt.AlignLeft
                
                st = m.group(2)
                self.cache["spacerCustomtext"] = ""
                if st == "___":
                    self.cache["spacerType"] = Qt.SolidLine
                elif st == "---":
                    self.cache["spacerType"] = Qt.DashLine
                elif st == "...":
                    self.cache["spacerType"] = Qt.DotLine
                elif st == "-.-":
                    self.cache["spacerType"] = Qt.DashDotLine
                elif st == "-..":
                    self.cache["spacerType"] = Qt.DashDotDotLine
                else:
                    self.cache["spacerType"] = Qt.CustomDashLine
                    self.cache["spacerCustomtext"] = st

                done = True

        if not done:
            self.cache["isSpacer"] = False
            self.cache["spacerAlignment"] = Qt.AlignLeft
            self.cache["spacerType"] = Qt.SolidLine
            self.cache["spacerCustomtext"] = ""

    @property
    def isSpacer(self):
        if "isSpacer" not in self.cache:
            self._updateSpacer()

        return self.cache["isSpacer"]

    @property
    def spacerAlignment(self):
        if "spacerAlignment" not in self.cache:
            self._updateSpacer()

        return self.cache["spacerAlignment"]

    @property
    def spacerType(self):
        if "spacerType" not in self.cache:
            self._updateSpacer()

        return self.cache["spacerType"]

    @property
    def spacerCustomtext(self):
        if "spacerCustomtext" not in self.cache:
            self._updateSpacer()

        return self.cache["spacerCustomtext"]

    @property
    def isPasswordProtected(self):
        if "isPasswordProtected" in self.cache:
            return self.cache["isPasswordProtected"]

        err, p = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelProperties.CHANNEL_FLAG_PASSWORD)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel ispasswordprotected flag", err,
                      self.schid, self.cid)
            return False
        else:
            self.cache["isPasswordProtected"] = p == 1
            return p == 1

    @property
    def isSubscribed(self):
        if "isSubscribed" in self.cache:
            return self.cache["isSubscribed"]

        err, sub = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                  ts3defines.ChannelPropertiesRare.CHANNEL_FLAG_ARE_SUBSCRIBED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel issubscribed flag", err,
                      self.schid, self.cid)
            return False
        else:
            self.cache["isSubscribed"] = sub == 1
            return sub == 1

    @property
    def neededTalkPower(self):
        if "neededTalkPower" in self.cache:
            return self.cache["neededTalkPower"]

        err, p = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelPropertiesRare.CHANNEL_NEEDED_TALK_POWER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel neededtalkpower", err, self.schid,
                      self.cid)
            return 0
        else:
            self.cache["neededTalkPower"] = p
            return p

    @property
    def isDefault(self):
        if "isDefault" in self.cache:
            return self.cache["isDefault"]

        err, d = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelProperties.CHANNEL_FLAG_DEFAULT)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel isdefault flag", err, self.schid,
                      self.cid)
            return False
        else:
            self.cache["isDefault"] = d == 1
            return d == 1

    @property
    def iconID(self):
        if "iconID" in self.cache:
            return self.cache["iconID"]

        err, i = ts3lib.getChannelVariableAsUInt64(self.schid, self.cid,
                                                   ts3defines.ChannelPropertiesRare.CHANNEL_ICON_ID)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel iconid", err, self.schid,
                      self.cid)
            return 0
        else:
            if i < 0:
                i = pow(2, 32) + i

            self.cache["iconID"] = i
            return i

    @property
    def maxClients(self):
        if "maxClients" in self.cache:
            return self.cache["maxClients"]

        err, m = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelPropertiesRare.CHANNEL_FLAG_MAXCLIENTS_UNLIMITED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel maxclientsunlimited flag", err,
                      self.schid, self.cid)
            return 300
        else:
            if m == 1:
                self.cache["maxClients"] = -1
                return -1

        err, m = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelProperties.CHANNEL_MAXCLIENTS)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel maxclients", err, self.schid,
                      self.cid)
            return 0
        else:
            self.cache["maxClients"] = m
            return m

    @property
    def codec(self):
        if "codec" in self.cache:
            return self.cache["codec"]

        err, c = ts3lib.getChannelVariableAsInt(self.schid, self.cid,
                                                ts3defines.ChannelProperties.CHANNEL_CODEC)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channel codec", err, self.schid, self.cid)
            return 0
        else:
            self.cache["codec"] = c
            return c

    def isFull(self):
        if self.maxClients == -1:
            return False

        return self.maxClients <= len(self.clients)

    def iconVariable(self):
        if self.isSpacer:
            return ""

        if self.isFull():
            if self.isSubscribed:
                return "CHANNEL_RED_SUBSCRIBED"
            else:
                return "CHANNEL_RED"

        if self.isPasswordProtected:
            if self.isSubscribed:
                return "CHANNEL_YELLOW_SUBSCRIBED"
            else:
                return "CHANNEL_YELLOW"

        if self.isSubscribed:
            return "CHANNEL_GREEN_SUBSCRIBED"
        else:
            return "CHANNEL_GREEN"

    def count(self):
        return len(self.clients) + len(self.subchans)

    def child(self, row): #TODO: sortorder
        if Channel.sortClientsAfterChannels:
            if row >= len(self.subchans):
                return self.clients[row - len(self.subchans)]
            else:
                return self.subchans[row]
        else:
            if row >= len(self.clients):
                return self.subchans[row - len(self.clients)]
            else:
                return self.clients[row]

    def sort(self):
        newsubchans = []
        i = 0
        next = 0
        while len(self.subchans) > 0:
            if self.subchans[i].sortOrder == next:
                newsubchans.append(self.subchans.pop(i))
                next = newsubchans[-1].cid
            else:
                i += 1

            if i >= len(self.subchans):
                i = 0

        self.subchans = newsubchans

    def __iter__(self): #TODO: sortorder
        if Channel.sortClientsAfterChannels:
            for c in self.subchans:
                yield c

            for c in self.clients:
                yield c
        else:
            for c in self.clients:
                yield c

            for c in self.subchans:
                yield c
    
    def hasClient(self, clid):
        for client in self.clients:
            if client.clid == clid:
                return True
        return False

    def getPassword(self, cid, askUser=False):
        if "password" in self.cache:
            return self.cache["password"]
        (err, path, pw) = ts3lib.getChannelConnectInfo(self.schid, self.cid) #TODO: fix this not working if we have a wrong pw saved
        if err != ts3defines.ERROR_ok:
            return ""
        if not pw:
            pw = inputBox(self, "Enter Channel Password", "Password:")
        self.cache["password"] = pw
        return pw


class Server(Channel):
    """
    Object wrapper for a TS3 server connection.
    """

    def __init__(self, schid):
        super().__init__(schid, 0)

        self.update()

    def update(self):
        self.cache = {}

    @property
    def name(self):
        if "name" in self.cache:
            return self.cache["name"]

        err, n = ts3lib.getServerVariableAsString(self.schid,
                                                  ts3defines.VirtualServerProperties.VIRTUALSERVER_NAME)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting server name", err, self.schid)
            return "ERROR_UNABLE_TO_GET_SERVERNAME"
        else:
            self.cache["name"] = n
            return n

    @property
    def iconID(self):
        if "iconID" in self.cache:
            return self.cache["iconID"]

        err, i = ts3lib.getServerVariableAsUInt64(self.schid,
                                                  ts3defines.VirtualServerPropertiesRare.VIRTUALSERVER_ICON_ID)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting server iconid", err, self.schid)
            return 0
        else:
            if i < 0:
                i = pow(2, 32) + i

            self.cache["iconID"] = i
            return i

    def rowOf(self, obj=None):
        if obj is None:
            return 0
        else:
            return super().rowOf(obj)

    def iconVariable(self):
        return "SERVER_GREEN"


class Client(object):
    """
    Object wrapper for a connected client on a TS3 server.
    """

    def __init__(self, schid, clid, isme):
        super().__init__()
        self.schid = schid
        self.clid = clid
        self.isme = isme
        self.parentNode = None
        self._isTalking = False
        self._isWhispering = False

        self.update()

    def update(self):
        self.cache = {}

    def count(self):
        return 0

    def rowOf(self):
        return self.parentNode.rowOf(self)

    def __lt__(self, other):
        assert type(other) is Client

        if self.channelGroup != other.channelGroup: #FIXME: check i_group_sort_id
            return self.channelGroup < other.channelGroup
        elif self.talkPower != other.talkPower:
            return other.talkPower < self.talkPower
        else:
            return self.name.lower() < other.name.lower()

    def __gt__(self, other):
        return other < self

    @property
    def name(self):
        if "name" in self.cache:
            return self.cache["name"]

        err, n = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                                  ts3defines.ClientProperties.CLIENT_NICKNAME)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client name", err, self.schid, self.clid)
            return "ERROR_GETTING_NICKNAME: {}".format(err)
        else:
            self.cache["name"] = n
            return n

    @property
    def displayName(self):
        if "displayName" in self.cache:
            return self.cache["displayName"]

        err, n = ts3lib.getClientDisplayName(self.schid, self.clid)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client displayname", err, self.schid,
                      self.clid)
            return "ERROR_GETTING_DISPLAYNAME: {}".format(err)
        else:
            self.cache["displayName"] = n
            return n

    @property
    def talkPower(self):
        if "talkPower" in self.cache:
            return self.cache["talkPower"]

        err, p = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_TALK_POWER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client talkpower", err, self.schid,
                      self.clid)
            return 0
        else:
            self.cache["talkPower"] = p
            return p

    @property
    def isRecording(self):
        if "isRecording" in self.cache:
            return self.cache["isRecording"]

        err, rec = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                                 ts3defines.ClientProperties.CLIENT_IS_RECORDING)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client isrecording flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["isRecording"] = rec == 1
            return rec == 1

    @property
    def isChannelCommander(self):
        if "isChannelCommander" in self.cache:
            return self.cache["isChannelCommander"]

        err, cc = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                                ts3defines.ClientPropertiesRare.CLIENT_IS_CHANNEL_COMMANDER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client channelcommander flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["isChannelCommander"] = cc == 1
            return cc == 1

    @property
    def isTalking(self):
        return self._isTalking

    @isTalking.setter
    def isTalking(self, val):
        self._isTalking = val

    @property
    def isWhispering(self):
        return self._isWhispering

    @isWhispering.setter
    def isWhispering(self, val):
        self._isWhispering = val

    @property
    def iconID(self):
        if "iconID" in self.cache:
            return self.cache["iconID"]

        err, i = ts3lib.getClientVariableAsUInt64(self.schid, self.clid,
                                                  ts3defines.ClientPropertiesRare.CLIENT_ICON_ID)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client iconid", err, self.schid,
                      self.clid)
            return 0
        else:
            if i < 0:
                i = pow(2, 32) + i

            self.cache["iconID"] = i
            return i

    @property
    def isPrioritySpeaker(self):
        if "isPrioritySpeaker" in self.cache:
            return self.cache["isPrioritySpeaker"]

        err, p = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_IS_PRIORITY_SPEAKER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client ispriorityspeaker flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["isPrioritySpeaker"] = p == 1
            return p == 1

    @property
    def isAway(self):
        if "isAway" in self.cache:
            return self.cache["isAway"]

        err, a = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_AWAY)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client isaway flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["isAway"] = a == 1
            return a == 1

    @property
    def awayMessage(self):
        if "awayMessage" in self.cache:
            return self.cache["awayMessage"]

        err, a = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_AWAY_MESSAGE)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client away message flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["awayMessage"] = a
            return a

    @property
    def country(self):
        if "country" in self.cache:
            return self.cache["country"]

        err, c = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                                  ts3defines.ClientPropertiesRare.CLIENT_COUNTRY)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client country", err, self.schid,
                      self.clid)
            return ""
        else:
            self.cache["country"] = c
            return c

    @property
    def isRequestingTalkPower(self):
        if "isRequestingTalkPower" in self.cache:
            return self.cache["isRequestingTalkPower"]

        err, r = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_TALK_REQUEST)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client isrequestingtalkpower flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["isRequestingTalkPower"] = r == 1
            return r == 1

    @property
    def isTalker(self):
        if "isTalker" in self.cache:
            return self.cache["isTalker"]

        err, t = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientPropertiesRare.CLIENT_IS_TALKER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client istalker flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["isTalker"] = t == 1
            return t == 1

    @property
    def outputMuted(self):
        if "outputMuted" in self.cache:
            return self.cache["outputMuted"]

        err, o = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_OUTPUT_MUTED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client outputmuted flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["outputMuted"] = o == 1
            return o == 1

    @property
    def inputMuted(self):
        if "inputMuted" in self.cache:
            return self.cache["inputMuted"]

        err, i = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_INPUT_MUTED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client inputmuted flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["inputMuted"] = i == 1
            return i == 1

    @property
    def isMuted(self):
        if "isMuted" in self.cache:
            return self.cache["isMuted"]

        err, i = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_IS_MUTED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client ismuted flag", err, self.schid,
                      self.clid)
            return False
        else:
            self.cache["isMuted"] = i == 1
            return i == 1

    @property
    def hardwareInputMuted(self):
        if "hardwareInputMuted" in self.cache:
            return self.cache["hardwareInputMuted"]

        err, i = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_INPUT_HARDWARE)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client hardwareinputmuted flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["hardwareInputMuted"] = i == 0
            return i == 0

    @property
    def hardwareOutputMuted(self):
        if "hardwareOutputMuted" in self.cache:
            return self.cache["hardwareOutputMuted"]

        err, o = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_OUTPUT_HARDWARE)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client hardwareoutputmuted flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["hardwareOutputMuted"] = o == 0
            return o == 0

    @property
    def inputDeactivated(self):
        if "inputDeactivated" in self.cache:
            return self.cache["inputDeactivated"]

        err, i = ts3lib.getClientVariableAsInt(self.schid, self.clid,
                                               ts3defines.ClientProperties.CLIENT_INPUT_DEACTIVATED)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client inputdeactivated flag", err,
                      self.schid, self.clid)
            return False
        else:
            self.cache["hardwareOutputMuted"] = i == 1
            return i == 1

    @property
    def channelGroup(self):
        if "channelGroup" in self.cache:
            return self.cache["channelGroup"]

        err, g = ts3lib.getClientVariableAsUInt64(self.schid, self.clid,
                                                  ts3defines.ClientPropertiesRare.CLIENT_CHANNEL_GROUP_ID)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client channelgroup", err, self.schid,
                      self.clid)
            return 0
        else:
            self.cache["channelGroup"] = g
            return g

    @property
    def serverGroups(self):
        if "serverGroups" in self.cache:
            return self.cache["serverGroups"]

        err, gs = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                                   ts3defines.ClientPropertiesRare.CLIENT_SERVERGROUPS)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client servergroups", err, self.schid,
                      self.clid)
            return []
        else:
            self.cache["serverGroups"] = list(map(int, gs.split(',')))
            return self.cache["serverGroups"]

    def iconVariable(self):
        if self.isAway:
            return "AWAY"

        if self.hardwareOutputMuted:
            return "HARDWARE_OUTPUT_MUTED"

        if self.outputMuted:
            return "OUTPUT_MUTED"

        if self.inputDeactivated:
            return "INPUT_MUTED_LOCAL"

        if self.hardwareInputMuted:
            return "HARDWARE_INPUT_MUTED"

        if self.inputMuted:
            return "INPUT_MUTED"

        if self.isMuted:
            return "INPUT_MUTED"

        if self.isTalking and self.isWhispering:
            return "PLAYER_WHISPER"

        if self.isChannelCommander:
            if self.isTalking:
                return "PLAYER_COMMANDER_ON"
            else:
                return "PLAYER_COMMANDER_OFF"

        if self.isTalking:
            return "PLAYER_ON"
        else:
            return "PLAYER_OFF"
    
    @property
    def badges(self):
        if "badges" in self.cache:
            return self.cache["badges"]

        err, b = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                                  ts3defines.ClientPropertiesRare.CLIENT_BADGES)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client badges", err, self.schid, self.clid)
            return "ERROR_GETTING_BADGES: {}".format(err)
        else:
            self.cache["badges"] = b
            return b
    
    @property
    def uid(self):
        if "uid" in self.cache:
            return self.cache["uid"]

        err, uid = ts3lib.getClientVariableAsString(self.schid, self.clid,
                                                  ts3defines.ClientProperties.CLIENT_UNIQUE_IDENTIFIER)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client unique id", err, self.schid, self.clid)
            return "ERROR_GETTING_UNIQUEID: {}".format(err)
        else:
            self.cache["uid"] = uid
            return uid
    
    @property
    def channelID(self):
        if "channelID" in self.cache:
            return self.cache["channelID"]

        err, chid = ts3lib.getChannelOfClient(self.schid, self.clid)

        if err != ts3defines.ERROR_ok:
            _errprint("Error getting client channel id", err, self.schid, self.clid)
            return "ERROR_GETTING_CHANNELID: {}".format(err)
        else:
            self.cache["channelID"] = chid
            return chid
        
# Helpers End

class NewTreeDelegate(QStyledItemDelegate):
    def __init__(self, schid, parent):
        super().__init__(parent)
        self.schid = schid
        self.objs = {}

        self.network = network()

        #read badges from settings.db
        self.badgePath = os.path.join(ts3lib.getConfigPath(), "cache", "badges")
        self.badges = loadBadges()[1]
        #read/download external badges
        self.badgesExtRemote = "https://raw.githubusercontent.com/R4P3-NET/CustomBadges/master/badges.json"
        self.externalBadges = {}
        self.externalBadgePath = os.path.join(self.badgePath, "badges.json")
        if not os.path.exists(self.externalBadgePath):
            self.downloadExtBadges()
        else:
            self.readExtBadges()

        self.downloadedBadges = {}

        #Get Options from settings.db
        self.options = getOptions()

        try:
            self.icons = ts3client.ServerCache(self.schid)

            self.countries = ts3client.CountryFlags()
            self.countries.open()
        except Exception as e:
            self.delete()
            raise e

        self.iconpackcreated = False
        try:
            self.iconpack = ts3client.IconPack.current()
            self.iconpack.open()
            self.iconpackcreated = True
        except Exception as e:
                self.delete()
                raise e

        #TODO: set proxy thingy to get ts callbacks

    def _paintSpacer(self, painter, option, index, obj):
        st = obj.spacerType

        if st != Qt.CustomDashLine:
            painter.drawLine(option.rect.x(),
                             option.rect.y() + option.rect.height() / 2,
                             option.rect.x() + option.rect.width(),
                             option.rect.y() + option.rect.height() / 2)
        else:
            align = obj.spacerAlignment
            ctext = obj.spacerCustomtext

            if align != Qt.AlignJustify:
                painter.drawText(option.rect.x(), option.rect.y(),
                                 option.rect.width(), option.rect.height(),
                                 align, ctext)
            else:
                fm = QFontMetrics(option.font)
                w = l = fm.width(ctext)
                txt = ctext
                while l < option.rect.width():
                    txt += ctext
                    l += w

                painter.drawText(option.rect.x(), option.rect.y(),
                                 option.rect.width(), option.rect.height(),
                                 Qt.AlignLeft, txt)

    def paint(self, painter, option, index):
        try:
            #if option.state & QStyle.State_MouseOver and option.state & ~QStyle.State_MouseOver:
            #    painter.fillRect(option.rect, option.palette.highlight()) #FIXME: get original color here too

            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight()) #FIXME: get original color of theme

            if not index.isValid():
                super().paint(painter, option, index)
                return

            name = index.data(Qt.EditRole)
            obj = self.getObject(name)

            drawName = index.data(Qt.DisplayRole)
            icon = index.data(Qt.DecorationRole)
            font = index.data(Qt.FontRole)
            brush = index.data(Qt.TextColorRole)
            if self.objs[name]:
                statusicons = self.statusIcons(self.objs[name])
                if type(self.objs[name]) is Channel and self.objs[name].isSpacer:
                    self._paintSpacer(painter, option, index, self.objs[name])
                    return

            if icon: #FIXME: icon size
                iconsize = icon.actualSize(option.decorationSize)
                #icon.paint(painter, option.rect, Qt.AlignLeft)
                icon.paint(painter, option.rect.x() + 3,
                                option.rect.center().y() - iconsize.height() / 2, iconsize.width(), iconsize.height())
            else:
                iconsize = option.decorationSize

            headerRect = option.rect
            headerRect.setLeft(headerRect.left() + iconsize.width() + 5)

            painter.save()

            if brush:
                pen = painter.pen()
                pen.setBrush(brush)
                painter.setPen(pen)
            if font:
                painter.setFont(font)

            painter.drawText(headerRect, Qt.AlignLeft, index.data())

            nextx = 18
            if statusicons:
                for ico in reversed(statusicons): #FIXME: check here if icon exists else don't draw
                    ico.paint(painter, option.rect.right() - nextx,
                                option.rect.center().y() - iconsize.height() / 2, iconsize.width(), iconsize.height())
                    nextx += 18
                    
            painter.restore()
        except: from traceback import format_exc;ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def getObject(self, name):
        if not name in self.objs or not self.objs[name]:
            self.objs[name] = getObjectByName(name, self.schid)
        return self.objs[name]

    def statusIcons(self, obj):
        ret = []
        if type(obj) is Channel:
            if obj.isDefault:
                ret.append(QIcon(self.iconpack.icon("DEFAULT")))
            if obj.isPasswordProtected:
                ret.append(QIcon(self.iconpack.icon("REGISTER")))
            if obj.codec == ts3defines.CodecType.CODEC_OPUS_MUSIC or obj.codec == ts3defines.CodecType.CODEC_CELT_MONO:
                ret.append(QIcon(self.iconpack.icon("MUSIC")))
            if obj.neededTalkPower > 0:
                ret.append(QIcon(self.iconpack.icon("MODERATED")))
            if obj.iconID != 0:
                ret.append(QIcon(self.icons.icon(obj.iconID)))
        elif type(obj) is Client:
            #TODO: isWhisperTarget
            #ret.append(QIcon(self.iconpack.icon("ON_WHISPERLIST")))
            # badges
            overwolf, badges = parseBadges(obj.badges)
            for badgeUuid in badges:
                #normal ts badge
                if badgeUuid in self.badges:
                    badge = self.badges[badgeUuid]
                    filePath = "{}.svg".format(os.path.join(self.badgePath, badge["filename"]))
                    if not os.path.exists(filePath): #download
                        if badgeUuid in self.downloadedBadges: #we already tried to download
                            return
                        self.network.downloadFile("{}.svg".format(badge["url"]), filePath)
                        self.downloadedBadges[badgeUuid] = True
                    ret.append(QIcon(filePath))
                #external badges
                if badgeUuid in self.externalBadges:
                    badge = self.externalBadges[badgeUuid]
                    filePath = "{}.svg".format(os.path.join(self.badgePath, badge["filename"]))
                    if not os.path.exists(filePath): #download
                        if badgeUuid in self.downloadedBadges: #we already tried to download
                            return
                        self.network.downloadFile("https://raw.githubusercontent.com/R4P3-NET/CustomBadges/master/img/{}".format(badge["filename"]), filePath)
                        self.downloadedBadges[badgeUuid] = True
                    ret.append(QIcon(filePath))
            # priority speaker
            if obj.isPrioritySpeaker:
                ret.append(QIcon(self.iconpack.icon("CAPTURE")))
            # istalker
            parentChannel = Channel(self.schid, obj.channelID)
            if obj.isTalker:
                ret.append(QIcon(self.iconpack.icon("IS_TALKER")))
            elif obj.talkPower < parentChannel.neededTalkPower:
                ret.append(QIcon(self.iconpack.icon("INPUT_MUTED")))
            #TODO: channelgroup
            """
            if obj.channelGroup in self.cgicons:
                cgID = self.cgicons[obj.channelGroup]
                if cgID in range(100, 700, 100):
                    ret.append(QIcon(self.iconpack.icon("group_{}".format(cgID))))
                else:
                    ret.append(QIcon(self.icons.icon(cgID)))
            """
            #TODO: servergroups
            """
            for sg in obj.serverGroups:
                if sg in self.sgicons:
                    sgID = self.sgicons[sg]
                    if sgID == 0:
                        continue
                    elif sgID in range(100, 700, 100):
                        ret.append(QIcon(self.iconpack.icon("group_{}".format(sgID))))
                    else:
                        ret.append(QIcon(self.icons.icon(sgID)))
            """
            # clienticon
            if obj.iconID != 0:
                ret.append(QIcon(self.icons.icon(obj.iconID)))
            # talkrequest
            if obj.isRequestingTalkPower:
                ret.append(QIcon(self.iconpack.icon("REQUEST_TALK_POWER")))
            #TODO: overwolf
            #if self.options["EnableOverwolfIcons"] == "1" and overwolf == 1:
                #ret.append()
            # flag
            if self.options["EnableCountryFlags"] == "1" and obj.country != "":
                ret.append(QIcon(self.countries.flag(obj.country)))
        else:
            assert type(obj) is Server
            if obj.iconID != 0:
                ret.append(QIcon(self.icons.icon(obj.iconID)))
        return ret

    def downloadExtBadges(self):
        self.network.nwmc.connect("finished(QNetworkReply*)", self._loadExtBadges)
        self.network.nwmc.get(QNetworkRequest(QUrl(self.badgesExtRemote)))

    def _loadExtBadges(self, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            self.externalBadges = loads(data.data().decode('utf-8'))
            self.network.saveDataToFile(self.externalBadgePath, data)
        self.network.nwmc.disconnect("finished(QNetworkReply*)", self._loadExtBadges)

    def readExtBadges(self):
        with open(self.externalBadgePath, 'r') as f:
            self.externalBadges = load(f)

def findChildWidget(widget, checkfunc, recursive):
    for c in widget.children():
        if c.isWidgetType():
            if checkfunc(c):
                return c
            elif recursive:
                recret = findChildWidget(c, checkfunc, recursive)
                if recret:
                    return recret

    return None


def findAllChildWidgets(widget, checkfunc, recursive):
    ret = []
    for c in widget.children():
        if c.isWidgetType():
            if checkfunc(c):
                ret.append(c)
            elif recursive:
                ret += findAllChildWidgets(c, checkfunc, recursive)

    return ret


class serverTreeDelegate(ts3plugin):
    name = "ServerTreeDelegate"
    requestAutoload = False
    version = "1.0.1"
    apiVersion = 21
    author = "exp111"
    description = "Just replace the ItemDelegate"
    offersConfigure = False
    commandKeyword = ""
    infoTitle = ""
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_GLOBAL, 0, "ToggleServerViewDelegate", os.path.join("ressources", "octicons", "git-pull-request.svg.png"))]
    hotkeys = []

    def __init__(self):
        self.svobserver = EventFilterObject([QEvent.ChildAdded])
        self.svobserver.connect("eventFiltered(QObject*, QEvent*)", self.onNewServerview)

        self.treekeyobserver = EventFilterObject([QEvent.KeyPress, QEvent.KeyRelease, QEvent.FocusOut])
        self.treekeyobserver.connect("eventFiltered(QObject*, QEvent*)", self.onTreeKey)

        self.main = None
        self.svmanagerstack = None

        self.control = False
        self.shift = False

        self.dlgs = {}
        self.autoStart = True

        self.retrieveWidgets()

    def stop(self):
        self.svobserver.delete()
        self.treekeyobserver.delete()

        for schid, dlg in self.dlgs.items():
            self.uninstallDelegate(schid)
            if dlg:
                dlg.delete()

    def onNewServerview(self, obj, ev):
        #this will cause to install eventfilters on the trees
        self.retrieveWidgets()

    def onTreeKey(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control:
                self.control = True
            elif event.key() == Qt.Key_Shift:
                self.shift = True
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control:
                self.control = False
            elif event.key() == Qt.Key_Shift:
                self.shift = False
        elif event.type() == QEvent.FocusOut:
            self.control = False
            self.shift = False

    def retrieveWidgets(self):
        if not self.main:
            for w in QApplication.instance().topLevelWidgets():
                if "MainWindow" in str(type(w)):
                    self.main = w
                    break

        if self.main and not self.svmanagerstack:
            self.svmanagerstack = findChildWidget(self.main, lambda x: x.objectName == "qt_tabwidget_stackedwidget" and "ServerViewManager" in str(type(x.parent())), True)

        if self.svmanagerstack:
            self.svmanagerstack.installEventFilter(self.svobserver)
            for tree in findAllChildWidgets(self.svmanagerstack, lambda x: "TreeView" in str(type(x)), True):
                tree.installEventFilter(self.treekeyobserver)
        else:
            QTimer.singleShot(300, self.retrieveWidgets)


    def installDelegate(self, schid):
        if schid not in self.dlgs or not self.dlgs[schid]:
            if not self.svmanagerstack: #We need the tabmanager to see which is the current active treeview/tab
                self.retrieveWidgets()
            #FIXME: get proper serverview for schid
            currentServerTree = [item for item in self.svmanagerstack.widget(self.svmanagerstack.currentIndex).children() if item.objectName == "ServerTreeView"][0]
            self.dlgs[schid] = NewTreeDelegate(schid, currentServerTree)
            currentServerTree.setItemDelegate(self.dlgs[schid])

    def uninstallDelegate(self, schid):
        if schid in self.dlgs and self.dlgs[schid]:
            if not self.svmanagerstack: #We need the tabmanager to see which is the current active treeview/tab
                self.retrieveWidgets()
            #FIXME: get proper serverview for schid
            currentServerTree = self.dlgs[schid].parent()
            oldDelegate = [item for item in currentServerTree.children() if type(item).__name__ == "TreeDelegate"][0]
            if not oldDelegate:
                return
            currentServerTree.setItemDelegate(oldDelegate)
            self.dlgs[schid].deleteLater()
            self.dlgs[schid] = None

    def onMenuItemEvent(self, schid, atype, menuItemID, selectedItemID):
        if menuItemID == 0:
            if schid in self.dlgs and self.dlgs[schid]:
                self.uninstallDelegate(schid)
            else:
                self.installDelegate(schid)

