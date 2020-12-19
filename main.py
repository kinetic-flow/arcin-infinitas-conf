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
    "label flags qe1_sens qe2_sens " +
    "debounce_ticks keycodes " +
    "remap_start_sel remap_b8_b9 "+
    "rgb_flags " +
    "rgb_red rgb_green rgb_blue " +
    "rgb_darkness " +
    "rgb_red_2 rgb_green_2 rgb_blue_2 " +
    "rgb_red_3 rgb_green_3 rgb_blue_3 " +
    "rgb_mode rgb_num_leds rgb_speed rgb_idle_brightness"
    )

Rgb = namedtuple("Rgb", "r g b")

RgbConfig = namedtuple(
    "RgbConfig", "flags rgb1 darkness rgb2 rgb3 mode num_leds speed idle_brightness")

ARCIN_CONFIG_VALID_KEYCODES = 13
ARCIN_RGB_MAX_DARKNESS = 255
ARCIN_RGB_NUM_LEDS_MAX = 60

# Infinitas controller VID/PID = 0x1ccf / 0x8048
VID = 0x1ccf
PID = 0x8048
CONFIG_SEGMENT_ID = hid.get_full_usage_id(0xff55, 0xc0ff)

STRUCT_FMT_EX = (
    "12s" + # uint8 label[12]
    "L" +   # uint32 flags
    "b" +   # int8 qe1_sens
    "b" +   # int8 qe2_sens
    "x" +   # uint8 reserved (was: effector_mode)
    "B" +   # uint8 debounce_ticks
    "16s" + # char keycodes[16]
    "B" +   # uint8 remap_start_sel
    "B" +   # uint8 remap_b8_b9
    "2x"+   # uint8 reserved[2]
    "B" +   # uint8 rgb_flags
    "BBB" + # uint8 red, green, blue (primary)
    "B" +   # uint8 rgb_darkness
    "BBB" + # uint8 red, green, blue (secondary)
    "BBB" + # uint8 red, green, blue (tertiary)
    "B" +   # uint8 rgb_mode
    "B" +   # uint8 rgb_num_leds
    "b" +   # int8 rgb_speed
    "B" +   # uint8 rgb_idle_brightness
    "5x")  # uint8 reserved[5]

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

EFFECTOR_NAMES = [
    "E1 (JOY 9)",
    "E2 (JOY 10)",
    "E3 (JOY 11)",
    "E4 (JOY 12)",
]

