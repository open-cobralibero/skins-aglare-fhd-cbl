#!/usr/bin/python
# -*- coding: utf-8 -*-

from .. import _
# Components
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
from enigma import eLabel
from errno import ENOENT
from os import system, remove
import skin

DEFAULT_MODULE_NAME = __name__.split(".")[-1]
pname = _("File Commander - Addon")
pdesc = _("play/show Files")
pversion = "1.0-r2"


def getTextBoundarySize(instance, font, targetSize, text):
    return eLabel.calculateTextSize(font, text, targetSize)


def fileReadLines(filename, default=None, source=DEFAULT_MODULE_NAME, debug=False):
    lines = None
    try:
        with open(filename, "r") as fd:
            lines = fd.read().splitlines()
    except OSError as err:
        if err.errno != ENOENT:  # ENOENT - No such file or directory.
            print("[%s] Error %d: Unable to read lines from file '%s'!  (%s)" % (source, err.errno, filename, err.strerror))
        lines = default
    return lines


class File_Commander(Screen):

    skin = """
        <screen name="File_Commander" position="40,80" size="1900,900" title="Linuxsat-support - File Commander">
            <widget name="list_head" position="8,10" size="1850,45" font="Regular;20" foregroundColor="#00fff000" />
            <widget name="filedata" scrollbarMode="showOnDemand" position="10,60" size="1850,750" itemHeight="50" />
            <widget name="key_red" position="100,840" size="260,25" transparent="1" font="Regular;20" />
            <widget name="key_green" position="395,840" size="260,25" transparent="1" font="Regular;20" />
            <widget name="key_yellow" position="690,840" size="260,25" transparent="1" font="Regular;20" />
            <widget name="key_blue" position="985,840" size="260,25" transparent="1" font="Regular;20" />
            <ePixmap position="70,840" size="260,25" zPosition="0" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />
            <ePixmap position="365,840" size="260,25" zPosition="0" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />
            <ePixmap position="660,840" size="260,25" zPosition="0" pixmap="skin_default/buttons/yellow.png" transparent="1" alphatest="on" />
            <ePixmap position="955,840" size="260,25" zPosition="0" pixmap="skin_default/buttons/blue.png" transparent="1" alphatest="on" />
        </screen>"""

    def __init__(self, session, file):
        self.skin = File_Commander.skin
        Screen.__init__(self, session)
        # HelpableScreen.__init__(self)
        self.file_name = file
        title = "Linuxsat-support - File Commander"
        self.list = []
        self["filedata"] = MenuList(self.list)
        self["actions"] = ActionMap(["WizardActions", "ColorActions", "DirectionActions"], {
            "ok": self.exitEditor,
            "green": self.SaveFile,
            "back": self.exitEditor,
            "red": self.exitEditor,
            "yellow": self.ConfirmSaveFile,
            "blue": self.exitEditor,
            "chplus": self.posStart,
            "chminus": self.posEnd,
        }, -1)
        self["list_head"] = Label(self.file_name)
        self["key_red"] = Label(_("Exit"))
        self["key_green"] = Label(_("Exit"))
        self["key_yellow"] = Label(_("Save"))
        self["key_blue"] = Label(_("Exit"))
        self.selLine = None
        self.oldLine = None
        self.isChanged = False
        self.skinName = "vEditorScreen"
        self.GetFileData(file)
        self.newtitle = title == 'vEditorScreen' and ('Console') or title
        self.onShown.append(self.updateTitle)

    def updateTitle(self):
        self.setTitle(self.newtitle)

    def exitEditor(self):
        # if fileExists(self.file_name):
            # remove(self.file_name)
        self.close()

    def GetFileData(self, fx):
        lines = fileReadLines(fx)
        if lines:
            for idx, line in enumerate(lines):
                self.list.append(str(idx + 1).zfill(4) + ": " + line)
        self["list_head"] = Label(fx)

    def posStart(self):
        self.selLine = 0
        self["filedata"].moveToIndex(0)

    def posEnd(self):
        self.selLine = len(self.list)
        self["filedata"].moveToIndex(len(self.list) - 1)

    def del_Line(self):
        self.selLine = self["filedata"].getSelectionIndex()
        if len(self.list) > 1:
            self.isChanged = True
            del self.list[self.selLine]
            self.refreshList()

    def ins_Line(self):
        self.selLine = self["filedata"].getSelectionIndex()
        self.list.insert(self.selLine, "0000: " + "" + '\n')
        self.isChanged = True
        self.refreshList()

    def refreshList(self):
        lineno = 1
        for x in self.list:
            my_x = x.partition(": ")[2]
            self.list.remove(x)
            self.list.insert(lineno - 1, str(lineno).zfill(4) + ": " + my_x)  # '\n')
            lineno += 1
        self["filedata"].setList(self.list)
    
    def ConfirmSaveFile(self):
        self.session.openWithCallback(self.SaveFile, MessageBox, _("Do you want to save the changes?"), MessageBox.TYPE_YESNO)
    
    def SaveFile(self, answer=True):
        if answer is True:
            try:
                if fileExists(self.file_name):
                    system("cp " + self.file_name + " " + self.file_name + ".bak")
                eFile = open(self.file_name, "w")
                for x in self.list:
                    my_x = x.partition(": ")[2]
                    eFile.writelines(my_x)
                eFile.close()
            except OSError:
                pass
            self.close()
        else:
            self.close()
