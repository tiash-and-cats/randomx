#include "../uwnd.h"

#define STB_TRUETYPE_IMPLEMENTATION
#include "./stb/stb_truetype.h"

#include <stdio.h>
#include <stdlib.h>

uwnd_Font* uwnd_new_Font(const char* path) {
    FILE* fp = fopen(path, "rb");

    if (!fp) {
        return NULL;
    }

    fseek(fp, 0, SEEK_END);

    long size = ftell(fp);

    rewind(fp);

    unsigned char* buffer = malloc(size);

    if (!buffer) {
        fclose(fp);
        return NULL;
    }

    fread(
        buffer,
        1,
        size,
        fp
    );

    fclose(fp);

    uwnd_Font* font = malloc(sizeof(uwnd_Font));

    if (!font) {
        free(buffer);
        return NULL;
    }

    if (!stbtt_InitFont(&font->info, buffer, 0)) {
        free(buffer);
        free(font);

        return NULL;
    }

    font->data = buffer;
    font->delete = uwnd_Font_delete;

    return font;
}

char* uwnd_find_font(const char* name) {
    return uwnd__platform_find_Font(name);
}

void uwnd_Font_delete(uwnd_Font* font) {
    if (!font) return;

    free(font->data);
    free(font);
}

static int uwnd__utf8_next(const char** text) {
    const unsigned char* s =
        (const unsigned char*)*text;

    int codepoint;

    if (!*s) {
        return 0;
    }

    if ((s[0] & 0x80) == 0) {
        codepoint = s[0];
        *text += 1;
        return codepoint;
    }

    if ((s[0] & 0xE0) == 0xC0) {
        codepoint =
            ((s[0] & 0x1F) << 6)
            | (s[1] & 0x3F);

        *text += 2;
        return codepoint;
    }

    if ((s[0] & 0xF0) == 0xE0) {
        codepoint =
            ((s[0] & 0x0F) << 12)
            | ((s[1] & 0x3F) << 6)
            | (s[2] & 0x3F);

        *text += 3;
        return codepoint;
    }

    if ((s[0] & 0xF8) == 0xF0) {
        codepoint =
            ((s[0] & 0x07) << 18)
            | ((s[1] & 0x3F) << 12)
            | ((s[2] & 0x3F) << 6)
            | (s[3] & 0x3F);

        *text += 4;
        return codepoint;
    }

    *text += 1;
    return 0xFFFD;
}

void uwnd_Framebuffer_text(
    uwnd_Framebuffer* self,

    uwnd_Font* font,

    int x,
    int y,

    int size,

    uint32_t color,

    const char* text
) {
    int ascent;

    float scale =
        stbtt_ScaleForPixelHeight(
            &font->info,
            (float)size
        );

    stbtt_GetFontVMetrics(
        &font->info,
        &ascent,
        NULL,
        NULL
    );

    int baseline =
        y + (int)(
            ascent * scale
        );

    float xpos =
        (float)x;

    while (*text) {
        int advance, lsb;
        int x0, y0, x1, y1;

        int codepoint =
            uwnd__utf8_next(&text);

        float x_shift =
            xpos - (float)(int)xpos;

        stbtt_GetCodepointHMetrics(&font->info, codepoint, &advance, &lsb);

        stbtt_GetCodepointBitmapBoxSubpixel(
            &font->info, codepoint,
            scale, scale,
            x_shift, 0,
            &x0, &y0,
            &x1, &y1
        );

        int w = x1 - x0;
        int h = y1 - y0;

        unsigned char* bitmap =
            malloc(w * h);

        if (!bitmap) {
            return;
        }

        stbtt_MakeCodepointBitmapSubpixel(
            &font->info,
            bitmap,
            w, h,
            w,
            scale, scale,
            x_shift, 0,
            codepoint
        );

        for (int yy = 0; yy < h; yy++) {
            for (int xx = 0; xx < w; xx++) {
                unsigned char a = bitmap[yy * w + xx];

                if (!a) continue;

                int px = (int)xpos + x0 + xx;

                int py = baseline + y0 + yy;

                if (px < 0 || px >= self->width || py < 0 || py >= self->height) {
                    continue;
                }

                uint8_t r = ((color >> 16) & 255) * a / 255;
                uint8_t g = ((color >> 8) & 255) * a / 255;
                uint8_t b = (color & 255) * a / 255;

                self->pixels[py * self->width + px] =
                    (r << 16) | (g << 8) | b;
            }
        }

        free(bitmap);

        xpos += advance * scale;

        const char* next_text = text;

        int next = *next_text ? uwnd__utf8_next(&next_text) : 0;

        if (next) {
            xpos += scale *
                stbtt_GetCodepointKernAdvance(
                    &font->info,
                    codepoint,
                    next
                );
        }
    }
}