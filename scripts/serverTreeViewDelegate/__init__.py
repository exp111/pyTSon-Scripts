import os

from ts3plugin import ts3plugin

import ts3lib, ts3defines
from ts3widgets.serverview import ServerviewModel, ServerviewDelegate, Client, Channel, Server

from PythonQt import BoolResult
from PythonQt.QtGui import (QApplication, QDialog, QAbstractItemView,
                            QTreeView, QHBoxLayout, QItemSelection,
                            QItemSelectionModel, QTextDocument, QWidget, 
                            QInputDialog, QLineEdit, QStyledItemDelegate)
from PythonQt.QtCore import Qt, QEvent, QTimer, QMimeData, QModelIndex
from PythonQt.pytson import EventFilterObject

class NewTreeDelegate(QStyledItemDelegate):
    def _paintSpacer(self, painter, option, index):
        ts3lib.printMessageToCurrentTab("no u")
        """
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
                fm = QFontMetrics(self.parent().model().tabWidget.font)
                w = l = fm.width(ctext)
                txt = ctext
                while l < option.rect.width():
                    txt += ctext
                    l += w

                painter.drawText(option.rect.x(), option.rect.y(),
                                 option.rect.width(), option.rect.height(),
                                 Qt.AlignLeft, txt)
        """

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        """
        #if option.state & QStyle.State_MouseOver and option.state & ~QStyle.State_MouseOver:
        #    painter.fillRect(option.rect, option.palette.highlight()) #FIXME: get original color here too

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight()) #FIXME: get original color of theme

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
        
        if icon: #FIXME: icon size
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
            for ico in reversed(statusicons): #FIXME: check here if icon exists else don't draw
                ico.paint(painter, option.rect.right() - nextx,
                          option.rect.center().y() - iconsize.height() / 2, iconsize.width(), iconsize.height())
                nextx += 18

        painter.restore()
        """


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
            currentServerTree = [item for item in self.svmanagerstack.widget(self.svmanagerstack.currentIndex).children() if item.objectName == "ServerTreeView"][0]
            oldDelegate = [item for item in currentServerTree.children() if type(item).__name__ == "QStyledItemDelegate"][0]
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