DEFAULT_EFFECTOR_MAPPING = [
    1, # start = e1
    2, # sel = e2
    3, # b8 = e3
    4  # b9 = e4
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

RGB_MODE_OPTIONS = [
    "Single-color",
    "Tricolor",
    "Single-color Rainbow",
    "Spiral rainbow",
    "Rainbow wave",
    "Single-color fade",
    "Two-color fade",
]

RGB_TT_FADE_OUT_OPTIONS = [
    "Instant",
    "Quick",
    "Slow",
    "Really slow",
]

ARCIN_CONFIG_FLAG_SEL_MULTI_TAP          = (1 << 0)
ARCIN_CONFIG_FLAG_INVERT_QE1             = (1 << 1)
# removed in favor of complete remapping of E buttons
# ARCIN_CONFIG_FLAG_SWAP_8_9               = (1 << 2)
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
ARCIN_CONFIG_FLAG_WS2812B                = (1 << 13)

ARCIN_RGB_FLAG_ENABLE_HID                = (1 << 0)
ARCIN_RGB_FLAG_REACT_TO_TT               = (1 << 1)
ARCIN_RGB_FLAG_FLIP_DIRECTION            = (1 << 2)
# 00 = instant
# 01 = 200ms
# 10 = 400ms
# 11 = 600ms
ARCIN_RGB_FLAG_FADE_OUT_FAST             = (1 << 3)
ARCIN_RGB_FLAG_FADE_OUT_SLOW             = (1 << 4)

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
            conf.debounce_ticks,
            conf.keycodes[0:16],
            conf.remap_start_sel,
            conf.remap_b8_b9, 
            conf.rgb_flags,
            conf.rgb_red,
            conf.rgb_green,
            conf.rgb_blue,
            conf.rgb_darkness,
            conf.rgb_red_2,
            conf.rgb_green_2,
            conf.rgb_blue_2,
            conf.rgb_red_3,
            conf.rgb_green_3,
            conf.rgb_blue_3,
            conf.rgb_mode,
            conf.rgb_num_leds,
            conf.rgb_speed
            )
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
    debounce_check = None
    mode_switch_check = None
    led_off_check = None
    ws2812b_check = None

    qe1_tt_ctrl = None
    debounce_ctrl = None

    qe1_sens_ctrl = None

    input_mode_ctrl = None

    led_mode_ctrl = None

    remapper_button = None
    remapper_frame = None
    remap = DEFAULT_EFFECTOR_MAPPING.copy()

    keybinds_button = None
    keybinds_frame = None
    keycodes = None

    rgb_button = None
    rgb_frame = None
    rgb_config = None

    def __init__(self, *args, **kw):
        default_size = (340, 680)
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

        remapper_label = wx.StaticText(panel, label="Configure gamepad")
        self.remapper_button = wx.Button(panel, label="Open")
        self.remapper_button.Bind(wx.EVT_BUTTON, self.on_remapper_button)
        grid.Add(remapper_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.remapper_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        keybinds_label = wx.StaticText(panel, label="Configure keyboard")
        self.keybinds_button = wx.Button(panel, label="Open")
        self.keybinds_button.Bind(wx.EVT_BUTTON, self.on_keybinds_button)
        grid.Add(keybinds_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.keybinds_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        rgb_label = wx.StaticText(panel, label="Configure WS2812B")
        self.rgb_button = wx.Button(panel, label="Open")
        self.rgb_button.Bind(wx.EVT_BUTTON, self.on_rgb_button)
        grid.Add(rgb_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.rgb_button, pos=(row, 1), flag=wx.EXPAND)
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

        self.mode_switch_check = wx.CheckBox(parent, label="Enable mode switching")
        self.mode_switch_check.SetToolTip(
            """Hold [Start + Sel + 1] for 3 seconds to switch input mode.
Hold [Start + Sel + 3] for 3 seconds to switch turntable mode.
Hold [Start + Sel + 5] for 3 seconds to switch LED state.
These only take in effect while plugged in; they are reset when unplugged""")
        box.Add(self.mode_switch_check, **box_kw)

        self.led_off_check = wx.CheckBox(parent, label="Turn off LED")
        self.led_off_check.SetToolTip("Check this to keep the lights out.")
        box.Add(self.led_off_check, **box_kw)

        self.debounce_check = wx.CheckBox(parent, label="Enable debouncing")
        self.debounce_check.SetToolTip(
            "Enables debounce logic for buttons to compensate for switch chatter.")
        self.debounce_check.Bind(wx.EVT_CHECKBOX, self.on_debounce_check)
        box.Add(self.debounce_check, **box_kw)

        self.ws2812b_check = wx.CheckBox(parent, label="Enable WS2812B for B9")
        self.ws2812b_check.SetToolTip("Use button 9 pins as WS2812B output.")
        box.Add(self.ws2812b_check, **box_kw)

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
        self.close_remapper_window()
        self.close_keybinds_window()
        self.close_rgb_window()
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
        # close windows to ensure values get extracted from UI on close
        self.close_remapper_window()
        self.close_keybinds_window()
        self.close_rgb_window()
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

    def on_remapper_button(self, e):
        if self.remapper_frame is None:
            self.remapper_frame = RemapperWindowFrame(
                self, title="Configure gamepad", remap=self.remap)

            self.remapper_frame.Bind(
                wx.EVT_CLOSE, self.on_remapper_frame_closed)

            self.remapper_frame.Show()

    def on_keybinds_button(self, e):
        if self.keybinds_frame is None:
            self.keybinds_frame = KeybindsWindowFrame(
                self, title="Configure keyboard", keycodes=self.keycodes)

            self.keybinds_frame.Bind(
                wx.EVT_CLOSE, self.on_keybinds_frame_closed)

            self.keybinds_frame.Show()

    def on_rgb_button(self, e):
        if self.rgb_frame is None:
            self.rgb_frame = RgbWindowFrame(
                self, title="Configure WS2812B", rgb_config=self.rgb_config)

            self.rgb_frame.Bind(
                wx.EVT_CLOSE, self.on_rgb_frame_closed)

            self.rgb_frame.Show()

    def close_remapper_window(self):
        if self.remapper_frame:
            self.remap = self.remapper_frame.extract_remap_from_ui()
            self.remapper_frame.Destroy()
            self.remapper_frame = None

    def close_keybinds_window(self):
        if self.keybinds_frame:
            self.keycodes = self.keybinds_frame.extract_keycodes_from_ui()
            self.keybinds_frame.Destroy()
            self.keybinds_frame = None

    def close_rgb_window(self):
        if self.rgb_frame:
            self.rgb_config = self.rgb_frame.extract_from_ui()
            self.rgb_frame.Destroy()
            self.rgb_frame = None

    def on_remapper_frame_closed(self, e):
        self.close_remapper_window()

    def on_keybinds_frame_closed(self, e):
        self.close_keybinds_window()

    def on_rgb_frame_closed(self, e):
        self.close_rgb_window()

    def __extract_conf_from_gui__(self):
        title = self.title_ctrl.GetValue()
        flags = 0
        if self.multitap_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_SEL_MULTI_TAP
        if self.qe1_invert_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_INVERT_QE1
        if self.debounce_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_DEBOUNCE
        if self.mode_switch_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_MODE_SWITCHING_ENABLE
        if self.led_off_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_LED_OFF
        if self.ws2812b_check.IsChecked():
            flags |= ARCIN_CONFIG_FLAG_WS2812B

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

        if self.keycodes:
            keycodes = bytes(self.keycodes)
        else:
            keycodes = bytes([0] * ARCIN_CONFIG_VALID_KEYCODES)

        remap_start_sel = (self.remap[0] << 4) | self.remap[1]
        remap_b8_b9 = (self.remap[2] << 4) | self.remap[3]

        rgb_flags = 0
        rgb_darkness = 0
        rgb_primary = Rgb(0, 0, 0)
        rgb_secondary = Rgb(0, 0, 0)
        rgb_tertiary = Rgb(0, 0, 0)
        rgb_mode = 0
        rgb_num_leds = ARCIN_RGB_NUM_LEDS_MAX
        rgb_speed = 0
        rgb_idle_brightness = 0
        if self.rgb_config:
            rgb_flags = self.rgb_config.flags
            rgb_primary = self.rgb_config.rgb1
            rgb_darkness = self.rgb_config.darkness
            rgb_secondary = self.rgb_config.rgb2
            rgb_tertiary = self.rgb_config.rgb3
            rgb_mode = self.rgb_config.mode
            rgb_num_leds = self.rgb_config.num_leds
            rgb_speed = self.rgb_config.speed
            rgb_idle_brightness = self.rgb_config.rgb_idle_brightness

        conf = ArcinConfig(
            label=title,
            flags=flags,
            qe1_sens=qe1_sens,
            qe2_sens=0,
            debounce_ticks=debounce_ticks,
            keycodes=keycodes,
            remap_start_sel=remap_start_sel,
            remap_b8_b9=remap_b8_b9,
            rgb_flags=rgb_flags,
            rgb_red=rgb_primary.r,
            rgb_green=rgb_primary.g,
            rgb_blue=rgb_primary.b,
            rgb_darkness=rgb_darkness,
            rgb_red_2=rgb_secondary.r,
            rgb_green_2=rgb_secondary.g,
            rgb_blue_2=rgb_secondary.b,
            rgb_red_3=rgb_tertiary.r,
            rgb_green_3=rgb_tertiary.g,
            rgb_blue_3=rgb_tertiary.b,
            rgb_mode=rgb_mode,
            rgb_num_leds=rgb_num_leds,
            rgb_speed=rgb_speed,
            rgb_idle_brightness=rgb_idle_brightness,
        )

        return conf

    def __populate_from_conf__(self, conf):
        # "label flags qe1_sens qe2_sens effector_mode debounce_ticks")
        self.title_ctrl.SetValue(conf.label)

        self.multitap_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_SEL_MULTI_TAP))

        self.qe1_invert_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_INVERT_QE1))

        self.debounce_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_DEBOUNCE))

        self.mode_switch_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_MODE_SWITCHING_ENABLE))

        self.led_off_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_LED_OFF))

        self.ws2812b_check.SetValue(
            bool(conf.flags & ARCIN_CONFIG_FLAG_WS2812B))

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

        self.keycodes = []
        for c in conf.keycodes:
            self.keycodes.append(c)

        self.remap[0] = (conf.remap_start_sel >> 4) & 0xF
        self.remap[1] = conf.remap_start_sel & 0xF
        self.remap[2] = (conf.remap_b8_b9 >> 4) & 0xF
        self.remap[3] = conf.remap_b8_b9 & 0xF

        self.rgb_config = RgbConfig(
            conf.rgb_flags,
            Rgb(conf.rgb_red, conf.rgb_green, conf.rgb_blue),
            conf.rgb_darkness,
            Rgb(conf.rgb_red_2, conf.rgb_green_2, conf.rgb_blue_2),
            Rgb(conf.rgb_red_3, conf.rgb_green_3, conf.rgb_blue_3),
            conf.rgb_mode,
            conf.rgb_num_leds,
            conf.rgb_speed,
            conf.rgb_idle_brightness,
            )

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

