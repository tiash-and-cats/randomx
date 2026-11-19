#include "uwnd.h"
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    uwnd_Window* win =
        uwnd_new_Window(
            800,
            600,
            "µWnd Font Demo"
        );

    if (!win) {
        return 1;
    }

    char* path = uwnd_find_font("Verdana");
    uwnd_Font* font = uwnd_new_Font(path);
    free(path);

    if (!font) {
        win->delete(win);
        return 1;
    }

    while (win->poll(win)) {
        win->framebuffer.rect(
            &win->framebuffer,
            0,
            0,
            win->framebuffer.width,
            win->framebuffer.height,
            0x202020
        );

        win->framebuffer.text(
            &win->framebuffer,
            font,

            20,
            20,

            24,

            0xFFFFFF,

            "Hello, µWnd!"
        );

        win->framebuffer.text(
            &win->framebuffer,
            font,

            20,
            60,

            48,

            0xCC00F3,

            "Verdana 48px"
        );

        win->framebuffer.text(
            &win->framebuffer,
            font,

            20,
            140,

            16,

            0x00FF00,

            "The quick brown fox jumps over the lazy dog."
        );

        win->render(win);
    }

    font->delete(font);
    win->delete(win);

    return 0;
}