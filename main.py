#!/usr/bin/env python3

import pywinusb.hid as hid
import struct
from collections import namedtuple
import wx
import wx.adv
# import wx.lib.mixins.inspection

ArcinConfig = namedtuple(
    "ArcinConfig",
    "label flags qe1_sens qe2_sens effector_mode ws2812b_mode")

# Infinitas controller VID/PID = 0x1ccf / 0x8048
VID = 0x1ccf
PID = 0x8048
CONFIG_SEGMENT_ID = hid.get_full_usage_id(0xff55, 0xc0ff)
STRUCT_FMT = ("12s" + # uint8 label[12]
              "L" +   # uint32 flags
              "b" +   # int8 qe1_sens
              "b" +   # int8 qe2_sens
              "B" +   # uint8 effector_mode
              "B")    # uint8 ws2812b_mode

SENS_OPTIONS = {
    "1:1": 0,
    "1:2": -2,
    "1:3": -3,
    "1:4": -4,
    "1:6": -6,
    "1:8": -8,
    "1:11": -11,
    "1:16": -16,
    "2:1": 2,
    "3:1": 3,
    "4:1": 4,
    "6:1": 6,
    "8:1": 8,
    "11:1": 11,
    "16:1": 16
}

E1E2_OPTIONS = [
    "E1, E2",
    "E2, E1",
    "E3, E4",
    "E4, E3",
]

ARCIN_CONFIG_FLAG_SEL_MULTI_TAP     = (1 << 0)
ARCIN_CONFIG_FLAG_INVERT_QE1        = (1 << 1)
ARCIN_CONFIG_FLAG_SWAP_8_9          = (1 << 2)
ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE = (1 << 3)
ARCIN_CONFIG_FLAG_DEBOUNCE          = (1 << 4)
ARCIN_CONFIG_FLAG_250HZ_READ_ONLY   = (1 << 5)

def get_devices():
    hid_filter = hid.HidDeviceFilter(vendor_id=VID, product_id=PID)
    return hid_filter.get_devices()

def load_from_device(device):
    conf = None
    try:
        device.open()
        for report in device.find_feature_reports():
            # 0xc0 = 192 = config report
            if report.report_id == 0xc0:

                print("Loading from device:")
                print(f"Name:\t {device.product_name}")
                print(f"Serial:\t {device.serial_number}")

                report.get()
                conf = parse_device(report)

    except:
        return None

    finally:
        device.close()

    return conf

def parse_device(report):
    config_page = report[CONFIG_SEGMENT_ID]
    data = bytes(config_page.value)
    expected_size = struct.calcsize(STRUCT_FMT)
    truncated = bytes(data[0:expected_size])
    unpacked = struct.unpack(STRUCT_FMT, truncated)
    return ArcinConfig._make(unpacked)

def save_to_device(device, conf):
    try:
        packed = struct.pack(
            STRUCT_FMT,
            conf.label[0:12].encode(),
            conf.flags,
            conf.qe1_sens,
            conf.qe2_sens,
            conf.effector_mode,
            conf.ws2812b_mode)
    except:
        return (False, "Format error")

    try:
        device.open()
        feature = [0x00] * 64

        # see definition of config_report_t in report_desc.h

        feature[0] = 0xc0 # report id
        feature[1] = 0x00 # segment
        feature[2] = 0x14 # size
        feature[3] = 0x00 # padding
        feature[4:4+len(packed)] = packed

        assert len(feature) == 64

        device.send_feature_report(feature)

        # restart the board

        feature = [0xb0, 0x20]
        device.send_feature_report(feature)

    except:
        return (False, "Failed to write to device")
    finally:
        device.close()
        
    return (True, "Success")

