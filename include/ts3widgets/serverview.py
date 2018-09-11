import os
from . import _errprint

from ts3plugin import PluginHost

import ts3lib
import ts3defines

import ts3client

import re

from PythonQt.QtCore import Qt, QAbstractItemModel, QModelIndex, QFile, QByteArray, QIODevice, QDataStream, QUrl
from PythonQt.QtGui import (QStyledItemDelegate, QStyle, QFontMetrics,
                            QApplication, QIcon, QColor, QTreeView)
from PythonQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Helper Stuff
def getContacts():
    """
    :return:
    """
    db = ts3client.Config()
    ret = []
    q = db.query("SELECT * FROM contacts")
    while q.next():
        try:
            cur = {"Key": int(q.value("key")), "Timestamp": q.value("timestamp")}
            val = q.value("value")
            for l in val.split('\n'):
                try:
                    l = l.split('=', 1)
                    if len(l) != 2: continue
                    if l[0] in ["Nickname","PhoneticNickname","LastSeenServerName"]: cur[l[0]] = l[1].encode('ascii', 'ignore')
                    elif l[0] in ["LastSeenServerAddress","IDS","VolumeModifier", "LastSeen"]: cur[l[0]] = l[1]
                    elif l[0] in ["Friend","NickShowType"]: cur[l[0]] = int(l[1])
                    elif l[0] in ["Automute","IgnorePublicMessages","IgnorePrivateMessages","IgnorePokes","IgnoreAvatar","IgnoreAwayMessage","HaveVolumeModifier","WhisperAllow"]:
                        if l[1] == "false": cur[l[0]] = False
                        elif l[1] == "true": cur[l[0]] = True
                    if l[0] == "LastSeen" and l[1]: cur["LastSeenEpoch"] = int(time.mktime(time.strptime(l[1], '%Y-%m-%dT%H:%M:%S')))
                except: continue
            ret.append(cur)
        except: continue
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
            with open(self.dlpath[url], 'wb') as file:
                file.write(data.data())   
                self.dlpath[url] = ""

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

# ServerView Classes
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
            m = re.match(r'\[([clr]*)spacer\d*](.*)', self.name)
            if m:
                self.cache["isSpacer"] = True

                al = m.group(1)
                if al == "l":
                    self.cache["spacerAlignment"] = Qt.AlignLeft
                elif al == "r":
                    self.cache["spacerAlignment"] = Qt.AlignRight
                elif al == "c":
                    self.cache["spacerAlignment"] = Qt.AlignHCenter
                elif al == "*": #FIXME: don't know if this is correct; but currently no problems
                    self.cache["spacerAlignment"] = Qt.AlignJustify

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
        for c in self.clients:
            yield c

        for c in self.subchans:
            yield c
    
    def hasClient(self, clid):
        for client in self.clients:
            if client.clid == clid:
                return True
        return False

    def getPassword(self, askUser=False):
        if "password" in self.cache:
            return self.cache["password"]
        (err, path, pw) = ts3lib.getChannelConnectInfo(self.schid, item.cid) #TODO: fix this not working if we have a wrong pw saved
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

        if self.talkPower != other.talkPower:
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

        if self.isWhispering:
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

