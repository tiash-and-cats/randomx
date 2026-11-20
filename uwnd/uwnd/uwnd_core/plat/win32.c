#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <windowsx.h>

#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <wchar.h>
#include <locale.h>

#include "uwnd.h"

typedef struct uwnd__PlatData {
    HWND hwnd;
    BITMAPINFO bmi;
} uwnd__PlatData;

static LRESULT CALLBACK uwnd__WindowProc(
    HWND hwnd,
    UINT msg,
    WPARAM wParam,
    LPARAM lParam
) {
    uwnd_Window* win =
        (uwnd_Window* )
        GetWindowLongPtr(
            hwnd,
            GWLP_USERDATA
        );

    switch (msg) {
        case WM_PAINT: {
            if (!win) {
                return DefWindowProc(
                    hwnd,
                    msg,
                    wParam,
                    lParam
                );
            }

            uwnd__PlatData* plat =
                (uwnd__PlatData* )
                win->platform_data;

            PAINTSTRUCT ps;

            HDC hdc =
                BeginPaint(
                    hwnd,
                    &ps
                );

            StretchDIBits(
                hdc,

                0,
                0,

                win->framebuffer.width,
                win->framebuffer.height,

                0,
                0,

                win->framebuffer.width,
                win->framebuffer.height,

                win->framebuffer.pixels,

                &plat->bmi,

                DIB_RGB_COLORS,
                SRCCOPY
            );

            EndPaint(
                hwnd,
                &ps
            );

            return 0;
        }
        
        case WM_MOUSEMOVE: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_MOUSE_MOVE;

            evt.x =
                GET_X_LPARAM(lParam);

            evt.y =
                GET_Y_LPARAM(lParam);

            uwnd__push_Event(
                win,
                evt
            );

            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_MOUSE_DOWN;

            evt.button = 1;

            evt.x =
                GET_X_LPARAM(lParam);

            evt.y =
                GET_Y_LPARAM(lParam);

            uwnd__push_Event(
                win,
                evt
            );

            return 0;
        }
        
        case WM_LBUTTONUP: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_MOUSE_UP;

            evt.button = 1;

            evt.x =
                GET_X_LPARAM(lParam);

            evt.y =
                GET_Y_LPARAM(lParam);

            uwnd__push_Event(
                win,
                evt
            );

            return 0;
        }
        
        case WM_KEYDOWN: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_KEY_DOWN;

            evt.key = (int)wParam;

            uwnd__push_Event(
                win,
                evt
            );

            return 0;
        }
        
        case WM_KEYUP: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_KEY_UP;

            evt.key = (int)wParam;

            uwnd__push_Event(
                win,
                evt
            );

            return 0;
        }
        
        case WM_SIZE: {
            if (!win) {
                return DefWindowProc(hwnd, msg, wParam, lParam);
            }

            int new_width = LOWORD(lParam);
            int new_height = HIWORD(lParam);

            if (new_width <= 0 || new_height <= 0) {
                return 0;
            }

            uwnd__PlatData* plat = (uwnd__PlatData*)win->platform_data;

            // reallocate the pixel buffer
            uint32_t* new_pixels = realloc(
                win->framebuffer.pixels,
                new_width * new_height * sizeof(uint32_t)
            );
            if (!new_pixels) return 0;

            win->framebuffer.pixels = new_pixels;
            win->framebuffer.width = new_width;
            win->framebuffer.height = new_height;

            // update the BITMAPINFO header dimensions for StretchDIBits
            plat->bmi.bmiHeader.biWidth = new_width;
            plat->bmi.bmiHeader.biHeight = -new_height;

            return 0;
        }

        case WM_DESTROY: {
            uwnd_Event evt = {0};

            evt.type =
                uwnd_EventType_QUIT;

            uwnd__push_Event(
                win,
                evt
            );

            PostQuitMessage(0);

            return 0;
        }
    }

    return DefWindowProc(
        hwnd,
        msg,
        wParam,
        lParam
    );
}

