#include <stdlib.h>
#include <stdbool.h>
#include "uwnd.h"
#include "./font.c"

#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "uwnd_core/stb/stb_image_resize2.h"

bool uwnd__fb_init_core(uwnd_Framebuffer* fb, int width, int height);

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

void uwnd_Framebuffer_delete(uwnd_Framebuffer* fb) {
    // PLEASE do not call this on win->fb! It will go kaboom because:
    //    1. win->fb is statically allocated
    //    2. win->fb is required for.... uh, rendering
    if (!fb) return;
    free(fb->pixels);
    free(fb);
}

void uwnd_Framebuffer_blit(
    uwnd_Framebuffer* self,
    uwnd_Framebuffer* src,
    int dest_x,
    int dest_y
) {
    if (!self || !src) return;

    int src_w = src->width;
    int src_h = src->height;
    int dest_w = self->width;
    int dest_h = self->height;

    // Calculate clipping boundaries
    int start_x = (dest_x < 0) ? -dest_x : 0;
    int start_y = (dest_y < 0) ? -dest_y : 0;
    
    int end_x = src_w;
    if (dest_x + src_w > dest_w) {
        end_x = dest_w - dest_x;
    }

    int end_y = src_h;
    if (dest_y + src_h > dest_h) {
        end_y = dest_h - dest_y;
    }

    if (start_x >= end_x || start_y >= end_y) {
        return; // Completely clipped out
    }

    // Row-by-row copy loop
    for (int y = start_y; y < end_y; y++) {
        uint32_t* dest_row = &self->pixels[(dest_y + y) * dest_w + (dest_x + start_x)];
        uint32_t* src_row  = &src->pixels[y * src_w + start_x];
        
        int width_to_copy = end_x - start_x;
        
        for (int x = 0; x < width_to_copy; x++) {
            uint32_t pixel = src_row[x];
            
            uint32_t a = (pixel >> 24) & 0xFF;
            if (a > 0) {
                dest_row[x] = pixel;
            }
        }
    }
}

uwnd_Framebuffer* uwnd_Framebuffer_scale(uwnd_Framebuffer* src, int target_w, int target_h) {
    if (!src || target_w <= 0 || target_h <= 0) return NULL;

    uwnd_Framebuffer* dst = malloc(sizeof(uwnd_Framebuffer));
    if (!dst) return NULL;

    if (!uwnd__fb_init_core(dst, target_w, target_h)) {
        free(dst);
        return NULL;
    }

    // stb_image_resize2 handles the heavy lifting with high quality filtering
    stbir_resize_uint8_linear(
        (const unsigned char*)src->pixels, src->width, src->height, 0,
        (unsigned char*)dst->pixels, target_w, target_h, 0,
        STBIR_RGBA
    );

    return dst;
}

bool uwnd__fb_init_core(uwnd_Framebuffer* fb, int width, int height) {
    fb->width = width;
    fb->height = height;
    fb->pixels = calloc(width * height, sizeof(uint32_t));

    if (!fb->pixels) {
        return false;
    }

    fb->putpixel = uwnd_Framebuffer_putpixel;
    fb->getpixel = uwnd_Framebuffer_getpixel;
    fb->rect     = uwnd_Framebuffer_rect;
    fb->text     = uwnd_Framebuffer_text;
    fb->delete   = uwnd_Framebuffer_delete;
    fb->blit     = uwnd_Framebuffer_blit;
    fb->scale    = uwnd_Framebuffer_scale;
    
    return true;
}

// A lazy wrapper so I don't have to change the existing platform backends!
bool uwnd__fb_init(uwnd_Window* win, int width, int height) {
    uwnd__fb_init_core(&win->framebuffer, width, height);    
    return true;
}