# Actual ServerView Stuff (Model etc.)
class ServerviewModel(QAbstractItemModel):
    """
    ItemModel to deliver data of a serverview to ItemWidgets. The data is
    delivered in one column.
    """

    def __init__(self, schid, iconpack=None, parent=None):
        """
        Instantiates a new ServerviewModel object. This raises an exception if
        the iconpack could not be opened. The object registers itself as
        callbackproxy to the PythonHost.
        @param schid: the ID of the serverconnection
        @type schid: int
        @param iconpack: the iconpack to use icons from. defaults to None to
        use the TS3 client's current IconPack
        @type iconpack: ts3client.IconPack
        @param parent: the QObject-parent. defaults to None
        @type parent: QObject
        """
        super().__init__(parent)

        self.schid = schid
        self.root = Server(schid)

        self.allchans = {}
        self.allclients = {}
        self.objs = {}

        self.cgicons = {}
        self.sgicons = {}

        self._reload()

        self.tabWidget = [item for item in QApplication.allWidgets() if item.objectName == "qt_tabwidget_stackedwidget"][0]
        #read badges from settings.db
        self.badgePath = os.path.join(ts3lib.getConfigPath(), "cache", "badges")
        self.badges = loadBadges()[1]
        #read friends/foes from settings.db
        self.contacts = getContacts()

        self.network = network()
        self.options = getOptions()
        #TODO: handle self.options["SortClientsAfterChannels"] somewhere
        #TODO: show hovered items in another color

        try:
            self.icons = ts3client.ServerCache(self.schid)

            self.countries = ts3client.CountryFlags()
            self.countries.open()
        except Exception as e:
            self.delete()
            raise e

        self.iconpackcreated = False
        if not iconpack:
            try:
                self.iconpack = ts3client.IconPack.current()
                self.iconpack.open()
                self.iconpackcreated = True
            except Exception as e:
                self.delete()
                raise e
        else:
            self.iconpack = iconpack

        PluginHost.registerCallbackProxy(self)

    def __del__(self):
        PluginHost.unregisterCallbackProxy(self)
        self.allchans = {}
        self.objs = {}

        if self.iconpackcreated:
            self.iconpack.close()

        self.countries.close()

    def setServerConnectionHandlerId(self, schid):
        self.schid = schid
        self._reload()

    def _reload(self):
        err, self.myid = ts3lib.getClientID(self.schid)

        err = ts3lib.requestServerGroupList(self.schid)
        if err != ts3defines.ERROR_ok:
            _errprint("Error requesting servergrouplist", err, self.schid)
        err = ts3lib.requestChannelGroupList(self.schid)
        if err != ts3defines.ERROR_ok:
            _errprint("Error requesting channelgroups", err, self.schid)

        self.beginResetModel()

        self.allchans = {}
        self.objs = {}

        self._reloadServerinfo()
        self._reloadChannellist()
        self._reloadClientlist()

        self.endResetModel()

    def _reloadServerinfo(self):
        self.onServerEditedEvent(self.schid, 0, "", "")

    def _reloadChannellist(self):
        err, cids = ts3lib.getChannelList(self.schid)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting channellist", err, self.schid)
            return

        unhandled = {}
        for c in cids:
            err, pcid = ts3lib.getParentChannelOfChannel(self.schid, c)

            if err != ts3defines.ERROR_ok:
                _errprint("Error getting channel parent", err, self.schid, c)
                pass

            if pcid == 0:
                parent = self.root
            elif pcid in self.allchans:
                parent = self.allchans[pcid]
            else:
                if pcid in unhandled:
                    unhandled[pcid].append(c)
                else:
                    unhandled[pcid] = [c]
                continue

            obj = Channel(self.schid, c)
            self.allchans[c] = obj
            parent.append(obj, False)

        self._addChilds(self.root, unhandled)
        self.root.sort()
        assert len(unhandled) == 0

    def _addChilds(self, node, d):
        for chan in node:
            for scid in d.pop(chan.cid, []):
                obj = Channel(self.schid, scid)
                self.allchans[scid] = obj
                chan.append(obj, False)

            chan.sort()

            self._addChilds(chan, d)

    def _reloadClientlist(self):
        err, clids = ts3lib.getClientList(self.schid)
        if err != ts3defines.ERROR_ok:
            _errprint("Error getting clientlist", err, self.schid)
            return

        for c in clids:
            err, parent = ts3lib.getChannelOfClient(self.schid, c)
            if err == ts3defines.ERROR_ok:
                self.onClientMoveEvent(self.schid, c, 0, parent,
                                       ts3defines.Visibility.ENTER_VISIBILITY,
                                       "")
            else:
                _errprint("Error getting client channel", err, self.schid, c)
                pass

    def onServerEditedEvent(self, schid, editerID, editerName, editerUID):
        if schid != self.schid:
            return

        self.root.update()
        idx = self._createIndex(0, 0, self.root)
        self.dataChanged(idx, idx)

    def onNewChannelEvent(self, schid, cid, pcid):
        if schid != self.schid:
            return

        if pcid == 0:
            parent = self.root
        elif pcid in self.allchans:
            parent = self.allchans[pcid]
        else:
            _errprint("Error, event on unrecognised channel", 0, self.schid,
                      pcid)
            return

        obj = Channel(schid, cid)
        self.allchans[cid] = obj

        newrow = parent.rowOf(obj)
        self.beginInsertRows(self._createIndex(parent.rowOf(), 0, parent),
                             newrow, newrow)
        parent.append(obj)
        self.endInsertRows()

    def onNewChannelCreatedEvent(self, schid, cid, parent, invokerID,
                                 invokerName, invokerUniqueIdentifier):
        self.onNewChannelEvent(schid, cid, parent)

    def onUpdateChannelEditedEvent(self, schid, cid, invokerID, invokerName,
                                   invokerUniqueIdentifier):
        if schid != self.schid:
            return

        chan = self.allchans[cid]
        oldsort = chan.sortOrder
        oldrow = chan.rowOf()

        chan.update()

        if oldsort != chan.sortOrder:
            # the channel (propably) has moved inside the parent
            newrow = chan.parentNode.rowOf(chan, True)
            pidx = self._createIndex(chan.parentNode.rowOf(), 0,
                                     chan.parentNode)
            self.beginMoveRows(pidx, oldrow, oldrow, pidx, newrow)
            chan.parentNode.remove(chan)
            chan.parentNode.append(chan)
            self.endMoveRows()
        else:
            row = chan.rowOf()

            idx = self._createIndex(row, 0, chan)
            self.dataChanged(idx, idx)

    def onChannelMoveEvent(self, schid, cid, newpcid, invokerID, invokerName,
                           invokerUniqueIdentifier):
        if schid != self.schid:
            return

        chan = self.allchans[cid]
        oldpidx = self._createIndex(chan.parentNode.rowOf(), 0,
                                    chan.parentNode)
        oldrow = chan.rowOf()
        newpar = self.allchans[newpcid]
        newpidx = self._createIndex(newpar.rowOf(), 0, newpar)

        self.beginMoveRows(oldpidx, oldrow, oldrow, newpidx,
                           newpar.rowOf(chan))
        chan.parentNode.remove(chan)
        newpar.append(chan)
        self.endMoveRows()

    def onDelChannelEvent(self, schid, cid, invokerID, invokerName,
                          invokerUID):
        if schid != self.schid:
            return

        chan = self.allchans[cid]
        row = chan.rowOf()
        paridx = self._createIndex(chan.parentNode.rowOf(), 0, chan.parentNode)

        self.beginRemoveRows(paridx, row, row)
        chan.parentNode.remove(chan)
        del self.allchans[cid]
        if id(chan) in self.objs:
            del self.objs[id(chan)]
        self.endRemoveRows()

    def onClientMoveEvent(self, schid, clientID, oldChannelID, newChannelID,
                          visibility, moveMessage):
        if schid != self.schid:
            return

        if visibility == ts3defines.Visibility.ENTER_VISIBILITY:
            obj = Client(schid, clientID, clientID == self.myid)
            self.allclients[clientID] = obj
            chan = self.allchans[newChannelID]

            newrow = chan.rowOf(obj)
            self.beginInsertRows(self._createIndex(chan.rowOf(), 0, chan),
                                 newrow, newrow)
            chan.append(obj)
            self.endInsertRows()
        elif visibility == ts3defines.Visibility.RETAIN_VISIBILITY:
            obj = self.allclients[clientID]
            oldchan = self.allchans[oldChannelID]
            oldidx = self._createIndex(oldchan.rowOf(), 0, oldchan)
            oldrow = oldchan.rowOf(obj)
            newchan = self.allchans[newChannelID]
            newidx = self._createIndex(newchan.rowOf(), 0, newchan)
            newrow = newchan.rowOf(obj)

            self.beginMoveRows(oldidx, oldrow, oldrow, newidx, newrow)
            oldchan.remove(obj)
            newchan.append(obj)
            self.endMoveRows()
        else:
            obj = self.allclients[clientID]
            oldchan = self.allchans[oldChannelID]
            oldidx = self._createIndex(oldchan.rowOf(), 0, oldchan)
            oldrow = oldchan.rowOf(obj)

            self.beginRemoveRows(oldidx, oldrow, oldrow)
            oldchan.remove(obj)
            del self.allclients[clientID]
            if id(obj) in self.objs:
                del self.objs[id(obj)]
            self.endRemoveRows()

    def onChannelUnsubscribeEvent(self, schid, channelID):
        if schid != self.schid:
            return

        chan = self.allchans[channelID]
        idx = self._createIndex(chan.rowOf(), 0, chan)

        self.beginRemoveRows(idx, len(chan.subchans), chan.count())
        clients = chan.clients
        for c in clients:
            chan.remove(c)
            del self.allclients[c.clid]
            if id(c) in self.objs:
                del self.objs[id(c)]
        self.endRemoveRows()

        chan.update()
        self.dataChanged(idx, idx)

    def onChannelSubscribeEvent(self, schid, channelID):
        if schid != self.schid:
            return

        chan = self.allchans[channelID]
        idx = self._createIndex(chan.rowOf(), 0, chan)
        chan.update()
        self.dataChanged(idx, idx)

    def onClientMoveMovedEvent(self, schid, clientID, oldChannelID,
                               newChannelID, visibility, moverID, moverName,
                               moverUniqueIdentifier, moveMessage):
        self.onClientMoveEvent(schid, clientID, oldChannelID, newChannelID,
                               visibility, "")

    def onUpdateClientEvent(self, schid, clientID, invokerID, invokerName,
                            invokerUniqueIdentifier):
        if schid != self.schid:
            return

        client = self.allclients[clientID]
        idx = self._createIndex(client.rowOf(), 0, client)
        client.update()
        self.dataChanged(idx, idx)

    def onClientSelfVariableUpdateEvent(self, schid, flag, oldValue, newValue):
        self.onUpdateClientEvent(schid, self.myid, 0, "", "")

    def onClientMoveSubscriptionEvent(self, schid, clientID, oldChannelID,
                                      newChannelID, visibility):
        self.onClientMoveEvent(schid, clientID, oldChannelID, newChannelID,
                               visibility, "")

    def onClientMoveTimeoutEvent(self, schid, clientID, oldChannelID,
                                 newChannelID, visibility, timeoutMessage):
        self.onClientMoveEvent(schid, clientID, oldChannelID, newChannelID,
                               visibility, "")

    def onClientKickFromServerEvent(self, schid, clientID, oldChannelID,
                                    newChannelID, visibility, kickerID,
                                    kickerName, kickerUniqueIdentifier,
                                    kickMessage):
        self.onClientMoveEvent(schid, clientID, oldChannelID, newChannelID,
                               visibility, "")

    def onClientDisplayNameChanged(self, schid, clientID, displayName, uid):
        self.onUpdateClientEvent(schid, clientID, 0, "", "")

    def onTalkStatusChangeEvent(self, schid, status, isReceivedWhisper, clid):
        if schid != self.schid:
            return

        changed = False
        obj = self.allclients[clid]
        talks = status == ts3defines.TalkStatus.STATUS_TALKING
        whispers = isReceivedWhisper == 1
        
        if obj.isTalking != talks:
            obj.isTalking = talks
            changed = True
        if obj.isWhispering != whispers:
            obj.isWhispering = whispers
            changed = True

        if changed:
            idx = self._createIndex(obj.rowOf(), 0, obj)
            self.dataChanged(idx, idx)

    def onServerGroupListEvent(self, schid, serverGroupID, name, atype, iconID,
                               saveDB):
        if schid != self.schid:
            return

        if iconID != 0:
            if iconID < 0:
                iconID = pow(2, 32) + iconID

            self.sgicons[serverGroupID] = iconID

    def onChannelGroupListEvent(self, schid, channelGroupID, name, atype,
                                iconID, saveDB):
        if schid != self.schid:
            return

        if iconID != 0:
            if iconID < 0:
                iconID = pow(2, 32) + iconID

            self.cgicons[channelGroupID] = iconID

    def _createIndex(self, row, column, obj):
        i = id(obj)
        self.objs[i] = obj
        return self.createIndex(row, column, i)

    def _indexObject(self, index):
        return self.objs[index.internalId()]

    def index(self, row, column, parent):
        if not parent.isValid():
            assert row == 0
            return self._createIndex(0, column, self.root)
        else:
            parobj = self._indexObject(parent)
            return self._createIndex(row, column, parobj.child(row))

    def parent(self, index):
        obj = self._indexObject(index)

        if obj == self.root:
            return QModelIndex()
        else:
            parent = obj.parentNode
            return self._createIndex(parent.rowOf(), 0, parent)

    def rowCount(self, parent):
        if not parent.isValid():
            return 1
        else:
            return self._indexObject(parent).count()

    def columnCount(self, parent):
        return 1

    def isFriend(self, id):
        return any(contact["IDS"] == id and contact["Friend"] == 0 for contact in self.contacts)

    def isBlocked(self, id):
        return any(contact["IDS"] == id and contact["Friend"] == 1 for contact in self.contacts)

    def data(self, index, role):
        obj = self._indexObject(index)

        if role == Qt.DisplayRole:
            if type(obj) is Client:
                if self.options["AwayMessageBesideNickName"] == "1" and obj.isAway:
                    if not obj.awayMessage:
                        return obj.displayName
                    return "{} [{}]".format(obj.displayName, obj.awayMessage)

                if obj.isRecording:
                    return "*** {} *** [RECORDING]".format(obj.displayName)
                else:
                    return obj.displayName
            return obj.name
        elif role == ServerViewRoles.isspacer:
            return type(obj) is Channel and obj.isSpacer
        elif type(obj) is Channel and role == ServerViewRoles.spacertype:
            return obj.spacerType
        elif type(obj) is Channel and role == ServerViewRoles.spacercustomtext:
            return obj.spacerCustomtext
        elif type(obj) is Channel and role == ServerViewRoles.spaceralignment:
            return obj.spacerAlignment
        elif role == Qt.DecorationRole:
            if not (type(obj) is Channel and obj.isSpacer):
                return QIcon(self.iconpack.icon(obj.iconVariable()))
        elif role == ServerViewRoles.statusicons:
            ret = []
            if type(obj) is Channel:
                if obj.isDefault:
                    ret.append(QIcon(self.iconpack.icon("DEFAULT")))
                if obj.codec == ts3defines.CodecType.CODEC_OPUS_MUSIC:
                    ret.append(QIcon(self.iconpack.icon("MUSIC")))
                if obj.neededTalkPower > 0:
                    ret.append(QIcon(self.iconpack.icon("MODERATED")))
                if obj.iconID != 0:
                    ret.append(QIcon(self.icons.icon(obj.iconID)))
            elif type(obj) is Client:
                #TODO: isWhisperTarget
                #ret.append(QIcon(self.iconpack.icon("ON_WHISPERLIST")))

                try:
                    #badges
                    overwolf, badges = parseBadges(obj.badges)
                    for badgeUuid in badges:
                        #normal ts badge
                        if badgeUuid in self.badges:
                            badge = self.badges[badgeUuid]
                            filePath = "{}.svg".format(os.path.join(self.badgePath, badge["filename"]))
                            if not os.path.exists(filePath):
                                #download
                                self.network.downloadFile("{}.svg".format(badge["url"]), filePath)
                            ret.append(QIcon(filePath))
                        #TODO: external badges
                except: from traceback import format_exc;ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

                # priority speaker
                if obj.isPrioritySpeaker:
                    ret.append(QIcon(self.iconpack.icon("CAPTURE")))
                # istalker
                if obj.isTalker:
                    ret.append(QIcon(self.iconpack.icon("IS_TALKER")))
                elif obj.talkPower < obj.parentNode.neededTalkPower:
                    ret.append(QIcon(self.iconpack.icon("INPUT_MUTED")))
                #FIXME: channelgroup
                if obj.channelGroup in self.cgicons:
                    ret.append(QIcon(self.icons.icon(
                        self.cgicons[obj.channelGroup])))
                #FIXME: servergroups
                for sg in obj.serverGroups:
                    if sg in self.sgicons:
                        ret.append(QIcon(self.icons.icon(self.sgicons[sg])))
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
        elif role == Qt.FontRole:
            if type(obj) is Client and obj.isme:
                font = self.tabWidget.font
                font.setBold(True)
                return font
        elif role == Qt.ForegroundRole:
            if type(obj) is Client:
                if obj.isRecording:
                    return QColor(Qt.darkRed)
                if self.isFriend(obj.uid):
                    return QColor(Qt.green)
                if self.isBlocked(obj.uid):
                    return QColor(Qt.red)

        return None


