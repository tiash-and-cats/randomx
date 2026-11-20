#include <emscripten.h>
#include <emscripten/html5.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

typedef struct uwnd__PlatData {
    int width;
    int height;
} uwnd__PlatData;

// Forward reference for event pushing from JS bindings
static uwnd_Window* g_active_win = NULL;

static EM_BOOL uwnd__js_mouse_callback(int eventType, const EmscriptenMouseEvent* e, void* userData) {
    uwnd_Window* win = (uwnd_Window*)userData;
    if (!win) return false;

    uwnd_Event evt = {0};
    
    // Convert client coordinates to canvas-relative coordinates
    double canvas_x, canvas_y;
    emscripten_get_mouse_position_pixel(e, &canvas_x, &canvas_y); // Or use e->targetX/Y

    if (eventType == EMSCRIPTEN_EVENT_MOUSEMOVE) {
        evt.type = uwnd_EventType_MOUSE_MOVE;
        evt.x = (int)e->targetX;
        evt.y = (int)e->targetY;
    } else if (eventType == EMSCRIPTEN_EVENT_MOUSEDOWN) {
        evt.type = uwnd_EventType_MOUSE_DOWN;
        evt.button = e->button + 1; // 1: Left, 2: Middle, 3: Right
        evt.x = (int)e->targetX;
        evt.y = (int)e->targetY;
    } else if (eventType == EMSCRIPTEN_EVENT_MOUSEUP) {
        evt.type = uwnd_EventType_MOUSE_UP;
        evt.button = e->button + 1;
        evt.x = (int)e->targetX;
        evt.y = (int)e->targetY;
    }

    uwnd__push_Event(win, evt);
    return true;
}

static EM_BOOL uwnd__js_key_callback(int eventType, const EmscriptenKeyboardEvent* e, void* userData) {
    uwnd_Window* win = (uwnd_Window*)userData;
    if (!win) return false;

    uwnd_Event evt = {0};
    if (eventType == EMSCRIPTEN_EVENT_KEYDOWN) {
        evt.type = uwnd_EventType_KEY_DOWN;
        evt.key = e->keyCode;
    } else if (eventType == EMSCRIPTEN_EVENT_KEYUP) {
        evt.type = uwnd_EventType_KEY_UP;
        evt.key = e->keyCode;
    }

    uwnd__push_Event(win, evt);
    
    // Prevent default browser scrolling/behavior for arrow keys, space, etc.
    return true;
}

bool uwnd__platform_init_Window(
    uwnd_Window* win,
    int width,
    int height,
    const char* title
) {
    uwnd__PlatData* plat = calloc(1, sizeof(uwnd__PlatData));
    if (!plat) {
        return false;
    }

    plat->width = width;
    plat->height = height;
    g_active_win = win;

    // Set up canvas in the DOM via JavaScript
    EM_ASM({
        let canvas = document.getElementById('uwnd-canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = 'uwnd-canvas';
            canvas.style.display = 'block';
            canvas.style.margin = '0 auto';
            canvas.style.background = '#000';
            document.body.appendChild(canvas);
        }
        canvas.width = $0;
        canvas.height = $1;
        document.title = UTF8ToString($2);
    }, width, height, title);

    if (!uwnd__fb_init(win, width, height)) {
        free(plat);
        return false;
    }

    win->platform_data = plat;

    // Register Emscripten HTML5 DOM event listeners
    emscripten_set_mousemove_callback("#uwnd-canvas", win, true, uwnd__js_mouse_callback);
    emscripten_set_mousedown_callback("#uwnd-canvas", win, true, uwnd__js_mouse_callback);
    emscripten_set_mouseup_callback("#uwnd-canvas", win, true, uwnd__js_mouse_callback);
    
    emscripten_set_keydown_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, win, true, uwnd__js_key_callback);
    emscripten_set_keyup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, win, true, uwnd__js_key_callback);

    return true;
}

void uwnd__platform_render(
    uwnd_Window* win
) {
    if (!win) return;
    void* pixels = win->framebuffer.pixels;
    int width = win->framebuffer.width;
    int height = win->framebuffer.height;

    // Zero-copy transfer from Wasm memory heap to HTML5 Canvas 2D Context
    EM_ASM({
        const ptr = $0;
        const width = $1;
        const height = $2;

        const canvas = document.getElementById('uwnd-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        const imgDataArray = new Uint8ClampedArray(HEAPU8.buffer, ptr, width * height * 4);
        const imageData = new ImageData(imgDataArray, width, height);
        
        ctx.putImageData(imageData, 0, 0);
    }, pixels, width, height);
}

void uwnd__platform_delete(
    uwnd_Window* win
) {
    if (!win) return;
    uwnd__PlatData* plat = (uwnd__PlatData*)win->platform_data;
    
    if (win->framebuffer.pixels) {
        free(win->framebuffer.pixels);
        win->framebuffer.pixels = NULL;
    }
    
    free(plat);
    g_active_win = NULL;
}

int uwnd__platform_poll(
    uwnd_Window* win
) {
    // In Emscripten, frame pacing is handled by emscripten_set_main_loop.
    // Returning 1 keeps the event loop active.
    return 1;
}

char* uwnd__platform_find_Font(const char* name) {
    // Fontconfig is not available out-of-the-box in WASM without heavy porting.
    // Return NULL so µWnd falls back gracefully to default built-in handling.
    return NULL;
}