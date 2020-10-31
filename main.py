#!/usr/bin/env python3

import struct
from collections import namedtuple
from os import system
import pywinusb.hid as hid
import wx
# import wx.lib.mixins.inspection
from usb_hid_keys import USB_HID_KEYS
from usb_hid_keys import USB_HID_KEYCODES

ArcinConfig = namedtuple(
    "ArcinConfig",
    "label flags qe1_sens qe2_sens effector_mode debounce_ticks keycodes")

ARCIN_CONFIG_VALID_KEYCODES = 13

# Infinitas controller VID/PID = 0x1ccf / 0x8048
VID = 0x1ccf
PID = 0x8048
CONFIG_SEGMENT_ID = hid.get_full_usage_id(0xff55, 0xc0ff)
STRUCT_FMT_ORIGNAL = (
    "12s" + # uint8 label[12]
    "L" +   # uint32 flags
    "b" +   # int8 qe1_sens
    "b" +   # int8 qe2_sens
    "B" +   # uint8 effector_mode
    "B")    # uint8 debounce_ticks

STRUCT_FMT_EX = (
    "12s" + # uint8 label[12]
    "L" +   # uint32 flags
    "b" +   # int8 qe1_sens
    "b" +   # int8 qe2_sens
    "B" +   # uint8 effector_mode
    "B" +   # uint8 debounce_ticks
    "16s" + # char keycodes[16]
    "24x")  # uint8 reserved[24]

TT_OPTIONS = [
    "Analog only (Infinitas)",
    "Digital only (LR2)",
    "Both analog and digital",
]

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

INPUT_MODE_OPTIONS = [
    "Controller only (IIDX, BMS)",
    "Keyboard only (DJMAX)",
    "Both controller and keyboard"
]

LED_OPTIONS = [
    "Default",
    "React to QE1 turntable",
    "HID-controlled",
]

ARCIN_CONFIG_FLAG_SEL_MULTI_TAP          = (1 << 0)
ARCIN_CONFIG_FLAG_INVERT_QE1             = (1 << 1)
ARCIN_CONFIG_FLAG_SWAP_8_9               = (1 << 2)
ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE      = (1 << 3)
ARCIN_CONFIG_FLAG_DEBOUNCE               = (1 << 4)
ARCIN_CONFIG_FLAG_250HZ_MODE             = (1 << 5)
ARCIN_CONFIG_FLAG_ANALOG_TT_FORCE_ENABLE = (1 << 6)
ARCIN_CONFIG_FLAG_KEYBOARD_ENABLE        = (1 << 7)
ARCIN_CONFIG_FLAG_JOYINPUT_DISABLE       = (1 << 8)
ARCIN_CONFIG_FLAG_MODE_SWITCHING_ENABLE  = (1 << 9)
ARCIN_CONFIG_FLAG_LED_OFF                = (1 << 10)
ARCIN_CONFIG_FLAG_TT_LED_REACTIVE        = (1 << 11)
ARCIN_CONFIG_FLAG_TT_LED_HID             = (1 << 12)

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
    expected_size = struct.calcsize(STRUCT_FMT_EX)
    truncated = bytes(data[0:expected_size])
    unpacked = struct.unpack(STRUCT_FMT_EX, truncated)
    return ArcinConfig._make(unpacked)

