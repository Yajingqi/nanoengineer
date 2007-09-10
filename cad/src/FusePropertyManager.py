# Copyright 2004-2007 Nanorex, Inc.  See LICENSE file for details. 
"""
FusePropertyManager.py
@author: Ninad
@version: $Id$
@copyright:2004-2007 Nanorex, Inc.  All rights reserved.

History: 
ninad070425 :1) Moved Fuse dashboard to Property manager 
             2) Implemented Translate/ Rotate enhancements
             
ninad20070723: code cleanup to define a fusePropMgr object. This was a 
prerequisite for 'command sequencer' and also needed to resolve potential 
multiple inheritance issues.

TODO: ninad20070723--
See if the signals can be connected in the 
fuseMde.connect_disconnect_signals OR better to call 
propMgr.connect_disconnect_signals in the fuseMde.connect_disconnect_signals?  
I think the latter will help decoupling ui elements from fuseMode. Same thing 
applies to other modes and Propert Managers (e.g. Move mode, Build Atoms mode)
"""

from PyQt4.Qt import SIGNAL
from PyQt4.Qt import Qt

from PM.PM_GroupBox        import PM_GroupBox
from PM.PM_ComboBox        import PM_ComboBox
from PM.PM_PushButton      import PM_PushButton
from PM.PM_CheckBox        import PM_CheckBox
from PM.PM_Slider          import PM_Slider

from MovePropertyManager    import  MovePropertyManager

class FusePropertyManager(MovePropertyManager):
    
    # <title> - the title that appears in the property manager header.
    title = "Fuse Chunks"
    # <iconPath> - full path to PNG file that appears in the header.
    iconPath = "ui/actions/Tools/Build Tools/Fuse_Chunks.png"
    
    def __init__(self, parentMode):
        """
        Constructor for Fuse Property manager. 
        @param parentMode: The parent mode for this property manager 
        @type  parentMode: L{fuseChunksmode}
        """
        
        self.parentMode = parentMode
        MovePropertyManager.__init__(self, self.parentMode)
                
        self.activate_translateGroupBox_in_fuse_PM()
    
    def _addGroupBoxes(self):
        """
        Add various groupboxes to Fuse property manager. 
        """
        
        self.fuseOptionsGroupBox = PM_GroupBox( self,
                                         title = "Fuse Options")
        self._loadFuseOptionsGroupBox(self.fuseOptionsGroupBox)
        
        MovePropertyManager._addGroupBoxes(self)
    
    def _loadFuseOptionsGroupBox(self, inPmGroupBox):
        """
        Load the widgets inside the Fuse Options groupbox.
        """
        fuseChoices = ['Make Bonds Between Chunks', 'Fuse Overlapping Atoms']
        
        self.fuseComboBox = \
            PM_ComboBox( inPmGroupBox,
                         label        = '', 
                         choices      = fuseChoices, 
                         index        = 0, 
                         setAsDefault = False,
                         spanWidth    = True)
        
        self.connect(self.fuseComboBox, 
                     SIGNAL("activated(const QString&)"), 
                     self.parentMode.change_fuse_mode)
        
        self.fusePushButton = PM_PushButton( inPmGroupBox,
                                             label     = "",
                                             text      = "Make Bonds",
                                             spanWidth = True )
        
        self.connect( self.fusePushButton,
                      SIGNAL("clicked()"),
                      self.parentMode.fuse_something)
        
        
        self.toleranceSlider =  PM_Slider( inPmGroupBox,
                                           currentValue = 100,
                                           minimum      = 0,
                                           maximum      = 300,
                                           label        = \
                                           'Tolerance:100% => 0 bondable pairs'
                                         )
        self.connect(self.toleranceSlider,
                       SIGNAL("valueChanged(int)"),
                       self.parentMode.tolerance_changed)
        
        self.mergeChunksCheckBox = PM_CheckBox( inPmGroupBox,
                                                text         = 'Merge Chunks',
                                                widgetColumn = 0,
                                                state        = Qt.Checked )
        

    def activate_translateGroupBox_in_fuse_PM(self):
        """
        Show contents of translate groupbox, deactivae the rotate groupbox. 
        Also check the action that was checked when this groupbox  was active 
        last time. (if applicable). This method is called only when move 
        groupbox button is clicked. 
        @see: L{self.activate_translateGroupBox_in_fuse_PM}
        """
                      
        self.toggle_translateGroupBox()
        self.deactivate_rotateGroupBox()
       
        buttonToCheck = self.getTranslateButtonToCheck()
                     
        if buttonToCheck:
            buttonToCheck.setChecked(True) 
        else:
            buttonToCheck = self.transFreeButton
            buttonToCheck.setChecked(True)
        
        self.changeMoveOption(buttonToCheck)
        
        self.isTranslateGroupBoxActive = True
        self.parentMode.update_cursor()
    
    def activate_rotateGroupBox_in_fuse_PM(self):
        """
        Show contents of rotate groupbox (in fuse PM), deactivae the 
        translate groupbox. 
        Also check the action that was checked when this groupbox  was active 
        last time. (if applicable). This method is called only when rotate 
        groupbox button is clicked. 
        @see: L{activate_rotateGroupBox_in_fuse_PM}
        """
     
        self.toggle_rotateGroupBox()
        self.deactivate_translateGroupBox()
           
        buttonToCheck = self.getRotateButtonToCheck()
                  
        if buttonToCheck:
            buttonToCheck.setChecked(True) 
        else:
            buttonToCheck = self.rotateFreeButton
            buttonToCheck.setChecked(True)
            
        self.changeRotateOption(buttonToCheck)
        
        self.isTranslateGroupBoxActive = False
        self.parentMode.update_cursor()
                
    
    def setupUi(self, fusePropMgrObject):
        """
        Overrides MovePropertyManager.setupUi
        @param fusePropMgrObject : fuse PM object is passed to the 
                                   Ui_FusePropertyManager class method which 
                                   defines the necessary ui elements for 
                                   Fuse Property Manager
        @see : MovePropertyManager.setupUI
        """
        fusePropMgr = fusePropMgrObject
        fuseUi = Ui_FusePropertyManager()
        fuseUi.setupUi(fusePropMgr)
    
    def updateMessage(self): 
        """
        Updates the message box with an informative message.
        Overrides the MovePropertyManager.updateMessage method
        @see: MovePropertyManager.updateMessage
        """
        
        #@bug: BUG: The message box height is fixed. The verticle scrollbar 
        #appears as the following message is long. It however tries to make the 
        # cursor visible within the message box . This results in scrolling the 
        # msg box to the last line and thus doesn't look good.-- ninad 20070723
        
        if self.fuseComboBox.currentIndex() == 0:
            #i.e. 'Make Bonds Between Chunks'
            msg = "To <b> make bonds</b> between two or more chunks, \
            drag the selected chunk(s) such that their one or more bondpoints \
            overlap with the other chunk(s). Then hit <b> Make Bonds </b> to \
            create bond(s) between them. "
        else:   
            msg = "To <b>fuse overlapping atoms</b> in two or more chunks,\
            drag the selected chunk(s) such that their one or more atoms \
            overlap  with the atoms in the other chunk(s). Then hit \
            <b> Fuse Atoms </b>\ to remove the overlapping atoms of unselected \
            chunk. "
        
        self.MessageGroupBox.insertHtmlMessage( msg, setAsDefault  =  True )
        