class RemapperWindowFrame(wx.Frame):

    panel = None
    grid = None

    remap_start_ctrl = None
    remap_select_ctrl = None
    remap_b8_ctrl = None
    remap_b9_ctrl = None

    def __init__(self, *args, **kw):
        default_size = (300, 200)
        kw['size'] = default_size
        kw['style'] = (
            wx.RESIZE_BORDER |
            wx.SYSTEM_MENU |
            wx.CAPTION |
            wx.CLOSE_BOX |
            wx.CLIP_CHILDREN
        )

        remap = kw.pop('remap')

        # ensure the parent's __init__ is called
        super().__init__(*args, **kw)

        # create a panel in the frame
        self.panel = wx.Panel(self)
        self.SetMinSize(default_size)
        box = wx.BoxSizer(wx.VERTICAL)

        self.grid = wx.GridBagSizer(10, 10)
        self.grid.SetCols(2)
        self.grid.AddGrowableCol(1)
        row = 0    

        self.remap_start_ctrl = wx.Choice(self.panel, choices=EFFECTOR_NAMES)
        self.grid.Add(
            wx.StaticText(self.panel, label="Start Button"),
            pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.remap_start_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.remap_select_ctrl = wx.Choice(self.panel, choices=EFFECTOR_NAMES)
        self.grid.Add(
            wx.StaticText(self.panel, label="Select Button"),
            pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.remap_select_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.remap_b8_ctrl = wx.Choice(self.panel, choices=EFFECTOR_NAMES)
        self.grid.Add(
            wx.StaticText(self.panel, label="Button 8"),
            pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.remap_b8_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.remap_b9_ctrl = wx.Choice(self.panel, choices=EFFECTOR_NAMES)
        self.grid.Add(
            wx.StaticText(self.panel, label="Button 9"),
            pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.remap_b9_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1
    
        box.Add(self.grid, 1, flag=(wx.EXPAND | wx.ALL), border=8)
        self.panel.SetSizer(box)

        if remap is not None:
            self.populate_ui_from_remap(remap)

    def populate_ui_from_remap(self, remap):
        for i, value in enumerate(remap):
            if value == 0:
                remap[i] = DEFAULT_EFFECTOR_MAPPING[i]

        self.remap_start_ctrl.Select(remap[0] - 1)
        self.remap_select_ctrl.Select(remap[1] - 1)
        self.remap_b8_ctrl.Select(remap[2] - 1)
        self.remap_b9_ctrl.Select(remap[3] - 1)

    def extract_remap_from_ui(self):
        remap = [
            self.remap_start_ctrl.GetSelection() + 1,
            self.remap_select_ctrl.GetSelection() + 1,
            self.remap_b8_ctrl.GetSelection() + 1,
            self.remap_b9_ctrl.GetSelection() + 1,
        ]
        return remap

def wxcolour_from_rgb(rgb):
    return wx.Colour(rgb.r, rgb.g, rgb.b)

def rgb_from_Wxcolour(wxcolour):
    return Rgb(wxcolour.red, wxcolour.green, wxcolour.blue)

class RgbWindowFrame(wx.Frame):

    panel = None
    grid = None

    hid_rgb_check = None
    qe1_react_check = None
    flip_direction_check = None

    rgb1_button = None
    rgb2_button = None
    rgb3_button = None

    led_mode_ctrl = None
    intensity_slider = None
    idle_intensity_slider = None
    num_leds_slider = None
    speed_slider = None
    fadeout_ctrl = None

    def __init__(self, *args, **kw):
        default_size = (340, 580)
        kw['size'] = default_size
        kw['style'] = (
            wx.RESIZE_BORDER |
            wx.SYSTEM_MENU |
            wx.CAPTION |
            wx.CLOSE_BOX |
            wx.CLIP_CHILDREN
        )

        rgb_config = kw.pop('rgb_config')

        # ensure the parent's __init__ is called
        super().__init__(*args, **kw)

        # create a panel in the frame
        self.panel = wx.Panel(self)
        self.SetMinSize(default_size)
        box = wx.BoxSizer(wx.VERTICAL)

        self.grid = wx.GridBagSizer(10, 10)
        self.grid.SetCols(2)
        self.grid.AddGrowableCol(1)
        row = 0

        self.grid.Add(
            self.__make_header_text__("LED configuration"),
            pos=(row, 0), span=(1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        row += 1

        checklist_label = wx.StaticText(self.panel, label="Options")
        self.grid.Add(checklist_label, pos=(row, 0), flag=wx.ALIGN_TOP, border=2)
        checklist_box = self.__create_checklist__(self.panel)
        self.grid.Add(checklist_box, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        num_leds_label = wx.StaticText(self.panel, label="Number of LEDs")
        self.num_leds_slider = wx.Slider(
            self.panel, style=wx.SL_VALUE_LABEL, minValue=1, maxValue=ARCIN_RGB_NUM_LEDS_MAX)
        self.num_leds_slider.SetTickFreq = 1
        self.num_leds_slider.SetValue(ARCIN_RGB_NUM_LEDS_MAX)
        self.grid.Add(num_leds_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.num_leds_slider, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.grid.Add(
            self.__make_header_text__("Color mode"),
            pos=(row, 0), span=(1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        row += 1

        led_mode_label = wx.StaticText(self.panel, label="Color mode")
        self.led_mode_ctrl = wx.Choice(self.panel, choices=RGB_MODE_OPTIONS)
        self.led_mode_ctrl.Select(0)
        self.grid.Add(led_mode_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.led_mode_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        intensity_label = wx.StaticText(self.panel, label="Brightness")
        self.intensity_slider = wx.Slider(
            self.panel, style=wx.SL_VALUE_LABEL, minValue=0, maxValue=ARCIN_RGB_MAX_DARKNESS)
        self.intensity_slider.SetTickFreq = 1
        self.intensity_slider.SetValue(ARCIN_RGB_MAX_DARKNESS)
        self.grid.Add(intensity_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.intensity_slider, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        speed_label = wx.StaticText(self.panel, label="Speed (default=0)")
        self.speed_slider = wx.Slider(
            self.panel, style=wx.SL_VALUE_LABEL, minValue=-128, maxValue=127)
        self.speed_slider.SetTickFreq = 1
        self.speed_slider.SetValue(0)
        self.grid.Add(speed_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.speed_slider, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.grid.Add(
            self.__make_header_text__("Colors"),
            pos=(row, 0), span=(1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        row += 1

        rgb_label = wx.StaticText(self.panel, label="Default color")
        self.rgb1_button = wx.ColourPickerCtrl(self.panel)
        self.grid.Add(rgb_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.rgb1_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        rgb_label = wx.StaticText(self.panel, label="Secondary color")
        self.rgb2_button = wx.ColourPickerCtrl(self.panel)
        self.grid.Add(rgb_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.rgb2_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        rgb_label = wx.StaticText(self.panel, label="Tertiary color")
        self.rgb3_button = wx.ColourPickerCtrl(self.panel)
        self.grid.Add(rgb_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.rgb3_button, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        self.grid.Add(
            self.__make_header_text__("Reactive turntable mode"),
            pos=(row, 0), span=(1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        row += 1

        self.qe1_react_check = wx.CheckBox(self.panel, label="Enable")
        self.qe1_react_check.SetToolTip("Behavior depends on the color algorithm.")
        self.grid.Add(self.qe1_react_check, pos=(row, 0), span=(1, 2))
        row += 1

        fadeout_label = wx.StaticText(self.panel, label="Fade out time")
        self.fadeout_ctrl = wx.Choice(self.panel, choices=RGB_TT_FADE_OUT_OPTIONS)
        self.fadeout_ctrl.Select(0)
        self.grid.Add(fadeout_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.fadeout_ctrl, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        idle_intensity_label = wx.StaticText(self.panel, label="Idle brightness")
        self.idle_intensity_slider = wx.Slider(
            self.panel, style=wx.SL_VALUE_LABEL, minValue=0, maxValue=ARCIN_RGB_MAX_DARKNESS)
        self.idle_intensity_slider.SetTickFreq = 1
        self.idle_intensity_slider.SetValue(0)
        self.grid.Add(idle_intensity_label, pos=(row, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.idle_intensity_slider, pos=(row, 1), flag=wx.EXPAND)
        row += 1

        box.Add(self.grid, 1, flag=(wx.EXPAND | wx.ALL), border=8)
        self.panel.SetSizer(box)

        if rgb_config is not None:
            self.populate_ui(rgb_config)

    def populate_ui(self, config):
        self.hid_rgb_check.SetValue(bool(config.flags & ARCIN_RGB_FLAG_ENABLE_HID))
        self.qe1_react_check.SetValue(bool(config.flags & ARCIN_RGB_FLAG_REACT_TO_TT))
        self.flip_direction_check.SetValue(bool(config.flags & ARCIN_RGB_FLAG_FLIP_DIRECTION))
        self.intensity_slider.SetValue(ARCIN_RGB_MAX_DARKNESS - config.darkness)
        self.idle_intensity_slider.SetValue(config.idle_brightness)
        self.rgb1_button.SetColour(wxcolour_from_rgb(config.rgb1))
        self.rgb2_button.SetColour(wxcolour_from_rgb(config.rgb2))
        self.rgb3_button.SetColour(wxcolour_from_rgb(config.rgb3))
        self.led_mode_ctrl.Select(config.mode)
        if config.num_leds == 0:
            self.num_leds_slider.SetValue(ARCIN_RGB_NUM_LEDS_MAX)
        else:
            self.num_leds_slider.SetValue(config.num_leds)

        fadeout_value = 0
        if config.flags & ARCIN_RGB_FLAG_FADE_OUT_FAST:
            fadeout_value |= 0x1
        if config.flags & ARCIN_RGB_FLAG_FADE_OUT_SLOW:
            fadeout_value |= 0x2
        self.fadeout_ctrl.Select(fadeout_value)

        self.speed_slider.SetValue(config.speed)        
        pass

    def extract_from_ui(self):
        flags = 0
        if self.hid_rgb_check.IsChecked():
            flags |= ARCIN_RGB_FLAG_ENABLE_HID
        if self.qe1_react_check.IsChecked():
            flags |= ARCIN_RGB_FLAG_REACT_TO_TT
        if self.flip_direction_check.IsChecked():
            flags |= ARCIN_RGB_FLAG_FLIP_DIRECTION

        fadeout = self.fadeout_ctrl.GetSelection()
        if fadeout & 0x2:
            flags |= ARCIN_RGB_FLAG_FADE_OUT_SLOW
        if fadeout & 0x1:
            flags |= ARCIN_RGB_FLAG_FADE_OUT_FAST

        intensity = ARCIN_RGB_MAX_DARKNESS - self.intensity_slider.GetValue()

        rgb1 = self.rgb1_button.GetColour()
        rgb2 = self.rgb2_button.GetColour()
        rgb3 = self.rgb3_button.GetColour()

        return RgbConfig(
            flags,
            rgb_from_Wxcolour(rgb1),
            intensity,
            rgb_from_Wxcolour(rgb2),
            rgb_from_Wxcolour(rgb3),
            self.led_mode_ctrl.GetSelection(),
            self.num_leds_slider.GetValue(),
            self.speed_slider.GetValue(),
            self.idle_intensity_slider.GetValue(),
            )

    def __make_header_text__(self, text):
        static_text = wx.StaticText(self.panel, label=text)
        static_text.SetFont(static_text.GetFont().MakeBold())
        return static_text

    def __create_checklist__(self, parent):
        box_kw = {
            "proportion": 0,
            "flag": wx.BOTTOM,
            "border": 4
        }

        box = wx.BoxSizer(wx.VERTICAL)

        self.hid_rgb_check = wx.CheckBox(parent, label="Allow HID control")
        self.hid_rgb_check.SetToolTip("Allow HID to directly control RGB values when enabled.")
        box.Add(self.hid_rgb_check, **box_kw)

        self.flip_direction_check = wx.CheckBox(parent, label="Flip LED direction")
        self.flip_direction_check.SetToolTip("Flip direction of color algorithm.")
        box.Add(self.flip_direction_check, **box_kw)

        return box

def ui_main():
    app = wx.App()
    frm = MainWindowFrame(None, title="arcin-infinitas conf")
    frm.Show()

    # wx.lib.inspection.InspectionTool().Show()

    app.MainLoop()

if __name__ == "__main__":
    ui_main()
