#ifndef RENDER_H
#define RENDER_H

#include "types.h"
#include <stddef.h>

scalar_t compute_diffuse(const Vec3 *normal, const Vec3 *light_dir);
scalar_t compute_triangle_area(const Vec3 *v0, const Vec3 *v1, const Vec3 *v2);
size_t render_get_vec3_size(void);

#endif
