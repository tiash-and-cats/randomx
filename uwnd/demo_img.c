#define uwnd_FPS_TARGET 120
#include "uwnd.h"
#include <stdio.h>
#include <math.h>

#define FRAME_PINGPONG(min, max, frame, period) \
    ((min) + ((max) - (min)) * (1.0f - fabsf(2.0f * (((float)(frame) / (period)) - floorf(((float)(frame) / (period)) + 0.5f)))))

int main(void) {
    uwnd_Window* win = uwnd_new_Window(800, 600, "µWnd Image Demo");
    if (!win) {
        printf("Failed to create window!\n");
        return 1;
    }

    char* path = uwnd_find_font("Verdana");
    uwnd_Font* font = uwnd_new_Font(path);
    free(path);

    uwnd_Framebuffer* img_raw = uwnd_load_image("Original_Utah_Teapot.jpg");
    if (!img_raw) {
        printf("Warning: Failed to load 'Original_Utah_Teapot.jpg'. Running with a blank image slot.\n");
    }
    uwnd_Framebuffer* img = img_raw->scale(img_raw, 460, 345);
    img->text(img, font, 20, 20, 24, 0xFF808000, "µWnd Image Blitting Demo");
    for (size_t i = 0; i < (img->width * img->height) / 2; i++) {
        img->pixels[i] = 0x00FFFFFF - img->pixels[i];
    }
    img->text(img, font, 20, 300, 24, 0xFF808000, "µWnd Image Blitting Demo");

    if (!font) {
        win->delete(win);
        return 1;
    }
    
    int frame = 0;
    
    uwnd_FPS_INIT;
    while (win->poll(win)) {
        uwnd_FPS_START;
        
        // Handle input events if needed
        uwnd_Event evt;
        while ((evt = win->popevent(win)).type != uwnd_EventType_NONE) {
            if (evt.type == uwnd_EventType_KEY_DOWN && evt.key == 0x1B) { // \e
                // Close on ESC
                goto cleanup;
            }
        }

        // Clear the window framebuffer to a dark gray background
        win->framebuffer.rect(&win->framebuffer, 0, 0, win->framebuffer.width, win->framebuffer.height, 0xFF222222);

        // Draw text or shapes
        win->framebuffer.text(&win->framebuffer, font, 20, 20, 24, 0xFFFFFFFF, "µWnd Image Blitting Demo");

        // Blit the loaded image onto the window framebuffer if available
        if (img) {
            win->framebuffer.blit(&win->framebuffer, img, 150, FRAME_PINGPONG(50, 100, frame, 240));
        }

        // Render the frame to the screen
        win->render(win);
        
        frame++;
        uwnd_FPS_END;
    }

cleanup:
    if (img) {
        img->delete(img);
    }
    win->delete(win);

    return 0;
}