bool uwnd__platform_init_Window(
    uwnd_Window* win,
    int width,
    int height,
    const char* title
) {
    // Convert title to wide char
    int len =
        MultiByteToWideChar(
            CP_UTF8,
            0,
            title,
            -1,
            NULL,
            0
        );

    wchar_t* titlew =
        malloc(
            len * sizeof(wchar_t)
        );

    MultiByteToWideChar(
        CP_UTF8,
        0,
        title,
        -1,
        titlew,
        len
    );
    
    static int registered = 0;

    HINSTANCE instance =
        GetModuleHandle(NULL);

    if (!registered) {
        WNDCLASS wc = {0};

        wc.lpfnWndProc =
            uwnd__WindowProc;

        wc.hInstance =
            instance;

        wc.lpszClassName =
            "uwnd_Window";

        wc.hCursor =
            LoadCursor(
                NULL,
                IDC_ARROW
            );

        wc.hbrBackground =
            (HBRUSH)(COLOR_WINDOW + 1);

        RegisterClass(&wc);

        registered = 1;
    }

    if (!uwnd__fb_init(win, width, height)) return false;

    uwnd__PlatData* plat =
        calloc(
            1,
            sizeof(uwnd__PlatData)
        );

    if (!plat) {
        free(win->framebuffer.pixels);
        return false;
    }

    plat->bmi.bmiHeader.biSize =
        sizeof(BITMAPINFOHEADER);

    plat->bmi.bmiHeader.biWidth =
        width;

    plat->bmi.bmiHeader.biHeight =
        -height;

    plat->bmi.bmiHeader.biPlanes =
        1;

    plat->bmi.bmiHeader.biBitCount =
        32;

    plat->bmi.bmiHeader.biCompression =
        BI_RGB;

    plat->hwnd =
        CreateWindowExW(
            0,
            L"uwnd_Window",
            titlew,

            WS_OVERLAPPEDWINDOW,

            CW_USEDEFAULT,
            CW_USEDEFAULT,

            width,
            height,

            NULL,
            NULL,

            instance,
            NULL
        );

    if (!plat->hwnd) {
        free(plat);
        free(win->framebuffer.pixels);
        return false;
    }

    win->platform_data =
        plat;

    SetWindowLongPtr(
        plat->hwnd,
        GWLP_USERDATA,
        (LONG_PTR)win
    );

    ShowWindow(
        plat->hwnd,
        SW_SHOW
    );

    UpdateWindow(
        plat->hwnd
    );

    return true;
}

void uwnd__platform_render(
    uwnd_Window* win
) {
    uwnd__PlatData* plat =
        (uwnd__PlatData* )
        win->platform_data;

    InvalidateRect(
        plat->hwnd,
        NULL,
        FALSE
    );

    UpdateWindow(
        plat->hwnd
    );
}

void uwnd__platform_delete(uwnd_Window* win) {
    if (!win) {
        return;
    }

    uwnd__PlatData* plat =
        (uwnd__PlatData* )
        win->platform_data;

    if (plat) {
        if (plat->hwnd) {
            DestroyWindow(
                plat->hwnd
            );
        }

        free(plat);
    }

    free(
        win->framebuffer.pixels
    );
}

int uwnd__platform_poll(uwnd_Window* _) {
    MSG msg;

    while (
        PeekMessage(
            &msg,
            NULL,
            0,
            0,
            PM_REMOVE
        )
    ) {
        if (msg.message == WM_QUIT) {
            return 0;
        }

        TranslateMessage(
            &msg
        );

        DispatchMessage(
            &msg
        );
    }

    return 1;
}

char* uwnd__platform_find_Font(const char* iname) {
    char* name = malloc(strlen(iname) + strlen(" (TrueType)") + 1);
    if (name != NULL) {
        strcpy(name, iname);
        strcat(name, " (TrueType)");
    }
    
    HKEY key;

    if (
        RegOpenKeyExA(
            HKEY_LOCAL_MACHINE,
            "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
            0,
            KEY_READ,
            &key
        ) != ERROR_SUCCESS
    ) {
        return NULL;
    }

    DWORD index = 0;

    char value_name[256];
    BYTE value_data[256];

    while (1) {
        DWORD value_name_size =
            sizeof(value_name);

        DWORD value_data_size =
            sizeof(value_data);

        DWORD type;

        LONG result =
            RegEnumValueA(
                key,
                index++,

                value_name,
                &value_name_size,

                NULL,

                &type,

                value_data,
                &value_data_size
            );

        if (result != ERROR_SUCCESS) {
            break;
        }

        if (
            type == REG_SZ
            && _stricmp(value_name, name) == 0
        ) {
            const char* fonts =
                "C:\\Windows\\Fonts\\";

            size_t len =
                strlen(fonts)
                + strlen((char*)value_data)
                + 1;

            char* path =
                malloc(len);

            if (!path) {
                RegCloseKey(key);
                return NULL;
            }

            strcpy(path, fonts);
            strcat(path, (char*)value_data);

            RegCloseKey(key);

            return path;
        }
    }

    RegCloseKey(key);

    return NULL;
}