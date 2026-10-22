#ifndef TYPES_H
#define TYPES_H

#ifdef USE_SINGLE_PRECISION
typedef float scalar_t;
#else
typedef double scalar_t;
#endif

typedef struct {
    scalar_t x;
    scalar_t y;
    scalar_t z;
} Vec3;

#endif
