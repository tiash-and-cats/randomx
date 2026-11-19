#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <fontconfig/fontconfig.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#include "../../uwnd.h"
#include "../fb.c"

typedef struct uwnd__PlatData {
    Display* display;
    Window window;
    GC gc;

    Atom wm_delete_window;
} uwnd__PlatData;

bool uwnd__platform_init_Window(
    uwnd_Window* win,
    int width,
    int height,
    const char* title
) {
    uwnd__PlatData* plat =
        calloc(
            1,
            sizeof(uwnd__PlatData)
        );

    if (!plat) {
        return false;
    }

    plat->display =
        XOpenDisplay(NULL);

    if (!plat->display) {
        free(plat);
        return false;
    }

    int screen =
        DefaultScreen(
            plat->display
        );

    plat->window =
        XCreateSimpleWindow(
            plat->display,

            RootWindow(
                plat->display,
                screen
            ),

            0,
            0,

            width,
            height,

            1,

            BlackPixel(
                plat->display,
                screen
            ),

            WhitePixel(
                plat->display,
                screen
            )
        );

    XStoreName(
        plat->display,
        plat->window,
        title
    );

    XSelectInput(
        plat->display,
        plat->window,

        ExposureMask
        | StructureNotifyMask
        | PointerMotionMask
        | ButtonPressMask
        | ButtonReleaseMask
        | KeyPressMask
        | KeyReleaseMask
    );

    plat->wm_delete_window =
        XInternAtom(
            plat->display,
            "WM_DELETE_WINDOW",
            False
        );

    XSetWMProtocols(
        plat->display,
        plat->window,

        &plat->wm_delete_window,
        1
    );

    plat->gc =
        DefaultGC(
            plat->display,
            screen
        );

    if (!uwnd__fb_init(win, width, height)) {
        XDestroyWindow(
            plat->display,
            plat->window
        );

        XCloseDisplay(
            plat->display
        );

        free(plat);

        return false;
    }

    win->platform_data =
        plat;

    XMapWindow(
        plat->display,
        plat->window
    );

    XFlush(
        plat->display
    );

    return true;
}

void uwnd__platform_render(
    uwnd_Window* win
) {
    uwnd__PlatData* plat =
        (uwnd__PlatData*)
        win->platform_data;

    int screen =
        DefaultScreen(
            plat->display
        );

    XImage* image =
        XCreateImage(
            plat->display,

            DefaultVisual(
                plat->display,
                screen
            ),

            DefaultDepth(
                plat->display,
                screen
            ),

            ZPixmap,

            0,

            (char*)
            win->framebuffer.pixels,

            win->framebuffer.width,
            win->framebuffer.height,

            32,

            0
        );

    XPutImage(
        plat->display,
        plat->window,
        plat->gc,

        image,

        0,
        0,

        0,
        0,

        win->framebuffer.width,
        win->framebuffer.height
    );

    image->data = NULL;

    XDestroyImage(
        image
    );

    XFlush(
        plat->display
    );
}

void uwnd__platform_delete(
    uwnd_Window* win
) {
    uwnd__PlatData* plat =
        (uwnd__PlatData*)
        win->platform_data;

    if (!plat) {
        return;
    }

    XDestroyWindow(
        plat->display,
        plat->window
    );

    XCloseDisplay(
        plat->display
    );

    free(plat);
}

int uwnd__platform_poll(
    uwnd_Window* win
) {
    uwnd__PlatData* plat =
        (uwnd__PlatData*)
        win->platform_data;

    while (
        XPending(
            plat->display
        )
    ) {
        XEvent xevt;

        XNextEvent(
            plat->display,
            &xevt
        );

        switch (xevt.type) {
            case MotionNotify: {
                uwnd_Event evt = {
                    .type =
                        uwnd_EventType_MOUSE_MOVE,

                    .x =
                        xevt.xmotion.x,

                    .y =
                        xevt.xmotion.y
                };

                uwnd__push_Event(
                    win,
                    evt
                );

                break;
            }

            case ButtonPress: {
                uwnd_Event evt = {
                    .type =
                        uwnd_EventType_MOUSE_DOWN,

                    .button =
                        xevt.xbutton.button,

                    .x =
                        xevt.xbutton.x,

                    .y =
                        xevt.xbutton.y
                };

                uwnd__push_Event(
                    win,
                    evt
                );

                break;
            }

            case ButtonRelease: {
                uwnd_Event evt = {
                    .type =
                        uwnd_EventType_MOUSE_UP,

                    .button =
                        xevt.xbutton.button,

                    .x =
                        xevt.xbutton.x,

                    .y =
                        xevt.xbutton.y
                };

                uwnd__push_Event(
                    win,
                    evt
                );

                break;
            }

            case KeyPress: {
                uwnd_Event evt = {
                    .type =
                        uwnd_EventType_KEY_DOWN,

                    .key =
                        xevt.xkey.keycode
                };

                uwnd__push_Event(
                    win,
                    evt
                );

                break;
            }

            case KeyRelease: {
                uwnd_Event evt = {
                    .type =
                        uwnd_EventType_KEY_UP,

                    .key =
                        xevt.xkey.keycode
                };

                uwnd__push_Event(
                    win,
                    evt
                );

                break;
            }

            case ConfigureNotify: {
                int new_width = xevt.xconfigure.width;
                int new_height = xevt.xconfigure.height;

                // Only reallocate if dimensions actually changed and are valid
                if (new_width > 0 && new_height > 0 &&
                    (new_width != win->framebuffer.width || new_height != win->framebuffer.height)) {

                    uint32_t* new_pixels = realloc(
                        win->framebuffer.pixels,
                        new_width * new_height * sizeof(uint32_t)
                    );

                    if (new_pixels) {
                        win->framebuffer.pixels = new_pixels;
                        win->framebuffer.width = new_width;
                        win->framebuffer.height = new_height;
                    }
                }

                break;
            }

            case ClientMessage: {
                if (
                    (Atom)
                    xevt.xclient.data.l[0]
                    ==
                    plat->wm_delete_window
                ) {
                    uwnd_Event evt = {
                        .type =
                            uwnd_EventType_QUIT
                    };

                    uwnd__push_Event(
                        win,
                        evt
                    );

                    return 0;
                }

                break;
            }
        }
    }

    return 1;
}

char* uwnd__platform_find_Font(const char* name) {
    if (!FcInit()) {
        return NULL;
    }

    // Parse the font name query (e.g., "Arial" or "DejaVu Sans")
    FcPattern* pat = FcNameParse((const FcChar8*)name);
    if (!pat) {
        FcFini();
        return NULL;
    }

    FcConfigSubstitute(0, pat, FcMatchPattern);
    FcDefaultSubstitute(pat);

    FcResult result;
    FcPattern* font = FcFontMatch(0, pat, &result);
    FcPatternDestroy(pat);

    if (!font) {
        FcFini();
        return NULL;
    }

    // Extract the file path property from the matched font pattern
    FcChar8* file = NULL;
    char* path = NULL;

    if (FcPatternGetString(font, FC_FILE, 0, &file) == FcResultMatch) {
        path = strdup((char*)file);
    }

    FcPatternDestroy(font);
    FcFini();

    return path; // Caller is responsible for free()ing this string
}