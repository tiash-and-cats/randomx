#include "uwnd.h"
#include <stdbool.h>
#include <stdint.h>

int main(void) {
    uwnd_Window* win =
        uwnd_new_Window(
            800,
            600,
            "µWnd - Drag Square Demo"
        );

    if (!win) return 1;

    // Square properties
    int sq_x = 350;
    int sq_y = 250;
    int sq_size = 100;

    bool is_dragging = false;
    int drag_offset_x = 0;
    int drag_offset_y = 0;

    while (win->poll(win)) {
        // get events
        uwnd_Event evt;
        while ((evt = win->popevent(win)).type != uwnd_EventType_NONE) {
            if (evt.type == uwnd_EventType_MOUSE_DOWN) {
                if (evt.button == 1) { // Left click
                    // Check if click is inside the square
                    if (evt.x >= sq_x && evt.x <= sq_x + sq_size &&
                        evt.y >= sq_y && evt.y <= sq_y + sq_size) {
                        is_dragging = true;
                        drag_offset_x = evt.x - sq_x;
                        drag_offset_y = evt.y - sq_y;
                    }
                }
            } else if (evt.type == uwnd_EventType_MOUSE_UP) {
                if (evt.button == 1) {
                    is_dragging = false;
                }
            } else if (evt.type == uwnd_EventType_MOUSE_MOVE) {
                if (is_dragging) {
                    sq_x = evt.x - drag_offset_x;
                    sq_y = evt.y - drag_offset_y;
                }
            }
        }

        win->framebuffer.rect(
            &win->framebuffer,
            0,
            0,
            win->framebuffer.width,
            win->framebuffer.height,
            0x1E1E1E
        );

        uint32_t sq_color = is_dragging ? 0x00FF9800 : 0x00FF5722;        
        win->framebuffer.rect(&win->framebuffer, sq_x, sq_y, sq_size, sq_size, sq_color);

        win->render(win);
    }

    win->delete(win);
    return 0;
}