#include "./fb.c"

#define STB_IMAGE_IMPLEMENTATION
#include "./stb/stb_image.h"

uwnd_Framebuffer* uwnd_load_image(const char* filepath) {
    int width, height, channels;
    
    // Force 4 channels (RGBA)
    unsigned char* data = stbi_load(filepath, &width, &height, &channels, 4);
    if (!data) {
        return NULL;
    }

    // Allocate the framebuffer struct itself
    uwnd_Framebuffer* fb = malloc(sizeof(uwnd_Framebuffer));
    if (!fb) {
        stbi_image_free(data);
        return NULL;
    }

    // Initialize core fields, allocate pixel buffer, and set up function pointers
    if (!uwnd__fb_init_core(fb, width, height)) {
        free(fb);
        stbi_image_free(data);
        return NULL;
    }

    // Copy and pack pixels into the framebuffer's pixel buffer
    for (int i = 0; i < width * height; i++) {
        unsigned char r = data[i * 4 + 0];
        unsigned char g = data[i * 4 + 1];
        unsigned char b = data[i * 4 + 2];
        unsigned char a = data[i * 4 + 3];

        fb->pixels[i] = ((uint32_t)a << 24) | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
    }

    stbi_image_free(data);
    return fb;
}