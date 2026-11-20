#define uwnd_FPS_TARGET 120
#include "uwnd.h"
#include <math.h>

int main(void) {
    uwnd_Window* win =
        uwnd_new_Window(
            800,
            600,
            "µWnd"
        );
    
    if (!win) return 1;

    float t = 0.0f;
    
    uwnd_FPS_INIT;
    while (win->poll(win)) {
        uwnd_FPS_START;
        
        for (int y = 0;
             y < win->framebuffer.height;
             y++) {
            for (int x = 0;
                 x < win->framebuffer.width;
                 x++) {
                float fx = (float)x;
                float fy = (float)y;

                uint8_t r =
                    (uint8_t)(
                        127 +
                        127 * sinf(
                            fx * 0.01f +
                            t
                        )
                    );

                uint8_t g =
                    (uint8_t)(
                        127 +
                        127 * sinf(
                            fy * 0.01f +
                            t * 1.3f
                        )
                    );

                uint8_t b =
                    (uint8_t)(
                        127 +
                        127 * sinf(
                            (fx + fy) * 0.01f +
                            t * 0.7f
                        )
                    );

                win->framebuffer.putpixel(&win->framebuffer, x, y,
                    b | (g << 8) | (r << 16) | 0xFF000000
                );
            }
        }

        t += 0.02f;
        win->render(win);
        
        uwnd_FPS_END;
    }

    win->delete(win);

    return 0;
}