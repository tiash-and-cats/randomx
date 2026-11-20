#ifndef uwnd__UWND_H
#define uwnd__UWND_H

#include <stdint.h>
#include <stddef.h>
#include "uwnd_core/stb/stb_truetype.h"
#include "uwnd_core/fps.h"

char* uwnd_find_font(const char* name);
struct uwnd_Font* uwnd_font_from_buf(unsigned char* buffer);
struct uwnd_Framebuffer* uwnd_load_image(const char* filepath);

// STRUCTS

typedef struct uwnd_Font {
    unsigned char* data;
    stbtt_fontinfo info;
    
    void (*delete)(struct uwnd_Font* self);
} uwnd_Font;

uwnd_Font* uwnd_new_Font(
    const char* path
);

void uwnd_Font_delete(
    uwnd_Font* font
);

typedef struct uwnd_Framebuffer {
    uint32_t* pixels;
    int width;
    int height;
    
    void (*putpixel)(struct uwnd_Framebuffer* self, int x, int y, uint32_t color);
    uint32_t (*getpixel)(struct uwnd_Framebuffer* self, int x, int y);
    void (*rect)(struct uwnd_Framebuffer* self, int x, int y, int w, int h, uint32_t color);
    void (*text)(
        struct uwnd_Framebuffer* self,

        uwnd_Font* font,

        int x,
        int y,

        int size,

        uint32_t color,

        const char* text
    );
    void (*delete)(struct uwnd_Framebuffer* self);
    void (*blit)(
        struct uwnd_Framebuffer* self,
        struct uwnd_Framebuffer* src,
        int dest_x,
        int dest_y
    );
    struct uwnd_Framebuffer* (*scale)(struct uwnd_Framebuffer* src, int target_w, int target_h);
} uwnd_Framebuffer;

void uwnd_Framebuffer_putpixel(uwnd_Framebuffer* self, int x, int y, uint32_t color);
uint32_t uwnd_Framebuffer_getpixel(uwnd_Framebuffer* self, int x, int y);
void uwnd_Framebuffer_rect(uwnd_Framebuffer* self, int x, int y, int w, int h, uint32_t color);
void uwnd_Framebuffer_delete(uwnd_Framebuffer* self);

void uwnd_Framebuffer_text(
    uwnd_Framebuffer* self,

    uwnd_Font* font,

    int x,
    int y,

    int size,

    uint32_t color,

    const char* text
);

void uwnd_Framebuffer_blit(
    uwnd_Framebuffer* self,
    uwnd_Framebuffer* src,
    int dest_x,
    int dest_y
);

#define uwnd_MAX_EVENTS 256

typedef enum {
    uwnd_EventType_NONE,

    uwnd_EventType_QUIT,

    uwnd_EventType_MOUSE_MOVE,

    uwnd_EventType_MOUSE_DOWN,
    uwnd_EventType_MOUSE_UP,

    uwnd_EventType_KEY_DOWN,
    uwnd_EventType_KEY_UP
} uwnd_EventType;

typedef struct uwnd_Event {
    uwnd_EventType type;

    int x;
    int y;

    int button;

    int key;
} uwnd_Event;

typedef struct uwnd_Window {
    void (*render)(struct uwnd_Window* self);
    void (*delete)(struct uwnd_Window* self);
    int (*poll)(struct uwnd_Window* self);

    uwnd_Framebuffer framebuffer;

    void* platform_data;

    uwnd_Event events[uwnd_MAX_EVENTS];
    int event_read;
    int event_write;
    
    void (*putpixel)(struct uwnd_Window* self, int x, int y, uint32_t color);
    uint32_t (*getpixel)(struct uwnd_Window* self, int x, int y);
    void (*rect)(struct uwnd_Window* self, int x, int y, int w, int h, uint32_t color);
    
    uwnd_Event (*popevent)(struct uwnd_Window* self);
} uwnd_Window;

uwnd_Window* uwnd_new_Window(
    int width,
    int height,
    const char* title
);

void uwnd_Window_render(uwnd_Window* self);
void uwnd_Window_delete(uwnd_Window* self);
int uwnd_Window_poll(uwnd_Window* self);

uwnd_Event uwnd_Window_popevent(uwnd_Window* self);

// Legacy aliases to framebuffer methods
void uwnd_Window_putpixel(uwnd_Window* self, int x, int y, uint32_t color);
uint32_t uwnd_Window_getpixel(uwnd_Window* self, int x, int y);
void uwnd_Window_rect(uwnd_Window* self, int x, int y, int w, int h, uint32_t color);

/* INTERNAL METHODS */

static void uwnd__push_Event(
    uwnd_Window* win,
    uwnd_Event evt
);

#endif /* #ifndef uwnd__UWND_H */