import ctypes
import time
import random
from ctypes import wintypes

# --- DLL and Function Setup ---
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Constants
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
HWND_MESSAGE = -3

# WM_INPUT = 0x00FF
# Windows sends WM_INPUT to your window when raw input data is available.
# This includes keyboard, mouse, and HID events.
# You handle this in your window procedure/callback to read input data via GetRawInputData().

# RID_INPUT = 0x10000003
# Flag for GetRawInputData()
# Tells Windows you want the actual input data, not just header info.

# RIDEV_INPUTSINK = 0x00000100
# Receive input even when not focused
# Used when registering raw input devices with RegisterRawInputDevices().
# Allows your window to receive input in the background.

# HWND_MESSAGE = -3
# Message-only window
# Special window handle that: Is invisible, Has no UI, Exists only to receive messages

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage",     wintypes.USHORT),
        ("dwFlags",     wintypes.DWORD),
        ("hwndTarget",  wintypes.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]

class RAWINPUT_UNION(ctypes.Union):
    _fields_ = [("keyboard", RAWKEYBOARD)]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWINPUT_UNION),
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON)
    ]

WNDPROC = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,  # Return Type (LRESULT)
    wintypes.HWND,    # hwnd
    wintypes.UINT,    # uMsg
    wintypes.WPARAM,  # wParam
    wintypes.LPARAM   # lParam
)

# Define API types to prevent Error 0
# Tell ctypes exactly how to call Windows API functions, so Python doesn’t crash or silently pass wrong data.
# When you call Win32 APIs from Python via ctypes, Python has no idea:
# how many arguments a function takes
# what types those arguments are
# what the function returns
# Without argtypes, Python may pass integers where Windows expects pointers.
user32.RegisterRawInputDevices.argtypes = (ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT)
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.GetRawInputData.argtypes = (wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT), wintypes.UINT)
user32.CreateWindowExW.argtypes = (
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
)
user32.CreateWindowExW.restype = wintypes.HWND

# --- Global Logic ---
def process_input(lParam):
    cbSize = wintypes.UINT()
    header_size = ctypes.sizeof(RAWINPUTHEADER)
    
    # Ask Windows how big the input data is
    # This is a two-call Win32 pattern:
    # First call (Get Size):
    #   Pass None as the buffer
    #   Windows fills cbSize with the required buffer size
    # This avoids buffer overruns.
    # Allocates exactly enough memory
    # Second call actually copies the raw input data into buffer

    # Get Size and guard
    user32.GetRawInputData(lParam, RID_INPUT, None, ctypes.byref(cbSize), header_size)    
    if not cbSize.value > 0:
        return 
    
    # Get Data and guard
    buffer = ctypes.create_string_buffer(cbSize.value)
    if not user32.GetRawInputData(lParam, RID_INPUT, buffer, ctypes.byref(cbSize), header_size) >= 0:
        return
    
    # Interpret the buffer as RAWINPUT
    # Treats raw bytes as a structured RAWINPUT
    raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents

    if raw.header.dwType == 1: # RIM_TYPEKEYBOARD
        # Mouse and other HID devices are ignored
        kbd = raw.data.keyboard
        

        # Determine key up vs key down
        # Check for Key Down (Flags & 1 == 0)
        # Flags & 0x01 = key release
        # No flag      = key press
        is_down = not (kbd.Flags & 0x01)
        state = "DOWN" if is_down else "UP"
        print(f"Raw Key: 0x{kbd.VKey:02X} | State: {state}")

        if (state == "UP" and kbd.VKey == 220):
            # (220 = VK_OEM_5) Usually \ or | (depends on keyboard layout)
            # Trigger happens on key release, not press (avoids repeats)            
            # This acts like an on/off toggle switch.
            global repeat_state
            repeat_state = not repeat_state

            if (repeat_state):
                print(f"Start repeat")
                # Seeds/Sends a synthetic key, this starts the feedback loop
                KeyPress()
            else:
                print(f"Stop repeat")
        
        if (repeat_state and not is_down and raw.header.hDevice == None):
            # Injected input typically has:
            # raw.header.hDevice == None
            # (Physical keyboards have a real device handle.)
            #
            # So this section triggers when: 
            # Repeat mode is ON and a synthetic key is released
            # A real input will never trigger this 
            KeyPress()
    # Summary: Listen to all keyboard input. 
    # When I release the \ key, toggle repeat mode and send the first simulated key. 
    # While repeat mode is on, every simulated key release triggers another simulated key press.
    # Notes: KeyPress has sleep functions, 
    # this callback will not be able to process other keys while it is sleeping