def save_to_device(device, conf):
    try:
        packed = struct.pack(
            STRUCT_FMT_EX,
            conf.label[0:12].encode(),
            conf.flags,
            conf.qe1_sens,
            conf.qe2_sens,
            conf.effector_mode,
            conf.debounce_ticks,
            conf.keycodes[0:16])
    except:
        return (False, "Format error")

    try:
        device.open()
        feature = [0x00] * 64

        # see definition of config_report_t in report_desc.h

        feature[0] = 0xc0 # report id
        feature[1] = 0x00 # segment
        feature[2] = 0x3C # size
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
    debounce_check = None
    mode_switch_check = None
    led_off_check = None

    qe1_tt_ctrl = None
    debounce_ctrl = None

    qe1_sens_ctrl = None
    e1e2_ctrl = None

    input_mode_ctrl = None

    led_mode_ctrl = None

    keybinds_button = None
    keybinds_frame = None

    keycodes = None

    def __init__(self, *args, **kw):
        default_size = (340, 640)
        kw['size'] = default_size
        kw['style'] = (
            wx.RESIZE_BORDER |
            wx.SYSTEM_MENU |
            wx.CAPTION |
            wx.CLOSE_BOX |
            wx.CLIP_CHILDREN
        )

        # ensure the parent's __init__ is called
        super().__init__(*args, **kw)

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

        self.devices_list.SetMaxSize((-1, 70))
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

        fw_label = wx.StaticText(panel, label="Poll rate")
        self.poll_rate_ctrl = wx.RadioBox(panel, choices=["1000hz", "250hz"])
        grid.Add(fw_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.poll_rate_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        checklist_label = wx.StaticText(panel, label="Options")
        grid.Add(checklist_label, pos=(row, 0), flag=wx.ALIGN_TOP, border=2)
        checklist_box = self.__create_checklist__(panel)
        grid.Add(checklist_box, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        debounce_label = wx.StaticText(panel, label="Debounce (ms)")
        self.debounce_ctrl = wx.SpinCtrl(panel, min=2, max=10, initial=2)
        grid.Add(debounce_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.debounce_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        qe1_tt_label = wx.StaticText(panel, label="QE1 turntable mode")
        self.qe1_tt_ctrl = wx.Choice(panel, choices=TT_OPTIONS)
        self.qe1_tt_ctrl.Select(0)
        grid.Add(qe1_tt_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.qe1_tt_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        qe1_sens_label = wx.StaticText(panel, label="QE1 sensitivity")
        self.qe1_sens_ctrl = wx.ComboBox(
            panel, choices=list(SENS_OPTIONS.keys()), style=wx.CB_READONLY)
        self.qe1_sens_ctrl.Select(0)
        grid.Add(qe1_sens_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.qe1_sens_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        e1e2_label = wx.StaticText(panel, label="Start and Select")
        self.e1e2_ctrl = wx.Choice(panel, choices=E1E2_OPTIONS)
        self.e1e2_ctrl.Select(0)
        grid.Add(e1e2_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.e1e2_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        input_mode_label = wx.StaticText(panel, label="Input mode")
        self.input_mode_ctrl = wx.Choice(panel, choices=INPUT_MODE_OPTIONS)
        self.input_mode_ctrl.Select(0)
        grid.Add(input_mode_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.input_mode_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        led_mode_label = wx.StaticText(panel, label="TT LED mode")
        self.led_mode_ctrl = wx.Choice(panel, choices=LED_OPTIONS)
        self.led_mode_ctrl.Select(0)
        grid.Add(led_mode_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.led_mode_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        keybinds_label = wx.StaticText(panel, label="Configure keybinds")
        self.keybinds_button = wx.Button(panel, label="Open")
        self.keybinds_button.Bind(wx.EVT_BUTTON, self.on_keybinds_button)
        grid.Add(keybinds_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.keybinds_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        box.Add(grid, 1, flag=(wx.EXPAND | wx.ALL), border=8)

        panel.SetSizer(box)

        self.makeMenuBar()
        self.CreateStatusBar()

        self.__evaluate_save_load_buttons__()
        self.__evaluate_debounce_options__()
        self.__populate_device_list__()

    def makeMenuBar(self):
        options_menu = wx.Menu()

        winjoy_item = options_menu.Append(
            wx.ID_ANY, item="Game Controllers control panel")

        options_menu.AppendSeparator()
        
        about_item = options_menu.Append(wx.ID_ANY, item="Help (opens in browser)")

        menu_bar = wx.MenuBar()
        menu_bar.Append(options_menu, "&Tools")

        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, self.OnAbout, about_item)
        self.Bind(wx.EVT_MENU, self.OnWinJoy, winjoy_item)

    def OnAbout(self, event):
        system("start https://github.com/minsang-github/arcin-infinitas")

    def OnWinJoy(self, event):
        system("start joy.cpl")

    def __create_checklist__(self, parent):
        box_kw = {
            "proportion": 0,
            "flag": wx.BOTTOM,
            "border": 4
        }

        box = wx.BoxSizer(wx.VERTICAL)
        self.multitap_check = wx.CheckBox(parent, label="E2 multi-function")
        self.multitap_check.SetToolTip(
            "When enabled: press E2 once for E2, twice for E3, three times for E2+E3, four times for E4")
        box.Add(self.multitap_check, **box_kw)

        self.qe1_invert_check = wx.CheckBox(parent, label="Invert QE1")
        self.qe1_invert_check.SetToolTip(
            "Inverts the direction of the turntable.")
        box.Add(self.qe1_invert_check, **box_kw)

        self.swap89_check = wx.CheckBox(parent, label="Swap buttons 8 && 9")
        self.swap89_check.SetToolTip("Swaps buttons 8 and 9 (E3 and E4).")
        box.Add(self.swap89_check, **box_kw)

        self.mode_switch_check = wx.CheckBox(parent, label="Enable mode switching")
        self.mode_switch_check.SetToolTip(
            """Hold [Start + Sel + 1] for 3 seconds to switch input mode.
Hold [Start + Sel + 3] for 3 seconds to switch turntable mode.
Hold [Start + Sel + 5] for 3 seconds to switch LED state.
These only take in effect while plugged in; they are reset when unplugged""")
        box.Add(self.mode_switch_check, **box_kw)

        self.led_off_check = wx.CheckBox(parent, label="Turn off LED")
        self.swap89_check.SetToolTip("Check this to keep the lights out.")
        box.Add(self.led_off_check, **box_kw)

        self.debounce_check = wx.CheckBox(parent, label="Enable debouncing")
        self.debounce_check.SetToolTip(
            "Enables debounce logic for buttons to compensate for switch chatter.")
        self.debounce_check.Bind(wx.EVT_CHECKBOX, self.on_debounce_check)
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

    def on_debounce_check(self, e):
        self.__evaluate_debounce_options__()

    def on_refresh(self, e):
        self.__populate_device_list__()

    def on_load(self, e):
        self.close_keybinds_window()
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
        self.__populate_from_conf__(conf)
        self.loading = False
        self.__evaluate_save_load_buttons__()
        self.__evaluate_debounce_options__()
        self.SetStatusText(
            f"Loaded from {device.product_name} ({device.serial_number}).")

    def on_save(self, e):
        self.close_keybinds_window()
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

    def on_keybinds_button(self, e):
        if self.keybinds_frame is None:
            self.keybinds_frame = KeybindsWindowFrame(
                self, title="Configure keybinds", keycodes=self.keycodes)

            self.keybinds_frame.Bind(
                wx.EVT_CLOSE, self.on_keybinds_frame_closed)

            self.keybinds_frame.Show()

    def close_keybinds_window(self):
        if self.keybinds_frame:
            self.keycodes = self.keybinds_frame.extract_keycodes_from_ui()
            self.keybinds_frame.Destroy()
            self.keybinds_frame = None

    def on_keybinds_frame_closed(self, e):
        self.close_keybinds_window()

    def __extract_conf_from_gui__(self):
        title = self.title_ctrl.GetValue()
        flags = 0
        if self.multitap_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_SEL_MULTI_TAP
        if self.qe1_invert_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_INVERT_QE1
        if self.swap89_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_SWAP_8_9
        if self.debounce_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_DEBOUNCE
        if self.mode_switch_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_MODE_SWITCHING_ENABLE
        if self.led_off_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_LED_OFF

        if self.poll_rate_ctrl.GetSelection() == 1:
            flags |= ARCIN_CONFIG_FLAG_250HZ_MODE

        if self.qe1_tt_ctrl.GetSelection() == 1:
            flags |= ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE
        elif self.qe1_tt_ctrl.GetSelection() == 2:
            flags |= ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE
            flags |= ARCIN_CONFIG_FLAG_ANALOG_TT_FORCE_ENABLE

        if self.input_mode_ctrl.GetSelection() == 1:
            # keyboard only
            flags |= ARCIN_CONFIG_FLAG_KEYBOARD_ENABLE
            flags |= ARCIN_CONFIG_FLAG_JOYINPUT_DISABLE
        elif self.input_mode_ctrl.GetSelection() == 2:
            # both gamepad and keyboard
            flags |= ARCIN_CONFIG_FLAG_KEYBOARD_ENABLE

        if self.led_mode_ctrl.GetSelection() == 1:
            flags |= ARCIN_CONFIG_FLAG_TT_LED_REACTIVE
        elif self.led_mode_ctrl.GetSelection() == 2:
            flags |= ARCIN_CONFIG_FLAG_TT_LED_HID
            
        if 2 <= self.debounce_ctrl.GetValue() <= 10:
            debounce_ticks = self.debounce_ctrl.GetValue()
        else:
            debounce_ticks = 2

        if self.qe1_sens_ctrl.GetValue() in SENS_OPTIONS:
            qe1_sens = SENS_OPTIONS[self.qe1_sens_ctrl.GetValue()]
        else:
            qe1_sens = -4 # 1:4: as the reasonable default

        effector_mode = self.e1e2_ctrl.GetSelection()

        keycodes = ""
        if self.keycodes:
            keycodes = bytes(self.keycodes)

        conf = ArcinConfig(
            label=title,
            flags=flags,
            qe1_sens=qe1_sens,
            qe2_sens=0,
            effector_mode=effector_mode,
            debounce_ticks=debounce_ticks,
            keycodes=keycodes
        )

        return conf

    def __populate_from_conf__(self, conf):
        # "label flags qe1_sens qe2_sens effector_mode debounce_ticks")
        self.title_ctrl.SetValue(conf.label)

        self.multitap_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_SEL_MULTI_TAP))

        self.qe1_invert_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_INVERT_QE1))

        self.swap89_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_SWAP_8_9))

        self.debounce_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_DEBOUNCE))

        self.mode_switch_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_MODE_SWITCHING_ENABLE))

        self.led_off_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_LED_OFF))

        if conf.flags & ARCIN_CONFIG_FLAG_250HZ_MODE:
            self.poll_rate_ctrl.Select(1)
        else:
            self.poll_rate_ctrl.Select(0)

        if (conf.flags & ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE and
            conf.flags & ARCIN_CONFIG_FLAG_ANALOG_TT_FORCE_ENABLE):
            self.qe1_tt_ctrl.Select(2)
        elif conf.flags & ARCIN_CONFIG_FLAG_DIGITAL_TT_ENABLE:
            self.qe1_tt_ctrl.Select(1)
        else:
            self.qe1_tt_ctrl.Select(0)

        if (conf.flags & ARCIN_CONFIG_FLAG_KEYBOARD_ENABLE and
            conf.flags & ARCIN_CONFIG_FLAG_JOYINPUT_DISABLE):
            self.input_mode_ctrl.Select(1)
        elif conf.flags & ARCIN_CONFIG_FLAG_KEYBOARD_ENABLE:
            self.input_mode_ctrl.Select(2)
        else:
            self.input_mode_ctrl.Select(0)

        if conf.flags & ARCIN_CONFIG_FLAG_TT_LED_REACTIVE:
            self.led_mode_ctrl.Select(1)
        elif conf.flags & ARCIN_CONFIG_FLAG_TT_LED_HID:
            self.led_mode_ctrl.Select(2)
        else:
            self.led_mode_ctrl.Select(0)

        self.debounce_ctrl.SetValue(conf.debounce_ticks)

        index = -4 # 1:4 is a reasonable default
        for i, value in enumerate(SENS_OPTIONS.values()):
            if conf.qe1_sens == value:
                index = i
                break
        self.qe1_sens_ctrl.Select(index)

        index = 0 # E1 E2 is a reasonable default
        effector_mode = min(conf.effector_mode, len(E1E2_OPTIONS) - 1)
        self.e1e2_ctrl.Select(effector_mode)

        self.keycodes = []
        for c in conf.keycodes:
            self.keycodes.append(c)

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

    def __evaluate_debounce_options__(self):
        self.debounce_ctrl.Enable(self.debounce_check.IsChecked())

    def __evaluate_save_load_buttons__(self):
        if self.devices_list.GetFirstSelected() >= 0 and not self.loading:
            self.save_button.Enable(True)
            self.load_button.Enable(True)
        else:
            self.save_button.Enable(False)
            self.load_button.Enable(False)