class MainWindowFrame(wx.Frame):

    # list of HID devices
    device = None

    loading = False

    # list control for selecting HID device
    devices_list = None
    load_button = None
    save_button = None

    title_ctrl = None

    multitap_check = None
    qe1_invert_check = None
    swap89_check = None
    digital_tt_check = None
    debounce_check = None

    qe1_sens_ctrl = None
    e1e2_ctrl = None

    def __init__(self, *args, **kw):
        default_size = (320, 500)
        kw['size'] = default_size
        kw['style'] = (
            wx.RESIZE_BORDER |
            wx.SYSTEM_MENU |
            wx.CAPTION |
            wx.CLOSE_BOX |
            wx.CLIP_CHILDREN
        )

        # ensure the parent's __init__ is called
        super(MainWindowFrame, self).__init__(*args, **kw)

        # create a panel in the frame
        panel = wx.Panel(self)
        self.SetMinSize(default_size)

        box = wx.BoxSizer(wx.VERTICAL)

        self.devices_list = wx.ListCtrl(
            panel, style=(wx.LC_REPORT | wx.LC_SINGLE_SEL))
        self.devices_list.AppendColumn("Label", width=120)
        self.devices_list.AppendColumn("Serial #", width=120)
        self.devices_list.Bind(
            wx.EVT_LIST_ITEM_SELECTED, self.on_device_list_select)
        self.devices_list.Bind(
            wx.EVT_LIST_ITEM_DESELECTED, self.on_device_list_deselect)
        box.Add(self.devices_list, flag=(wx.EXPAND | wx.ALL), border=4)

        button_box = wx.BoxSizer(wx.HORIZONTAL)
        self.save_button = wx.Button(panel, label="Save")
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)
        self.load_button = wx.Button(panel, label="Load")
        self.load_button.Bind(wx.EVT_BUTTON, self.on_load)
        refresh_button = wx.Button(panel, label="Refresh")
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh)
        button_box.Add(refresh_button, flag=wx.RIGHT, border=4)
        button_box.Add(self.load_button, flag=wx.RIGHT, border=4)
        button_box.Add(self.save_button)
        box.Add(button_box, flag=wx.ALL, border=4)

        # and create a sizer to manage the layout of child widgets
        grid = wx.GridBagSizer(10, 10)
        grid.SetCols(2)
        grid.AddGrowableCol(1)
        row = 0

        title_label = wx.StaticText(panel, label="Label")
        self.title_ctrl = wx.TextCtrl(panel)
        self.title_ctrl.SetMaxLength(11)
        grid.Add(title_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.title_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        fw_label = wx.StaticText(panel, label="Firmware")
        self.fw_ctrl = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.fw_ctrl.Disable()
        grid.Add(fw_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.fw_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        checklist_label = wx.StaticText(panel, label="Options")
        grid.Add(checklist_label, pos=(row, 0), flag=wx.ALIGN_TOP, border=2)
        checklist_box = self.__create_checklist__(panel)
        grid.Add(checklist_box, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        qe1_sens_label = wx.StaticText(panel, label="QE1 sensitivity")
        self.qe1_sens_ctrl = wx.ComboBox(
            panel, choices=list(SENS_OPTIONS.keys()), style=wx.CB_READONLY)
        self.qe1_sens_ctrl.Select(0)
        grid.Add(qe1_sens_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.qe1_sens_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        e1e2_label = wx.StaticText(panel, label="Start and Select")
        self.e1e2_ctrl = wx.ComboBox(
            panel, choices=E1E2_OPTIONS, style=wx.CB_READONLY)
        self.e1e2_ctrl.Select(0)
        grid.Add(e1e2_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.e1e2_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        box.Add(grid, 1, flag=(wx.EXPAND | wx.ALL), border=8)
        panel.SetSizer(box)

        self.makeMenuBar()
        self.CreateStatusBar()

        self.__evaluate_save_load_buttons__()
        self.__populate_device_list__()

    def makeMenuBar(self):
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT)

        menu_bar = wx.MenuBar()
        menu_bar.Append(help_menu, "&Help")

        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, self.OnAbout, about_item)

    def OnAbout(self, event):
        info = wx.adv.AboutDialogInfo()

        info.SetName('arcin infinitas conf')
        info.SetWebSite('https://github.com/minsang-github/arcin-infinitas')

        wx.adv.AboutBox(info)

    def __create_checklist__(self, parent):
        box_kw = {
            "proportion": 0,
            "flag": wx.BOTTOM,
            "border": 4
        }

        box = wx.BoxSizer(wx.VERTICAL)
        self.multitap_check = wx.CheckBox(parent, label="E2 multi-function")
        box.Add(self.multitap_check, **box_kw)
        self.qe1_invert_check = wx.CheckBox(parent, label="Invert QE1")
        box.Add(self.qe1_invert_check, **box_kw)
        self.swap89_check = wx.CheckBox(parent, label="Swap 8/9")
        box.Add(self.swap89_check, **box_kw)
        self.digital_tt_check = wx.CheckBox(parent, label="LR2 digital TT")
        box.Add(self.digital_tt_check, **box_kw)
        self.debounce_check = wx.CheckBox(parent, label="Debounce (5ms)")
        box.Add(self.debounce_check, **box_kw)
        return box

    def on_device_list_select(self, e):
        self.__evaluate_save_load_buttons__()

    def on_device_list_deselect(self, e):
        self.__evaluate_save_load_buttons__()
        wx.CallAfter(self.__do_forced_selection__, e.GetIndex())

    def __do_forced_selection__(self, index):
        if self.devices_list.GetSelectedItemCount() == 0:
            self.devices_list.Select(index)

    def on_refresh(self, e):
        self.__populate_device_list__()

    def on_load(self, e):
        index = self.devices_list.GetFirstSelected()
        if index < 0:
            return

        device = self.devices[index]
        conf = load_from_device(device)

        self.loading = True
        self.__evaluate_save_load_buttons__()

        if conf is not None:
            self.SetStatusText(
                f"Reading from {device.product_name} ({device.serial_number})...")

            wx.CallLater(500, self.on_load_deferred, device, conf)

        else:
            self.SetStatusText("Error while trying to read from device.")
            self.loading = False
            self.__evaluate_save_load_buttons__()


    def on_load_deferred(self, device, conf):
        self.loading = False
        self.__evaluate_save_load_buttons__()
        self.__populate_from_conf__(conf)
        self.SetStatusText(
            f"Loaded from {device.product_name} ({device.serial_number}).")

    def on_save(self, e):
        index = self.devices_list.GetFirstSelected()
        if index < 0:
            return

        device = self.devices[index]       
        conf = self.__extract_conf_from_gui__()

        self.loading = True
        self.__evaluate_save_load_buttons__()
        self.SetStatusText(
                f"Saving to {device.product_name} ({device.serial_number})...")
        wx.CallLater(500, self.on_save_deferred, device, conf)

    def on_save_deferred(self, device, conf):
        self.loading = False
        self.__evaluate_save_load_buttons__()
        result, error_message = save_to_device(device, conf)
        if result:
            self.SetStatusText(
                f"Saved to {device.product_name} ({device.serial_number}).")
        else:
            self.SetStatusText("Error: " + error_message)

    def __extract_conf_from_gui__(self):
        title = self.title_ctrl.GetValue()
        flags = 0
        if self.multitap_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_SEL_MULTI_TAP
        if self.qe1_invert_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_INVERT_QE1
        if self.swap89_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_SWAP_8_9
        if self.digital_tt_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE
        if self.debounce_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_DEBOUNCE

        if self.qe1_sens_ctrl.GetValue() in SENS_OPTIONS:
            qe1_sens = SENS_OPTIONS[self.qe1_sens_ctrl.GetValue()]
        else:
            qe1_sens = -4 # 1:4: as the reasonable default

        effector_mode = self.e1e2_ctrl.GetSelection()
        conf = ArcinConfig(
            label=title,
            flags=flags,
            qe1_sens=qe1_sens,
            qe2_sens=0,
            effector_mode=effector_mode,
            ws2812b_mode=0
        )

        return conf

    def __populate_from_conf__(self, conf):
        # "label flags qe1_sens qe2_sens effector_mode ws2812b_mode")
        self.title_ctrl.SetValue(conf.label)

        self.multitap_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_SEL_MULTI_TAP))

        self.qe1_invert_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_INVERT_QE1))

        self.swap89_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_SWAP_8_9))

        self.digital_tt_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE))

        self.debounce_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_DEBOUNCE))

        if conf.flags & ARCIN_CONFIG_FLAG_250HZ_READ_ONLY:
            self.fw_ctrl.SetValue("Poll rate = 250hz")
        else:
            self.fw_ctrl.SetValue("Poll rate = 1000hz")

        index = -4 # 1:4 is a reasonable default
        for i, value in enumerate(SENS_OPTIONS.values()):
            if conf.qe1_sens == value:
                index = i
                break
        self.qe1_sens_ctrl.Select(index)

        index = 0 # E1 E2 is a reasonable default
        effector_mode = min(conf.effector_mode, len(E1E2_OPTIONS) - 1)
        self.e1e2_ctrl.Select(effector_mode)

    def __populate_device_list__(self):
        if self.devices_list is None:
            return
        
        self.devices_list.DeleteAllItems()
        self.__evaluate_save_load_buttons__()
        self.devices = get_devices()
        for d in self.devices:
            self.devices_list.Append([d.product_name, d.serial_number])
        if len(self.devices) > 0:
            self.devices_list.Select(0)

        self.SetStatusText(f"Found {len(self.devices)} device(s).")

    def __evaluate_save_load_buttons__(self):
        if self.devices_list.GetFirstSelected() >= 0 and not self.loading:
            self.save_button.Enable(True)
            self.load_button.Enable(True)
        else:
            self.save_button.Enable(False)
            self.load_button.Enable(False)

def ui_main():
    app = wx.App()
    frm = MainWindowFrame(None, title="arcin-infinitas conf")
    frm.Show()

    # wx.lib.inspection.InspectionTool().Show()

    app.MainLoop()

if __name__ == "__main__":
    ui_main()
