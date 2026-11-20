#include "uwnd.h"

#include "uwnd_core/img.c"
#include "uwnd_core/plat.c"

uwnd_Window* uwnd_new_Window(
    int width,
    int height,
    const char* title
) {
    uwnd_Window* win =
        calloc(
            1,
            sizeof(uwnd_Window)
        );

    if (!win) {
        return NULL;
    }

    win->delete   = uwnd_Window_delete;
    win->render   = uwnd_Window_render;
    win->poll     = uwnd_Window_poll;
    win->putpixel = uwnd_Window_putpixel;
    win->getpixel = uwnd_Window_getpixel;
    win->rect     = uwnd_Window_rect;
    win->popevent = uwnd_Window_popevent;

    if (!uwnd__platform_init_Window(
        win,
        width,
        height,
        title
    )) {
        free(win);
        return NULL;
    }
    
    return win;
}

void uwnd_Window_render(
    uwnd_Window* win
) {
    uwnd__platform_render(win);
}

void uwnd_Window_delete(
    uwnd_Window* win
) {
    uwnd__platform_delete(win);
    free(win);
}

int uwnd_Window_poll(uwnd_Window* win) {
    return uwnd__platform_poll(win);
}

void uwnd_Window_putpixel(uwnd_Window* self, int x, int y, uint32_t color) { uwnd_Framebuffer_putpixel(&self->framebuffer, x, y, color); }
uint32_t uwnd_Window_getpixel(uwnd_Window* self, int x, int y) { return uwnd_Framebuffer_getpixel(&self->framebuffer, x, y); }
void uwnd_Window_rect(uwnd_Window* self, int x, int y, int w, int h, uint32_t color) { uwnd_Framebuffer_rect(&self->framebuffer, x, y, w, h, color); }

static void uwnd__push_Event(
    uwnd_Window* win,
    uwnd_Event evt
) {
    int next =
        (win->event_write + 1)
        % uwnd_MAX_EVENTS;

    if (next == win->event_read) {
        return;
    }

    win->events[
        win->event_write
    ] = evt;

    win->event_write = next;
}

uwnd_Event uwnd_Window_popevent(uwnd_Window* win) {
    if (win->event_read == win->event_write) {
        return (uwnd_Event) {
            .type = uwnd_EventType_NONE,
            .x = 0, .y = 0,
            .button = 0, .key = 0
        };
    }
    
    uwnd_Event evt = win->events[win->event_read];
    win->event_read = (win->event_read + 1) % uwnd_MAX_EVENTS;
    
    return evt;
}