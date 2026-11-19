#include <stdlib.h>
#include <stdbool.h>
#include "../uwnd.h"
#include "./font.c"

void uwnd_Framebuffer_putpixel(uwnd_Framebuffer* self, int x, int y, uint32_t color) {
    if (x >= 0 && x < self->width && y >= 0 && y < self->height) {
        self->pixels[y * self->width + x] = color;
    }
}

uint32_t uwnd_Framebuffer_getpixel(uwnd_Framebuffer* self, int x, int y) {
    if (x >= 0 && x < self->width && y >= 0 && y < self->height) {
        return self->pixels[y * self->width + x];
    }
    return 0;
}

void uwnd_Framebuffer_rect(uwnd_Framebuffer* self, int x, int y, int w, int h, uint32_t color) {
    int fb_width = self->width;
    int fb_height = self->height;

    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > fb_width)  w = fb_width - x;
    if (y + h > fb_height) h = fb_height - y;

    if (w <= 0 || h <= 0) return;

    for (int i = 0; i < h; i++) {
        uint32_t* row = &self->pixels[(y + i) * fb_width + x];
        
        for (int j = 0; j < w; j++) {
            row[j] = color;
        }
    }
}

bool uwnd__fb_init(uwnd_Window* win, int width, int height) {
    win->framebuffer.width =
        width;

    win->framebuffer.height =
        height;

    win->framebuffer.pixels =
        calloc(
            width*  height,
            sizeof(uint32_t)
        );

    if (!win->framebuffer.pixels) {
        return false;
    }

    win->framebuffer.putpixel = uwnd_Framebuffer_putpixel;
    win->framebuffer.getpixel = uwnd_Framebuffer_getpixel;
    win->framebuffer.rect     = uwnd_Framebuffer_rect;
    win->framebuffer.text     = uwnd_Framebuffer_text;
    
    return true;
}