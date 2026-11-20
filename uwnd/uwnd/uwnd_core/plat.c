#include "uwnd.h"
#include <stdbool.h>

bool uwnd__platform_init_Window(
    uwnd_Window* win,
    int width,
    int height,
    const char* title
);

void uwnd__platform_render(
    uwnd_Window* win
);

void uwnd__platform_delete(
    uwnd_Window* win
);

int uwnd__platform_poll(
    uwnd_Window* win
);

char* uwnd__platform_find_Font(const char* name);

#ifdef _WIN32
    #include "./plat/win32.c"
#elif defined(__linux__)
    #include "./plat/x11.c"
#elif defined(__EMSCRIPTEN__)
    #include "./plat/emscripten.c"
#endif