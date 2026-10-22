#ifndef MATH_OPS_H
#define MATH_OPS_H

#include "types.h"
#include <stddef.h>

scalar_t vec3_dot(const Vec3 *a, const Vec3 *b);
void vec3_normalize(const Vec3 *v, Vec3 *out);
void vec3_cross(const Vec3 *a, const Vec3 *b, Vec3 *out);
scalar_t vec3_length(const Vec3 *v);
size_t math_get_vec3_size(void);

#endif