class ServerviewDelegate(QStyledItemDelegate):
    """
    Delegate to display Serverview items and query the properties and icons
    from the model to display and show them in one column.
    """

    def _paintSpacer(self, painter, option, index):
        st = index.data(ServerViewRoles.spacertype)

        if st != Qt.CustomDashLine:
            #painter.setPen(st)
            painter.drawLine(option.rect.x(),
                             option.rect.y() + option.rect.height() / 2,
                             option.rect.x() + option.rect.width(),
                             option.rect.y() + option.rect.height() / 2)
        else:
            align = index.data(ServerViewRoles.spaceralignment)
            ctext = index.data(ServerViewRoles.spacercustomtext)

            if align != Qt.AlignJustify:
                painter.drawText(option.rect.x(), option.rect.y(),
                                 option.rect.width(), option.rect.height(),
                                 align, ctext)
            else:
                fm = QFontMetrics(QApplication.font())
                w = l = fm.width(ctext)
                txt = ctext
                while l < option.rect.width():
                    txt += ctext
                    l += w

                painter.drawText(option.rect.x(), option.rect.y(),
                                 option.rect.width(), option.rect.height(),
                                 Qt.AlignLeft, txt)

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        if not index.isValid():
            super().paint(painter, option, index)
            return

        if index.data(ServerViewRoles.isspacer):
            #painter.save()
            self._paintSpacer(painter, option, index)
            #painter.restore()
            return

        icon = index.data(Qt.DecorationRole)
        statusicons = index.data(ServerViewRoles.statusicons)
        font = index.data(Qt.FontRole)
        brush = index.data(Qt.ForegroundRole)
        
        if icon:
            iconsize = icon.actualSize(option.decorationSize)
            icon.paint(painter, option.rect, Qt.AlignLeft)
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
            for ico in reversed(statusicons):
                ico.paint(painter, option.rect.right() - nextx,
                          option.rect.y(), iconsize.width(), iconsize.height())
                nextx += 18

        painter.restore()


class Serverview(QTreeView):
    """
    A QTreeView widget to display the complete view on a TS3 Server.
    """

    def __init__(self, parent=None, *, schid=None):
        """
        Instantiates a new Serverview widget (including model and delegate).
        @param schid: the ID of the serverconnection
        @type schid: int
        @param parent: parent widget
        @type parent: QWidget
        """
        super().__init__(parent)

        self.svmodel = None

        delegate = ServerviewDelegate(self)
        self.setItemDelegate(delegate)

        self.header().hide()

        if schid:
            try:
                self.setServerConnectionHandlerId(schid)
            except Exception as e:
                self.delete()
                raise e

    def setServerConnectionHandlerId(self, schid):
        if not self.svmodel:
            self.svmodel = ServerviewModel(schid, None, self)
            self.setModel(self.svmodel)
        else:
            self.svmode.setServerConnectionHandlerId(schid)

        self.expandAll()

    def indexToObject(self, index):
        """
        Returns the underlying object of a QModelIndex.
        @param index: the index of the model
        @type index: QModelIndex
        @return: the wrapped viewitem
        @rtype: Server or Channel or Client
        """
        if self.svmodel:
            return self.svmodel._indexObject(index)
        else:
            return None