# WndProc Callback
def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        process_input(lparam)
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

# Keep a reference to the WNDPROC so it isn't garbage collected
WNDPROC_FUNC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)(wnd_proc)

def Listen():
    hinst = kernel32.GetModuleHandleW(None)
    classname = u"RawInputListenerClass"

    # 1. Properly define and initialize the Window Class
    # The WNDPROC must be a persistent reference
    global persistent_wnd_proc
    persistent_wnd_proc = WNDPROC(wnd_proc)

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW) # This MUST be correct or RegisterClass fails
    wc.style = 0
    wc.lpfnWndProc = persistent_wnd_proc
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hinst
    wc.hIcon = 0
    wc.hCursor = 0
    wc.hbrBackground = 0
    wc.lpszMenuName = None
    wc.lpszClassName = classname
    wc.hIconSm = 0

    if not user32.RegisterClassExW(ctypes.byref(wc)):
        # If this fails, check if the class already exists (Error 1410)
        error = ctypes.get_last_error()
        if error != 1410: 
            print(f"RegisterClassExW failed with error: {error}")
            return

    # 2. Create the Window
    # Use 0 for x, y, width, and height as it's a hidden message-only window
    hwnd = user32.CreateWindowExW(
        0,              # dwExStyle
        classname,      # lpClassName
        u"Hidden",      # lpWindowName
        0,              # dwStyle
        0, 0, 0, 0,     # x, y, nWidth, nHeight
        HWND_MESSAGE,   # hWndParent (-3 makes it a message-only window)
        0,              # hMenu
        hinst,          # hInstance
        0               # lpParam
    )
    
    if not hwnd:
        print(f"CreateWindowExW failed! Error: {ctypes.get_last_error()}")
        return

    # 3. Register for Raw Input using the new HWND
    rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
    if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        print(f"RegisterRawInputDevices failed! Error: {ctypes.get_last_error()}")
        return

    print("Listening... (Press Ctrl+C to exit)")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

# ----------------------------
SendInput = ctypes.windll.user32.SendInput
repeat_state = False

# C struct redefinitions 
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time",ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                 ("mi", MouseInput),
                 ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Actual Functions
def PressKey(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    # Uses scan codes (not virtual keys)
    # 0x0008 = KEYEVENTF_SCANCODE
    # Sends a key DOWN event
    # The 0 in the first position means no virtual key
    # Windows interprets this as a hardware-level key press
    ii_.ki = KeyBdInput( 0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra) )
    x = Input( ctypes.c_ulong(1), ii_ )
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def ReleaseKey(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    # 0x0008 is scan code
    # 0x0002 is KEYEVENTF_KEYUP
    ii_.ki = KeyBdInput( 0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra) )
    x = Input( ctypes.c_ulong(1), ii_ )
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def KeyPress():
    # randomness to prevent bot catchers
    # rand1 up to 0.1s delay, total 0.8s
    rand1 = random.randint(1, 100)/1000
    time.sleep(0.7 + rand1)
    PressKey(0x12) # press E
    #PressKey(0x39) # press Space
    # rand2 up to 0.05s delay, total 0.1s
    rand2 = random.randint(1, 500)/10000
    time.sleep(.05 + rand2)
    ReleaseKey(0x12) # release E
    #ReleaseKey(0x39) # press Space

#------- Main
Listen()


# Intended behavior
# You press \ (VK 220), repeat mode toggles ON
# Any key release triggers KeyPress()
# KeyPress() injects E down and E up
# That injected E up comes back through WM_INPUT
# Because repeat mode is still ON:
# It triggers KeyPress() again
# This continues forever
# You press \ again, repeat mode OFF
# Loop stops