class KeybindsWindowFrame(wx.Frame):

    panel = None
    grid = None
    row = 0

    # controls
    controls_list = []

    def __init__(self, *args, **kw):
        default_size = (320, 550)
        kw['size'] = default_size
        kw['style'] = (
            wx.RESIZE_BORDER |
            wx.SYSTEM_MENU |
            wx.CAPTION |
            wx.CLOSE_BOX |
            wx.CLIP_CHILDREN
        )

        keycodes = kw.pop('keycodes')

        # ensure the parent's __init__ is called
        super().__init__(*args, **kw)

        # create a panel in the frame
        self.panel = wx.Panel(self)
        self.SetMinSize(default_size)
        box = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self.panel,
            label="Use any of the presets from the menu above, or configure each key below.")
        label.Wrap(default_size[0] - 20)
        box.Add(label, flag=(wx.EXPAND | wx.ALL), border=8)

        self.grid = wx.GridBagSizer(10, 10)
        self.grid.SetCols(2)
        self.grid.AddGrowableCol(1)

        self.controls_list = []

        self.__create_button__("Button 1")
        self.__create_button__("Button 2")
        self.__create_button__("Button 3")
        self.__create_button__("Button 4")
        self.__create_button__("Button 5")
        self.__create_button__("Button 6")
        self.__create_button__("Button 7")

        self.__create_button__("E1")
        self.__create_button__("E2")
        self.__create_button__("E3")
        self.__create_button__("E4")

        self.__create_button__("Turntable CW")
        self.__create_button__("Turntable CCW")

        if keycodes is not None:
            self.populate_ui_from_keycodes(keycodes)

        box.Add(self.grid, 1, flag=(wx.EXPAND | wx.ALL), border=8)
        self.panel.SetSizer(box)
        self.makeMenuBar()

    def makeMenuBar(self):
        presets_menu = wx.Menu()

        clearall_item = presets_menu.Append(wx.ID_ANY, item="Clear all")
        buttons_item = presets_menu.Append(wx.ID_ANY, item="All letters")
        player_1_item = presets_menu.Append(wx.ID_ANY, item="DJMAX 1p")
        player_2_item = presets_menu.Append(wx.ID_ANY, item="DJMAX 2p")

        menu_bar = wx.MenuBar()
        menu_bar.Append(presets_menu, "&Load a preset...")
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, self.on_clear_all, clearall_item)
        self.Bind(wx.EVT_MENU, self.on_buttons, buttons_item)
        self.Bind(wx.EVT_MENU, self.on_preset_1p, player_1_item)
        self.Bind(wx.EVT_MENU, self.on_preset_2p, player_2_item)

    def on_clear_all(self, e):
        keycodes = [0] * ARCIN_CONFIG_VALID_KEYCODES
        self.populate_ui_from_keycodes(keycodes)

    def on_buttons(self, e):
        keycodes = [
            # keys
            USB_HID_KEYS['Z'],
            USB_HID_KEYS['S'],
            USB_HID_KEYS['X'],
            USB_HID_KEYS['D'],
            USB_HID_KEYS['C'],
            USB_HID_KEYS['F'],
            USB_HID_KEYS['V'],

            # E1 - E4
            USB_HID_KEYS['Q'],
            USB_HID_KEYS['W'],
            USB_HID_KEYS['E'],
            USB_HID_KEYS['R'],

            # TT CW / CCW
            USB_HID_KEYS['J'],
            USB_HID_KEYS['K'],
        ]

        self.populate_ui_from_keycodes(keycodes)

    def on_preset_1p(self, e):
        keycodes = [
            # keys
            USB_HID_KEYS['Z'],
            USB_HID_KEYS['S'],
            USB_HID_KEYS['X'],
            USB_HID_KEYS['D'],
            USB_HID_KEYS['C'],
            USB_HID_KEYS['F'],
            USB_HID_KEYS['V'],

            # E1 - E4
            USB_HID_KEYS['ENTER'],
            USB_HID_KEYS['TAB'],
            USB_HID_KEYS['SPACE'],
            USB_HID_KEYS['ESC'],

            # TT CW / CCW
            USB_HID_KEYS['DOWN'],
            USB_HID_KEYS['UP'],
        ]

        self.populate_ui_from_keycodes(keycodes)

    def on_preset_2p(self, e):
        keycodes = [
            # keys
            USB_HID_KEYS['H'],
            USB_HID_KEYS['U'],
            USB_HID_KEYS['J'],
            USB_HID_KEYS['I'],
            USB_HID_KEYS['K'],
            USB_HID_KEYS['O'],
            USB_HID_KEYS['L'],

            # E1 - E4
            USB_HID_KEYS['ENTER'],
            USB_HID_KEYS['TAB'],
            USB_HID_KEYS['LEFTSHIFT'],
            USB_HID_KEYS['RIGHTSHIFT'],

            # TT CW / CCW
            USB_HID_KEYS['RIGHT'],
            USB_HID_KEYS['LEFT'],
        ]
        self.populate_ui_from_keycodes(keycodes)

    def populate_ui_from_keycodes(self, keycodes):

        assert len(self.controls_list) <= len(keycodes)
        assert len(self.controls_list) == ARCIN_CONFIG_VALID_KEYCODES

        for i, c in enumerate(self.controls_list):
            keycode = keycodes[i]
            if keycode in USB_HID_KEYCODES:
                c.Select(USB_HID_KEYCODES[keycode])
            else:
                c.Select(0)

    def extract_keycodes_from_ui(self):

        assert len(self.controls_list) == ARCIN_CONFIG_VALID_KEYCODES

        extracted_keycodes = []
        keycodes = list(USB_HID_KEYCODES.keys())
        for c in self.controls_list:
            selected_index = c.GetSelection()
            extracted_keycodes.append(keycodes[selected_index])
    
        return extracted_keycodes

    def __create_button__(self, label):
        label = wx.StaticText(self.panel, label=label)
        combobox = wx.Choice(self.panel, choices=list(USB_HID_KEYS.keys()))
        self.controls_list.append(combobox)
        combobox.Select(0)
        self.grid.Add(label, pos=(self.row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(combobox, pos=(self.row, 1), flag=wx.EXPAND)
        self.row += 1
        return combobox

def ui_main():
    app = wx.App()
    frm = MainWindowFrame(None, title="arcin-infinitas conf")
    frm.Show()

    # wx.lib.inspection.InspectionTool().Show()

    app.MainLoop()

if __name__ == "__main__":
    ui_main()
