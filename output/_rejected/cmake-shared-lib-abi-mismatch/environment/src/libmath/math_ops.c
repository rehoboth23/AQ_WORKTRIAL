#include "math_ops.h"
#include <math.h>

scalar_t vec3_dot(const Vec3 *a, const Vec3 *b) {
    return a->x * b->x + a->y * b->y + a->z * b->z;
}

void vec3_normalize(const Vec3 *v, Vec3 *out) {
    scalar_t len = vec3_length(v);
    out->x = v->x / len;
    out->y = v->y / len;
    out->z = v->z / len;
}

void vec3_cross(const Vec3 *a, const Vec3 *b, Vec3 *out) {
    out->x = a->y * b->z - a->z * b->y;
    out->y = a->z * b->x - a->x * b->z;
    out->z = a->x * b->y - a->y * b->x;
}

scalar_t vec3_length(const Vec3 *v) {
    return sqrt(vec3_dot(v, v));
}

size_t math_get_vec3_size(void) {
    return sizeof(Vec3);
}
