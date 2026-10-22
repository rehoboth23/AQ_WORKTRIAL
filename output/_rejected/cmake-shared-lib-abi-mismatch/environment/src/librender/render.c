#include "render.h"
#include "math_ops.h"

scalar_t compute_diffuse(const Vec3 *normal, const Vec3 *light_dir) {
    Vec3 n, l;
    vec3_normalize(normal, &n);
    vec3_normalize(light_dir, &l);
    return vec3_dot(&n, &l);
}

scalar_t compute_triangle_area(const Vec3 *v0, const Vec3 *v1, const Vec3 *v2) {
    Vec3 edge1 = {v1->x - v0->x, v1->y - v0->y, v1->z - v0->z};
    Vec3 edge2 = {v2->x - v0->x, v2->y - v0->y, v2->z - v0->z};
    Vec3 cross;
    vec3_cross(&edge1, &edge2, &cross);
    return 0.5 * vec3_length(&cross);
}

size_t render_get_vec3_size(void) {
    return sizeof(Vec3);
}
