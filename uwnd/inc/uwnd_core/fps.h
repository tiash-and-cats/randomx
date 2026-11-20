#ifndef uwnd__UWND_CORE_FPS_H
#define uwnd__UWND_CORE_FPS_H

#include <time.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <time.h>
#endif

#ifdef _WIN32
    #define uwnd_FPS__SLEEP(ms) Sleep(ms)
#else
    #define uwnd_FPS__SLEEP(ms) usleep((ms) * 1000)
#endif

#ifndef uwnd_FPS_TARGET
    #define uwnd_FPS_TARGET 60
#endif

#define uwnd_FPS_END do { \
    uwnd_FPS__GET_ELAPSED_MS; \
    double uwnd_FPS__target_ms = 1000.0 / (double)(uwnd_FPS_TARGET); \
    if (uwnd_FPS__elapsed_ms < uwnd_FPS__target_ms) { \
        int uwnd_FPS__sleep_time = (int)(uwnd_FPS__target_ms - uwnd_FPS__elapsed_ms); \
        if (uwnd_FPS__sleep_time > 1) { \
            uwnd_FPS__SLEEP(uwnd_FPS__sleep_time - 1); /* leave a 1ms buffer to prevent oversleeping */ \
        } \
    } \
} while (0)

#ifdef _WIN32
    #define uwnd_FPS_INIT \
        LARGE_INTEGER uwnd_FPS__freq, uwnd_FPS__start, uwnd_FPS__end; \
        QueryPerformanceFrequency(&uwnd_FPS__freq)
#else
    #define uwnd_FPS_INIT \
        struct timespec uwnd_FPS__start, uwnd_FPS__end
#endif

#ifdef _WIN32
    #define uwnd_FPS_START \
        QueryPerformanceCounter(&uwnd_FPS__start)
#else
    #define uwnd_FPS_START \
        clock_gettime(CLOCK_MONOTONIC, &uwnd_FPS__start)
#endif

#ifdef _WIN32
    #define uwnd_FPS__GET_ELAPSED_MS \
        QueryPerformanceCounter(&uwnd_FPS__end); \
        double uwnd_FPS__elapsed_ms = (double)(uwnd_FPS__end.QuadPart - uwnd_FPS__start.QuadPart) * 1000.0 / uwnd_FPS__freq.QuadPart
#else
    #define uwnd_FPS__GET_ELAPSED_MS \
        clock_gettime(CLOCK_MONOTONIC, &uwnd_FPS__end); \
        double uwnd_FPS__elapsed_ms = (uwnd_FPS__end.tv_sec - uwnd_FPS__start.tv_sec) * 1000.0 + (uwnd_FPS__end.tv_nsec - uwnd_FPS__start.tv_nsec) / 1000000.0
#endif

#endif /* #ifndef uwnd__UWND_CORE_FPS_H */